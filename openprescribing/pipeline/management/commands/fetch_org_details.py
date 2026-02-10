import json
import os
from datetime import datetime

import requests
from django.conf import settings
from django.core.management import BaseCommand

from openprescribing.utils import mkdir_p


class Command(BaseCommand):
    def handle(self, **kwargs):
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
                "offset": 0,
                "batchSize": 100000,
            },
        )

        output_dir = os.path.join(
            settings.PIPELINE_DATA_BASEDIR,
            "orgs",
            datetime.today().strftime("%Y_%m"),
        )

        mkdir_p(output_dir)

        with open(os.path.join(output_dir, "org_details.json"), "w") as f:
            json.dump(rsp.json(), f, indent=2)
