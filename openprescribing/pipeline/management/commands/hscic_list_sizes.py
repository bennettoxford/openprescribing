import datetime
import os
import re
import shutil
import zipfile
from urllib.parse import urlparse

import requests
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from lxml import html

from openprescribing.utils import mkdir_p

# NHS-D have an exciting variety of names for this file
SOURCE_FILE_PATTERNS = [
    r"gp-reg-pat-prac-quin-age[\w\-]*\.zip$",
    r"gp-reg-pat(ients)?-prac-quin-age\.csv$",
    r"gp-reg-pat-prac-quin-age[\w\-]*\.csv$",
    r"gp-reg-patients[\d\-]*\.csv$",
    r"gp_practice_counts\.csv$",
]

OUTPUT_FILENAME = "gp-reg-pat-prac-quin-age.csv"


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

        source_url = find_url(rsp.content, *SOURCE_FILE_PATTERNS)

        dir_path = os.path.join(
            settings.PIPELINE_DATA_BASEDIR, "patient_list_size", datestamp
        )
        mkdir_p(dir_path)
        csv_path = os.path.join(dir_path, OUTPUT_FILENAME)

        rsp = requests.get(source_url)

        if source_url.endswith(".zip"):
            zip_path = os.path.join(
                dir_path, os.path.basename(urlparse(source_url).path)
            )
            with open(zip_path, "wb") as f:
                f.write(rsp.content)
            with zipfile.ZipFile(zip_path) as zf:
                members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                assert len(members) == 1, f"Expected exactly one CSV in zip: {members}"
                with zf.open(members[0]) as src, open(csv_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        elif source_url.endswith(".csv"):
            with open(csv_path, "wb") as f:
                f.write(rsp.content)
        else:
            raise CommandError(f"Unhandled file type: {source_url}")


def find_url(content, *url_regexes):
    tree = html.fromstring(content)
    hrefs = tree.xpath("//a/@href")
    for url_re in url_regexes:
        matcher = re.compile(url_re)
        matches = {href for href in hrefs if matcher.search(href)}
        assert len(matches) <= 1, f"Ambiguous matches for {url_re!r}: {matches}"
        if matches:
            return matches.pop()
    raise CommandError(f"No matching file found: {url_regexes}")
