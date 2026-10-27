import csv
import tempfile
from decimal import Decimal

from django.test import TestCase
from dmd.models import VMPP
from frontend.models import PCT
from gcutils.bigquery import Client, TableExporter, build_schema
from gcutils.storage import Client as StorageClient
from google.cloud.exceptions import NotFound


class BQClientTest(TestCase):
    fixtures = ["dmd-subset"]

    def setUp(self):
        client = Client("test")
        self.storage_prefix = "test_bq_client/{}-".format(client.dataset_id)
        client.create_dataset()

        archive_client = Client("archive")
        archive_client.create_dataset()

    def tearDown(self):
        client = Client("test")
        client.delete_dataset()

        client = StorageClient()
        bucket = client.bucket()
        for blob in bucket.list_blobs(prefix=self.storage_prefix):
            blob.delete()

        archive_client = Client("archive")
        archive_client.delete_dataset()

    def test_the_lot(self):
        client = Client("test")
        archive_client = Client("archive")

        orig_schema = build_schema(("a", "STRING"), ("b", "INTEGER"))

        schema = build_schema(("a", "INTEGER"), ("b", "STRING"))

        headers = ["a", "b"]
        rows = [(1, "apple"), (2, "banana"), (3, "coconut")]

        t1 = client.get_or_create_table("t1", orig_schema)
        t1_qname = t1.qualified_name

        # Test Table.insert_rows_from_csv
        t1.insert_rows_from_csv("gcutils/tests/test_table.csv", schema)

        self.assertEqual(sorted(t1.get_rows()), rows)

        # Test Table.insert_rows_from_query
        t2 = client.get_table("t2")

        sql = "SELECT * FROM {} WHERE a > 1".format(t1_qname)
        t2.insert_rows_from_query(sql)

        self.assertEqual(sorted(t2.get_rows()), rows[1:])

        # Test Client.query
        sql = "SELECT * FROM {} WHERE a > 2".format(t1_qname)
        results = client.query(sql)

        self.assertEqual(sorted(results.rows), rows[2:])

        # Test Client.query_into_dataframe
        sql = "SELECT * FROM {} WHERE a > 2".format(t1_qname)
        df = client.query_into_dataframe(sql)

        self.assertEqual(df.values.tolist(), [list(rows[2])])

        # Test TableExporter.export_to_storage and
        # TableExporter.download_from_storage_and_unzip
        t1_exporter = TableExporter(t1, self.storage_prefix + "test_table-")
        t1_exporter.export_to_storage()

        with tempfile.NamedTemporaryFile(mode="r+") as f:
            t1_exporter.download_from_storage_and_unzip(f)
            f.seek(0)
            reader = csv.reader(f)
            data = [next(reader)] + sorted(reader)

        self.assertEqual(data, [list(map(str, row)) for row in [headers] + rows])

        # Test Table.insert_rows_from_storage
        storage_path = self.storage_prefix + "test_table.csv"
        self.upload_to_storage("gcutils/tests/test_table.csv", storage_path)

        t2.insert_rows_from_storage(storage_path)

        self.assertEqual(sorted(t2.get_rows()), rows)

        # Test Client.create_storage_backed_table
        storage_path = self.storage_prefix + "test_table_headers.csv"
        self.upload_to_storage("gcutils/tests/test_table_headers.csv", storage_path)

        schema = build_schema(("a", "INTEGER"), ("b", "STRING"))

        t3 = client.create_storage_backed_table("t3", schema, storage_path)

        results = client.query("SELECT * FROM {}".format(t3.qualified_name))

        self.assertEqual(sorted(results.rows), rows)

        self.upload_to_storage("gcutils/tests/test_table_headers_2.csv", storage_path)

        results = client.query("SELECT * FROM {}".format(t3.qualified_name))

        self.assertEqual(sorted(results.rows), rows + [(4, "damson")])

        # Test Client.create_table_with_view
        sql = "SELECT * FROM {{project}}.{} WHERE a > 1".format(t1_qname)

        t4 = client.create_table_with_view("t4", sql, False)

        results = client.query("SELECT * FROM {}".format(t4.qualified_name))

        self.assertEqual(sorted(results.rows), rows[1:])

        # Test Table.copy_to_new_dataset
        t1.copy_to_new_dataset("archive")
        t1_archived = archive_client.get_table("t1")
        self.assertEqual(sorted(t1_archived.get_rows()), rows)
        self.assertEqual(sorted(t1.get_rows()), rows)

        # Test Table.move_to_new_dataset
        t2.move_to_new_dataset("archive")
        t2_archived = archive_client.get_table("t2")
        self.assertEqual(sorted(t2_archived.get_rows()), rows)
        with self.assertRaises(NotFound):
            list(t2.get_rows())

        # Test Client.insert_rows_from_pg
        PCT.objects.create(code="ABC", name="CCG 1")
        PCT.objects.create(code="XYZ", name="CCG 2")

        def transformer(row):
            return [ord(row[0][0]), row[1]]

        t1.insert_rows_from_pg(
            PCT,
            build_schema(("code", "INTEGER"), ("name", "STRING")),
            transformer=transformer,
        )

        self.assertEqual(sorted(t1.get_rows()), [(65, "CCG 1"), (88, "CCG 2")])

        # Test Table.delete_all_rows
        t1.delete_all_rows()

        self.assertEqual(list(t1.get_rows()), [])

        # Test Table.insert_rows_from_csv without schema
        t5 = client.get_table("t5")
        t5.insert_rows_from_csv("gcutils/tests/test_table.csv")

        self.assertEqual(sorted(t5.get_rows()), rows)

    def upload_to_storage(self, local_path, storage_path):
        client = StorageClient()
        bucket = client.bucket()
        blob = bucket.blob(storage_path)
        with open(local_path, "rb") as f:
            blob.upload_from_file(f)

    def test_upload_model(self):
        client = Client("dmd")
        client.upload_model(VMPP)
        table = client.get_table("vmpp")
        rows = list(table.get_rows_as_dicts())
        self.assertEqual(len(rows), 4)

        for row in rows:
            if row["id"] != 1079211000001106:
                continue

            for k, v in {
                "invalid": False,
                "nm": "Chlortalidone 50mg tablets 28 tablet",
                "vmp": 317935006,
                "qtyval": Decimal("28.00"),
                "qty_uom": 428673006,
                "combpack": None,
                "bnf_code": "0202010F0AAAAAA",
            }.items():
                self.assertEqual(row[k], v)
