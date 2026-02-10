import os
import unittest

from django.core.management import call_command
from django.test import TestCase
from frontend.models import Practice


def setUpModule():
    Practice.objects.create(
        code="N84014",
        name="AINSDALE VILLAGE SURGERY",
        address1="THE SURGERY",
        address2="2 LEAMINGTON RD AINSDALE",
        address3="SOUTHPORT",
        address4="MERSEYSIDE",
        postcode="PR8 3LB",
    )
    Practice.objects.create(
        code="G82650",
        name="MOCKETTS WOOD SURGERY",
        address1="THE MOCKETT'S WOOD SURG.",
        address2="HOPEVILLE AVE ST PETERSY",
        address3="BROADSTAIRS",
        address4="KENT",
        postcode="CT10 2TR",
    )


def tearDownModule():
    call_command("flush", verbosity=0, interactive=False)


class CommandsTestCase(TestCase):
    @unittest.skipIf(
        "TRAVIS" in os.environ and os.environ["TRAVIS"],
        "Skipping this test on Travis CI.",
    )
    def test_import_practice_geocoding(self):
        args = []
        opts = {"filename": "frontend/tests/fixtures/commands/gridall.csv"}
        call_command("geocode_practices", *args, **opts)

        practice = Practice.objects.get(code="N84014")
        loc = practice.location
        self.assertAlmostEqual(loc.x, -3.0366194249598926, places=4)
        self.assertAlmostEqual(loc.y, 53.601301070769146, places=4)

        practice = Practice.objects.get(code="G82650")
        self.assertEqual(practice.location, None)
