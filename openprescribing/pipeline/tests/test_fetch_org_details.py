import argparse
from unittest import mock

from django.test import SimpleTestCase
from pipeline.management.commands.fetch_org_details import Command, fetch_org_details


class FetchOrgDetailsTest(SimpleTestCase):
    def test_command_batch_size_argument(self):
        parser = argparse.ArgumentParser()
        Command().add_arguments(parser)

        self.assertEqual(parser.parse_args([]).batch_size, 1000)
        self.assertEqual(parser.parse_args(["--batch-size", "250"]).batch_size, 250)

    def test_command_rejects_non_positive_batch_size(self):
        parser = argparse.ArgumentParser(exit_on_error=False)
        Command().add_arguments(parser)

        with self.assertRaisesRegex(
            argparse.ArgumentError, "must be greater than zero"
        ):
            parser.parse_args(["--batch-size", "0"])

    @mock.patch("pipeline.management.commands.fetch_org_details.requests.post")
    def test_fetches_and_merges_pages(self, post):
        first_page = {
            "orgArray": [{"id": str(i)} for i in range(1000)],
            "orgCodeSystemUpdatedAt": "22-09-2026",
        }
        second_page = {
            "orgArray": [{"id": "1000"}],
            "orgCodeSystemUpdatedAt": "23-09-2026",
        }
        post.side_effect = [
            mock.Mock(**{"json.return_value": first_page}),
            mock.Mock(**{"json.return_value": second_page}),
        ]

        result = fetch_org_details(batch_size=1000)

        self.assertEqual(len(result["orgArray"]), 1001)
        self.assertEqual(result["orgArray"][0], {"id": "0"})
        self.assertEqual(result["orgArray"][-1], {"id": "1000"})
        self.assertEqual(result["orgCodeSystemUpdatedAt"], "22-09-2026")
