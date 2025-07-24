import os
import re

import requests
from django.conf import settings
from django.core.management import BaseCommand

from openprescribing.utils import mkdir_p


class Command(BaseCommand):
    def handle(self, **kwargs):
        rsp = requests.get(
            "https://opendata.nhsbsa.net/api/3/action/package_show?id=bnf-code-information-current-year"
        )
        resources = rsp.json()["result"]["resources"]
        names = [r["name"] for r in resources]
        assert names == sorted(names)
        latest = resources[-1]

        match = re.match(
            r"^BNF_CODE_CURRENT_(?P<year>\d{4})(?P<month>\d{2})_VERSION_(\d+)$",
            latest["name"],
        )
        assert match is not None
        year = match.group("year")
        month = match.group("month")

        url = latest["url"]
        filename = url.split("/")[-1]
        rsp = requests.get(url)
        assert rsp.ok

        dir_path = os.path.join(
            settings.PIPELINE_DATA_BASEDIR,
            "bnf_codes",
            "{year}_{month}".format(year=year, month=month),
        )
        mkdir_p(dir_path)

        with open(os.path.join(dir_path, filename), "w") as f:
            f.write(rsp.text)
