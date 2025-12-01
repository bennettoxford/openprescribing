import datetime
from django.forms.models import model_to_dict
from django.test import TestCase
from frontend.models import PCN, PCT, Practice, RegionalTeam, STP
from pipeline.management.commands.import_org_details import import_all, import_sicbls


class ImportOrgCodes(TestCase):
    def test_import_org_codes(self):
        records = [
            {
                "id": "Y61",
                "name": "EAST OF ENGLAND COMMISSIONING REGION",
                "inactive": False,
                "roleName": [],
                "primaryRoleName": "NHS ENGLAND (REGION)",
                "isPartnerToCode": [],
                "RE4": "",
                "ICB": "QUE",
                "NHSER": "Y61",
                "country": "ENGLAND",
                "legStartDate": "2019-04-01",
                "legEndDate": "",
            },
            {
                "id": "QHG",
                "name": "NHS BEDFORDSHIRE INTEGRATED CARE BOARD",
                "inactive": False,
                "roleName": ["INTEGRATED CARE BOARD"],
                "primaryRoleName": "STRATEGIC PARTNERSHIP",
                "isPartnerToCode": [],
                "RE4": "",
                "ICB": "QHG",
                "NHSER": "Y61",
                "country": "ENGLAND",
                "legStartDate": "2017-04-01",
                "legEndDate": "",
            },
            {
                "id": "M1J4Y",
                "name": "NHS BEDFORDSHIRE ICB - M1J4Y",
                "inactive": False,
                "roleName": ["SUB ICB LOCATION"],
                "primaryRoleName": "CLINICAL COMMISSIONING GROUP",
                "isPartnerToCode": [],
                "RE4": "",
                "ICB": "QHG",
                "NHSER": "Y61",
                "country": "ENGLAND",
                "legStartDate": "2021-04-01",
                "legEndDate": "",
            },
            {
                "id": "U49574",
                "name": "ASCENT PCN",
                "inactive": False,
                "roleName": [],
                "primaryRoleName": "PRIMARY CARE NETWORK",
                "isPartnerToCode": [],
                "RE4": "M1J4Y",
                "ICB": "QHG",
                "NHSER": "Y61",
                "country": "ENGLAND",
                "legStartDate": "2020-07-01",
                "legEndDate": "",
            },
            {
                "id": "E81050",
                "name": "ASPLANDS MEDICAL CENTRE",
                "inactive": False,
                "roleName": ["GP PRACTICE"],
                "primaryRoleName": "PRESCRIBING COST CENTRE",
                "isPartnerToCode": ["U49574"],
                "RE4": "M1J4Y",
                "ICB": "QHG",
                "NHSER": "Y61",
                "country": "ENGLAND",
                "status": "Active",
                "legStartDate": "1974-04-01",
                "legEndDate": "",
            },
            {
                "id": "Y08176",
                "name": "ACHE PUTNOE BEDS",
                "inactive": False,
                "roleName": ["COMMUNITY HEALTH SERVICE PRESCRIBING COST CENTRE"],
                "primaryRoleName": "PRESCRIBING COST CENTRE",
                "isPartnerToCode": [],
                "RE4": "M1J4Y",
                "ICB": "QHG",
                "NHSER": "Y61",
                "country": "ENGLAND",
                "status": "Active",
                "legStartDate": "2023-12-11",
                "legEndDate": "",
            },
            {
                "id": "W95633",
                "name": "74 MONK STREET",
                "inactive": False,
                "roleName": ["GP PRACTICE"],
                "primaryRoleName": "PRESCRIBING COST CENTRE",
                "isPartnerToCode": [],
                "RE4": "7A5",
                "ICB": "",
                "NHSER": "",
                "country": "WALES",
                "status": "Active",
                "legStartDate": "1988-11-01",
                "legEndDate": "",
            },
        ]

        import_all(records)

        self.assertEqual(
            model_to_dict(RegionalTeam.objects.get()),
            {
                "code": "Y61",
                "name": "EAST OF ENGLAND COMMISSIONING REGION",
                "open_date": datetime.date(2019, 4, 1),
                "close_date": None,
                "address": None,
                "postcode": None,
            },
        )
        self.assertEqual(
            model_to_dict(STP.objects.get()),
            {
                "code": "QHG",
                "name": "NHS BEDFORDSHIRE INTEGRATED CARE BOARD",
                "ons_code": None,
            },
        )
        self.assertEqual(
            model_to_dict(PCT.objects.get()),
            {
                "code": "M1J4Y",
                "name": "NHS BEDFORDSHIRE ICB - M1J4Y",
                "regional_team": "Y61",
                "stp": "QHG",
                "org_type": "CCG",
                "open_date": datetime.date(2021, 4, 1),
                "close_date": None,
                "address": None,
                "postcode": None,
                "boundary": None,
                "centroid": None,
                "ons_code": None,
            },
        )
        self.assertEqual(
            model_to_dict(PCN.objects.get()),
            {
                "code": "U49574",
                "name": "ASCENT PCN",
            },
        )
        self.assertEqual(
            model_to_dict(Practice.objects.get()),
            {
                "code": "E81050",
                "name": "ASPLANDS MEDICAL CENTRE",
                "setting": 4,
                "status_code": "A",
                "pcn": "U49574",
                "ccg": "M1J4Y",
                "open_date": datetime.date(1974, 4, 1),
                "close_date": None,
                "address1": "",
                "address2": "",
                "address3": "",
                "address4": "",
                "address5": "",
                "postcode": "",
                "location": None,
                "boundary": None,
                "ccg_change_reason": None,
                "join_provider_date": None,
                "leave_provider_date": None,
            },
        )

    def test_import_sicbls_keeps_original_name(self):
        RegionalTeam.objects.create(code="Y63")
        STP.objects.create(code="QOQ")
        PCT.objects.create(code="03Q", name="NHS Vale of York")

        import_sicbls(
            [
                {
                    "id": "03Q",
                    "name": "NHS HUMBER AND NORTH YORKSHIRE ICB - 03Q",
                    "inactive": False,
                    "roleName": ["SUB ICB LOCATION"],
                    "primaryRoleName": "CLINICAL COMMISSIONING GROUP",
                    "isPartnerToCode": [],
                    "RE4": "",
                    "ICB": "QOQ",
                    "NHSER": "Y63",
                    "country": "ENGLAND",
                    "legStartDate": "2019-04-01",
                    "legEndDate": "2030-03-31",
                },
            ]
        )

        self.assertEqual(
            model_to_dict(PCT.objects.get()),
            {
                "code": "03Q",
                "name": "NHS Vale of York",
                "regional_team": "Y63",
                "stp": "QOQ",
                "org_type": "CCG",
                "open_date": datetime.date(2019, 4, 1),
                "close_date": datetime.date(2030, 3, 31),
                "address": None,
                "postcode": None,
                "boundary": None,
                "centroid": None,
                "ons_code": None,
            },
        )
