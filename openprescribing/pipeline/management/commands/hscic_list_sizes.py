import datetime
import os
import zipfile

import requests
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from lxml import html

from openprescribing.utils import mkdir_p


class Command(BaseCommand):
    help = """
    Fetches HSCIC list size data for given year and month.  Does nothing if
    data already downloaded.  Raises exception if data not found.
    """

    def add_arguments(self, parser):
        parser.add_argument("year", type=int)
        parser.add_argument("month", type=int)

    def handle(self, *args, **kwargs):
        date = datetime.date(kwargs["year"], kwargs["month"], 1)
        datestamp = date.strftime("%Y_%m")

        # See https://github.com/bennettoxford/nhsd-proxy/ for details.
        url = date.strftime(
            "http://nhsd-proxy.openprescribing.net:8080/data-and-information/publications/statistical/patients-registered-at-a-gp-practice/%B-%Y"
        ).lower()

        rsp = requests.get(url)

        if rsp.status_code != 200:
            raise CommandError("Could not find any data for %s" % datestamp)

        filename = "gp-reg-pat-prac-quin-age.zip"
        tree = html.fromstring(rsp.content)
        source_url = tree.xpath(f"//a[contains(@href, '{filename}')]/@href")[0]

        dir_path = os.path.join(
            settings.PIPELINE_DATA_BASEDIR, "patient_list_size", datestamp
        )
        zip_path = os.path.join(dir_path, filename)
        mkdir_p(dir_path)

        rsp = requests.get(source_url)

        with open(zip_path, "wb") as f:
            f.write(rsp.content)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extract("gp-reg-pat-prac-quin-age.csv", dir_path)
