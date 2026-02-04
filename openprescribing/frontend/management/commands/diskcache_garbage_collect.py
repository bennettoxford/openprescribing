import textwrap

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = textwrap.dedent("""
        Deletes oldest values from the DiskCache instance until it is within
        its specified maximum size. See the CACHE section of the settings file
        for more detail.
        """)

    def handle(self, *args, **options):
        while True:
            deleted = cache.cull()
            if deleted <= 0:
                break
