import json
from frontend.models import PCN, PCT, Practice, RegionalTeam, STP
from django.core.management import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--path")

    def handle(self, **kwargs):
        with open(kwargs["path"]) as f:
            records = json.load(f)["orgArray"]
        import_all(records)


@transaction.atomic
def import_all(records):
    # By importing in this order, we guarantee that parent organisations have been
    # created before child organisations that reference them.
    import_regions(records)
    import_icbs(records)
    import_sicbls(records)
    import_pcns(records)
    import_practices(records)


def import_regions(records):
    for r in records:
        if r["primaryRoleName"] != "NHS ENGLAND (REGION)":
            continue

        RegionalTeam.objects.update_or_create(
            code=r["id"],
            defaults={
                "name": r["name"],
                "open_date": r["legStartDate"],
                "close_date": r["legEndDate"] or None,
            },
        )


def import_icbs(records):
    for r in records:
        if "INTEGRATED CARE BOARD" not in r["roleName"]:
            continue

        STP.objects.update_or_create(
            code=r["id"],
            defaults={
                "name": r["name"],
            },
        )


def import_sicbls(records):
    for r in records:
        if "SUB ICB LOCATION" not in r["roleName"]:
            continue

        sicbl, created = PCT.objects.update_or_create(
            code=r["id"],
            defaults={
                "org_type": "CCG",
                "open_date": r["legStartDate"],
                "close_date": r["legEndDate"] or None,
                "regional_team_id": r["NHSER"],
                "stp_id": r["ICB"],
            },
        )

        if created:
            # ODS names for SICBLs are not as descriptive as the original CCG names, so
            # we prefer those.  When we update to Django 5.0 we'll be able to use
            # create_defaults as an argument to update_or_create().
            sicbl.name = r["name"]
            sicbl.save()


def import_pcns(records):
    for r in records:
        if r["primaryRoleName"] != "PRIMARY CARE NETWORK":
            continue

        PCN.objects.update_or_create(
            code=r["id"],
            defaults={
                "name": r["name"],
            },
        )


def import_practices(records):
    status_to_code = {status: code for code, status in Practice.STATUS_SETTINGS}
    for r in records:
        if "GP PRACTICE" not in r["roleName"]:
            continue

        Practice.objects.update_or_create(
            code=r["id"],
            defaults={
                "name": r["name"],
                "address1": r.get("address1", ""),
                "address2": r.get("address2", ""),
                "address3": r.get("address3", ""),
                "address4": r.get("town", ""),
                "address5": "",  # address5 is not present in the new data
                "postcode": r.get("postcode", ""),
                "open_date": r["legStartDate"],
                "close_date": r["legEndDate"] or None,
                "status_code": status_to_code[r["status"]],
                "setting": 4,  # All GP PRACTICE records have setting 4
                "ccg_id": r["PCO"],
                "pcn_id": r["isPartnerToCode"][0] if r["isPartnerToCode"] else None,
            },
        )
