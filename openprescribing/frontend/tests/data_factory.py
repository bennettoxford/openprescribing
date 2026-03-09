import itertools
import random

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from dmd import models as dmd_models
from frontend.models import (
    PCN,
    PCT,
    STP,
    ImportLog,
    Measure,
    NCSOConcession,
    NCSOConcessionBookmark,
    OrgBookmark,
    Practice,
    Prescription,
    Presentation,
    RegionalTeam,
    TariffPrice,
)


class DataFactory(object):
    """
    This class provides methods to generate test fixtures programatically
    """

    def __init__(self, seed=1):
        self.random = random.Random()
        self.random.seed(seed)
        counter = itertools.count()
        self.next_id = lambda: next(counter)

    def create_months_array(self, start_date=None, num_months=1):
        if start_date is None:
            start_date = "2019-07-01"
        date = parse_date(start_date)
        return [
            (date + relativedelta(months=i)).strftime("%Y-%m-%d")
            for i in range(0, num_months)
        ]

    def create_practice(self, ccg=None, pcn=None, setting=-1):
        if ccg is None:
            ccg = self.create_ccg()
        index = self.next_id()
        return Practice.objects.create(
            name="Practice {}".format(index),
            code="ABC{:03}".format(index),
            ccg=ccg,
            pcn=pcn,
            setting=setting,
        )

    def create_ccg(self, stp=None, regional_team=None):
        index = self.next_id()
        return PCT.objects.create(
            name="CCG {}".format(index),
            code="A{:02}".format(index),
            org_type="CCG",
            stp=stp,
            regional_team=regional_team,
        )

    def create_pcn(self):
        index = self.next_id()
        return PCN.objects.create(
            name="PCN {}".format(index), code="E000{:02}".format(index)
        )

    def create_stp(self):
        index = self.next_id()
        return STP.objects.create(
            name="STP {}".format(index), code="E{:02}".format(index)
        )

    def create_regional_team(self):
        index = self.next_id()
        return RegionalTeam.objects.create(
            name="Regional Team {}".format(index), code="R{:02}".format(index)
        )

    def create_presentations(self, num_presentations, vmpp_per_presentation=1):
        presentations = []
        vmp_basis, _ = dmd_models.BasisOfName.objects.get_or_create(
            cd=1, descr="rINN - Recommended International Non-proprietary"
        )
        vmp_pres_stat, _ = dmd_models.VirtualProductPresStatus.objects.get_or_create(
            cd=1, descr="Valid as a prescribable product"
        )
        for i in range(num_presentations):
            presentation = Presentation.objects.create(
                bnf_code="0123456789ABCD{}".format(i),
                name="Foo Tablet {}".format(i),
                dmd_name="VMP Foo Tablet {}".format(i),
                quantity_means_pack=self.random.choice([True, False, None]),
            )
            vmp = dmd_models.VMP.objects.create(
                id=i,
                invalid=False,
                nm="VMP " + presentation.name,
                basis=vmp_basis,
                pres_stat=vmp_pres_stat,
                sug_f=False,
                glu_f=False,
                pres_f=False,
                cfc_f=False,
                bnf_code=presentation.bnf_code,
            )
            qtyval = self.random.randint(5, 25)
            for vppid in range(0, vmpp_per_presentation):
                vppid = i * 10 + vppid
                dmd_models.VMPP.objects.create(
                    id=vppid,
                    vmp=vmp,
                    invalid=False,
                    nm="VMPP %s (%s)" % (presentation.name, vppid),
                    qtyval=qtyval,
                    bnf_code=presentation.bnf_code,
                )
            presentations.append(presentation)
        return presentations

    def create_tariff_and_ncso_costings_for_presentations(
        self, presentations, months=None
    ):
        for presentation in presentations:
            for date in months:
                price_pence = self.random.randint(10, 100)
                for vmpp in dmd_models.VMPP.objects.filter(
                    bnf_code=presentation.bnf_code
                ):
                    tariff_price = TariffPrice.objects.create(
                        date=date,
                        vmpp=vmpp,
                        tariff_category=self.create_tariff_category(),
                        price_pence=price_pence,
                    )
                    if self.random.choice([True, False]):
                        NCSOConcession.objects.create(
                            vmpp=vmpp,
                            date=date,
                            drug="",
                            pack_size="",
                            price_pence=(
                                tariff_price.price_pence + self.random.randint(10, 100)
                            ),
                        )

    def create_tariff_category(self):
        categories = [
            (1, "Part VIIIA Category A"),
            (3, "Part VIIIA Category C"),
            (5, "Part IXa"),
            (6, "Part IXb"),
            (7, "Part IXc"),
            (8, "Part IXr"),
            (9, "Part X"),
            (10, "Parts IXb and IXc"),
            (11, "Part VIIIA Category M"),
            (12, "Part VIIIB"),
            (13, "Part VIIIC"),
            (14, "Part VIIID"),
        ]
        cd, descr = self.random.choice(categories)
        tariff_category, _ = dmd_models.DtPaymentCategory.objects.get_or_create(
            cd=cd, descr=descr
        )
        return tariff_category

    def create_prescribing_for_practice(
        self, practice, presentations=None, months=None
    ):
        if months is None:
            months = self.create_months_array()

        for date in months:
            self.create_import_log(date)
            for i, presentation in enumerate(presentations):
                Prescription.objects.create(
                    processing_date=date,
                    practice=practice,
                    pct_id=practice.ccg_id,
                    presentation_code=presentation.bnf_code,
                    quantity=self.random.randint(1, 1000),
                    total_items=0,
                    net_cost=self.random.randint(1, 1000),
                    actual_cost=0,
                )

    def create_import_log(self, date):
        ImportLog.objects.create(current_at=date, category="prescribing")

    def create_user(self, email=None):
        index = self.next_id()
        email = email or "user-{}@example.com".format(index)
        return User.objects.create_user(username="User {}".format(index), email=email)

    def create_ncso_concessions_bookmark(self, org, user=None):
        kwargs = {"user": user or self.create_user()}

        if org is None:
            # All England
            pass
        elif isinstance(org, PCT):
            kwargs["pct"] = org
        elif isinstance(org, Practice):
            kwargs["practice"] = org
        elif isinstance(org, PCN):
            kwargs["pcn"] = org
        elif isinstance(org, STP):
            kwargs["stp"] = org
        elif isinstance(org, RegionalTeam):
            kwargs["regional_team"] = org
        else:
            assert False

        return NCSOConcessionBookmark.objects.create(**kwargs)

    def create_org_bookmark(self, org, user=None):
        kwargs = {"user": user or self.create_user()}

        if org is None:
            # All England
            pass
        elif isinstance(org, PCN):
            kwargs["pcn"] = org
        elif isinstance(org, PCT):
            kwargs["pct"] = org
        elif isinstance(org, Practice):
            kwargs["practice"] = org
        elif isinstance(org, STP):
            kwargs["stp"] = org
        else:
            assert False

        return OrgBookmark.objects.create(**kwargs)

    def create_measure(self, tags=None):
        index = self.next_id()
        return Measure.objects.create(
            id="measure_{}".format(index),
            name="Measure {}".format(index),
            title="Measure {}".format(index),
            tags=tags,
            numerator_from="",
            numerator_where="",
            numerator_columns="",
            denominator_from="",
            denominator_where="",
            denominator_columns="",
            numerator_bnf_codes=[],
            denominator_bnf_codes=[],
        )
