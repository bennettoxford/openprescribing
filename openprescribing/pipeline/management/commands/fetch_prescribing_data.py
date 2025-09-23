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
        rsp = requests.get(
            "https://opendata.nhsbsa.net/api/3/action/package_show?id=english-prescribing-dataset-epd-with-snomed-code"
        )
        resources = rsp.json()["result"]["resources"]
        urls = [
            r["url"]
            for r in resources
            if r["name"] == "EPD_SNOMED_{year}{month:02d}".format(year=year, month=month)
        ]
        assert len(urls) == 1, urls
        rsp = requests.get(urls[0], stream=True)
        assert rsp.ok

        dir_path = os.path.join(
            settings.PIPELINE_DATA_BASEDIR,
            "prescribing_v2",
            "{year}_{month:02d}".format(year=year, month=month),
        )
        mkdir_p(dir_path)
        filename = "epd_{year}{month:02d}.csv".format(year=year, month=month)

        with open(os.path.join(dir_path, filename), "wb") as f:
            for block in rsp.iter_content(32 * 1024):
                f.write(block)
