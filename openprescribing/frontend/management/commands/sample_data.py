"""A command to generate or load a subset of data from the live
database.

The `load` operation truncates all existing data.

"""

import json
import os
import tempfile

from django.apps import apps
from django.core.management import BaseCommand
from django.db import connection

# Tables for which we should copy all the data
copy_all = [
    "django_migrations",
    "auth_user",
    "frontend_chemical",
    "frontend_importlog",
    "frontend_measure",
    "frontend_measureglobal",
    "frontend_ncsoconcession",
    "frontend_orgbookmark",
    "frontend_pct",
    "frontend_practice",
    "frontend_practiceisdispensing",
    "frontend_presentation",
    "frontend_product",
    "frontend_profile",
    "frontend_qofprevalence",
    "frontend_regionalteam",
    "frontend_searchbookmark",
    "frontend_section",
    "frontend_stp",
    "frontend_tariffprice",
    "pipeline_tasklog",
    "spatial_ref_sys",
]

for m in apps.get_app_config("dmd").get_models():
    copy_all.append(m._meta.db_table)

# tables with WHERE clauses
copy_sample = {
    "frontend_measurevalue": "pct_id = '{}'",
    "frontend_prescription": "pct_id = '{}'",
    "frontend_practicestatistics": "pct_id = '{}'",
}

tables_to_sample = ["frontend_prescription"]


def dump_create_table(table, dest_dir):
    """
    Save an array of column names in the order they'll be dumped.

    This allows us to recreate them on loading.
    """
    dest = os.path.join(dest_dir, table + ".json")
    with connection.cursor() as cursor:
        sql = (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = '{}'".format(table)
        )
        cursor.execute(sql)
        fields = cursor.fetchall()
        with open(dest, "wb") as f:
            json.dump([x[0] for x in fields], f)


def quote_cols(cols):
    """Quote SQL column names (because dm+d uses the reserved word `desc`)"""
    return ['"{}"'.format(item) for item in cols]


class Command(BaseCommand):
    def dump(self, path, ccg):
        with connection.cursor() as cursor:
            for table in copy_all:
                with open(os.path.join(path, table), "wb") as f:
                    sql = r"copy (SELECT * FROM {}) TO STDOUT WITH NULL '\N'"
                    sql = sql.format(table)
                    dump_create_table(table, path)
                    cursor.copy_expert(sql, f)
            for table, where in copy_sample.items():
                where = where.format(ccg)
                with open(os.path.join(path, table), "wb") as f:
                    if table in tables_to_sample:
                        sample = "TABLESAMPLE SYSTEM (1)"
                    else:
                        sample = ""
                    sql = (
                        r"copy (SELECT * FROM {} {} WHERE {}) "
                        r"TO STDOUT WITH NULL '\N'"
                    )
                    sql = sql.format(table, sample, where)
                    dump_create_table(table, path)
                    cursor.copy_expert(sql, f)

    def load(self, path):
        with connection.cursor() as cursor:
            # Create DMD tables
            view_sql = os.path.join("dmd", "dmd_structure.sql")
            with open(view_sql, "rb") as f:
                cursor.execute(f.read())
            # Now fill other (existing) tables
            for table in copy_all:
                with open(os.path.join(path, table), "rb") as f:
                    cursor.execute("TRUNCATE TABLE {} CASCADE".format(table))
                    with open(os.path.join(path, table + ".json"), "rb") as f2:
                        cols = json.load(f2)
                    cursor.copy_from(f, table, null=r"\N", columns=quote_cols(cols))
            for table, where in copy_sample.items():
                with open(os.path.join(path, table), "rb") as f:
                    cursor.execute("TRUNCATE TABLE {} CASCADE".format(table))
                    with open(os.path.join(path, table + ".json"), "rb") as f2:
                        cols = json.load(f2)
                    cursor.copy_from(f, table, null=r"\N", columns=quote_cols(cols))

    def add_arguments(self, parser):
        parser.add_argument("operation", nargs=1, choices=["load", "dump"])
        parser.add_argument(
            "--dir",
            help="directory containing previously dumped files",
            default=tempfile.gettempdir(),
        )
        parser.add_argument("--ccg", help="CCG to sample data for", default="09X")

    def handle(self, *args, **options):
        if "load" in options["operation"]:
            self.load(options["dir"])
        else:
            self.dump(options["dir"], options["ccg"])
