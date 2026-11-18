import csv

from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from frontend.models import Practice


class Command(BaseCommand):
    args = ""
    help = "Add eastings and northings to practices, "
    help += " from the HSCIC gridall.csv file. "

    def add_arguments(self, parser):
        parser.add_argument("--filename")

    def handle(self, *args, **options):
        """
        Import practice eastings and northings, from HSCIC data.
        """
        if not options["filename"]:
            print("Please supply a filename")
        else:
            self.IS_VERBOSE = False
            if options["verbosity"] > 1:
                self.IS_VERBOSE = True

            with open(options["filename"], newline="") as csvfile:
                gridall = csv.reader(csvfile)
                postcodes = {}
                for row in gridall:
                    postcode = row[1].replace(" ", "").strip()
                    postcodes[postcode] = [row[36], row[37]]

            wgs84 = SpatialReference(4326)
            bng = SpatialReference(27700)
            trans = CoordTransform(bng, wgs84)

            practices = Practice.objects.filter(postcode__isnull=False).reverse()
            for practice in practices:
                practice.location = None
                postcode = practice.postcode.replace(" ", "").strip()
                if postcode in postcodes:
                    lng = postcodes[postcode][0]
                    lat = postcodes[postcode][1]
                    if lng and lat:
                        pnt = Point(int(lng), int(lat), srid=27700)
                        pnt.transform(trans)
                        practice.location = pnt
                practice.save()
