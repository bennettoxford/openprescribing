"""Reset frontend_measurevalue_id_seq.

This sequence is used to generate incrementing row IDs for the frontend_measurevalue
table.  The ID column is an 4-byte integer, with maximum value 2147483647 (about 2bn).

As part of each monthly import of prescribing data, we recalculate all measure values,
except for those belonging to preview measures.

We do this by deleting existing measure values and then creating new ones.  For each
measure, there is one measure value for each organisation for each of 61 months.  This
means that there are about 600k measure values for each measure.

Each time a measure value is created, frontend_measurevalue_id_seq is incremented, and
after a few years of monthly imports it exceeds 2147483647, which triggers a
NumericValueOutOfRange exception.

Because preview measure values are not deleted as part of the monthly import, we need to
delete them here, otherwise we risk reusing row IDs.  It is easy to recreate preview
measure values, but before running this command, check with the clinical informaticians
that this will not cause any surprises.

See https://github.com/bennettoxford/openprescribing/issues/2847 for background.
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = __doc__

    def handle(self, **kwargs):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM frontend_measurevalue WHERE measure_id LIKE 'preview_%'"
                )
                cursor.execute("ALTER SEQUENCE frontend_measurevalue_id_seq RESTART")
