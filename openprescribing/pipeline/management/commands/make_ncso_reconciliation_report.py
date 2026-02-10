# coding=utf8


import re
from collections import Counter

from django.core.management import BaseCommand
from frontend.models import NCSOConcession
from pipeline.management.commands.fetch_and_import_ncso_concessions import (
    regularise_ncso_name,
)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        rows = Counter()

        for c in NCSOConcession.objects.select_related("vmpp"):
            ncso_name_raw = "{} {}".format(c.drug, c.pack_size)
            ncso_name = regularise_ncso_name(ncso_name_raw)

            vpmm_name = re.sub(" */ *", "/", c.vmpp.nm.lower())

            if vpmm_name == ncso_name or vpmm_name.startswith(ncso_name + " "):
                continue

            key = (c.drug.replace("\xa0", ""), c.pack_size, c.vmpp.vppid, c.vmpp.nm)
            rows[key] += 1

        print("""
<html>
  <head>
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css" integrity="sha384-Gn5384xqQ1aoWXA+058RXPxPg6fy4IWvTNh0E263XmFcJlSAwiGgFAW/dAiS6JXm" crossorigin="anonymous">
  </head>
  <body>
    <table class="table">
      <tr>
        <th>NCSO name</th>
        <th>NCSO pack size</th>
        <th>VMPP name</th>
        <th>Count</th>
      </tr>""")

        for row, count in sorted(rows.items()):
            print("  <tr>")
            print("    <td>{}</td>".format(row[0]))
            print("    <td>{}</td>".format(row[1]))
            print(
                '    <td><a href="http://dmd.medicines.org.uk/DesktopDefault.aspx?VMPP={}">{}</a></td>'.format(
                    row[2], row[3]
                )
            )
            print("    <td>{}</td>".format(count))
            print("  </tr>")

        print("""
    </table>
  </body>
</html>""")
