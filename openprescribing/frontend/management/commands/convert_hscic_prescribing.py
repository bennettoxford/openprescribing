import datetime
import logging
import os

from django.core.management.base import BaseCommand, CommandError
from frontend.bq_schemas import RAW_PRESCRIBING_SCHEMA_V2
from frontend.models import ImportLog
from gcutils.bigquery import Client, NotFound

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Processes manually-fetched detailed prescribing information CSV.

    We assume that the source CSV file has been uploaded to Cloud Storage, at
    hscic/prescribing/{year_and_month}/{filename}.csv.

    The source CSV file contains "figures on the number of prescription items
    that are dispensed each month and information relating to costs for English
    practices".

    The source CSV file has one line for each presentation and pack size for
    each practice, (so prescriptions of 28 paracetamol will be on a separate
    line from prescriptions of 100 paracetamol).

    The converted CSV file has one line for each presentation of any pack size
    for each practice, (so a practice prescribing 2 items of 28 paracetamol and
    1 item of 100 paracetamol will have a line with 2 items and 156 quantity).
    """

    def add_arguments(self, parser):
        parser.add_argument("--filename")

    def handle(self, *args, **options):
        path = options["filename"]
        head, filename = os.path.split(path)
        _, year_and_month = os.path.split(head)

        logger.info("path: %s", path)
        logger.info("year_and_month: %s", year_and_month)

        date = year_and_month + "_01"
        try:
            datetime.datetime.strptime(date, "%Y_%m_%d")
        except ValueError:
            message = (
                "The file path must have a YYYY_MM "
                "date component in the containing directory: "
            )
            message += path
            raise CommandError(message)

        hscic_dataset_client = Client("hscic")
        tmp_dataset_client = Client("tmp_eu")

        # Check that we haven't already processed data for this month
        sql = """SELECT COUNT(*)
        FROM {hscic}.prescribing_v2
        WHERE month = TIMESTAMP('{date}')"""

        try:
            results = hscic_dataset_client.query(
                sql, substitutions={"date": date.replace("_", "-")}
            )
            assert results.rows[0][0] == 0
        except NotFound:
            pass

        # Create BQ table backed backed by uploaded source CSV file
        raw_data_table_name = "raw_prescribing_data_{}".format(year_and_month)
        gcs_path = "hscic/prescribing_v2/{}/{}".format(year_and_month, filename)

        logger.info("raw_data_table_name: %s", raw_data_table_name)
        logger.info("gcs_path: %s", gcs_path)

        raw_data_table = tmp_dataset_client.create_storage_backed_table(
            raw_data_table_name, RAW_PRESCRIBING_SCHEMA_V2, gcs_path
        )

        # Append aggregated data to prescribing table
        sql = """
         SELECT
          ICB_CODE AS sha,
          LEFT(PCO_CODE, 3) AS pct,
          PRACTICE_CODE AS practice,
          BNF_PRESENTATION_CODE AS bnf_code,
          BNF_PRESENTATION_DESCRIPTION AS bnf_name,
          SUM(ITEMS) AS items,
          SUM(NIC) AS net_cost,
          SUM(ACTUAL_COST) AS actual_cost,
          SUM(TOTAL_QUANTITY) AS quantity,
          TIMESTAMP('%s') AS month,
         FROM %s
         WHERE PRACTICE_CODE NOT LIKE '%%998'  -- see issue #349
         GROUP BY
           bnf_code, bnf_name, pct,
           practice, sha
        """ % (
            date.replace("_", "-"),
            raw_data_table.qualified_name,
        )

        logger.info("sql: %s", sql)

        prescribing_table = hscic_dataset_client.get_table("prescribing_v2")
        prescribing_table.insert_rows_from_query(
            sql, legacy=True, write_disposition="WRITE_APPEND"
        )

        ImportLog.objects.create(
            current_at=date.replace("_", "-"), filename=filename, category="prescribing"
        )
