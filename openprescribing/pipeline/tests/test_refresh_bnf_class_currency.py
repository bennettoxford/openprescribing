from django.core.management import call_command
from django.test import TestCase
from frontend.models import Chemical, Presentation, Product, Section
from matrixstore.tests.contextmanagers import (
    patched_global_matrixstore_from_data_factory,
)
from matrixstore.tests.data_factory import DataFactory


class TestCommand(TestCase):
    def test_refresh_bnf_class_currency(self):
        Section.objects.create(bnf_id="01", bnf_chapter=1, is_current=True)
        Section.objects.create(bnf_id="02", bnf_chapter=2, is_current=True)
        Section.objects.create(bnf_id="03", bnf_chapter=3, is_current=False)
        Section.objects.create(bnf_id="04", bnf_chapter=4, is_current=False)

        Chemical.objects.create(bnf_code="010101001", is_current=True)
        Chemical.objects.create(bnf_code="020101001", is_current=True)
        Chemical.objects.create(bnf_code="030101001", is_current=False)
        Chemical.objects.create(bnf_code="040101001", is_current=False)

        Product.objects.create(bnf_code="010101001AA", is_current=True)
        Product.objects.create(bnf_code="020101001AA", is_current=True)
        Product.objects.create(bnf_code="030101001AA", is_current=False)
        Product.objects.create(bnf_code="040101001AA", is_current=False)

        Presentation.objects.create(bnf_code="010101001AAAAAA", is_current=True)
        Presentation.objects.create(bnf_code="020101001AAAAAA", is_current=True)
        Presentation.objects.create(bnf_code="030101001AAAAAA", is_current=False)
        Presentation.objects.create(bnf_code="040101001AAAAAA", is_current=False)

        factory = DataFactory()
        factory.create_prescribing_for_bnf_codes(["010101001AAAAAA", "030101001AAAAAA"])

        with patched_global_matrixstore_from_data_factory(factory):
            call_command("refresh_bnf_class_currency")

        self.assertTrue(Section.objects.get(bnf_id="01").is_current)
        self.assertTrue(Section.objects.get(bnf_id="02").is_current)
        self.assertTrue(Section.objects.get(bnf_id="03").is_current)
        self.assertFalse(Section.objects.get(bnf_id="04").is_current)

        self.assertTrue(Chemical.objects.get(bnf_code="010101001").is_current)
        self.assertTrue(Chemical.objects.get(bnf_code="020101001").is_current)
        self.assertTrue(Chemical.objects.get(bnf_code="030101001").is_current)
        self.assertFalse(Chemical.objects.get(bnf_code="040101001").is_current)

        self.assertTrue(Product.objects.get(bnf_code="010101001AA").is_current)
        self.assertTrue(Product.objects.get(bnf_code="020101001AA").is_current)
        self.assertTrue(Product.objects.get(bnf_code="030101001AA").is_current)
        self.assertFalse(Product.objects.get(bnf_code="040101001AA").is_current)

        self.assertTrue(Presentation.objects.get(bnf_code="010101001AAAAAA").is_current)
        self.assertTrue(Presentation.objects.get(bnf_code="020101001AAAAAA").is_current)
        self.assertTrue(Presentation.objects.get(bnf_code="030101001AAAAAA").is_current)
        self.assertFalse(Presentation.objects.get(bnf_code="040101001AAAAAA").is_current)
