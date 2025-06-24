"""
Downloads and unzips the latest dm+d data to
PIPELINE_DATA_BASEDIR/dmd/[yyyy_mm_dd]/[release]/

Does nothing if file already downloaded.
"""

import glob
import os
import zipfile

import requests
from django.conf import settings
from django.core.management import BaseCommand

from openprescribing.utils import mkdir_p


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **kwargs):
        index_url = f"https://isd.digital.nhs.uk/trud/api/v1/keys/{settings.TRUD_API_KEY}/items/24/releases?latest"
        rsp = requests.get(index_url)
        release_metadata = rsp.json()["releases"][0]
        release_date = release_metadata["releaseDate"].replace("-", "_")
        download_url = release_metadata["archiveFileUrl"]
        filename = release_metadata["archiveFileName"]
        dir_path = os.path.join(settings.PIPELINE_DATA_BASEDIR, "dmd", release_date)
        zip_path = os.path.join(dir_path, filename)
        unzip_dir_path = os.path.join(dir_path, os.path.splitext(filename)[0])

        if os.path.exists(zip_path):
            return

        rsp = requests.get(download_url, stream=True)
        mkdir_p(dir_path)

        with open(zip_path, "wb") as f:
            for block in rsp.iter_content(32 * 1024):
                f.write(block)

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(unzip_dir_path)

        for nested_zip_path in glob.glob(os.path.join(unzip_dir_path, "*.zip")):
            with zipfile.ZipFile(nested_zip_path) as zf:
                zf.extractall(unzip_dir_path)
