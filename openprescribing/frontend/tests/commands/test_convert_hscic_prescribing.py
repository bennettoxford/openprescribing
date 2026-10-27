import os

from django.core.management import call_command
from django.test import TestCase
from frontend.bq_schemas import PRESCRIBING_SCHEMA
from gcutils.bigquery import Client as BQClient
from gcutils.bigquery import NotFound, results_to_dicts
from gcutils.storage import Client as StorageClient


class ConvertHscicPrescribingTests(TestCase):
    """Test that data in the "detailed" format is correctly aggregated to
    the level we currently use in the website.

    The source format has one iine for each presentation *and pack
    size*, so prescriptions of 28 paracetamol will be on a separate
    line from prescriptions of 100 paracetamol.

    The destination format has one line for paracetamol of any pack
    size.

    """

    def test_data_is_aggregated(self):
        # there are 11 rows in the input file; 2 are for the same
        # practice/presentation and should be collapsed, and 1 is for
        # an UNKNONWN SURGERY (see issue #349)

        raw_data_path = (
            "frontend/tests/fixtures/commands/"
            + "convert_hscic_prescribing/2016_01/"
            + "EPD_201601.csv"
        )
        gcs_path = "hscic/prescribing_v2/2016_01/EPD_201601.csv"

        client = StorageClient()
        bucket = client.get_bucket()
        blob = bucket.blob(gcs_path)

        with open(raw_data_path, "rb") as f:
            blob.upload_from_file(f)

        call_command("convert_hscic_prescribing", filename=raw_data_path)

        # Test that data added to prescribing table
        client = BQClient()
        sql = """SELECT *
        FROM {hscic}.prescribing_v2
        WHERE month = TIMESTAMP('2016-01-01')"""

        rows = list(results_to_dicts(client.query(sql)))
        self.assertEqual(len(rows), 9)
        for row in rows:
            if row["practice"] == "P92042" and row["bnf_code"] == "0202010B0AAABAB":
                self.assertEqual(row["quantity"], 1288)

    def setUp(self):
        client = BQClient("hscic")
        client.get_or_create_table("prescribing_v2", PRESCRIBING_SCHEMA)

    def tearDown(self):
        table_name = "raw_prescribing_data_2016_01"
        try:
            BQClient("tmp_eu").delete_table(table_name)
        except NotFound:
            pass

        table = BQClient("hscic").get_table("prescribing_v2")
        table.delete_all_rows()

        try:
            os.remove(
                "frontend/tests/fixtures/commands/"
                + "convert_hscic_prescribing/2016_01/"
                + "Detailed_Prescribing_Information_formatted.CSV"
            )
        except OSError:
            pass
