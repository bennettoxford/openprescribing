# coding=utf8

import contextlib
import datetime
import tempfile
from pathlib import Path

import mock
import pipeline.management.commands.fetch_and_import_ncso_concessions as fetch_ncso
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from frontend.models import NCSOConcession


class TestFetchAndImportNCSOConcesions(TestCase):
    fixtures = ["for_ncso_concessions"]

    def test_parse_concessions(self):
        base_path = Path(settings.APPS_ROOT) / "pipeline/test-data/pages"
        page_content = (base_path / "price_concessions.html").read_text()
        items = list(fetch_ncso.parse_concessions(page_content))
        self.assertEqual(len(items), 46)
        self.assertEqual(
            items[:3] + items[-3:],
            [
                {
                    "date": datetime.date(2024, 1, 1),
                    "drug": "Amiloride 5mg tablets",
                    "pack_size": "28",
                    "price_pence": 1554,
                },
                {
                    "date": datetime.date(2024, 1, 1),
                    "drug": "Baclofen 5mg/5ml oral solution sugar free",
                    "pack_size": "300",
                    "price_pence": 397,
                },
                {
                    "date": datetime.date(2024, 1, 1),
                    "drug": "Betamethasone valerate 0.1% cream",
                    "pack_size": "100",
                    "price_pence": 405,
                },
                {
                    "date": datetime.date(2024, 1, 1),
                    "drug": "Zonisamide 50mg capsules",
                    "pack_size": "56",
                    "price_pence": 1352,
                },
                {
                    "date": datetime.date(2024, 1, 1),
                    "drug": "Zopiclone 3.75mg tablets",
                    "pack_size": "28",
                    "price_pence": 143,
                },
                {
                    "date": datetime.date(2024, 1, 1),
                    "drug": "Zopiclone 7.5mg tablets",
                    "pack_size": "28",
                    "price_pence": 156,
                },
            ],
        )

    def test_parse_concessions_archive(self):
        base_path = Path(settings.APPS_ROOT) / "pipeline/test-data/pages"
        page_content = (base_path / "price_concessions_archive.html").read_text()
        items = list(fetch_ncso.parse_concessions(page_content))
        self.assertEqual(len(items), 460)
        self.assertEqual(
            items[:3] + items[-3:],
            [
                {
                    "date": datetime.date(2023, 12, 1),
                    "drug": "Acamprosate 333mg gastro-resistant tablets",
                    "pack_size": "168",
                    "price_pence": 2276,
                },
                {
                    "date": datetime.date(2023, 12, 1),
                    "drug": "Aciclovir 800mg tablets",
                    "pack_size": "35",
                    "price_pence": 360,
                },
                {
                    "date": datetime.date(2023, 12, 1),
                    "drug": "Amiloride 5mg tablets",
                    "pack_size": "28",
                    "price_pence": 1570,
                },
                {
                    "date": datetime.date(2019, 11, 1),
                    "drug": "Tizanidine 2mg tablets",
                    "pack_size": "120",
                    "price_pence": 1283,
                },
                {
                    "date": datetime.date(2019, 11, 1),
                    "drug": "Trihexyphenidyl 2mg tablets",
                    "pack_size": "84",
                    "price_pence": 1350,
                },
                {
                    "date": datetime.date(2019, 11, 1),
                    "drug": "Venlafaxine 75mg tablets",
                    "pack_size": "56",
                    "price_pence": 496,
                },
            ],
        )

    def test_read_concessions_csv(self):
        contents = (
            "Date,Name,Pack Size,Price Pence,Notes,URL (if applicable)\n"
            "2025-03-01,Trimethoprim 200mg tablets,6,179,,\n"
            "2025-03-01,Trimethoprim 200mg tablets,14,419,,"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "concessions.csv"
            with open(file_path, "w") as f:
                f.write(contents)
            concessions = fetch_ncso.read_concessions_csv(file_path)
        self.assertEqual(
            concessions,
            [
                {
                    "date": datetime.date(2025, 3, 1),
                    "drug": "Trimethoprim 200mg tablets",
                    "pack_size": "6",
                    "price_pence": 179,
                    "manually_added": True,
                },
                {
                    "date": datetime.date(2025, 3, 1),
                    "drug": "Trimethoprim 200mg tablets",
                    "pack_size": "14",
                    "price_pence": 419,
                    "manually_added": True,
                },
            ],
        )

    def test_convert_concessions_csv_row_raises_error_for_incorrect_date(self):
        with self.assertRaises(
            AssertionError, msg="2025-03-03 is not the first of the month"
        ):
            fetch_ncso.convert_concessions_csv_row(
                {
                    "Date": "2025-03-03",
                    "Name": "Trimethoprim 200mg tablets",
                    "Pack Size": "6",
                    "Price Pence": "179",
                }
            )

    def test_manually_added_concessions_file(self):
        concessions = fetch_ncso.read_concessions_csv(
            fetch_ncso.MANUALLY_ADDED_CONCESSIONS_PATH
        )  # Should not error
        self.assertGreaterEqual(len(concessions), 0)

    def test_match_concession_vmpp_ids_unambiguous_match(self):
        # The happy case: there's a single VMPP which matches the name and pack-size
        concession = {
            "drug": "Amiloride 5mg tablets",
            "pack_size": "28",
        }
        vmpp_id_to_name = {
            1191111000001100: "Amiloride 5mg tablets 28 tablet",
        }
        expected = {
            "drug": "Amiloride 5mg tablets",
            "pack_size": "28",
            "vmpp_id": 1191111000001100,
        }
        self.assertEqual(
            fetch_ncso.match_concession_vmpp_ids([concession], vmpp_id_to_name),
            [expected],
        )

    def test_match_concession_vmpp_ids_when_ambiguous(self):
        # Although we have VMPPs that match, we don't have a single unambiguous match so
        # we refuse to match any.
        concession = {
            "drug": "Bevacizumab 1.25mg/0.05ml solution for injection vials",
            "pack_size": "1",
        }
        vmpp_id_to_name = {
            19680811000001105: "Bevacizumab 1.25mg/0.05ml solution for injection vials 1 ml",
            19812211000001101: "Bevacizumab 1.25mg/0.05ml solution for injection vials 1 vial",
        }
        expected = {
            "drug": "Bevacizumab 1.25mg/0.05ml solution for injection vials",
            "pack_size": "1",
            "vmpp_id": None,
        }
        self.assertEqual(
            fetch_ncso.match_concession_vmpp_ids([concession], vmpp_id_to_name),
            [expected],
        )

    def test_match_concession_vmpp_ids_using_previous_concession(self):
        concession = {
            "drug": "Amilorde 5mg tablets",  # typo is deliberate
            "pack_size": "28",
        }
        vmpp_id_to_name = {
            1191111000001100: "Amiloride 5mg tablets 28 tablet",
        }
        # Create previous, manually reconciled concession using the typoed name
        NCSOConcession.objects.create(
            date="2017-10-01",
            drug="Amilorde 5mg tablets",
            pack_size="28",
            price_pence=925,
            vmpp_id=1191111000001100,
        )
        expected = {
            "drug": "Amilorde 5mg tablets",
            "pack_size": "28",
            "vmpp_id": 1191111000001100,
        }
        self.assertEqual(
            fetch_ncso.match_concession_vmpp_ids([concession], vmpp_id_to_name),
            [expected],
        )

    def test_match_concession_vmpp_ids_using_manual_correction(self):
        concession = {
            "drug": "Co-amoxiclav 500/125 tablets",
            "pack_size": "21",
        }
        vmpp_id_to_name = {
            1247311000001103: "Co-amoxiclav 500mg/125mg tablets 21 tablet",
        }
        expected = {
            "drug": "Co-amoxiclav 500/125 tablets",
            "pack_size": "21",
            "vmpp_id": 1247311000001103,
        }
        self.assertEqual(
            fetch_ncso.match_concession_vmpp_ids([concession], vmpp_id_to_name),
            [expected],
        )

    def test_fetch_and_import_ncso_concessions(self):
        matched = [
            {
                "date": datetime.date(2023, 3, 1),
                "drug": "Amiloride 5mg tablets",
                "pack_size": "28",
                "price_pence": 925,
                "vmpp_id": 1191111000001100,
            },
            {
                "date": datetime.date(2023, 3, 1),
                "drug": "Duloxetine 40mg gastro-resistant capsules",
                "pack_size": "56",
                "price_pence": 396,
                "vmpp_id": 8049011000001108,
            },
            {
                "date": datetime.date(2023, 3, 1),
                "drug": "Bicalutamide 150mg tablets",
                "pack_size": "28",
                "price_pence": 450,
                "vmpp_id": None,
            },
        ]

        # Create existing concession which we expect to be updated
        NCSOConcession.objects.create(
            date="2023-03-01",
            drug="Duloxetine 40mg gastro-resistant capsules",
            pack_size="56",
            price_pence=350,
            vmpp_id=8049011000001108,
        )

        with ContextStack(mock.patch.object) as patch:
            patch(fetch_ncso, "requests")
            patch(fetch_ncso, "parse_concessions")
            patch(fetch_ncso, "read_concessions_csv")
            patch(fetch_ncso, "match_concession_vmpp_ids", return_value=matched)

            Client = patch(fetch_ncso, "Client")
            notify_slack = patch(fetch_ncso, "notify_slack")

            call_command("fetch_and_import_ncso_concessions")

            self.assertEqual(NCSOConcession, Client().upload_model.call_args[0][0])
            self.assertIn(
                "Fetched 3 concessions, including 0 manually added concessions. Imported 2 new concessions.",
                notify_slack.call_args[0][0],
            )

        # Check that all three concessions now exist in the database
        for item in matched:
            self.assertTrue(
                NCSOConcession.objects.filter(
                    date=item["date"],
                    drug=item["drug"],
                    pack_size=item["pack_size"],
                    price_pence=item["price_pence"],
                    vmpp_id=item["vmpp_id"],
                ).exists()
            )

    def test_fetch_and_import_ncso_concessions_includes_manual_additions(self):
        manual_additions = [
            {
                "date": datetime.date(2023, 3, 1),
                "drug": "Amiloride 5mg tablets",
                "pack_size": "28",
                "price_pence": 925,
                "manually_added": True,
            },
        ]

        item_exists = NCSOConcession.objects.filter(
            date=datetime.date(2023, 3, 1),
            drug="Amiloride 5mg tablets",
            pack_size="28",
            price_pence=925,
        ).exists
        self.assertFalse(item_exists())

        with ContextStack(mock.patch.object) as patch:
            patch(fetch_ncso, "requests")
            patch(fetch_ncso, "parse_concessions", return_value=[])
            patch(fetch_ncso, "read_concessions_csv", return_value=manual_additions)
            patch(fetch_ncso, "get_vmpp_id_to_name_map", return_value={})
            patch(fetch_ncso, "Client")
            notify_slack = patch(fetch_ncso, "notify_slack")

            call_command("fetch_and_import_ncso_concessions")
            self.assertIn(
                "Fetched 1 concessions, including 1 manually added concessions. Imported 1 new concessions.",
                notify_slack.call_args[0][0],
            )
        self.assertTrue(item_exists())

    def test_format_message_when_nothing_to_do(self):
        msg = fetch_ncso.format_message([])
        self.assertEqual(
            msg,
            "Fetched 0 concessions, including 0 manually added concessions. Found no new concessions to import.",
        )

    def test_regularise_name(self):
        self.assertEqual(
            fetch_ncso.regularise_name(" * Some Drug Name 500 mg"), "some drug name 500"
        )

    def test_parse_price(self):
        cases = [
            ("£12.34", 1234),
            ("12.34", 1234),
            ("12.3", 1230),
            ("12.03", 1203),
            ("12", 1200),
            ("£12", 1200),
            ("£7.02 (previously £6.17)", 702),
            # Correct weird one-off typo
            ("11..35", 1135),
        ]
        for price_str, value in cases:
            with self.subTest(price_str=price_str, value=value):
                self.assertEqual(fetch_ncso.parse_price(price_str), value)

    def test_parse_price_reject_invalid(self):
        cases = [
            "£.35",
            ".35",
            "1.350",
            "12..34",
            "12,34",
        ]
        for price_str in cases:
            with self.subTest(price_str=price_str):
                with self.assertRaises(AssertionError):
                    fetch_ncso.parse_price(price_str)


class ContextStack(contextlib.ExitStack):
    """
    Apply multiple context managers without either nesting or using the hideous multi
    argument form
    """

    def __init__(self, context_manager):
        super().__init__()
        self._context_manager = context_manager

    def __call__(self, *args, **kwargs):
        return self.enter_context(self._context_manager(*args, **kwargs))
