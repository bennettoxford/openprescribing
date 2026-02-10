import json

from django.test import TestCase
from dmd.models import DtPaymentCategory
from frontend.models import Presentation, TariffPrice
from frontend.tests.data_factory import DataFactory
from matrixstore.tests.contextmanagers import (
    patched_global_matrixstore_from_data_factory,
)
from matrixstore.tests.data_factory import DataFactory as MSDataFactory
from matrixstore.tests.decorators import (
    copy_fixtures_to_matrixstore,
    matrixstore_from_postgres,
    patch_global_matrixstore,
)


@copy_fixtures_to_matrixstore
class TestDMDObjView(TestCase):
    fixtures = ["dmd-objs", "dmd-import-log", "minimal-prescribing"]

    def test_vtm(self):
        rsp = self.client.get("/dmd/vtm/68088000/")
        self.assertContains(rsp, "<td>Name</td><td>Acebutolol</td>", html=True)
        self.assertNotContains(rsp, "This VTM cannot be matched")

    def test_vmp(self):
        rsp = self.client.get("/dmd/vmp/318412000/")
        self.assertContains(
            rsp, "<td>Name</td><td>Acebutolol 100mg capsules</td>", html=True
        )
        self.assertNotContains(rsp, "Analyse prescribing")
        self.assertNotContains(rsp, "See prices paid")

        factory = DataFactory()
        practice = factory.create_practice()
        presentation = Presentation.objects.create(
            bnf_code="0204000C0AAAAAA", name="Acebut HCl_Cap 100mg"
        )
        factory.create_prescribing_for_practice(practice, [presentation])
        stop_patching = patch_global_matrixstore(matrixstore_from_postgres())
        try:
            rsp = self.client.get("/dmd/vmp/318412000/")
            self.assertContains(rsp, "Analyse prescribing")
            self.assertContains(rsp, "See prices paid")
        finally:
            stop_patching()

    def test_amp(self):
        rsp = self.client.get("/dmd/amp/632811000001105/")
        self.assertContains(
            rsp,
            "<td>Description</td><td>Sectral 100mg capsules (Sanofi)</td>",
            html=True,
        )

    def test_vmpp(self):
        rsp = self.client.get("/dmd/vmpp/1098611000001105/")
        self.assertContains(
            rsp,
            "<td>Description</td><td>Acebutolol 100mg capsules 84 capsule</td>",
            html=True,
        )
        self.assertNotContains(rsp, "View Drug Tariff history")

        TariffPrice.objects.create(
            date="2019-07-01",
            vmpp_id=1098611000001105,
            tariff_category=DtPaymentCategory.objects.create(cd=1, descr="Cat A"),
            price_pence=100,
        )

        rsp = self.client.get("/dmd/vmpp/1098611000001105/")
        self.assertContains(rsp, "View Drug Tariff history")

    def test_ampp(self):
        rsp = self.client.get("/dmd/ampp/9703311000001100/")
        self.assertContains(
            rsp,
            """
            <td>Description</td>
            <td>Acebutolol 100mg capsules (A A H Pharmaceuticals Ltd) 84 capsule</td>
            """,
            html=True,
        )
        self.assertContains(rsp, "This AMPP cannot be matched")


@copy_fixtures_to_matrixstore
class TestSearchView(TestCase):
    fixtures = ["dmd-objs", "dmd-import-log", "minimal-prescribing"]

    def test_search_returning_no_results(self):
        rsp = self._get("bananas")

        # We expect to see "No results found".
        self.assertContains(rsp, "No results found.")

    def test_search_by_returning_one_result(self):
        rsp = self._get("acebutolol", obj_types=["vmp"])

        # We expect to be redirected to the page for the one matching object.
        self.assertRedirects(rsp, "/dmd/vmp/318412000/")

    def test_search_returning_many_results(self):
        rsp = self._get("acebutolol")

        # We expect to see lists of the matching objects.
        self.assertContains(rsp, "Virtual Medicinal Products (1)")
        self.assertContains(rsp, "Acebutolol 100mg capsules")
        self.assertContains(rsp, "Virtual Medicinal Product Packs (1)")
        self.assertContains(rsp, "Acebutolol 100mg capsules 84 capsule")

    def test_search_for_all_obj_types_shows_limited_results(self):
        rsp = self._get(
            "acebutolol",
            include=["invalid", "unavailable", "no_bnf_code"],
            max_results_per_obj_type=5,
        )

        # We expect to see 5 out of 6 of the AMPPs, and a link to show all of them.
        self.assertContains(rsp, "Actual Medicinal Product Packs (6)")
        for supplier in [
            "A A H Pharmaceuticals Ltd",
            "Alliance Healthcare (Distribution) Ltd",
            "Kent Pharmaceuticals Ltd",
            "Phoenix Healthcare Distribution Ltd",
            "Sigma Pharmaceuticals Plc",
        ]:
            self.assertContains(rsp, supplier)
        self.assertNotContains(rsp, "Waymade Healthcare Plc")
        self.assertContains(rsp, "Show all Actual Medicinal Product Packs")

        # We don't expect to see a link to show all VMPPs, since there aren't
        # more than 5.
        self.assertNotContains(rsp, "Show all Virtual Medicinal Product Packs")

    def test_search_for_one_obj_type_shows_all_results(self):
        rsp = self._get(
            "acebutolol",
            obj_types=["ampp"],
            include=["invalid", "unavailable", "no_bnf_code"],
            max_results_per_obj_type=5,
        )

        # We expect to see all 6 AMPPs, and no link to show all of them.
        for supplier in [
            "A A H Pharmaceuticals Ltd",
            "Alliance Healthcare (Distribution) Ltd",
            "Kent Pharmaceuticals Ltd",
            "Phoenix Healthcare Distribution Ltd",
            "Sigma Pharmaceuticals Plc",
            "Waymade Healthcare Plc",
        ]:
            self.assertContains(rsp, supplier)

        self.assertNotContains(rsp, "Show all Actual Medicinal Product Packs")

    def test_search_by_snomed_code_returning_one_result(self):
        rsp = self._get("318412000")

        # We expect to be redirected to the page for the one matching object.
        self.assertRedirects(rsp, "/dmd/vmp/318412000/")

    def test_search_by_snomed_code_returning_no_results(self):
        rsp = self._get("12345678")

        # We expect to see "No results found".
        self.assertContains(rsp, "No results found.")

    def test_with_invalid_form(self):
        rsp = self._get("aa")

        # We expect to see an error message because the search string was too short.
        self.assertContains(rsp, "Ensure this value has at least")

        # We don't expect to see that a search has happened.
        self.assertNotContains(rsp, "No results found.")

    def test_with_no_obj_types(self):
        rsp = self.client.get("/dmd/", {"q": "acebutolol"})

        # We expect to see lists of the matching objects.
        self.assertContains(rsp, "Virtual Medicinal Products (1)")
        self.assertContains(rsp, "Acebutolol 100mg capsules")
        self.assertContains(rsp, "Virtual Medicinal Product Packs (1)")
        self.assertContains(rsp, "Acebutolol 100mg capsules 84 capsule")

    def _get(self, q, **extra_params):
        params = {
            "q": q,
            "obj_types": ["vtm", "vmp", "amp", "vmpp", "ampp"],
            "include": [],
        }
        params.update(extra_params)
        return self.client.get("/dmd/", params)


class TestAdvancedSearchView(TestCase):
    # These tests just kick the tyres.

    fixtures = ["dmd-objs", "dmd-import-log"]

    def test_search_returning_no_results(self):
        search = ["nm", "contains", "banana"]
        rsp = self._get(search)
        self.assertContains(rsp, "Found 0 Actual Medicinal Products")

    def test_simple_search(self):
        search = ["nm", "contains", "acebutolol"]
        rsp = self._get(search, ["unavailable"])
        self.assertContains(rsp, "Found 2 Actual Medicinal Products")
        self.assertContains(rsp, "Analyse prescribing")

    def test_compound_search(self):
        search = [
            "and",
            [
                ["bnf_code", "begins_with", "0204000C0"],
                ["bnf_code", "not_begins_with", "0204000C0BB"],
                ["supp", "equal", 2073701000001100],
            ],
        ]
        rsp = self._get(search, ["unavailable"])
        self.assertContains(rsp, "Found 1 Actual Medicinal Product")
        self.assertContains(rsp, "Analyse prescribing")

    def test_csv(self):
        search = ["nm", "contains", "acebutolol"]
        rsp = self._get(search, ["unavailable"], format="csv")
        self.assertContains(rsp, "10347111000001100,Acebutolol 100mg capsules")

    def _get(self, search, include=None, format=None):
        params = {"search": json.dumps(search), "include": include or []}
        if format:
            params["format"] = "csv"

        bnf_codes = [
            "0204000C0AAAAAA",  # Acebut HCl_Cap 100mg
            "0204000C0BBAAAA",  # Sectral_Cap 100mg
            "0204000D0AAAAAA",  # Practolol_Inj 2mg/ml 5ml Amp
        ]

        factory = MSDataFactory()
        factory.create_prescribing_for_bnf_codes(bnf_codes)

        with patched_global_matrixstore_from_data_factory(factory):
            return self.client.get("/dmd/advanced-search/amp/", params)
