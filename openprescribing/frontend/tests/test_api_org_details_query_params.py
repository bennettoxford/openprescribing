import csv

from .api_test_base import ApiTestBase


class TestAPIOrgDetailsQueryParams(ApiTestBase):
    def test_api_view_org_details_rejects_unknown_query_params(self):
        for param in ("org_code", "org_id", "q", "unexpected"):
            with self.subTest(param=param):
                url = self.api_prefix
                url += f"/org_details?format=csv&org_type=pcn&{param}=U81825"
                response = self.client.get(url, follow=True)

                self.assertEqual(response.status_code, 400)
                rows = list(
                    csv.DictReader(response.content.decode("utf8").splitlines())
                )
                self.assertEqual(
                    rows[0]["detail"], f"{param} is not a valid query parameter"
                )

    def test_api_view_org_details_sorts_multiple_unknown_query_params(self):
        url = self.api_prefix
        url += "/org_details?format=csv&z=1&org_code=U81825"
        response = self.client.get(url, follow=True)

        self.assertEqual(response.status_code, 400)
        rows = list(csv.DictReader(response.content.decode("utf8").splitlines()))
        self.assertEqual(
            rows[0]["detail"],
            "org_code, z are not valid query parameters",
        )
