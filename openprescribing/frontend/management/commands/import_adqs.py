"""This command extracts ADQ information from monthly detailed
prescribing data.

See https://github.com/ebmdatalab/openprescribing/issues/905 for
details.

"""

from django.core.management.base import BaseCommand
from django.db import transaction
from frontend.models import ImportLog, Presentation
from gcutils.bigquery import Client

SQL = """
WITH
  codes AS (
  SELECT
    BNF_PRESENTATION_CODE AS bnf_code,
    IEEE_DIVIDE(ADQ_USAGE, TOTAL_QUANTITY) AS adq_per_quantity,
    ROW_NUMBER() OVER (PARTITION BY BNF_PRESENTATION_CODE) AS row_number
  FROM
    {detailed_raw_data_table})
SELECT DISTINCT
  CONCAT(
    SUBSTR(codes.bnf_code, 0, 9),
    '.*',
    SUBSTR(codes.bnf_code, 14, 2)) AS bnf_code_regex,
  adq_per_quantity
FROM
  codes
WHERE
  row_number = 1
  AND adq_per_quantity > 0

"""


class Command(BaseCommand):
    help = "Imports ADQ codes from current raw prescribing data in BigQuery"

    def handle(self, *args, **options):
        client = Client("tmp_eu")
        year_and_month = ImportLog.objects.latest_in_category(
            "prescribing"
        ).current_at.strftime("%Y_%m")
        raw_data_table_name = "raw_prescribing_data_{}".format(year_and_month)
        sql = SQL.format(detailed_raw_data_table="{tmp_eu}.%s" % raw_data_table_name)
        with transaction.atomic():
            for row in client.query(sql).rows:
                bnf_code_regex, adq_per_quantity = row
                matches = Presentation.objects.filter(bnf_code__regex=bnf_code_regex)
                matches.update(adq_per_quantity=adq_per_quantity)
