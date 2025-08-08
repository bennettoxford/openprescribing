from __future__ import print_function

import csv
import itertools
import json
import os
import re
import tempfile
from random import Random
from urllib.parse import parse_qs

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from frontend import bq_schemas as schemas
from frontend.management.commands.import_measures import (
    build_bnf_codes_query,
    load_measure_defs,
)
from frontend.models import (
    PCN,
    PCT,
    STP,
    ImportLog,
    Measure,
    MeasureGlobal,
    MeasureValue,
    Practice,
    RegionalTeam,
)
from gcutils.bigquery import Client
from google.api_core.exceptions import BadRequest
from google.cloud.exceptions import Conflict
from matrixstore.tests.contextmanagers import (
    patched_global_matrixstore_from_data_factory,
)
from matrixstore.tests.data_factory import DataFactory
from mock import patch

# These tests test import_measures by repeating the measure calculations with
# Pandas, and asserting that the values stored on MeasureValue and
# MeasureGlobal objects match those calculated with Pandas.  See
# notebooks/measure-calculations.ipynb for an explanation of these
# calculations.


class ImportMeasuresTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        random = Random()
        random.seed(1980)

        set_up_bq()
        create_import_log()
        create_organisations(random)
        upload_ccgs_and_practices()
        upload_presentations()
        cls.prescriptions = upload_prescribing(random.randint)
        cls.practice_stats = upload_practice_statistics(random.randint)
        cls.factory = build_factory()
        create_old_measure_value()

    def test_cost_based_percentage_measure(self):
        # This test verifies the behaviour of import_measures for a cost-based
        # measure that calculates the ratio between:
        #  * quantity prescribed of a branded presentation (numerator)
        #  * total quantity prescribed of the branded presentation and its
        #      generic equivalent (denominator)

        # Do the work.
        with patched_global_matrixstore_from_data_factory(self.factory):
            call_command("import_measures", measure="desogestrel")

        # Check that old MeasureValue and MeasureGlobal objects have been deleted.
        self.assertFalse(MeasureValue.objects.filter(month__lt="2011-01-01").exists())
        self.assertFalse(MeasureGlobal.objects.filter(month__lt="2011-01-01").exists())

        # Check that numerator_bnf_codes and denominator_bnf_codes have been set.
        m = Measure.objects.get(id="desogestrel")
        self.assertEqual(m.numerator_bnf_codes, ["0703021Q0BBAAAA"])
        self.assertEqual(
            m.denominator_bnf_codes, ["0703021Q0AAAAAA", "0703021Q0BBAAAA"]
        )

        # Check that analyse_url has been set.
        querystring = m.analyse_url.split("#")[1]
        params = parse_qs(querystring)
        self.assertEqual(
            params,
            {
                "measure": ["desogestrel"],
                "numIds": ["0703021Q0BB"],
                "denomIds": ["0703021Q0"],
            },
        )

        # Check calculations by redoing calculations with Pandas, and asserting
        # that results match.
        month = "2018-08-01"
        prescriptions = self.prescriptions[self.prescriptions["month"] == month]
        numerators = prescriptions[
            prescriptions["bnf_code"].str.startswith("0703021Q0B")
        ]
        denominators = prescriptions[
            prescriptions["bnf_code"].str.startswith("0703021Q0")
        ]
        self.validate_calculations(
            self.calculate_cost_based_percentage_measure,
            numerators,
            denominators,
            month,
        )

    def test_practice_statistics_measure(self):
        # This test verifies the behaviour of import_measures for a measure
        # that calculates the ratio between:
        #  * items prescribed of a particular presentation (numerator)
        #  * patients / 1000 (denominator)
        #
        # Of interest is the case where the number of patients may be null for
        # a given practice in a given month.  See #1520.

        # Do the work.
        with patched_global_matrixstore_from_data_factory(self.factory):
            call_command("import_measures", measure="coproxamol")

        # Check that numerator_bnf_codes has, and denominator_bnf_codes has not, been
        # set.
        m = Measure.objects.get(id="coproxamol")
        self.assertEqual(m.numerator_bnf_codes, ["0407010Q0AAAAAA"])
        self.assertEqual(m.denominator_bnf_codes, None)

        # Check that analyse_url has been set.
        querystring = m.analyse_url.split("#")[1]
        params = parse_qs(querystring)
        self.assertEqual(
            params,
            {
                "measure": ["coproxamol"],
                "numIds": ["0407010Q0"],
                "denom": ["total_list_size"],
            },
        )

        # Check calculations by redoing calculations with Pandas, and asserting
        # that results match.
        month = "2018-08-01"
        prescriptions = self.prescriptions[self.prescriptions["month"] == month]
        numerators = prescriptions[prescriptions["bnf_code"] == "0407010Q0AAAAAA"]
        denominators = self.practice_stats[self.practice_stats["month"] == month]
        self.validate_calculations(
            self.calculate_practice_statistics_measure, numerators, denominators, month
        )

    def test_cost_based_practice_statistics_measure(self):
        # This test verifies the behaviour of import_measures for a cost-based
        # measure that calculates the ratio between:
        #  * cost of prescribing of a particular presentation (numerator)
        #  * patients / 1000 (denominator)

        # Do the work.
        with patched_global_matrixstore_from_data_factory(self.factory):
            call_command("import_measures", measure="glutenfree")

        # Check calculations by redoing calculations with Pandas, and asserting
        # that results match.
        month = "2018-08-01"
        prescriptions = self.prescriptions[self.prescriptions["month"] == month]
        numerators = prescriptions[prescriptions["bnf_code"] == "0904010AUBBAAAA"]
        denominators = self.practice_stats[self.practice_stats["month"] == month]
        self.validate_calculations(
            self.calculate_cost_based_practice_statistics_measure,
            numerators,
            denominators,
            month,
        )

    def calculate_cost_based_percentage_measure(
        self, numerators, denominators, org_type, org_codes
    ):
        org_column = org_type + "_id"
        df = pd.DataFrame(index=org_codes)

        df["quantity_total"] = sum_by_group(denominators, org_column, "quantity")
        df["cost_total"] = sum_by_group(denominators, org_column, "actual_cost")
        df["quantity_branded"] = sum_by_group(numerators, org_column, "quantity")
        df["cost_branded"] = sum_by_group(numerators, org_column, "actual_cost")
        df = df.fillna(0)
        df["quantity_total"] = df["quantity_total"].astype("int")
        df["quantity_branded"] = df["quantity_branded"].astype("int")
        df["quantity_generic"] = df["quantity_total"] - df["quantity_branded"]
        df["cost_generic"] = df["cost_total"] - df["cost_branded"]
        df["quantity_ratio"] = df["quantity_branded"] / df["quantity_total"]
        ranks = df["quantity_ratio"].rank(method="min")
        num_non_nans = df["quantity_ratio"].count()
        df["quantity_ratio_percentile"] = (ranks - 1) / ((num_non_nans - 1) / 100.0)
        global_unit_cost_branded = (
            df["cost_branded"].sum() / df["quantity_branded"].sum()
        )
        global_unit_cost_generic = (
            df["cost_generic"].sum() / df["quantity_generic"].sum()
        )
        df["unit_cost_branded"] = df["cost_branded"] / df["quantity_branded"]
        df["unit_cost_generic"] = df["cost_generic"] / df["quantity_generic"]
        df["unit_cost_branded"] = df["unit_cost_branded"].fillna(
            global_unit_cost_branded
        )
        df["unit_cost_generic"] = df["unit_cost_generic"].fillna(
            global_unit_cost_generic
        )
        quantity_ratio_10 = df["quantity_ratio"].quantile(0.1)
        df["quantity_branded_10"] = df["quantity_total"] * quantity_ratio_10
        df["quantity_generic_10"] = df["quantity_total"] - df["quantity_branded_10"]
        df["target_cost_10"] = (
            df["unit_cost_branded"] * df["quantity_branded_10"]
            + df["unit_cost_generic"] * df["quantity_generic_10"]
        )
        df["cost_saving_10"] = df["cost_total"] - df["target_cost_10"]

        return pd.DataFrame.from_dict(
            {
                "numerator": df["quantity_branded"],
                "denominator": df["quantity_total"],
                "ratio": df["quantity_ratio"],
                "ratio_percentile": df["quantity_ratio_percentile"],
                "cost_saving_10": df["cost_saving_10"],
            }
        )

    def calculate_practice_statistics_measure(
        self, numerators, denominators, org_type, org_codes
    ):
        org_column = org_type + "_id"
        df = pd.DataFrame(index=org_codes)

        df["items"] = sum_by_group(numerators, org_column, "items")
        df["thousand_patients"] = sum_by_group(
            denominators, org_column, "thousand_patients"
        )
        df["ratio"] = df["items"] / df["thousand_patients"]
        df["items"] = df["items"].fillna(0)
        df["thousand_patients"] = df["thousand_patients"].fillna(0)
        ranks = df["ratio"].rank(method="min")
        num_non_nans = df["ratio"].count()
        df["ratio_percentile"] = (ranks - 1) / ((num_non_nans - 1) / 100.0)

        return pd.DataFrame.from_dict(
            {
                "numerator": df["items"],
                "denominator": df["thousand_patients"],
                "ratio": df["ratio"],
                "ratio_percentile": df["ratio_percentile"],
            }
        )

    def calculate_cost_based_practice_statistics_measure(
        self, numerators, denominators, org_type, org_codes
    ):
        org_column = org_type + "_id"
        df = pd.DataFrame(index=org_codes)

        df["cost"] = sum_by_group(numerators, org_column, "actual_cost")
        df["thousand_patients"] = sum_by_group(
            denominators, org_column, "thousand_patients"
        )
        df["ratio"] = df["cost"] / df["thousand_patients"]
        df["cost"] = df["cost"].fillna(0)
        df["thousand_patients"] = df["thousand_patients"].fillna(0)
        ranks = df["ratio"].rank(method="min")
        num_non_nans = df["ratio"].count()
        df["ratio_percentile"] = (ranks - 1) / ((num_non_nans - 1) / 100.0)
        ratio_10 = df["ratio"].quantile(0.1)
        df["target_cost_10"] = ratio_10 * df["thousand_patients"]
        df["cost_saving_10"] = df["cost"] - df["target_cost_10"]

        return pd.DataFrame.from_dict(
            {
                "numerator": df["cost"],
                "denominator": df["thousand_patients"],
                "ratio": df["ratio"],
                "ratio_percentile": df["ratio_percentile"],
                "cost_saving_10": df["cost_saving_10"],
            }
        )

    def validate_calculations(self, calculator, numerators, denominators, month):
        """Validate measure calculations by redoing calculations with Pandas."""

        mg = MeasureGlobal.objects.get(month=month)

        practices = calculator(
            numerators,
            denominators,
            "practice",
            Practice.objects.values_list("code", flat=True),
        )
        self.validate_measure_global(mg, practices, "practice")
        mvs = MeasureValue.objects.filter_by_org_type("practice").filter(month=month)
        self.assertEqual(mvs.count(), Practice.objects.count())
        for mv in mvs:
            self.validate_measure_value(mv, practices.loc[mv.practice_id])

        pcns = calculator(
            numerators, denominators, "pcn", PCN.objects.values_list("code", flat=True)
        )
        self.validate_measure_global(mg, pcns, "pcn")
        mvs = MeasureValue.objects.filter_by_org_type("pcn").filter(month=month)
        self.assertEqual(mvs.count(), PCN.objects.count())
        for mv in mvs:
            self.validate_measure_value(mv, pcns.loc[mv.pcn_id])

        ccgs = calculator(
            numerators, denominators, "ccg", PCT.objects.values_list("code", flat=True)
        )
        self.validate_measure_global(mg, ccgs, "ccg")
        mvs = MeasureValue.objects.filter_by_org_type("ccg").filter(month=month)
        self.assertEqual(mvs.count(), PCT.objects.count())
        for mv in mvs:
            self.validate_measure_value(mv, ccgs.loc[mv.pct_id])

        stps = calculator(
            numerators,
            denominators,
            "stp",
            STP.objects.values_list("code", flat=True),
        )
        self.validate_measure_global(mg, stps, "stp")
        mvs = MeasureValue.objects.filter_by_org_type("stp").filter(month=month)
        self.assertEqual(mvs.count(), STP.objects.count())
        for mv in mvs:
            self.validate_measure_value(mv, stps.loc[mv.stp_id])

        regtms = calculator(
            numerators,
            denominators,
            "regional_team",
            RegionalTeam.objects.values_list("code", flat=True),
        )
        self.validate_measure_global(mg, regtms, "regional_team")
        mvs = MeasureValue.objects.filter_by_org_type("regional_team").filter(
            month=month
        )
        self.assertEqual(mvs.count(), RegionalTeam.objects.count())
        for mv in mvs:
            self.validate_measure_value(mv, regtms.loc[mv.regional_team_id])

    def validate_measure_global(self, mg, df, org_type):
        numerator = df["numerator"].sum()
        denominator = df["denominator"].sum()
        self.assertAlmostEqual(mg.numerator, numerator)
        self.assertAlmostEqual(mg.denominator, denominator)
        self.assertAlmostEqual(mg.calc_value, 1.0 * numerator / denominator)
        self.assertAlmostEqual(
            mg.percentiles[org_type]["10"], df["ratio"].quantile(0.1)
        )
        if mg.measure.is_cost_based:
            self.assertAlmostEqual(
                mg.cost_savings[org_type]["10"],
                df[df["cost_saving_10"] > 0]["cost_saving_10"].sum(),
            )

    def validate_measure_value(self, mv, series):
        self.assertAlmostEqual(mv.numerator, series["numerator"])
        self.assertAlmostEqual(mv.denominator, series["denominator"])
        if mv.percentile is None:
            self.assertTrue(np.isnan(series["ratio"]))
            self.assertTrue(np.isnan(series["ratio_percentile"]))
        else:
            self.assertAlmostEqual(mv.calc_value, series["ratio"])
            self.assertAlmostEqual(mv.percentile, series["ratio_percentile"])

        if mv.measure.is_cost_based:
            self.assertAlmostEqual(mv.cost_savings["10"], series["cost_saving_10"])


class BuildMeasureSQLTests(TestCase):
    def test_build_bnf_codes_query(self):
        base_query = "SELECT bnf_code FROM {hscic}.presentation WHERE name LIKE '% Tab'"
        filter_ = [
            "010101 # Everything in 1.1.1",
            "~010101000BBABA0 # Langdales_Cinnamon Tab",
            "~0302000N0%AV # Fluticasone Prop_Inh Soln 500mcg/2ml Ud (brands and generic)",
            "# #GlucoRx Smart Glucose testing strips (GlucoRx Ltd) WAITING FOR BNF CODE",
        ]

        expected_sql = """
        WITH subquery AS (SELECT bnf_code FROM {hscic}.presentation WHERE name LIKE '% Tab')
        SELECT bnf_code
        FROM subquery
        WHERE (bnf_code LIKE '010101%') AND NOT (bnf_code = '010101000BBABA0' OR bnf_code LIKE '0302000N0%AV')
        """

        self.assertEqual(build_bnf_codes_query(base_query, filter_), expected_sql)

    def test_build_bnf_codes_query_without_base_query(self):
        filter_ = [
            "010101 # Everything in 1.1.1",
            "~010101000BBABA0 # Langdales_Cinnamon Tab",
            "~0302000N0%AV # Fluticasone Prop_Inh Soln 500mcg/2ml Ud (brands and generic)",
        ]

        expected_sql = """
        WITH subquery AS (SELECT bnf_code FROM {hscic}.presentation)
        SELECT bnf_code
        FROM subquery
        WHERE (bnf_code LIKE '010101%') AND NOT (bnf_code = '010101000BBABA0' OR bnf_code LIKE '0302000N0%AV')
        """

        self.assertEqual(build_bnf_codes_query(None, filter_), expected_sql)

    def test_build_bnf_codes_query_includes_only(self):
        filter_ = [
            "010101000BBABA0 # Langdales_Cinnamon Tab",
            "0302000N0%AV # Fluticasone Prop_Inh Soln 500mcg/2ml Ud (brands and generic)",
        ]

        expected_sql = """
        WITH subquery AS (SELECT bnf_code FROM {hscic}.presentation)
        SELECT bnf_code
        FROM subquery
        WHERE (bnf_code = '010101000BBABA0' OR bnf_code LIKE '0302000N0%AV')
        """

        self.assertEqual(build_bnf_codes_query(None, filter_), expected_sql)

    def test_build_bnf_codes_query_excludes_only(self):
        filter_ = [
            "~010101000BBABA0 # Langdales_Cinnamon Tab",
            "~0302000N0%AV # Fluticasone Prop_Inh Soln 500mcg/2ml Ud (brands and generic)",
        ]

        expected_sql = """
        WITH subquery AS (SELECT bnf_code FROM {hscic}.presentation)
        SELECT bnf_code
        FROM subquery
        WHERE NOT (bnf_code = '010101000BBABA0' OR bnf_code LIKE '0302000N0%AV')
        """

        self.assertEqual(build_bnf_codes_query(None, filter_), expected_sql)

    def test_build_bnf_codes_query_without_filter(self):
        base_query = "SELECT bnf_code FROM {hscic}.presentation WHERE name LIKE '% Tab'"

        self.assertEqual(build_bnf_codes_query(base_query, None), base_query)


class ImportMeasuresDefinitionsOnlyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_import_log()

    def test_all_definitions(self):
        # Test that all production measure definitions can be imported.  We don't test
        # get_num_or_denom_bnf_codes(), since it requires a lot of setup in BQ, and is
        # exercised properly in the end-to-end tests.

        assert Measure.objects.count() == 0

        measure_defs_path = os.path.join(settings.APPS_ROOT, "measures", "definitions")
        with override_settings(MEASURE_DEFINITIONS_PATH=measure_defs_path):
            with patch(
                "frontend.management.commands.import_measures.get_num_or_denom_bnf_codes"
            ) as get_num_or_denom_bnf_codes:
                with patch(
                    "frontend.management.commands.import_measures.get_bnf_codes"
                ) as get_bnf_codes:
                    get_num_or_denom_bnf_codes.return_value = []
                    get_bnf_codes.return_value = []
                    call_command("import_measures", definitions_only=True)

        assert Measure.objects.count() > 0


class CheckMeasureDefinitionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_import_log()
        set_up_bq()
        upload_presentations()

    def test_check_definition(self):
        upload_dummy_prescribing(["0703021Q0AAAAAA", "0703021Q0BBAAAA"])

        with patched_global_matrixstore_from_data_factory(build_factory()):
            call_command("import_measures", measure="desogestrel", check=True)

    @override_settings(
        MEASURE_DEFINITIONS_PATH=os.path.join(
            settings.MEASURE_DEFINITIONS_PATH, "bad", "json"
        )
    )
    def test_check_definition_bad_json(self):
        with self.assertRaises(ValueError) as command_error:
            call_command("import_measures", check=True)
        self.assertIn("Problems parsing JSON", str(command_error.exception))

    @override_settings(
        MEASURE_DEFINITIONS_PATH=os.path.join(
            settings.MEASURE_DEFINITIONS_PATH, "bad", "sql"
        )
    )
    def test_check_definition_bad_sql(self):
        with self.assertRaises(BadRequest) as command_error:
            call_command("import_measures", check=True)
        self.assertIn("SQL error", str(command_error.exception))


class LoadMeasureDefsTests(TestCase):
    def test_order(self):
        measure_defs_path = os.path.join(settings.APPS_ROOT, "measures", "definitions")
        with override_settings(MEASURE_DEFINITIONS_PATH=measure_defs_path):
            measure_defs = load_measure_defs()
        measure_ids = [measure_def["id"] for measure_def in measure_defs]
        lpzomnibus_ix = list(measure_ids).index("lpzomnibus")
        lptrimipramine_ix = list(measure_ids).index("lptrimipramine")
        # The order of these specific measures matters, as the SQL for
        # the omnibus measure relies on the other LP measures having
        # been calculated first
        self.assertTrue(lptrimipramine_ix < lpzomnibus_ix)

    def test_with_no_measure_ids_loads_all_definitions(self):
        measure_defs = load_measure_defs()
        self.assertEqual(len(measure_defs), 3)

    def test_with_measure_ids_loads_some_definitions(self):
        measure_defs = load_measure_defs(["coproxamol", "desogestrel"])
        self.assertEqual(len(measure_defs), 2)


class LowPriorityOmnibusTest(TestCase):
    """
    The Low Priority Omnibus measure is manually created from the list of Low
    Priority measures and we want to make sure they don't get out of sync
    """

    def test_low_priority_omnibus_divisor(self):
        measure_path = os.path.join(
            settings.APPS_ROOT, "measures", "definitions", "lpzomnibus.json"
        )
        with open(measure_path, "r") as f:
            denominator_columns = "\n".join(json.load(f)["denominator_columns"])
        divisor_match = re.search(r"/([0-9]+)", denominator_columns)
        self.assertIsNotNone(divisor_match)
        divisor_count = int(divisor_match.group(1))
        self.assertEqual(divisor_count, len(self.get_low_priority_tables()))

    def test_low_priority_tables_match_measures(self):
        self.assertEqual(
            sorted(self.get_low_priority_tables()),
            sorted(self.get_low_priority_measures()),
        )

    def get_low_priority_tables(self):
        sql_path = os.path.join(
            settings.APPS_ROOT,
            "measures",
            "views",
            "vw__practice_data_all_low_priority.sql",
        )
        with open(sql_path, "r") as f:
            all_low_priority_sql = f.read()
        return re.findall(r"\{measures\}\.practice_data_(\w+)", all_low_priority_sql)

    def get_low_priority_measures(self):
        files = os.listdir(os.path.join(settings.APPS_ROOT, "measures", "definitions"))
        return [
            name[: -len(".json")]
            for name in files
            if (
                name.startswith("lp")
                and name.endswith(".json")
                and name != "lpzomnibus.json"
            )
        ]


class ConstraintsTests(TestCase):
    @patch("common.utils.db")
    def test_reconstructor_not_called_when_not_enabled(self, db):
        from frontend.management.commands.import_measures import (
            conditional_constraint_and_index_reconstructor,
        )

        with conditional_constraint_and_index_reconstructor(False):
            pass
        execute = db.connection.cursor.return_value.__enter__.return_value.execute
        execute.assert_not_called()

    @patch("common.utils.db")
    def test_reconstructor_called_when_enabled(self, db):
        from frontend.management.commands.import_measures import (
            conditional_constraint_and_index_reconstructor,
        )

        with conditional_constraint_and_index_reconstructor(True):
            pass
        execute = db.connection.cursor.return_value.__enter__.return_value.execute
        execute.assert_called()


def set_up_bq():
    """Set up BQ datasets and tables."""

    try:
        Client("measures").create_dataset()
    except Conflict:
        pass

    client = Client("hscic")
    client.get_or_create_table("ccgs", schemas.CCG_SCHEMA)
    client.get_or_create_table("practices", schemas.PRACTICE_SCHEMA)
    client.get_or_create_table("normalised_prescribing", schemas.PRESCRIBING_SCHEMA)
    client.get_or_create_table(
        "practice_statistics", schemas.PRACTICE_STATISTICS_SCHEMA
    )
    client.get_or_create_table("presentation", schemas.PRESENTATION_SCHEMA)


def upload_dummy_prescribing(bnf_codes):
    """Upload enough dummy prescribing data to BQ to allow the BNF code simplification
    to be meaningful."""

    prescribing_rows = []
    for bnf_code in bnf_codes:
        row = [
            None,  # sha
            None,  # pct
            None,  # practice
            bnf_code,  # bnf_code
            None,  # bnf_name
            None,  # items
            None,  # net_cost
            None,  # actual_cost
            None,  # quantity
            None,  # month
        ]
        prescribing_rows.append(row)

    table = Client("hscic").get_table("normalised_prescribing")
    with tempfile.NamedTemporaryFile("wt") as f:
        writer = csv.writer(f)
        for row in prescribing_rows:
            writer.writerow(row)
        f.seek(0)
        table.insert_rows_from_csv(f.name, schemas.PRESCRIBING_SCHEMA)


def create_import_log():
    """Create ImportLog used by import_measures to work out which months is should
    import data."""
    ImportLog.objects.create(category="prescribing", current_at="2018-08-01")


def create_old_measure_value():
    """Create MeasureValue and MeasureGlobal that are to be deleted because they are
    more than five years old."""
    with patched_global_matrixstore_from_data_factory(build_factory()):
        call_command("import_measures", definitions_only=True, measure="desogestrel")
    m = Measure.objects.get(id="desogestrel")
    m.measurevalue_set.create(month="2010-01-01")
    m.measureglobal_set.create(month="2010-01-01")


def create_organisations(random):
    """Create RegionalTeams, STPs, CCGs, PCNs, Practices in local DB."""

    for regtm_ix in range(5):
        regtm = RegionalTeam.objects.create(
            code="Y0{}".format(regtm_ix), name="Region {}".format(regtm_ix)
        )

        for stp_ix in range(5):
            stp = STP.objects.create(
                code="E{}{}".format(regtm_ix, stp_ix),
                name="STP {}/{}".format(regtm_ix, stp_ix),
            )

            pcns = []
            for pcn_ix in range(5):
                pcn = PCN.objects.create(
                    code="E00000{}{}{}".format(regtm_ix, stp_ix, pcn_ix),
                    name="PCN {}/{}/{}".format(regtm_ix, stp_ix, pcn_ix),
                )
                pcns.append(pcn)

            # Function to return next PCN, looping round forever
            get_next_pcn = itertools.cycle(pcns).__next__

            for ccg_ix in range(5):
                ccg = PCT.objects.create(
                    regional_team=regtm,
                    stp=stp,
                    code="{}{}{}".format(regtm_ix, stp_ix, ccg_ix).replace("0", "A"),
                    name="CCG {}/{}/{}".format(regtm_ix, stp_ix, ccg_ix),
                    org_type="CCG",
                )

                for prac_ix in range(5):
                    Practice.objects.create(
                        ccg=ccg,
                        pcn=get_next_pcn(),
                        code="P0{}{}{}{}".format(regtm_ix, stp_ix, ccg_ix, prac_ix),
                        name="Practice {}/{}/{}/{}".format(
                            regtm_ix, stp_ix, ccg_ix, prac_ix
                        ),
                        setting=4,
                    )


def upload_ccgs_and_practices():
    """Upload CCGs and Practices to BQ."""

    table = Client("hscic").get_table("ccgs")
    table.insert_rows_from_pg(
        PCT, schemas.CCG_SCHEMA, transformer=schemas.ccgs_transform
    )
    table = Client("hscic").get_table("practices")
    table.insert_rows_from_pg(Practice, schemas.PRACTICE_SCHEMA)


def upload_presentations():
    """Upload presentations to BQ."""

    table = Client("hscic").get_table("presentation")

    presentations = [
        ("0703021Q0AAAAAA", "Desogestrel_Tab 75mcg"),
        ("0703021Q0BBAAAA", "Cerazette_Tab 75mcg"),
        ("076543210AAAAAA", "Etynodiol Diacet_Tab 500mcg"),
        ("0407010Q0AAAAAA", "Co-Proxamol_Tab 32.5mg/325mg"),
        ("0904010AUBBAAAA", "Mrs Crimble's_G/F W/F Cheese Bites Orig"),
    ]

    with tempfile.NamedTemporaryFile("wt") as f:
        writer = csv.writer(f)
        for presentation in presentations:
            row = presentation + (None, None)
            writer.writerow(row)
        f.seek(0)
        table.insert_rows_from_csv(f.name, schemas.PRESENTATION_SCHEMA)


def upload_prescribing(randint):
    """Generate prescribing data, and upload to BQ."""

    prescribing_rows = []

    # These are for the desogestrel measure
    presentations = [
        ("0703021Q0AAAAAA", "Desogestrel_Tab 75mcg"),  # generic
        ("0703021Q0BBAAAA", "Cerazette_Tab 75mcg"),  # branded
        ("076543210AAAAAA", "Etynodiol Diacet_Tab 500mcg"),  # irrelevant
    ]

    seen_practice_with_no_prescribing = False
    seen_practice_with_no_relevant_prescribing = False
    seen_practice_with_no_generic_prescribing = False
    seen_practice_with_no_branded_prescribing = False

    for practice in Practice.objects.all():
        for month in [7, 8]:
            timestamp = "2018-0{}-01 00:00:00 UTC".format(month)

            for ix, (bnf_code, bnf_name) in enumerate(presentations):
                if practice.code == "P00000":
                    seen_practice_with_no_prescribing = True
                    continue
                elif practice.code == "P00010" and "0703021Q" in bnf_code:
                    seen_practice_with_no_relevant_prescribing = True
                    continue
                elif practice.code == "P00020" and bnf_code == "0703021Q0AAAAAA":
                    seen_practice_with_no_generic_prescribing = True
                    continue
                elif practice.code == "P00030" and bnf_code == "0703021Q0BBAAAA":
                    seen_practice_with_no_branded_prescribing = True
                    continue

                items = randint(0, 100)
                quantity = randint(6, 28) * items

                # Multiplying by (1 + ix) ensures that the branded cost is
                # always higher than the generic cost.
                actual_cost = (1 + ix) * randint(100, 200) * quantity * 0.01

                # We don't care about net_cost.
                net_cost = actual_cost

                row = [
                    "sha",  # This value doesn't matter.
                    practice.ccg.regional_team_id,
                    practice.ccg.stp_id,
                    practice.ccg_id,
                    practice.pcn_id,
                    practice.code,
                    bnf_code,
                    bnf_name,
                    items,
                    net_cost,
                    actual_cost,
                    quantity,
                    timestamp,
                ]

                prescribing_rows.append(row)

    assert seen_practice_with_no_prescribing
    assert seen_practice_with_no_relevant_prescribing
    assert seen_practice_with_no_generic_prescribing
    assert seen_practice_with_no_branded_prescribing

    # These are for the coproxamol and glutenfree measures
    presentations = [
        ("0407010Q0AAAAAA", "Co-Proxamol_Tab 32.5mg/325mg"),
        ("0904010AUBBAAAA", "Mrs Crimble's_G/F W/F Cheese Bites Orig"),
    ]

    for practice in Practice.objects.all():
        for month in [7, 8]:
            timestamp = "2018-0{}-01 00:00:00 UTC".format(month)

            for bnf_code, bnf_name in presentations:
                items = randint(0, 100)
                quantity = randint(6, 28) * items

                actual_cost = randint(100, 200) * quantity * 0.01

                # We don't care about net_cost.
                net_cost = actual_cost

                row = [
                    "sha",  # This value doesn't matter.
                    practice.ccg.regional_team_id,
                    practice.ccg.stp_id,
                    practice.ccg_id,
                    practice.pcn_id,
                    practice.code,
                    bnf_code,
                    bnf_name,
                    items,
                    net_cost,
                    actual_cost,
                    quantity,
                    timestamp,
                ]

                prescribing_rows.append(row)

    # In production, normalised_prescribing is actually a view,
    # but for the tests it's much easier to set it up as a normal table.
    table = Client("hscic").get_table("normalised_prescribing")

    headers = [
        "sha",
        "regional_team_id",
        "stp_id",
        "ccg_id",
        "pcn_id",
        "practice_id",
        "bnf_code",
        "bnf_name",
        "items",
        "net_cost",
        "actual_cost",
        "quantity",
        "month",
    ]

    headers_to_exclude_from_bq = ["regional_team_id", "stp_id", "pcn_id"]

    with tempfile.NamedTemporaryFile("wt") as f:
        writer = csv.writer(f)
        for row in prescribing_rows:
            row_to_upload = [
                item
                for item, header in zip(row, headers)
                if header not in headers_to_exclude_from_bq
            ]
            writer.writerow(row_to_upload)
        f.seek(0)
        table.insert_rows_from_csv(f.name, schemas.PRESCRIBING_SCHEMA)

    prescriptions = pd.DataFrame.from_records(prescribing_rows, columns=headers)
    prescriptions["month"] = prescriptions["month"].str[:10]

    return prescriptions


def upload_practice_statistics(randint):
    """Generate practice statistics data, and upload to BQ."""

    practice_statistics_rows = []
    dataframe_rows = []
    seen_practice_with_no_statistics = False

    for practice in Practice.objects.all():
        for month in [7, 8]:
            timestamp = "2018-0{}-01 00:00:00 UTC".format(month)

            if month == 8 and practice.code == "P00000":
                seen_practice_with_no_statistics = True
                continue

            total_list_size = randint(100, 200)

            row = [
                timestamp,  # month
                0,  # male_0_4
                0,  # female_0_4
                0,  # male_5_14
                0,  # male_15_24
                0,  # male_25_34
                0,  # male_35_44
                0,  # male_45_54
                0,  # male_55_64
                0,  # male_65_74
                0,  # male_75_plus
                0,  # female_5_14
                0,  # female_15_24
                0,  # female_25_34
                0,  # female_35_44
                0,  # female_45_54
                0,  # female_55_64
                0,  # female_65_74
                0,  # female_75_plus
                total_list_size,  # total_list_size
                0,  # astro_pu_cost
                0,  # astro_pu_items
                "{}",  # star_pu
                practice.ccg_id,  # pct_id
                practice.code,  # practice
            ]

            practice_statistics_rows.append(row)
            dataframe_rows.append(
                {
                    "month": timestamp[:10],
                    "practice_id": practice.code,
                    "pcn_id": practice.pcn_id,
                    "ccg_id": practice.ccg_id,
                    "stp_id": practice.ccg.stp_id,
                    "regional_team_id": practice.ccg.regional_team_id,
                    "thousand_patients": total_list_size / 1000.0,
                }
            )

    assert seen_practice_with_no_statistics

    # Upload practice_statistics_rows to BigQuery.
    table = Client("hscic").get_table("practice_statistics")

    with tempfile.NamedTemporaryFile("wt") as f:
        writer = csv.writer(f)
        for row in practice_statistics_rows:
            writer.writerow(row)
        f.seek(0)
        table.insert_rows_from_csv(f.name, schemas.PRACTICE_STATISTICS_SCHEMA)

    return pd.DataFrame.from_records(dataframe_rows)


def build_factory():
    """Build a MatrixStore DataFactory with prescriptions for several different
    presentations, to allow the BNF code simplification to be meaningful."""

    bnf_codes = [
        "0407010Q0AAAAAA",  # Co-Proxamol_Tab 32.5mg/325mg
        "0407010P0AAAAAA",  # Nefopam HCl_Inj 20mg/ml 1ml Amp
        "0703021Q0AAAAAA",  # Desogestrel_Tab 75mcg
        "0703021Q0BBAAAA",  # Cerazette_Tab 75mcg
        "0703021P0AAAAAA",  # Norgestrel_Tab 75mcg
        "0904010AUBBAAAA",  # Mrs Crimble's_G/F W/F Cheese Bites Orig
        "0904010AVBBAAAA",  # Mrs Crimble's_W/F Dutch Apple Cake
    ]
    factory = DataFactory()
    factory.create_prescribing_for_bnf_codes(bnf_codes)
    return factory


def sum_by_group(df, group_column, value_column):
    # The rounding is to work around a change in floating point behaviour which appeared
    # in Pandas 1.3 whereby sequences of values which used to sum as equal are now
    # returned as slightly different. See:
    # https://github.com/ebmdatalab/openprescribing/pull/3222
    return df.groupby(group_column)[value_column].sum().round(decimals=10)
