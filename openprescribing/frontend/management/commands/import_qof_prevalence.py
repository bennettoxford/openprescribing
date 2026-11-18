import csv
import sys

from django.core.management.base import BaseCommand
from frontend.models import PCT, Practice, QOFPrevalence


class Command(BaseCommand):
    args = ""
    help = "Imports prevalence data by CCG and practice."

    def add_arguments(self, parser):
        parser.add_argument("--by_ccg")
        parser.add_argument("--by_practice")
        parser.add_argument("--start_year")

    def handle(self, *args, **options):
        if "by_ccg" not in options:
            print("Please supply a filename for QOF prevalence by CCG")
            sys.exit
        if "by_ccg" not in options:
            print("Please supply a filename for QOF prevalence by practice")
            sys.exit
        if "start_year" not in options:
            print("Please supply an option for year, e.g. 2013")
            sys.exit

        start_year = options["start_year"]
        ccg_file = options["by_ccg"]
        practice_file = options["by_practice"]

        with open(ccg_file, newline="") as csvfile:
            ccg_prevalence = csv.DictReader(csvfile)
            for row in ccg_prevalence:
                ccg_code = row["ccgcode"]
                ccg = PCT.objects.get(code=ccg_code)
                q, created = QOFPrevalence.objects.get_or_create(
                    pct=ccg,
                    start_year=start_year,
                    indicator_group=row["indicator_group"],
                    register_description=row["Register_description"],
                    disease_register_size=row["disease_register_size"],
                )

        with open(practice_file, newline="") as csvfile:
            practice_prevalence = csv.DictReader(csvfile)
            for row in practice_prevalence:
                practicecode = row["practicecode"]
                practice = Practice.objects.get(code=practicecode)
                q, created = QOFPrevalence.objects.get_or_create(
                    practice=practice,
                    start_year=start_year,
                    indicator_group=row["indicator_group"],
                    register_description=row["Register_description"],
                    disease_register_size=row["disease_register_size"],
                )
