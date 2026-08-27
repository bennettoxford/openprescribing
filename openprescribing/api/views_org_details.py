from django.db.models import Q
from frontend.models import PCN, PCT, STP, Practice, RegionalTeam
from matrixstore.db import get_db, get_row_grouper
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from . import view_utils as utils

ALLOWED_QUERY_PARAMS = {"format", "keys", "org", "org_type"}

STATS_COLUMN_WHITELIST = (
    "total_list_size",
    "astro_pu_items",
    "astro_pu_cost",
    "nothing",
)


class KeysNotValid(APIException):
    status_code = 400
    default_detail = "The keys you provided are not supported"


class QueryParamsNotValid(APIException):
    status_code = 400
    default_detail = "The query parameters you provided are not supported"


@api_view(["GET"])
def org_details(request, format=None):
    """
    Get list size and ASTRO-PU by month, for CCGs or practices.
    """
    _validate_query_params(request.query_params)
    org_type = request.GET.get("org_type", None)
    org_type = utils.translate_org_type(org_type)
    keys = utils.param_to_list(request.query_params.get("keys", []))
    org_codes = utils.param_to_list(request.query_params.get("org", []))
    if org_type is None:
        org_type = "all_practices"
    orgs = _get_orgs(org_type, org_codes)
    data = _get_practice_stats_entries(keys, org_type, orgs)
    return Response(list(data))


def _validate_query_params(query_params):
    invalid_params = sorted(set(query_params) - ALLOWED_QUERY_PARAMS)
    if not invalid_params:
        return

    if len(invalid_params) == 1:
        detail = f"{invalid_params[0]} is not a valid query parameter"
    else:
        detail = f"{', '.join(invalid_params)} are not valid query parameters"
    raise QueryParamsNotValid(detail)


def _get_orgs(org_type, org_codes):
    if org_type == "practice":
        orgs = Practice.objects.order_by("code").only("code", "name")
        if org_codes:
            orgs = orgs.filter(Q(code__in=org_codes) | Q(ccg_id__in=org_codes))
    elif org_type == "ccg":
        orgs = PCT.objects.filter(org_type="CCG").order_by("code").only("code", "name")
        if org_codes:
            orgs = orgs.filter(code__in=org_codes)
    elif org_type == "pcn":
        orgs = PCN.objects.order_by("code").only("code", "name")
        if org_codes:
            orgs = orgs.filter(
                Q(code__in=org_codes) | Q(practice__ccg_id__in=org_codes)
            )
            orgs = orgs.distinct("code")
    elif org_type == "stp":
        orgs = STP.objects.order_by("code").only("code", "name")
        if org_codes:
            orgs = orgs.filter(code__in=org_codes)
    elif org_type == "regional_team":
        orgs = RegionalTeam.objects.order_by("code").only("code", "name")
        if org_codes:
            orgs = orgs.filter(code__in=org_codes)
    elif org_type == "all_practices":
        orgs = []
    else:
        raise ValueError("Unknown org_type: {}".format(org_type))
    return orgs


def _get_practice_stats_entries(keys, org_type, orgs):
    db = get_db()
    practice_stats = db.query(*_get_query_and_params(keys))
    group_by_org = get_row_grouper(org_type)
    practice_stats = [
        (name, group_by_org.sum(matrix)) for (name, matrix) in practice_stats
    ]
    # `group_by_org.offsets` maps each organisation's primary key to its row
    # offset within the matrices. We pair each organisation with its row
    # offset, ignoring those organisations which aren't in the mapping (which
    # implies that we have no statistics for them)
    org_offsets = [
        (org, group_by_org.offsets[org.pk])
        for org in orgs
        if org.pk in group_by_org.offsets
    ]
    # For the "all_practices" grouping we have no orgs and just a single row
    if org_type == "all_practices":
        org_offsets = [(None, 0)]
    date_offsets = sorted(db.date_offsets.items())
    # Yield entries for each organisation on each date
    for date, col_offset in date_offsets:
        for org, row_offset in org_offsets:
            entry = {"date": date}
            if org is not None:
                entry["row_id"] = org.pk
                entry["row_name"] = org.name
            index = (row_offset, col_offset)
            star_pu = {}
            has_value = False
            for name, matrix in practice_stats:
                value = matrix[index]
                if value != 0:
                    has_value = True
                if isinstance(value, float):
                    value = round(value, 2)
                if name.startswith("star_pu."):
                    star_pu[name[8:]] = value
                else:
                    entry[name] = value
            if star_pu:
                entry["star_pu"] = star_pu
            # The special "nothing" key always takes the value 1
            if "nothing" in keys:
                entry["nothing"] = 1
                has_value = True
            if has_value:
                yield entry


def _get_query_and_params(keys):
    params = []
    for key in keys:
        if key == "nothing":
            # "nothing" is a special key which always has the value 1
            pass
        elif key in STATS_COLUMN_WHITELIST or key.startswith("star_pu."):
            params.append(key)
        else:
            raise KeysNotValid("%s is not a valid key" % key)
    if keys:
        # `params` might be empty here because the only key supplied was
        # "nothing", but that's fine: the empty IN clause won't match any rows,
        # which is what we want
        where = "name IN ({})".format(",".join("?" * len(params)))
    else:
        # If no keys are supplied we treat this as an implicit "select all"
        where = "1=1"
    query = "SELECT name, value FROM practice_statistic WHERE {}".format(where)
    return query, params
