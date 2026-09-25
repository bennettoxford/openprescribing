import argparse
import json
import os
from datetime import datetime

import requests
from django.conf import settings
from django.core.management import BaseCommand

from openprescribing.utils import mkdir_p


def fetch_org_details(batch_size):
    offset = 0
    org_details = None

    while True:
        rsp = requests.post(
            "https://www.odsdatasearchandexport.nhs.uk/api/search/organisationReportSearch",
            json={
                "searchQueryPrimaryRoleCodes": ",".join(
                    # Full list of role codes available at:
                    # https://directory.spineservices.nhs.uk/ORD/2-0-0/roles
                    [
                        # PRESCRIBING COST CENTRE
                        # Includes GP practices, plus a whole load of other organisation
                        # types for which we have prescribing data
                        "RO177",
                        #
                        # PRIMARY CARE NETWORK
                        "RO272",
                        #
                        # CLINICAL COMMISSIONING GROUP
                        # SICBLs still have this as their primary role name, though they
                        # also have their new name as a non-primary role
                        "RO98",
                        #
                        # STRATEGIC PARTNERSHIP
                        # ICBs still have this as their primary role name, though they
                        # also have their new name as a non-primary role
                        "RO261",
                        #
                        # NHS ENGLAND (REGION)
                        "RO209",
                    ]
                ),
                "searchQueryIsActive": "All (Status)",
                "offset": offset,
                "batchSize": batch_size,
            },
        )
        page = rsp.json()

        if org_details is None:
            org_details = page
        else:
            org_details["orgArray"].extend(page["orgArray"])

        if len(page["orgArray"]) < batch_size:
            return org_details

        offset += batch_size


class Command(BaseCommand):
    def add_arguments(self, parser):
        def positive_int(value):
            value = int(value)
            if value <= 0:
                raise argparse.ArgumentTypeError("must be greater than zero")
            return value

        parser.add_argument("--batch-size", type=positive_int, default=1000)

    def handle(self, **kwargs):
        org_details = fetch_org_details(kwargs["batch_size"])

        output_dir = os.path.join(
            settings.PIPELINE_DATA_BASEDIR,
            "orgs",
            datetime.today().strftime("%Y_%m"),
        )

        mkdir_p(output_dir)

        with open(os.path.join(output_dir, "org_details.json"), "w") as f:
            json.dump(org_details, f, indent=2)
