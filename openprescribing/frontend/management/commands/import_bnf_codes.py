import csv

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from frontend.models import Chemical, Presentation, Product, Section


class Command(BaseCommand):
    args = ""
    help = "Imports BNF chapter, section and paragraph codes."

    def add_arguments(self, parser):
        parser.add_argument("--filename")

    def handle(self, *args, **options):
        """
        Import BNF numbered chapters, sections and paragraphs.
        """
        if "filename" not in options:
            raise CommandError("Please supply a filename")

        reader = csv.DictReader(open(options["filename"]))

        sections = {}
        with transaction.atomic():
            for row in reader:
                # Add to sections list.
                c_id = row["BNF_CHAPTER_CODE"]
                if c_id not in sections:
                    sections[c_id] = {"id": c_id, "name": row["BNF_CHAPTER"]}
                s_id = row["BNF_SECTION_CODE"]
                if s_id not in sections:
                    sections[s_id] = {"id": s_id, "name": row["BNF_SECTION"]}
                p_id = row["BNF_PARAGRAPH_CODE"]
                if p_id not in sections:
                    sections[p_id] = {"id": p_id, "name": row["BNF_PARAGRAPH"]}
                sp_id = row["BNF_SUBPARAGRAPH_CODE"]
                if sp_id not in sections:
                    sections[sp_id] = {"id": sp_id, "name": row["BNF_SUBPARAGRAPH"]}

                chemical_name = row["BNF_CHEMICAL_SUBSTANCE"].strip()
                chemical_code = row["BNF_CHEMICAL_SUBSTANCE_CODE"].strip()
                if not chemical_name.startswith("DUMMY "):
                    try:
                        p = Chemical.objects.get(bnf_code=chemical_code)
                        p.chem_name = chemical_name
                        p.save()
                    except ObjectDoesNotExist:
                        p = Chemical.objects.create(
                            bnf_code=chemical_code, chem_name=chemical_name
                        )

                product_name = row["BNF_PRODUCT"].strip()
                product_code = row["BNF_PRODUCT_CODE"].strip()
                if not product_name.startswith("DUMMY "):
                    try:
                        p = Product.objects.get(bnf_code=product_code)
                        p.name = product_name
                        p.save()
                    except ObjectDoesNotExist:
                        p = Product.objects.create(
                            bnf_code=product_code, name=product_name
                        )

                pres_name = row["BNF_PRESENTATION"].strip()
                pres_code = row["BNF_PRESENTATION_CODE"].strip()
                if not pres_name.startswith("DUMMY "):
                    try:
                        p = Presentation.objects.get(bnf_code=pres_code)
                        p.name = pres_name
                        p.save()
                    except ObjectDoesNotExist:
                        p = Presentation.objects.create(
                            bnf_code=pres_code, name=pres_name
                        )

            for s in sections:
                id = sections[s]["id"].strip()
                name = sections[s]["name"]
                bnf_chapter = id[:2]
                bnf_section = id[2:4]
                bnf_para = id[4:6]
                bnf_subpara = id[6:7]
                bnf_section = self.convert_bnf_id_section(bnf_section)
                bnf_para = self.convert_bnf_id_section(bnf_para)
                bnf_subpara = self.convert_bnf_id_section(bnf_subpara)
                if self.is_valid_section(id, name, bnf_para):
                    try:
                        sec = Section.objects.get(bnf_id=id)
                        sec.name = name
                        sec.bnf_chapter = bnf_chapter
                        sec.bnf_section = bnf_section
                        sec.bnf_para = bnf_para
                        sec.bnf_subpara = bnf_subpara
                        sec.save()
                    except ObjectDoesNotExist:
                        sec = Section.objects.create(
                            bnf_id=id,
                            name=name,
                            bnf_chapter=bnf_chapter,
                            bnf_section=bnf_section,
                            bnf_para=bnf_para,
                            bnf_subpara=bnf_subpara,
                        )

    def convert_bnf_id_section(self, id):
        if id == "":
            return None
        else:
            return int(id)

    def is_valid_section(self, id, name, bnf_para):
        """
        Check for duplicate or dummy sections.
        """
        if name.lower().startswith("dummy") or id[-2:] == "00" or bnf_para == "0":
            return False
        return True
