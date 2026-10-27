import json

from .api_test_base import ApiTestBase


class TestAPIBNFCodeViews(ApiTestBase):
    api_prefix = "/api/1.0"

    def assertNotJson(self, content):
        try:
            json.loads(content)
            raise AssertionError("Expected %s... to be non-JSON" % content[:10])
        except ValueError:
            pass

    def assertJson(self, content):
        try:
            json.loads(content)
        except ValueError:
            raise AssertionError("Expected %s... to be JSON" % content[:10])

    def test_header_and_query_string_json_negotiation(self):
        url = "%s/bnf_code?q=lor&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertJson(response.content)

        url = "%s/bnf_code?q=lor&format=json" % self.api_prefix
        response = self.client.get(url, {}, follow=True, HTTP_ACCEPT="text/html")
        self.assertJson(response.content)

        url = "%s/bnf_code?q=lor" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertNotJson(response.content)

        url = "%s/bnf_code?q=lor" % self.api_prefix
        response = self.client.get(url, {}, follow=True, HTTP_ACCEPT="application/json")
        self.assertNotJson(response.content)

    def test_api_view_bnf_chemical(self):
        url = "%s/bnf_code?q=lor&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 5)
        self.assertEqual(content[0]["id"], "0202010D0")
        self.assertEqual(content[0]["name"], "Chlorothiazide")
        self.assertEqual(content[0]["type"], "chemical")
        self.assertEqual(content[3]["id"], "0202010D0AA")
        self.assertEqual(content[3]["name"], "Chloroth")
        self.assertEqual(content[3]["type"], "product")

        url = "%s/bnf_code?q=0202010D0BD&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["id"], "0202010D0BD")
        self.assertEqual(content[0]["name"], "Chlotride")
        self.assertEqual(content[0]["is_generic"], False)

        url = "%s/bnf_code?q=0202010D0bd&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["id"], "0202010D0BD")
        self.assertEqual(content[0]["name"], "Chlotride")
        self.assertEqual(content[0]["is_generic"], False)

    def test_inactive_chemical(self):
        url = "%s/bnf_code?q=0204ZZZZZ&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 0)

    def test_api_view_bnf_section(self):
        url = "%s/bnf_code?q=diuretics&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]["id"], "2.2")
        self.assertEqual(content[0]["name"], "Diuretics")
        self.assertEqual(content[0]["type"], "BNF section")
        self.assertEqual(content[1]["id"], "2.2.1")
        self.assertEqual(content[1]["name"], "Thiazides And Related Diuretics")
        self.assertEqual(content[1]["type"], "BNF paragraph")

        url = "%s/bnf_code?q=cardio&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["id"], "2")
        self.assertEqual(content[0]["name"], "Cardiovascular System")
        self.assertEqual(content[0]["type"], "BNF chapter")

        url = "%s/bnf_code?q=2.2&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["id"], "2.2")
        self.assertEqual(content[0]["name"], "Diuretics")
        self.assertEqual(content[0]["type"], "BNF section")

        url = "%s/bnf_code?q=0202&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["id"], "2.2")
        self.assertEqual(content[0]["name"], "Diuretics")
        self.assertEqual(content[0]["type"], "BNF section")

    def test_inactive_section(self):
        url = "%s/bnf_code?q=5.99&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 0)

    def test_api_view_bnf_presentation(self):
        url = "%s/bnf_code?q=Bendroflume&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 3)
        self.assertEqual(content[0]["id"], "0202010B0")
        self.assertEqual(content[0]["name"], "Bendroflumethiazide")

        url = "%s/bnf_code?q=0202010F0AAAAAA&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["id"], "0202010F0AAAAAA")
        self.assertEqual(content[0]["name"], "Chlortalidone_Tab 50mg")
        self.assertEqual(content[0]["type"], "product format")

        url = "%s/bnf_code?q=0202010F0AAA&exact=true&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 0)

    def test_inactive_presentation(self):
        url = "%s/bnf_code?q=non-current+product&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 0)

    def test_api_view_bnf_presentation_replacements(self):
        url = "%s/bnf_code?q=Labetalol+50&format=json" % self.api_prefix
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(len(content), 1)
