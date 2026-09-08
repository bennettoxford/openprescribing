"""
Sets is_current to True on any BNF class with prescribing.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from frontend.models import Chemical, Presentation, Product, Section
from frontend.utils.bnf_hierarchy import get_all_bnf_codes


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        all_bnf_codes = get_all_bnf_codes()
        all_bnf_prefixes = {
            bnf_code[:i]
            for bnf_code in all_bnf_codes
            for i in range(1, len(bnf_code) + 1)
        }

        classes = [
            (Section, "bnf_id"),
            (Chemical, "bnf_code"),
            (Product, "bnf_code"),
            (Presentation, "bnf_code"),
        ]
        with transaction.atomic():
            for model, field_name in classes:
                for obj in model.objects.filter():
                    prefix = getattr(obj, field_name)
                    obj.is_current = prefix in all_bnf_prefixes
                    obj.save(update_fields=["is_current"])
