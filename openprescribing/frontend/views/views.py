import datetime
import functools
import json
import logging
import os
import re
import sys
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from common.utils import parse_date
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db.models import Avg, Sum
from django.http import Http404, HttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import get_resolver, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from dmd.models import VMP
from frontend.forms import (
    BookmarkListForm,
    NCSOConcessionBookmarkForm,
    OrgBookmarkForm,
    SearchBookmarkForm,
)
from frontend.measure_tags import MEASURE_TAGS
from frontend.models import (
    PCN,
    PCT,
    STP,
    Chemical,
    EmailMessage,
    ImportLog,
    Measure,
    MeasureGlobal,
    MeasureValue,
    NCSOConcessionBookmark,
    OrgBookmark,
    Practice,
    Presentation,
    Profile,
    RegionalTeam,
    SearchBookmark,
    Section,
)
from frontend.price_per_unit.savings import get_total_savings_for_org
from frontend.price_per_unit.substitution_sets import (
    get_substitution_sets_by_presentation,
)
from frontend.views.spending_utils import (
    ncso_spending_breakdown_for_entity,
    ncso_spending_for_entity,
)
from gcutils.bigquery import interpolate_sql
from lxml import html
from matrixstore.db import latest_prescribing_date, org_has_prescribing

logger = logging.getLogger(__name__)


class BadRequestError(Exception):
    pass


def handle_bad_request(view_function):
    @functools.wraps(view_function)
    def wrapper(request, *args, **kwargs):
        try:
            return view_function(request, *args, **kwargs)
        except BadRequestError as e:
            context = {"error_code": 400, "reason": str(e)}
            return render(request, "500.html", context, status=400)

    return wrapper


def first_or_none(lst):
    try:
        return lst[0]
    except IndexError:
        return None


def home(request):
    return render(
        request,
        "index.html",
        {
            "news_feed": cache.get("news_feed", [])[:3],
        },
    )


##################################################
# BNF sections
##################################################


def all_bnf(request):
    sections = Section.objects.filter(is_current=True)
    context = {"sections": sections, **get_org_context(request.GET)}
    return render(request, "all_bnf.html", context)


def bnf_section(request, section_id):
    section = get_object_or_404(Section, bnf_id=section_id)
    id_len = len(section_id)
    bnf_chapter = None
    bnf_section = None
    try:
        if id_len > 2:
            bnf_chapter = Section.objects.get(bnf_id=section_id[:2])
        if id_len > 4:
            bnf_section = Section.objects.get(bnf_id=section_id[:4])
    except Section.DoesNotExist:
        pass
    chemicals = None
    subsections = Section.objects.filter(
        bnf_id__startswith=section_id, is_current=True
    ).extra(where=["CHAR_LENGTH(bnf_id)=%s" % (id_len + 2)])
    if not subsections:
        chemicals = Chemical.objects.filter(
            bnf_code__startswith=section_id, is_current=True
        ).order_by("chem_name")
    context = {
        "section": section,
        "bnf_chapter": bnf_chapter,
        "bnf_section": bnf_section,
        "subsections": subsections,
        "chemicals": chemicals,
        "page_id": section_id,
        **get_org_context(request.GET),
    }
    return render(request, "bnf_section.html", context)


##################################################
# Chemicals
##################################################


def all_chemicals(request):
    chemicals = Chemical.objects.filter(is_current=True).order_by("bnf_code")
    context = {"chemicals": chemicals, **get_org_context(request.GET)}
    return render(request, "all_chemicals.html", context)


def chemical(request, bnf_code):
    c = get_object_or_404(Chemical, bnf_code=bnf_code)

    # Get BNF chapter, section etc.
    bnf_chapter = Section.objects.get(bnf_id=bnf_code[:2])
    bnf_section = Section.objects.get(bnf_id=bnf_code[:4])
    try:
        bnf_para = Section.objects.get(bnf_id=bnf_code[:6])
    except Section.DoesNotExist:
        bnf_para = None

    context = {
        "page_id": bnf_code,
        "chemical": c,
        "bnf_chapter": bnf_chapter,
        "bnf_section": bnf_section,
        "bnf_para": bnf_para,
        **get_org_context(request.GET),
    }
    return render(request, "chemical.html", context)


def get_org_context(params):
    org_type = params.get("org_type", "")
    org_code = params.get("org", "")
    if not org_type or not org_code:
        return {
            "org": None,
            "extra_url_params": "",
            "extra_api_params": "",
        }

    org = _get_entity(org_type, org_code)
    return {
        "org": org,
        "extra_url_params": format_html("?org_type={}&org={}", org_type, org.code),
        "extra_api_params": format_html("&org_type={}&org={}", org_type, org.code),
    }


##################################################
# GP practices
##################################################


def all_practices(request):
    practices = Practice.objects.filter(setting=4).order_by("name")
    context = {"practices": practices}
    return render(request, "all_practices.html", context)


def practice_home_page(request, practice_code):
    practice = get_object_or_404(Practice, code=practice_code)
    if request.method == "POST":
        return _handle_bookmark_post(request, OrgBookmark)

    form = _build_bookmark_form(OrgBookmark, {"practice_id": practice_code})
    context = _home_page_context_for_entity(request, practice)
    context["form"] = form
    if context["has_prescribing"]:
        template = "entity_home_page.html"
    else:
        template = "closed_entity_home_page.html"
    return render(request, template, context)


##################################################
# PCNs
##################################################


def all_pcns(request):
    pcns = PCN.objects.active().order_by("name")
    pcn_data = [
        {
            "name": pcn.cased_name,
            "code": pcn.code,
            "url": reverse("pcn_home_page", args=[pcn.code]),
        }
        for pcn in pcns
    ]
    context = {"pcn_data": pcn_data}
    return render(request, "all_pcns.html", context)


def pcn_home_page(request, pcn_code):
    pcn = get_object_or_404(PCN, code=pcn_code)
    if request.method == "POST":
        return _handle_bookmark_post(request, OrgBookmark)

    form = _build_bookmark_form(OrgBookmark, {"pcn_id": pcn_code})
    practices = Practice.objects.filter(pcn=pcn, setting=4).order_by("name")
    num_open_practices = len([p for p in practices if p.status_code == "A"])
    num_non_open_practices = len([p for p in practices if p.status_code != "A"])
    context = _home_page_context_for_entity(request, pcn)
    extra_context = {
        "practices": practices,
        "num_open_practices": num_open_practices,
        "num_non_open_practices": num_non_open_practices,
        "form": form,
    }
    context.update(extra_context)
    if context["has_prescribing"]:
        template = "entity_home_page.html"
    else:
        template = "closed_entity_home_page.html"
    return render(request, template, context)


##################################################
# CCGs
##################################################


def all_ccgs(request):
    ccgs = PCT.objects.filter(close_date__isnull=True, org_type="CCG").order_by("name")
    context = {"ccgs": ccgs}
    return render(request, "all_ccgs.html", context)


def ccg_home_page(request, ccg_code):
    ccg = get_object_or_404(PCT, code=ccg_code)
    if request.method == "POST":
        return _handle_bookmark_post(request, OrgBookmark)

    form = _build_bookmark_form(OrgBookmark, {"pct_id": ccg_code})
    practices = Practice.objects.filter(ccg=ccg, setting=4).order_by("name")
    num_open_practices = len([p for p in practices if p.status_code == "A"])
    num_non_open_practices = len([p for p in practices if p.status_code != "A"])
    context = _home_page_context_for_entity(request, ccg)
    extra_context = {
        "form": form,
        "practices": practices,
        "num_open_practices": num_open_practices,
        "num_non_open_practices": num_non_open_practices,
        "pcns": ccg.pcns(),
    }
    context.update(extra_context)
    if context["has_prescribing"]:
        template = "entity_home_page.html"
    else:
        template = "closed_entity_home_page.html"
    return render(request, template, context)


##################################################
# STPs
##################################################


def all_stps(request):
    stps = STP.objects.order_by("name")
    context = {"stps": stps}
    return render(request, "all_stps.html", context)


def stp_home_page(request, stp_code):
    stp = get_object_or_404(STP, code=stp_code)
    if request.method == "POST":
        return _handle_bookmark_post(request, OrgBookmark)

    form = _build_bookmark_form(OrgBookmark, {"stp_id": stp_code})
    ccgs = PCT.objects.filter(
        stp=stp, close_date__isnull=True, org_type="CCG"
    ).order_by("name")
    context = _home_page_context_for_entity(request, stp)
    context["ccgs"] = ccgs
    context["form"] = form
    if context["has_prescribing"]:
        template = "entity_home_page.html"
    else:
        template = "closed_entity_home_page.html"
    return render(request, template, context)


##################################################
# Regional teams
##################################################


def all_regional_teams(request):
    # NHS reorganisations sometimes include regions before CCGs have
    # been assigned, hence the filter on an aggregation here:
    regional_teams = RegionalTeam.objects.active().order_by("name")
    context = {"regional_teams": regional_teams}
    return render(request, "all_regional_teams.html", context)


def regional_team_home_page(request, regional_team_code):
    regional_team = get_object_or_404(RegionalTeam, code=regional_team_code)
    ccgs = PCT.objects.filter(
        regional_team=regional_team, close_date__isnull=True, org_type="CCG"
    ).order_by("name")
    context = _home_page_context_for_entity(request, regional_team)
    context["ccgs"] = ccgs
    if context["has_prescribing"]:
        template = "entity_home_page.html"
    else:
        template = "closed_entity_home_page.html"
    return render(request, template, context)


##################################################
# All England
##################################################


def cached(function, *args):
    """
    Wrapper which caches the result of calling `function` with the supplied
    arguments.

    Note that all arguments must be serializable as strings. The commit sha of
    the code is used as part of the cache key so any new deployment will
    automatically invalidate the cache.
    """
    if not settings.ENABLE_CACHING:
        return function(*args)
    key_parts = [settings.SOURCE_COMMIT_ID, __name__, function.__name__]
    key_parts.extend(map(str, args))
    key = ":".join(key_parts)
    result = cache.get(key)
    if result is None:
        result = function(*args)
        # We cache for a week which is likely to be the maximum useful lifetime
        # of these values, given that they are invalidated on every deploy. (We
        # don't need to worry about stale data after an import as the functions
        # we're caching include a date in their arguments)
        cache.set(key, result, timeout=60 * 60 * 24 * 7)
    return result


@handle_bad_request
def all_england(request):
    if request.method == "POST":
        return _handle_bookmark_post(request, OrgBookmark)

    form = _build_bookmark_form(OrgBookmark, {})

    tag_filter = _get_measure_tag_filter(request.GET)
    entity_type = request.GET.get("entity_type", "CCG")
    date = _specified_or_last_date(request, "dashboard_data")
    ppu_savings = get_total_savings_for_org(str(date), "all_standard_practices", None)
    # We cache the results of these expensive function calls which only change
    # when `date` changes
    measure_savings = cached(all_england_measure_savings, entity_type, date)
    low_priority_savings = cached(all_england_low_priority_savings, entity_type, date)
    low_priority_total = cached(all_england_low_priority_total, entity_type, date)
    # We deliberately DON'T cache the NCSO spending query as this can change
    # whenever new concession data comes in, which can happen at any time
    ncso_spending = first_or_none(
        ncso_spending_for_entity(None, "all_england", num_months=1)
    )
    other_entity_type = "practice" if entity_type == "CCG" else "CCG"
    other_entity_query = request.GET.copy()
    other_entity_query["entity_type"] = other_entity_type

    measure_options = {
        "aggregate": True,
        "chartTitleUrlTemplate": _url_template("measure_for_all_ccgs"),
        "globalMeasuresUrl": _build_global_measures_url(tags=tag_filter["tags"]),
        "measureUrlTemplate": _url_template("measure_for_all_ccgs"),
        "measureDefinitionUrlTemplate": _url_template("measure_definition"),
        "oneEntityUrlTemplate": _url_template("measure_for_all_england"),
        "orgName": "All {}s in England".format(entity_type),
        "orgType": entity_type.lower(),
        "orgTypeHuman": _entity_type_human(entity_type.lower()),
        "panelMeasuresUrl": _build_panel_measures_url(
            entity_type.lower(), tags=tag_filter["tags"], aggregate=True
        ),
        "rollUpBy": "measure_id",
        "tags": ",".join(tag_filter["tags"]),
        "tagsFocusUrlTemplate": reverse("all_england"),
    }

    context = {
        "tag_filter": tag_filter,
        "entity_type": entity_type,
        "other_entity_type": other_entity_type,
        "other_entity_url": "?" + other_entity_query.urlencode(),
        "ppu_savings": ppu_savings,
        "measure_savings": measure_savings,
        "low_priority_savings": low_priority_savings,
        "low_priority_total": low_priority_total,
        "ncso_spending": ncso_spending,
        "date": date,
        "measure_options": measure_options,
        "form": form,
    }
    return render(request, "all_england.html", context)


##################################################
# Analyse
##################################################


def analyse(request):
    if request.method == "POST":
        return _handle_bookmark_post(request, SearchBookmark)

    # Note that the (hidden) URL field is filled via javascript on
    # page load (see `alertForm` in `chart.js`)
    form = _build_bookmark_form(SearchBookmark, {})
    return render(request, "analyse.html", {"form": form})


##################################################
# Measures
##################################################


@handle_bad_request
def all_measures(request):
    tag_filter = _get_measure_tag_filter(request.GET, show_all_by_default=True)
    query = {}
    if tag_filter["tags"]:
        query["tags__overlap"] = tag_filter["tags"]
    if request.GET.get("show_previews"):
        measures = Measure.objects.preview()
    else:
        measures = Measure.objects.non_preview()
    measures = measures.filter(**query).order_by("name")
    context = {"tag_filter": tag_filter, "measures": measures}
    return render(request, "all_measures.html", context)


def measure_definition(request, measure):
    measure = get_object_or_404(Measure, pk=measure)

    context = {
        "measure": measure,
        "measure_details": _get_measure_details(measure.id),
        "measure_tags": _get_tags_with_names(measure.tags),
        "numerator_sql": _format_measure_sql(
            columns=measure.numerator_columns,
            from_=measure.numerator_from,
            where=measure.numerator_where,
        ),
        "denominator_sql": _format_measure_sql(
            columns=measure.denominator_columns,
            from_=measure.denominator_from,
            where=measure.denominator_where,
        ),
    }
    return render(request, "measure_definition.html", context)


def _format_measure_sql(**kwargs):
    sql = interpolate_sql(
        "SELECT\n"
        "     CAST(month AS DATE) AS month,\n"
        "     practice AS practice_id,\n"
        "     {columns}\n"
        " FROM {from_}\n"
        " WHERE {where}\n"
        " GROUP BY month, practice_id",
        **kwargs,
    )
    # Remove "1 = 1" WHERE conditions to avoid confusion and visual clutter
    sql = re.sub(r"WHERE\s+1\s*=\s*1\s+GROUP BY", "GROUP BY", sql)
    return sql


# We cache these in memory to avoid hitting the disk every time
@functools.lru_cache(maxsize=None)
def _get_measure_details(measure_id):
    """
    Get extra measure data which is currently only stored in the JSON on disk,
    not in the database
    """
    file = os.path.join(settings.MEASURE_DEFINITIONS_PATH, measure_id + ".json")
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        details = json.load(f)
    for key, value in details.items():
        if isinstance(value, list):
            # We approximate support for multi-line strings by allowing strings
            # to be split into a list of shorter strings.
            if key == "change_log":
                # change_log is a list of dicts not strings, so we ignore it here.
                continue
            details[key] = "\n".join(value)
    return details


def measure_for_one_entity(request, measure, entity_code, entity_type):
    entity = _get_entity(entity_type, entity_code)
    measure = get_object_or_404(Measure, pk=measure)

    entity_type = _org_type_for_entity(entity)
    entity_type_lower = entity_type.lower()

    measure_options = {
        "chartTitleUrlTemplate": _url_template("measure_for_one_" + entity_type_lower),
        "globalMeasuresUrl": _build_global_measures_url(measure_id=measure.id),
        "orgId": entity.code,
        "orgLocationUrl": _build_org_location_url(entity),
        "orgName": entity.name,
        "orgType": entity_type,
        "orgTypeHuman": _entity_type_human(entity_type_lower),
        "panelMeasuresUrl": _build_panel_measures_url(
            entity_type_lower, entity_code=entity.code, measure_id=measure.id
        ),
        "rollUpBy": "measure_id",
        "tagsFocusUrlTemplate": _url_template("measures_for_one_" + entity_type),
        "allMeasuresForOrgUrl": reverse(
            "measures_for_one_" + entity_type,
            kwargs={entity_type + "_code": entity_code},
        ),
    }

    _add_measure_for_children_in_entity_url(measure_options, entity_type)
    _add_measure_for_siblings_url(measure_options, entity_type)
    _add_improvement_radar_url(measure_options, entity_type)
    _add_measure_url(measure_options, entity_type)

    if entity_type == "practice":
        measure_options["parentOrgId"] = entity.ccg_id

    _add_measure_details(measure_options, measure)

    entity_type_human = _entity_type_human(entity_type)
    context = {
        "entity": entity,
        "entity_type": entity_type,
        "entity_type_human": entity_type_human,
        "measures_url_name": "measures_for_one_{}".format(entity_type),
        "measure": measure,
        "measure_options": measure_options,
        "current_at": parse_date(latest_prescribing_date()),
        "numerator_breakdown_url": _build_api_url(
            "measure_numerators_by_org",
            {"org": entity.code, "org_type": entity_type, "measure": measure.id},
        ),
    }
    return render(request, "measure_for_one_entity.html", context)


def measure_for_all_england(request, measure):
    measure = get_object_or_404(Measure, pk=measure)
    entity_type = request.GET.get("entity_type", "ccg")

    measure_options = {
        "aggregate": True,
        "chartTitleUrlTemplate": _url_template("measure_for_all_ccgs"),
        "globalMeasuresUrl": _build_global_measures_url(measure_id=measure.id),
        "orgName": "All {}s in England".format(entity_type),
        "orgType": entity_type.lower(),
        "orgTypeHuman": _entity_type_human(entity_type.lower()),
        "panelMeasuresUrl": _build_panel_measures_url(
            entity_type.lower(), measure_id=measure.id, aggregate=True
        ),
        "rollUpBy": "measure_id",
        "tagsFocusUrlTemplate": reverse("all_england"),
        "allMeasuresForOrgUrl": reverse("all_england"),
    }

    _add_measure_details(measure_options, measure)
    _add_measure_url(measure_options, entity_type)

    context = {
        "entity_type": entity_type,
        "measures_url_name": "measures_for_one_{}".format(entity_type),
        "measure": measure,
        "measure_options": measure_options,
        "current_at": parse_date(latest_prescribing_date()),
        "numerator_breakdown_url": _build_api_url(
            "measure_numerators_by_org",
            {"org": "", "org_type": entity_type, "measure": measure.id},
        ),
    }
    return render(request, "measure_for_one_entity.html", context)


# Note that we cannot have a single view function for measures_for_one_entity or
# measure_for_children_in_entity (as we do for eg measure_for_one_entity)
# because the parameter names are used for building URLs by _url_template()
# below and _buildUrl() in measure_utils.js.


@handle_bad_request
def measures_for_one_practice(request, practice_code):
    return _measures_for_one_entity(request, practice_code, "practice")


@handle_bad_request
def measures_for_one_pcn(request, pcn_code):
    return _measures_for_one_entity(request, pcn_code, "pcn")


@handle_bad_request
def measures_for_one_ccg(request, ccg_code):
    return _measures_for_one_entity(request, ccg_code, "ccg")


@handle_bad_request
def measures_for_one_stp(request, stp_code):
    return _measures_for_one_entity(request, stp_code, "stp")


@handle_bad_request
def measures_for_one_regional_team(request, regional_team_code):
    return _measures_for_one_entity(request, regional_team_code, "regional_team")


def _measures_for_one_entity(request, entity_code, entity_type):
    entity = _get_entity(entity_type, entity_code)
    tag_filter = _get_measure_tag_filter(request.GET)
    entity_type_lower = entity_type.lower()

    measure_options = {
        "chartTitleUrlTemplate": _url_template("measure_for_one_" + entity_type_lower),
        "globalMeasuresUrl": _build_global_measures_url(tags=tag_filter["tags"]),
        "oneEntityUrlTemplate": _url_template("measure_for_one_{}".format(entity_type)),
        "orgId": entity_code,
        "orgLocationUrl": _build_org_location_url(entity),
        "orgName": entity.name,
        "orgType": entity_type,
        "orgTypeHuman": _entity_type_human(entity_type.lower()),
        "panelMeasuresUrl": _build_panel_measures_url(
            entity_type.lower(), entity_code=entity.code, tags=tag_filter["tags"]
        ),
        "rollUpBy": "measure_id",
        "tags": ",".join(tag_filter["tags"]),
        "tagsFocusUrlTemplate": _url_template("measures_for_one_" + entity_type),
    }

    _add_measure_for_children_in_entity_url(measure_options, entity_type)
    _add_measure_for_siblings_url(measure_options, entity_type)
    _add_improvement_radar_url(measure_options, entity_type)
    _add_measure_url(measure_options, entity_type)

    if entity_type == "practice":
        measure_options["parentOrgId"] = entity.ccg_id

    context = {
        "entity": entity,
        "entity_type": entity_type,
        "entity_type_human": _entity_type_human(entity_type),
        "page_id": entity_code,
        "tag_filter": tag_filter,
        "low_priority_url": reverse(
            "measure_for_one_" + entity_type,
            kwargs={"measure": "lpzomnibus", "entity_code": entity.code},
        ),
        "measure_options": measure_options,
    }

    if entity_type in ["pcn", "ccg"]:
        context["practices"] = entity.practice_set.filter(setting=4).order_by("name")
    elif entity_type in ["stp", "regional_team"]:
        context["ccgs"] = entity.pct_set.filter(
            close_date__isnull=True, org_type="CCG"
        ).order_by("name")

    return render(request, "measures_for_one_entity.html", context)


def measure_for_practices_in_ccg(request, ccg_code, measure):
    return _measure_for_children_in_entity(request, measure, ccg_code, "ccg")


def measure_for_practices_in_pcn(request, pcn_code, measure):
    return _measure_for_children_in_entity(request, measure, pcn_code, "pcn")


def measure_for_ccgs_in_stp(request, stp_code, measure):
    return _measure_for_children_in_entity(request, measure, stp_code, "stp")


def measure_for_ccgs_in_regional_team(request, regional_team_code, measure):
    return _measure_for_children_in_entity(
        request, measure, regional_team_code, "regional_team"
    )


def _measure_for_children_in_entity(
    request, measure, parent_entity_code, parent_entity_type
):
    parent = _get_entity(parent_entity_type, parent_entity_code)
    child_entity_type = {
        "pcn": "practice",
        "ccg": "practice",
        "stp": "ccg",
        "regional_team": "ccg",
    }[parent_entity_type]
    measure = get_object_or_404(Measure, pk=measure)

    measure_options = {
        "chartTitleUrlTemplate": _url_template("measures_for_one_" + child_entity_type),
        "globalMeasuresUrl": _build_global_measures_url(measure_id=measure.id),
        "measure": measure,
        "oneEntityUrlTemplate": _url_template("measure_for_one_" + child_entity_type),
        "orgId": parent.code,
        "orgLocationUrl": _build_org_location_url(parent),
        "orgName": parent.name,
        "orgType": child_entity_type,
        "orgTypeHuman": _entity_type_human(child_entity_type),
        "parentOrgType": _org_type_for_entity(parent),
        "parentOrgTypeHuman": _entity_type_human(_org_type_for_entity(parent)),
        "panelMeasuresUrl": _build_panel_measures_url(
            child_entity_type,
            entity_code=parent.code,
            parent_org_type=_org_type_for_entity(parent),
            measure_id=measure.id,
        ),
        "rollUpBy": "org_id",
        "tagsFocusUrlTemplate": _url_template("measures_for_one_" + child_entity_type),
    }

    _add_measure_details(measure_options, measure)
    _add_improvement_radar_url(measure_options, child_entity_type)
    _add_measure_for_children_in_entity_url(measure_options, child_entity_type)

    context = {
        "parent_entity_type": parent_entity_type,
        "parent_entity_type_human": _entity_type_human(parent_entity_type),
        "child_entity_type_human": _entity_type_human(child_entity_type),
        "parent": parent,
        "page_id": parent_entity_code,
        "parent_entity_measure_url": reverse(
            "measure_for_one_" + parent_entity_type,
            kwargs={"measure": measure.id, "entity_code": parent_entity_code},
        ),
        "all_measures_url": reverse(
            "measures_for_one_" + parent_entity_type,
            kwargs={parent_entity_type + "_code": parent_entity_code},
        ),
        "measure": measure,
        "measure_options": measure_options,
        "measure_tags": _get_tags_with_names(measure.tags),
    }

    if not _user_is_bot(request):
        # Don't show link to bots.  We don't want it crawled.
        context["csv_download_url"] = measure_options["panelMeasuresUrl"].replace(
            "format=json", "format=csv"
        )

    return render(request, "measure_for_children_in_entity.html", context)


def measure_for_all_entities(request, measure, entity_type):
    measure = get_object_or_404(Measure, id=measure)

    measure_options = {
        "chartTitleUrlTemplate": _url_template("measures_for_one_" + entity_type),
        "globalMeasuresUrl": _build_global_measures_url(measure_id=measure.id),
        "measure": measure,
        "oneEntityUrlTemplate": _url_template("measure_for_one_{}".format(entity_type)),
        "orgType": entity_type,
        "orgTypeHuman": _entity_type_human(entity_type),
        "panelMeasuresUrl": _build_panel_measures_url(
            entity_type, measure_id=measure.id
        ),
        "rollUpBy": "org_id",
        "tagsFocusUrlTemplate": _url_template("measures_for_one_" + entity_type),
    }

    _add_measure_for_children_in_entity_url(measure_options, entity_type)
    _add_improvement_radar_url(measure_options, entity_type)
    _add_measure_details(measure_options, measure)

    entity_type_human = _entity_type_human(entity_type)

    context = {
        "measure": measure,
        "measure_options": measure_options,
        "entity_type": entity_type,
        "entity_type_human": entity_type_human,
        "measure_tags": _get_tags_with_names(measure.tags),
        "all_measures_url": reverse("all_measures"),
    }

    if not _user_is_bot(request):
        # Don't show link to bots.  We don't want it crawled.
        context["csv_download_url"] = measure_options["panelMeasuresUrl"].replace(
            "format=json", "format=csv"
        )

    return render(request, "measure_for_all_entities.html", context)


##################################################
# Price per unit
##################################################


@handle_bad_request
def practice_price_per_unit(request, code):
    date = _specified_or_last_date(request, "prescribing")
    practice = get_object_or_404(Practice, code=code)
    context = {
        "entity": practice,
        "entity_name": practice.cased_name,
        "entity_name_and_status": practice.name_and_status,
        "highlight": practice.code,
        "highlight_name": practice.cased_name,
        "date": date,
        "by_practice": True,
    }
    return render(request, "price_per_unit.html", context)


@handle_bad_request
def ccg_price_per_unit(request, code):
    date = _specified_or_last_date(request, "prescribing")
    ccg = get_object_or_404(PCT, code=code)
    context = {
        "entity": ccg,
        "entity_name": ccg.cased_name,
        "entity_name_and_status": ccg.name_and_status,
        "highlight": ccg.code,
        "highlight_name": ccg.cased_name,
        "date": date,
        "by_ccg": True,
    }
    return render(request, "price_per_unit.html", context)


@handle_bad_request
def all_england_price_per_unit(request):
    date = _specified_or_last_date(request, "prescribing")
    context = {
        "entity_name": "NHS England",
        "entity_name_and_status": "NHS England",
        "highlight_name": "NHS England",
        "date": date,
        "by_ccg": True,
        "entity_type": "CCG",
        "aggregate": True,
    }
    return render(request, "price_per_unit.html", context)


@handle_bad_request
def price_per_unit_by_presentation(request, entity_code, bnf_code):
    date = _specified_or_last_date(request, "prescribing")
    primary_code, product_name, dmd_info = _get_substitution_details(bnf_code)
    if bnf_code != primary_code:
        url = request.get_full_path().replace(bnf_code, primary_code)
        return HttpResponseRedirect(url)
    if len(entity_code) in [3, 5]:
        entity = get_object_or_404(PCT, code=entity_code)
    elif len(entity_code) == 6:
        entity = get_object_or_404(Practice, code=entity_code)

    params = {
        "format": "json",
        "bnf_code": bnf_code,
        "highlight": entity.code,
        "date": date.strftime("%Y-%m-%d"),
    }

    bubble_data_url = _build_api_url("bubble", params)

    context = {
        "entity": entity,
        "entity_name": entity.cased_name,
        "entity_name_and_status": entity.name_and_status,
        "highlight": entity.code,
        "highlight_name": entity.cased_name,
        "name": product_name,
        "bnf_code": bnf_code,
        "dmd_info": dmd_info,
        "date": date,
        "by_presentation": True,
        "bubble_data_url": bubble_data_url,
    }
    return render(request, "price_per_unit.html", context)


@handle_bad_request
def all_england_price_per_unit_by_presentation(request, bnf_code):
    date = _specified_or_last_date(request, "prescribing")
    primary_code, product_name, dmd_info = _get_substitution_details(bnf_code)
    if bnf_code != primary_code:
        url = request.get_full_path().replace(bnf_code, primary_code)
        return HttpResponseRedirect(url)

    params = {
        "format": "json",
        "bnf_code": bnf_code,
        "date": date.strftime("%Y-%m-%d"),
    }

    bubble_data_url = _build_api_url("bubble", params)

    context = {
        "name": product_name,
        "bnf_code": bnf_code,
        "dmd_info": dmd_info,
        "date": date,
        "by_presentation": True,
        "bubble_data_url": bubble_data_url,
        "entity_name": "NHS England",
        "entity_name_and_status": "NHS England",
        "entity_type": "CCG",
    }
    return render(request, "price_per_unit.html", context)


def _get_substitution_details(bnf_code):
    """
    If this BNF code belongs to a "substitution set" (e.g. it's a branded
    version of a generic presentation) then return the primary code of that
    substitution set.  Otherwise, just return the original code
    """
    substitution_sets = get_substitution_sets_by_presentation()
    try:
        substitution = substitution_sets[bnf_code]
    except KeyError:
        substitution = None

    presentation = Presentation.objects.filter(pk=bnf_code).first()

    if substitution is not None:
        new_bnf_code = substitution.id
        name = substitution.name
        dmd_info = presentation.dmd_info() if presentation else None
    elif presentation is not None:
        new_bnf_code = bnf_code
        name = presentation.product_name
        dmd_info = presentation.dmd_info()
    else:
        raise Http404()

    return new_bnf_code, name, dmd_info


##################################################
# Ghost generics
##################################################


@handle_bad_request
def ghost_generics_for_entity(request, code, entity_type):
    date = _specified_or_last_date(request, "prescribing")
    entity = _get_entity(entity_type, code)
    measure_for_entity_url = reverse(
        "measure_for_one_{}".format(entity_type.lower()),
        kwargs={"measure": "ghost_generic_measure", "entity_code": code},
    )
    context = {
        "entity": entity,
        "entity_name": entity.cased_name,
        "entity_name_and_status": entity.name_and_status,
        "entity_type": entity_type,
        "highlight": entity.code,
        "highlight_name": entity.cased_name,
        "date": date,
        "measure_for_entity_url": measure_for_entity_url,
    }
    if entity_type == "practice":
        context["by_practice"] = True
    elif entity_type == "CCG":
        context["by_ccg"] = True
    else:
        raise ValueError("Unhandled entity_type: {}".format(entity_type))
    return render(request, "ghost_generics.html", context)


##################################################
# Tariffs
##################################################


def tariff(request, code=None):
    vmps = (
        VMP.objects.filter(vmpp__tariffprice__isnull=False, bnf_code__isnull=False)
        .distinct()
        .order_by("nm")
    )
    codes = []
    if code:
        codes = [code]
    if "codes" in request.GET:
        codes.extend(request.GET.getlist("codes"))
    if codes:
        presentations = Presentation.objects.filter(bnf_code__in=codes)
    else:
        presentations = []
    selected_vmps = VMP.objects.filter(bnf_code__in=codes)
    context = {
        "bnf_codes": codes,
        "presentations": presentations,
        "vmps": vmps,
        "selected_vmps": selected_vmps,
        "chart_title": "Tariff prices for "
        + ", ".join([x.product_name for x in presentations]),
    }
    return render(request, "tariff.html", context)


##################################################
# Spending
##################################################


def spending_for_one_entity(request, entity_code, entity_type):
    # Temporary hack as this page is very expensive to render and brings the
    # site to its knees when bots decide to crawl us (most other pages do the
    # expensive data loading via JS and so don't have this issue)
    if _user_is_bot(request):
        raise Http404()

    entity = _get_entity(entity_type, entity_code)

    if request.method == "POST":
        return _handle_bookmark_post(request, NCSOConcessionBookmark)

    if entity_type == "practice":
        form = _build_bookmark_form(NCSOConcessionBookmark, {"practice_id": entity.pk})
    elif entity_type.lower() == "ccg":
        form = _build_bookmark_form(NCSOConcessionBookmark, {"pct_id": entity.pk})
    elif entity_type == "all_england":
        form = _build_bookmark_form(NCSOConcessionBookmark, {})
    else:
        form = None

    current_month = _get_current_month()
    monthly_totals = ncso_spending_for_entity(
        entity, entity_type, current_month=current_month
    )
    # In the very rare cases where we don't have data we just return a 404
    # rather than triggering an error
    if not monthly_totals:
        raise Http404("No data available")
    end_date = max(row["month"] for row in monthly_totals)
    last_prescribing_date = monthly_totals[-1]["last_prescribing_date"]
    last_12_months = monthly_totals[-12:]
    rolling_annual_total = sum(row["additional_cost"] for row in last_12_months)
    financial_ytd_total = _financial_ytd_total(last_12_months)
    breakdown_date = request.GET.get("breakdown_date")
    breakdown_date = parse_date(breakdown_date) if breakdown_date else end_date
    breakdown = ncso_spending_breakdown_for_entity(entity, entity_type, breakdown_date)
    breakdown_metadata = [i for i in monthly_totals if i["month"] == breakdown_date][0]
    url_template = reverse("tariff", kwargs={"code": "AAA"}).replace(
        "AAA", "{bnf_code}"
    )
    if entity_type == "all_england":
        entity_name = "NHS England"
        title = "Impact of price concessions across {}".format(entity_name)
        entity_short_desc = "nhs-england"
    else:
        entity_name = entity.cased_name
        title = "Impact of price concessions on {}".format(entity.name_and_status)
        entity_short_desc = "{}-{}".format(entity_type, entity.code)
    context = {
        "title": title,
        "entity_name": entity_name,
        "monthly_totals": monthly_totals,
        "rolling_annual_total": rolling_annual_total,
        "financial_ytd_total": financial_ytd_total,
        "available_dates": [row["month"] for row in reversed(monthly_totals)],
        "breakdown": {
            "table": breakdown,
            "url_template": url_template,
            "filename": "price-concessions-cost-{}-{}".format(
                entity_short_desc, breakdown_date
            ),
        },
        "breakdown_date": breakdown_date,
        "breakdown_is_estimate": breakdown_metadata["is_estimate"],
        "breakdown_is_incomplete_month": breakdown_metadata["is_incomplete_month"],
        "last_prescribing_date": last_prescribing_date,
        "form": form,
    }
    return render(request, "spending_for_one_entity.html", context)


def _user_is_bot(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    # Despite appearances this is actually a fairly robust way of detecting bots
    # See: https://webmasters.stackexchange.com/a/64805
    match = re.search("(bot|crawl|spider)", user_agent.lower())
    return bool(match)


def _get_current_month():
    return datetime.datetime.now().date().replace(day=1)


def _financial_ytd_total(monthly_totals):
    end_date = max(row["month"] for row in monthly_totals)
    financial_year = end_date.year if end_date.month >= 4 else end_date.year - 1
    financial_year_start = end_date.replace(year=financial_year, month=4)
    return sum(
        row["additional_cost"]
        for row in monthly_totals
        if row["month"] >= financial_year_start
    )


##################################################
# Bookmarks.
##################################################


def bookmarks(request, key):
    profile = get_object_or_404(Profile, key=key)
    user = profile.user

    search_bookmarks = user.searchbookmark_set.all()
    org_bookmarks = user.orgbookmark_set.all()
    ncso_concessions_bookmarks = user.ncsoconcessionbookmark_set.all()

    if request.method == "POST":
        if not request.POST.get("unsuball"):
            org_bookmarks = org_bookmarks.filter(
                pk__in=request.POST.getlist("org_bookmarks")
            )
            search_bookmarks = search_bookmarks.filter(
                pk__in=request.POST.getlist("search_bookmarks")
            )
            ncso_concessions_bookmarks = ncso_concessions_bookmarks.filter(
                pk__in=request.POST.getlist("ncso_concessions_bookmarks")
            )

        # QuerySet.delete() returns a tuple whose first element is the number
        # of records deleted.
        count = (
            org_bookmarks.delete()[0]
            + search_bookmarks.delete()[0]
            + ncso_concessions_bookmarks.delete()[0]
        )

        if count > 0:
            msg = "Unsubscribed from %s alert" % count
            if count > 1:
                msg += "s"
            messages.success(request, msg)

        return redirect(reverse("bookmarks", args=[key]))

    form = BookmarkListForm(
        org_bookmarks=org_bookmarks,
        search_bookmarks=search_bookmarks,
        ncso_concessions_bookmarks=ncso_concessions_bookmarks,
    )
    count = (
        search_bookmarks.count()
        + org_bookmarks.count()
        + ncso_concessions_bookmarks.count()
    )

    if count == 1:
        single_bookmark = (
            search_bookmarks.first()
            or org_bookmarks.first()
            or ncso_concessions_bookmarks.first()
        )
    else:
        single_bookmark = None

    ctx = {
        "search_bookmarks": search_bookmarks,
        "org_bookmarks": org_bookmarks,
        "ncso_concessions_bookmarks": ncso_concessions_bookmarks,
        "form": form,
        "count": count,
        "single_bookmark": single_bookmark,
    }

    return render(request, "bookmarks/bookmark_list.html", ctx)


BOOKMARK_CLS_TO_FORM_CLS = {
    OrgBookmark: OrgBookmarkForm,
    SearchBookmark: SearchBookmarkForm,
    NCSOConcessionBookmark: NCSOConcessionBookmarkForm,
}


def _build_bookmark_form(bookmark_cls, initial):
    """Build form for alert signup."""

    form_cls = BOOKMARK_CLS_TO_FORM_CLS[bookmark_cls]
    return form_cls(initial=initial)


def _handle_bookmark_post(request, bookmark_cls):
    """Create a bookmark, email the user, add confirmation message, and
    redirect to bookmark's dashboard URL.
    """

    bookmark = _get_or_create_bookmark(request, bookmark_cls)
    _send_alert_signup_confirmation(bookmark)
    _add_confirmation_message(request, bookmark)
    return redirect(bookmark.dashboard_url())


def _get_or_create_bookmark(request, bookmark_cls):
    """Get or create bookmark object.

    Note that this will raise a ValidationError if the email address is invalid
    (which shouldn't happen because it should be validated by the browser) or
    or an IntegrityError if the submitted pct_id/practice_id/pcn_id doesn't
    correspond to an existing PCT/Practice/PCN (which shouldn't happen because
    the entity id should be set in the initial form by _build_bookmark_form().)
    """

    form_cls = BOOKMARK_CLS_TO_FORM_CLS[bookmark_cls]
    form = form_cls(request.POST)
    form.full_clean()
    email = form.cleaned_data["email"].lower()
    user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
    bookmark_args = {k: v or None for k, v in form.cleaned_data.items() if k != "email"}
    bookmark, _ = bookmark_cls.objects.get_or_create(user=user, **bookmark_args)
    return bookmark


def _send_alert_signup_confirmation(bookmark):
    """Send email confirming that user has signed up for alert."""

    user = bookmark.user
    subject = "[OpenPrescribing] Your OpenPrescribing alert subscription"
    context = {
        "user": user,
        "bookmark": bookmark,
        "unsubscribe_link": settings.GRAB_HOST
        + reverse("bookmarks", kwargs={"key": user.profile.key}),
    }

    bodies = {}
    for ext in ["html", "txt"]:
        template_name = "account/email/email_confirmation_signup_message." + ext
        bodies[ext] = render_to_string(template_name, context).strip()

    msg = EmailMultiAlternatives(
        subject, bodies["txt"], settings.DEFAULT_FROM_EMAIL, [user.email]
    )
    msg.attach_alternative(bodies["html"], "text/html")

    msg.extra_headers = {"message-id": msg.message()["message-id"]}
    # pre-November 2019, these messages were tagged with "allauth"
    msg.tags = ["alert_signup"]
    msg = EmailMessage.objects.create_from_message(msg)
    msg.send()


def _add_confirmation_message(request, bookmark):
    """Add message indicating success."""

    message_lines = [
        "Thanks, you're now subscribed to alerts about {}.".format(bookmark.topic()),
        'Have you <a href="{}">signed up to our newsletter</a>?'.format(
            reverse("contact")
        ),
    ]
    message = mark_safe("\n".join(message_lines))
    messages.success(request, message)


##################################################
# Misc.
##################################################


def gdoc_view(request, doc_id):
    try:
        gdoc_id = settings.GDOC_DOCS[doc_id]
    except KeyError:
        raise Http404("No doc named %s" % doc_id)
    url = "https://docs.google.com/document/d/%s/pub?embedded=true" % gdoc_id
    page = requests.get(url)
    tree = html.fromstring(page.text)

    content = (
        "<style>"
        + "".join(
            [
                html.tostring(child).decode("utf8")
                for child in tree.head.xpath("//style")
            ]
        )
        + "</style>"
    )
    content += "".join([html.tostring(child).decode("utf8") for child in tree.body])
    context = {"content": content}
    return render(request, "gdoc.html", context)


##################################################
# Custom HTTP errors
##################################################
def custom_500(request):
    type_, value, traceback = sys.exc_info()
    reason = "Server error"
    if "canceling statement due to statement timeout" in str(value):
        reason = (
            "The database took too long to respond.  If you were running an"
            "analysis with multiple codes, try again with fewer."
        )
    if (request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest") or (
        "application/json" in request.META.get("HTTP_ACCEPT", "")
    ):
        return HttpResponse(reason, status=500)
    else:
        return render(request, "500.html", {"reason": reason}, status=500)


# This view deliberately triggers an error
def error(request):
    raise RuntimeError("Deliberate error triggered for testing purposes")


# This view is for uptime monitoring
def ping(request):
    num_practices = Practice.objects.count()
    rsp = "Pong: there are {} practices".format(num_practices)
    return HttpResponse(rsp)


##################################################
# Helpers
##################################################

CORE_TAG = "core"


def _get_measure_tag_filter(params, show_all_by_default=False):
    tags = params.getlist("tags")
    # Support passing a single "tags" param with a comma separated list
    tags = sum([tag.split(",") for tag in tags], [])
    tags = [_f for _f in tags if _f]
    default_tags = [] if show_all_by_default else [CORE_TAG]
    if not tags:
        tags = default_tags
    try:
        tag_details = [MEASURE_TAGS[tag] for tag in tags]
    except KeyError as e:
        raise BadRequestError("Unrecognised tag: {}".format(e.args[0]))
    return {
        "tags": tags,
        "names": [tag["name"] for tag in tag_details],
        "details": [tag for tag in tag_details if tag["description"]],
        "show_message": (tags != default_tags),
        "all_tags": _get_tags_select_options(tags, show_all_by_default),
    }


def _get_tags_select_options(selected_tags, show_all_by_default):
    options = [
        {"id": key, "name": tag["name"], "selected": (key in selected_tags)}
        for (key, tag) in MEASURE_TAGS.items()
    ]
    options.sort(key=_sort_core_tag_first)
    if show_all_by_default:
        options.insert(
            0, {"id": "", "name": "All Measures", "selected": (len(selected_tags) == 0)}
        )
    return options


def _get_tags_with_names(tags):
    return [{"tag": tag, "name": MEASURE_TAGS[tag]["name"]} for tag in tags]


def _sort_core_tag_first(option):
    return (0 if option["id"] == CORE_TAG else 1, option["name"])


def _specified_or_last_date(request, category):
    if category == "prescribing":
        latest_date = parse_date(latest_prescribing_date())
    else:
        latest_date = ImportLog.objects.latest_in_category(category).current_at
    date = request.GET.get("date", None)
    if not date:
        date = latest_date
    else:
        try:
            date = parse_date(date)
        except ValueError:
            raise BadRequestError("Date not in valid YYYY-MM-DD format: %s" % date)
        if date > latest_date:
            raise BadRequestError(
                f"No data available for {date} (latest is {latest_date})"
            )
    return date


def _home_page_context_for_entity(request, entity):
    entity_type = _org_type_for_entity(entity)
    context = {
        "entity": entity,
        "entity_type": entity_type,
        "entity_type_human": _entity_type_human(entity_type),
        "public_entity_type": {"ccg": "sicbl", "stp": "icb"}.get(
            entity_type, entity_type
        ),
        "has_prescribing": org_has_prescribing(entity_type, entity.code),
    }
    if not context["has_prescribing"]:
        return context
    prescribing_date = parse_date(latest_prescribing_date())
    six_months_ago = prescribing_date - relativedelta(months=6)
    mv_filter = {
        "month__gte": six_months_ago,
        "measure__tags__contains": ["core"],
        "percentile__isnull": False,
    }
    if entity_type == "practice":
        mv_filter["practice_id"] = entity.code
    elif entity_type == "pcn":
        mv_filter["pcn_id"] = entity.code
    elif entity_type == "ccg":
        mv_filter["pct_id"] = entity.code
    elif entity_type == "stp":
        mv_filter["stp_id"] = entity.code
    elif entity_type == "regional_team":
        mv_filter["regional_team_id"] = entity.code
    else:
        raise RuntimeError("Can't handle type: {!r}".format(entity_type))
    # find the core measurevalue that is most outlierish
    extreme_measurevalue = (
        MeasureValue.objects.filter_by_org_type(entity_type)
        .filter(**mv_filter)
        .exclude(measure_id="lpzomnibus")
        .exclude(measure__low_is_good__isnull=True)
        .values("measure_id")
        .annotate(average_percentile=Avg("percentile"))
        .order_by("-average_percentile", "-measure_id")
        .first()
    )
    if extreme_measurevalue:
        extreme_measure = Measure.objects.get(pk=extreme_measurevalue["measure_id"])
    else:
        extreme_measure = None
    measures_count = Measure.objects.non_preview().count()

    specific_measures = [
        {"measure": "lpzomnibus", "chartContainerId": "#lpzomnibus-container"}
    ]

    if extreme_measure:
        # extreme_measure will be None for new practices (and in tests)
        specific_measures.append(
            {
                "measure": extreme_measure.id,
                "chartContainerId": "#top-measure-container",
            }
        )

    specific_measure_ids = [
        specific_measure["measure"] for specific_measure in specific_measures
    ]

    measure_options = {
        "chartTitleUrlTemplate": _url_template("measure_for_one_" + entity_type),
        "globalMeasuresUrl": _build_global_measures_url(
            measure_ids=specific_measure_ids
        ),
        "oneEntityUrlTemplate": _url_template("measure_for_one_{}".format(entity_type)),
        "orgId": entity.code,
        "orgLocationUrl": _build_org_location_url(entity),
        "orgType": entity_type,
        "orgTypeHuman": _entity_type_human(entity_type),
        "panelMeasuresUrl": _build_panel_measures_url(
            entity_type, measure_ids=specific_measure_ids, entity_code=entity.code
        ),
        "rollUpBy": "measure_id",
        "specificMeasures": specific_measures,
        "tagsFocusUrlTemplate": _url_template("measures_for_one_" + entity_type),
    }

    _add_measure_for_children_in_entity_url(measure_options, entity_type)
    _add_measure_for_siblings_url(measure_options, entity_type)
    _add_improvement_radar_url(measure_options, entity_type)
    _add_measure_url(measure_options, entity_type)

    if entity_type == "practice":
        measure_options["parentOrgId"] = entity.ccg_id

    entity_outlier_report_url = (
        None
        if entity_type == "regional_team"
        else f"labs/outlier_reports/html/static_{entity_type}_{entity.code}.html"
    )

    context.update(
        {
            "measure": extreme_measure,
            "measures_count": measures_count,
            "measures_for_one_entity_url": "measures_for_one_{}".format(
                entity_type.lower().replace(" ", "_")
            ),
            "date": prescribing_date,
            "measure_options": measure_options,
            "measure_tags": [
                (k, v) for (k, v) in sorted(MEASURE_TAGS.items()) if k != "core"
            ],
            "ncso_spending": first_or_none(
                ncso_spending_for_entity(entity, entity_type, num_months=1)
            ),
            "spending_for_one_entity_url": "spending_for_one_{}".format(
                entity_type.lower()
            ),
            "entity_outlier_report_url": entity_outlier_report_url,
        }
    )

    if entity_type in ["practice", "ccg"]:
        context["entity_price_per_unit_url"] = "{}_price_per_unit".format(
            entity_type.lower()
        )
        context["possible_savings"] = get_total_savings_for_org(
            str(context["date"]), _org_type_for_entity(entity), entity.pk
        )
        context["entity_ghost_generics_url"] = "{}_ghost_generics".format(
            entity_type.lower()
        )

    return context


def _url_template(view_name):
    """Generate a URL template for a given view, to be interpolated by JS in
    the browser.

    >>> _url_template("measure_for_one_ccg")
    '/measure/{measure}/sicbl/{entity_code}/'
    """

    resolver = get_resolver()

    # For the example above, `pattern` is "measure/%(measure)s/sicbl/%(entity_code)s/"
    pattern = resolver.reverse_dict[view_name][0][0][0]
    return "/" + pattern.replace("%(", "{").replace(")s", "}")


def _org_type_for_entity(entity):
    return {
        Practice: "practice",
        PCN: "pcn",
        PCT: "ccg",
        STP: "stp",
        RegionalTeam: "regional_team",
    }[type(entity)]


def _add_measure_details(options, measure):
    options["measure"] = measure.id
    options["numerator"] = measure.numerator_short
    options["denominator"] = measure.denominator_short
    options["isCostBasedMeasure"] = measure.is_cost_based
    options["lowIsGood"] = measure.low_is_good
    if measure.tags_focus:
        options["tagsFocus"] = ",".join(measure.tags_focus)


def _add_measure_for_children_in_entity_url(options, entity_type):
    if entity_type == "practice":
        return

    if entity_type in ["stp", "regional_team"]:
        key = "measureForAllCCGsUrlTemplate"
        view_name = "measure_for_ccgs_in_" + entity_type
    elif entity_type == "ccg":
        key = "measureForAllPracticesUrlTemplate"
        view_name = "measure_for_practices_in_ccg"
    elif entity_type == "pcn":
        key = "measureForAllPracticesUrlTemplate"
        view_name = "measure_for_practices_in_pcn"
    else:
        assert False, entity_type

    options[key] = _url_template(view_name)


def _add_measure_for_siblings_url(options, entity_type):
    if entity_type == "practice":
        options["measureForSiblingsUrlTemplate"] = _url_template(
            "measure_for_practices_in_ccg"
        )


def _add_improvement_radar_url(options, entity_type):
    if entity_type in ["practice", "pcn"]:
        return
    # This is correct, and shouldn't be `+ f"{measure}"`, because we're going to do the
    # interpolation in JS.
    options["improvementRadarUrlTemplate"] = (
        _url_template("sicbl_improvement_radar") + "#{measure}"
    )


def _add_measure_url(options, entity_type):
    options["measureDefinitionUrlTemplate"] = _url_template("measure_definition")
    if entity_type == "practice":
        options["measureUrlTemplate"] = _url_template("measure_for_all_ccgs")
    # We're deliberately not showing a link to compare all PCNS for "political"
    # reasons
    elif entity_type != "pcn":
        options["measureUrlTemplate"] = _url_template(
            "measure_for_all_{}s".format(entity_type)
        )


def _build_api_url(view_name, params):
    path = reverse(view_name)
    querystring = urlencode(params)

    parsed_url = urlparse(settings.API_HOST)

    return urlunparse(
        (
            parsed_url.scheme,  # scheme
            parsed_url.netloc,  # host
            path,  # path
            "",  # params
            querystring,  # query
            "",  # fragment
        )
    )


def _build_global_measures_url(measure_id=None, measure_ids=None, tags=None):
    params = {"format": "json"}
    if measure_id is not None:
        params["measure"] = measure_id
    if measure_ids is not None:
        params["measure"] = ",".join(measure_ids)
    if tags is not None:
        params["tags"] = ",".join(tags)

    return _build_api_url("measure", params)


def _build_panel_measures_url(
    entity_type,
    entity_code=None,
    parent_org_type=None,
    measure_id=None,
    measure_ids=None,
    tags=None,
    aggregate=None,
):
    params = {"format": "json"}
    if entity_code is not None:
        params["org"] = entity_code
    if parent_org_type is not None:
        params["parent_org_type"] = parent_org_type
    if measure_id is not None:
        params["measure"] = measure_id
    if measure_ids is not None:
        params["measure"] = ",".join(measure_ids)
    if tags is not None:
        params["tags"] = ",".join(tags)
    if aggregate is not None:
        params["aggregate"] = aggregate

    return _build_api_url("measure_by_" + entity_type, params)


def _build_org_location_url(entity):
    params = {"org_type": _org_type_for_entity(entity), "q": entity.code}
    return _build_api_url("org_location", params)


def all_england_measure_savings(entity_type, date):
    return (
        MeasureValue.objects.filter_by_org_type(entity_type.lower())
        .filter(month=date)
        .exclude(measure_id="lpzomnibus")
        .aggregate_cost_savings()
    )


def all_england_low_priority_savings(entity_type, date):
    target_costs = MeasureGlobal.objects.get(
        month=date, measure_id="lpzomnibus"
    ).percentiles[entity_type.lower()]
    return (
        MeasureValue.objects.filter_by_org_type(entity_type.lower())
        .filter(month=date, measure_id="lpzomnibus")
        .calculate_cost_savings(target_costs)
    )


def all_england_low_priority_total(entity_type, date):
    result = (
        MeasureValue.objects.filter_by_org_type(entity_type.lower())
        .filter(month=date, measure_id="lpzomnibus")
        .aggregate(total=Sum("numerator"))
    )
    return result["total"]


def _get_entity(entity_type, entity_code):
    entity_type = entity_type.lower()

    if entity_type == "practice":
        return get_object_or_404(Practice, code=entity_code)
    elif entity_type == "pcn":
        return get_object_or_404(PCN, code=entity_code)
    elif entity_type == "ccg" or entity_type == "sicbl":
        return get_object_or_404(PCT, code=entity_code)
    elif entity_type == "stp" or entity_type == "icb":
        return get_object_or_404(STP, code=entity_code)
    elif entity_type == "regional_team":
        return get_object_or_404(RegionalTeam, code=entity_code)
    elif entity_type == "all_england":
        return None
    else:
        raise ValueError("Unknown entity_type: " + entity_type)


def _entity_type_human(entity_type):
    return {
        "practice": "practice",
        "pcn": "PCN",
        "ccg": "Sub-ICB Location",
        "stp": "ICB",
        "regional_team": "Regional Team",
    }[entity_type]
