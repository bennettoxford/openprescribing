"""
This tests the MatrixStore build process:

    `TestMatrixStoreBuild` runs entirely in memory and therefore shortcuts
    various parts of the build process which involve downloading data from
    BigQuery

    'TestMatrixStoreBuildEndToEnd` runs the same set of tests but uploads data
    to BigQuery and exports it to Google Cloud Storage in order to excercise
    the full build process

The end-to-end test contains an additional check whereby it builds a file using
the fast process and checks that the resulting SQL dump is identical to that
produced by the full end-to-end process.
"""

import json
import numbers
import os
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict

import numpy
from django.test import SimpleTestCase
from matrixstore.serializer import deserialize
from matrixstore.tests.data_factory import DataFactory
from matrixstore.tests.import_test_data_fast import import_test_data_fast
from matrixstore.tests.import_test_data_full import import_test_data_full


class TestMatrixStoreBuild(SimpleTestCase):
    """
    Runs a test of the MatrixStore build process entirely in memory
    """

    @classmethod
    def setUpClass(cls):
        factory = DataFactory()
        cls.months = factory.create_months("2019-01-01", 3)
        # This practice won't do any prescribing but it will have practice
        # statistics so it should still show up in our data
        cls.non_prescribing_practice = factory.create_practice()
        # Create some practices that prescribe during the period
        cls.prescribing_practices = factory.create_practices(3)
        # Create some presentations and some prescribing
        cls.presentations = factory.create_presentations(4)
        cls.prescribing = factory.create_prescribing(
            cls.presentations, cls.prescribing_practices, cls.months
        )
        # Create practices statistics for all active practices
        cls.active_practices = cls.prescribing_practices + [
            cls.non_prescribing_practice
        ]
        cls.practice_statistics = factory.create_practice_statistics(
            cls.active_practices, cls.months
        )
        # Create a presentation which changes its BNF code and create some
        # prescribing with both old and new codes
        cls.presentation_to_update = factory.create_presentation()
        cls.updated_presentation = factory.update_bnf_code(cls.presentation_to_update)
        cls.prescribing_with_old_code = factory.create_prescribing(
            [cls.presentation_to_update], cls.active_practices, cls.months
        )
        cls.prescribing_with_new_code = factory.create_prescribing(
            [cls.updated_presentation], cls.active_practices, cls.months
        )
        # Create a presenation without creating any prescribing for it so we can
        # check it doesn't appear in the final file
        cls.presentation_without_prescribing = factory.create_presentation()
        # We deliberately import data for fewer months than we've created so we
        # can test that only the right data is included
        cls.months_to_import = cls.months[1:]
        # This practice only has data for the month we don't import, so it
        # shouldn't show up at all in our data
        cls.closed_practice = factory.create_practice()
        factory.create_prescription(
            cls.presentations[0], cls.closed_practice, cls.months[0]
        )
        factory.create_statistics_for_one_practice_and_month(
            cls.closed_practice, cls.months[0]
        )
        cls.data_factory = factory
        # The format of `end_date` only uses year and month
        cls.end_date = max(cls.months_to_import)[:7]
        cls.number_of_months = len(cls.months_to_import)
        cls.create_matrixstore(factory, cls.end_date, cls.number_of_months)

    @classmethod
    def create_matrixstore(cls, data_factory, end_date, number_of_months):
        cls.connection = sqlite3.connect(":memory:")
        import_test_data_fast(
            cls.connection, data_factory, end_date, months=number_of_months
        )

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def setUp(self):
        # Reset this as at least one test modifies it
        self.connection.row_factory = None

    def test_dates_are_correct(self):
        dates = [
            row[0]
            for row in self.connection.execute("SELECT date FROM date ORDER BY offset")
        ]
        expected_dates = [date[:10] for date in self.months_to_import]
        self.assertEqual(dates, expected_dates)

    def test_practices_are_correct(self):
        practice_codes = [
            row[0]
            for row in self.connection.execute(
                "SELECT code FROM practice ORDER BY code"
            )
        ]
        expected_codes = sorted(
            [practice["code"] for practice in self.active_practices]
        )
        self.assertEqual(practice_codes, expected_codes)
        self.assertNotIn(self.closed_practice["code"], practice_codes)

    def test_presentations_are_correct(self):
        expected = [p["bnf_code"] for p in self.presentations]
        expected.append(self.updated_presentation["bnf_code"])
        expected.sort()
        results = self.connection.execute(
            "SELECT bnf_code FROM presentation ORDER BY bnf_code"
        )
        results = [row[0] for row in results]
        self.assertEqual(results, expected)
        self.assertNotIn(self.presentation_to_update, results)
        self.assertNotIn(self.presentation_without_prescribing, results)

    def test_practice_statistics_are_correct(self):
        get_value = MatrixValueFetcher(
            self.connection, "practice_statistic", "name", "value"
        )
        expected_entries = 0
        for entry in self.practice_statistics:
            practice = entry["practice"]
            month = entry["month"]
            if month not in self.months_to_import:
                continue
            for field, expected_value in entry.items():
                if field in ("month", "practice", "pct_id", "star_pu"):
                    continue
                expected_entries += 1
                value = get_value(field, practice, month)
                self.assertEqual(value, expected_value)
            for name, expected_value in json.loads(entry["star_pu"]).items():
                expected_entries += 1
                value = get_value("star_pu." + name, practice, month)
                self.assertEqual(value, expected_value)
        # Check there are no additional values that we weren't expecting
        self.assertEqual(get_value.nonzero_values, expected_entries)

    def test_prescribing_values_are_correct(self):
        for field in ["items", "quantity", "net_cost", "actual_cost"]:
            # Cost figures are originally in pounds but we store them in pence
            # as ints
            multiplier = 100 if field.endswith("_cost") else 1
            get_value = MatrixValueFetcher(
                self.connection, "presentation", "bnf_code", field
            )
            expected_entries = 0
            for entry in self._expected_prescribing_values():
                expected_entries += 1
                value = get_value(entry["bnf_code"], entry["practice"], entry["month"])
                if field == "quantity":
                    expected_value = entry[field] * multiplier
                else:
                    expected_value = round(entry[field] * multiplier)
                self.assertEqual(value, expected_value)
            # Check there are no additional values that we weren't expecting
            self.assertEqual(get_value.nonzero_values, expected_entries)

    def _expected_prescribing_values(self):
        # First we yield the standard prescribing, filtered by month
        for entry in self.prescribing:
            if entry["month"] in self.months_to_import:
                yield entry
        # Next we sum together prescribing done under both our old and new BNF
        # code and yield the results under the new BNF code
        summed_values = defaultdict(dict)
        for entry in self.prescribing_with_old_code + self.prescribing_with_new_code:
            current_value = summed_values[entry["practice"], entry["month"]]
            sum_dicts(current_value, entry)
        for (practice, month), values in summed_values.items():
            if month in self.months_to_import:
                yield {
                    "bnf_code": self.updated_presentation["bnf_code"],
                    "practice": practice,
                    "month": month,
                    "items": values["items"],
                    "quantity": values["quantity"],
                    "net_cost": values["net_cost"],
                    "actual_cost": values["actual_cost"],
                }

    def test_precalculated_totals(self):
        for field in ["items", "quantity", "net_cost", "actual_cost"]:
            # Cost figures are originally in pounds but we store them in pence
            # as ints
            multiplier = 100 if field.endswith("_cost") else 1
            get_value = MatrixValueFetcher(
                # This table doesn't have a key column as it only has one row,
                # so we just use 1 as a pseudo-column
                self.connection,
                "all_presentations",
                1,
                field,
            )
            # Calculate totals over all presentations
            if field == "quantity":
                totals = defaultdict(float)
            else:
                totals = defaultdict(int)
            for entry in self._expected_prescribing_values():
                if field == "quantity":
                    value = entry[field] * multiplier
                else:
                    value = round(entry[field] * multiplier)
                totals[entry["practice"], entry["month"]] += value
            # Check they match the stored values
            for (practice, month), expected_value in totals.items():
                value = get_value(1, practice, month)
                self.assertEqual(value, expected_value)
            # Check there are no additional values that we weren't expecting
            self.assertEqual(get_value.nonzero_values, len(totals))


class TestMatrixStoreBuildEndToEnd(TestMatrixStoreBuild):
    """
    Runs the same test as above but as a full integration test against actual
    BigQuery and Google Cloud Storage. Also checks that the fast build process
    produces an identical file to the full process.
    """

    @classmethod
    def create_matrixstore(cls, data_factory, end_date, number_of_months):
        cls.tempdir = tempfile.mkdtemp()
        # Upload data to BigQuery and build file
        cls.data_file = import_test_data_full(
            cls.tempdir, data_factory, end_date, months=number_of_months
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def setUp(self):
        # We have to check this because the `sqlite3.connect` call will
        # implicitly create the file if it doesn't exist
        if not os.path.exists(self.data_file):
            raise RuntimeError("No SQLite file created")
        self.connection = sqlite3.connect(self.data_file)

    def tearDown(self):
        self.connection.close()

    def test_same_file_produced_by_import_test_data_fast(self):
        # This is awful: we do some sys.module munging in settings.base to
        # globally replace sqlite3 with pysqlite3. However we were also using
        # `iterdump` as a lazy way of comparing the contents of two databases
        # and it turns out that pysqlite3 doesn't include that. So we
        # temporarily undo the monkey patch and grab `iterdump` from the
        # stdlib. Nice.
        orig_sqlite3 = sys.modules.pop("sqlite3")
        from sqlite3.dump import _iterdump

        sys.modules["sqlite3"] = orig_sqlite3
        other_connection = sqlite3.connect(":memory:")
        import_test_data_fast(
            other_connection, self.data_factory, self.end_date, self.number_of_months
        )
        db_dump = list(_iterdump(self.connection))
        other_db_dump = list(_iterdump(other_connection))
        self.assertEqual(db_dump, other_db_dump)


class MatrixValueFetcher(object):
    """
    Provides convenient access to values stored in matrices in SQLite
    """

    def __init__(self, connection, table, key_field, value_field):
        results = connection.execute(
            "SELECT {}, {} FROM {}".format(key_field, value_field, table)
        )
        self.matrices = {}
        self.nonzero_values = 0
        for key, value in results:
            matrix = deserialize(value)
            self.matrices[key] = matrix
            if hasattr(matrix, "count_nonzero"):
                self.nonzero_values += matrix.count_nonzero()
            else:
                self.nonzero_values += numpy.count_nonzero(matrix)
        self.practices = dict(connection.execute("SELECT code, offset FROM practice"))
        self.dates = dict(connection.execute("SELECT date, offset FROM date"))
        for date, offset in list(self.dates.items()):
            self.dates[date + " 00:00:00 UTC"] = offset

    def __call__(self, key, practice, date):
        """
        Find the row in `table` where `key_field` matches `key` and extract the
        matrix stored in `value_field`. Return the value at the row and column
        corresponding to `practice` and `date`
        """
        row = self.practices[practice]
        column = self.dates[date]
        return self.matrices[key][row, column]


def sum_dicts(current_values, new_values):
    """
    Add the numeric parts of `new_values` to `current_values`
    """
    for field, value in new_values.items():
        if not isinstance(value, numbers.Number):
            continue
        zero = type(value)()
        current_values[field] = current_values.get(field, zero) + value
