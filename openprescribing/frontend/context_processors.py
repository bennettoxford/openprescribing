import logging
from urllib.parse import quote

from django.conf import settings

logger = logging.getLogger(__name__)


def support_email(request):
    path = request.get_full_path()
    if path.strip("/"):
        page_hint = f" ({path})"
    else:
        page_hint = ""
    subject = f"OpenPrescribing Feedback{page_hint}:"
    return {
        "SUPPORT_TO_EMAIL": settings.SUPPORT_TO_EMAIL,
        "SUPPORT_FROM_EMAIL": settings.SUPPORT_FROM_EMAIL,
        "FEEDBACK_MAILTO": f"{settings.SUPPORT_TO_EMAIL}?subject={quote(subject)}",
    }


def api_host(request):
    return {"API_HOST": settings.API_HOST}


def debug(request):
    return {"DEBUG": settings.DEBUG}


def google_tracking_id(request):
    tracking_id = None
    container_id = None
    if "PhantomJS" in request.META.get("HTTP_USER_AGENT", ""):
        # Google's JavaScript breaks the ancient JS engine in PhantomJS which we use for
        # taking screenshots of charts (plus I'm not sure we want analytics to be
        # running in this case anyway)
        pass
    elif hasattr(settings, "GOOGLE_TRACKING_ID"):
        tracking_id = settings.GOOGLE_TRACKING_ID
        container_id = getattr(settings, "GOOGLE_OPTIMIZE_CONTAINER_ID", "")
    else:
        logger.warn("No GOOGLE_TRACKING_ID set")
    return {
        "GOOGLE_TRACKING_ID": tracking_id,
        "GOOGLE_OPTIMIZE_CONTAINER_ID": container_id,
    }


def source_commit_id(request):
    return {"SOURCE_COMMIT_ID": getattr(settings, "SOURCE_COMMIT_ID", None)}
