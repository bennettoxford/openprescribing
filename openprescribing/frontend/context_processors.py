from urllib.parse import quote

from django.conf import settings


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


def source_commit_id(request):
    return {"SOURCE_COMMIT_ID": getattr(settings, "SOURCE_COMMIT_ID", None)}
