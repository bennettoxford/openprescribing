"""Import monthly patient list size data for use in
PracticeStatistics.

Note that historic data was imported based on data contained in a
one-off FOI request; and subsequently in quarterly files, until April
2017. See this file's revision history for related import functions.

"""

import datetime
import re

import pandas as pd
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from frontend.models import ImportLog, Practice, PracticeStatistics


class Command(BaseCommand):
    args = ""

    def add_arguments(self, parser):
        parser.add_argument("--filename", required=True)

    def _date_from_filename(self, filename):
        match = re.match(r".*/([0-9]{4}_[0-9]{2})/", filename)
        year, month = match.groups()[0].split("_")
        return datetime.date(int(year), int(month), 1)

    def handle(self, *args, **options):
        filename = options["filename"]
        month = self._date_from_filename(filename)
        self.process_practices(filename, month)
        ImportLog.objects.create(
            current_at=month, filename=filename, category="patient_list_size"
        )

    def process_practices(self, filename, month):
        df = pd.read_csv(filename)
        df = df[df.ORG_TYPE == "GP"]
        by_practice = df.groupby("ORG_CODE")
        genders = ["male", "female"]
        age_groups = {
            "0_4": ["0_4"],
            "5_14": ["5_9", "10_14"],
            "15_24": ["15_19", "20_24"],
            "25_34": ["25_29", "30_34"],
            "35_44": ["35_39", "40_44"],
            "45_54": ["45_49", "50_54"],
            "55_64": ["55_59", "60_64"],
            "65_74": ["65_69", "70_74"],
            "75_plus": ["75_79", "80_84", "85_89", "90_94", "95+"],
        }

        for code, group in by_practice:
            try:
                practice = Practice.objects.get(code=code)
            except Practice.DoesNotExist:
                return
            data = {}
            for gender in genders:
                for age_group, quintiles in age_groups.items():
                    val = 0
                    for quintile in quintiles:
                        val += int(
                            group[
                                (group.SEX == gender.upper())
                                & (group.AGE_GROUP_5 == quintile)
                            ].NUMBER_OF_PATIENTS.iloc[0]
                        )
                        data["%s_%s" % (gender, age_group)] = val
            try:
                prac_list = PracticeStatistics.objects.get(practice=code, date=month)
                for k, v in data:
                    setattr(prac_list, k, v)
                prac_list.pct = practice.ccg  # Reset CCG to current membership
                prac_list.save()
            except ObjectDoesNotExist:
                data["practice"] = practice
                data["pct"] = practice.ccg
                data["date"] = month
                prac_list = PracticeStatistics.objects.create(**data)
