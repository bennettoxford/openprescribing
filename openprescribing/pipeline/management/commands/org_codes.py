import datetime
import os
from io import BytesIO
from zipfile import ZipFile

import requests
from django.conf import settings
from django.core.management import BaseCommand

"""Practice and CCG metadata, keyed by code.

Similar data, pertaining to specific points in time, is also found in
the files downloaded to `data/raw_data/T<datestamp>ADDR+BNFT.CSV`.

We prefer data from these files to the `ADDR+BNFT` versions, but the
data we download here is only available as current data; this means we
would lack address information for historic data points if we only
relied on these org files.

This data is therefore worth updating every month.

"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--ccg", action="store_true")
        parser.add_argument("--practice", action="store_true")
        parser.add_argument("--postcode", action="store_true")
        parser.add_argument("--region", action="store_true")
        parser.add_argument("--pcn", action="store_true")

    def handle(self, *args, **kwargs):
        self.verbose = kwargs["verbosity"] > 1

        if kwargs["practice"]:
            self.fetch_and_extract_zipped_file("epraccur", "practice_details")
        if kwargs["ccg"]:
            self.fetch_and_extract_zipped_file("eccg", "ccg_details")
        if kwargs["postcode"]:
            self.fetch_and_extract_zipped_file("gridall", "nhs_postcode_file")
        if kwargs["region"]:
            self.fetch_and_extract_zipped_file("eauth", "region_details")
        if kwargs["pcn"]:
            self.fetch_and_extract_zipped_file("epcn", "pcn_details")

    def fetch_and_extract_zipped_file(self, base_filename, dest_dirname):
        """Grab a zipfile from a url, and extract a single file from it."""

        zip_filename = base_filename + ".zip"
        if base_filename == "epcn":
            # See https://github.com/bennettoxford/nhsd-proxy/ for details.
            url = "http://nhsd-proxy.openprescribing.net:8080/binaries/content/assets/website-assets/services/ods/data-downloads-other-nhs-organisations/epcn.zip"
            filename = "epcn.xlsx"
        else:
            url = "https://files.digital.nhs.uk/assets/ods/current/" + zip_filename
            filename = base_filename + ".csv"

        buf = BytesIO()
        buf.write(requests.get(url).content)
        buf.flush()
        zipfile = ZipFile(buf)

        dest_dir = os.path.join(
            settings.PIPELINE_DATA_BASEDIR,
            dest_dirname,
            datetime.datetime.today().strftime("%Y_%m"),
        )

        zipfile.extract(filename, dest_dir)
