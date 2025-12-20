import csv
import os

import requests
from django.conf import settings
from django.core.management import BaseCommand

from openprescribing.utils import mkdir_p


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("year", type=int)
        parser.add_argument("month", type=int)

    def handle(self, year, month, **kwargs):
        year_month = f"{year}{month:02}"

        rsp = requests.get(
            "https://opendata.nhsbsa.net/api/3/action/package_show?id=english-prescribing-dataset-epd-with-snomed-code"
        )
        resources = rsp.json()["result"]["resources"]
        urls = [r["url"] for r in resources if r["name"] == f"EPD_SNOMED_{year_month}"]
        assert len(urls) == 1, urls
        rsp = requests.get(urls[0], stream=True)
        assert rsp.ok

        dir_path = os.path.join(
            settings.PIPELINE_DATA_BASEDIR, "prescribing_v2", f"{year}_{month:02}"
        )
        mkdir_p(dir_path)
        full_path = os.path.join(dir_path, f"epd_{year_month}_full.csv")
        path = os.path.join(dir_path, f"epd_{year_month}.csv")

        with open(full_path, "wb") as f:
            for block in rsp.iter_content(32 * 1024):
                f.write(block)

        # The BSA now only publish prescribing data with an extra column containing
        # SNOMED codes.  Downstream actions can't process this extra column, so we
        # remove it.
        with open(full_path) as f1:
            with open(path, "w") as f2:
                reader = csv.reader(f1)
                writer = csv.writer(f2)
                for row in reader:
                    writer.writerow(row[:-1])

        # The pipeline runner will try to call convert_hscic_prescribing on any
        # unimported files, so we delete the full file once we have processed it.
        os.remove(full_path)
