import requests
from django.conf import settings


def notify_slack(message, is_error=False, channel="default"):
    """Posts the message to #technoise by default

    See https://my.slack.com/services/new/incoming-webhook/
    """
    if not settings.SLACK_SENDING_ACTIVE:
        return

    webhooks = {
        "default": settings.SLACK_TECHNOISE_POST_KEY,
        "op": settings.SLACK_OP_POST_KEY,
    }
    webhook_url = webhooks.get(channel, webhooks["default"])
    slack_data = {"text": message}

    response = requests.post(webhook_url, json=slack_data)
    if is_error and channel != "op":
        # Also post error messages to OP channel
        response = requests.post(webhooks["op"], json=slack_data)

    if response.status_code != 200:
        raise ValueError(
            "Request to slack returned an error %s, the response is:\n%s"
            % (response.status_code, response.text)
        )
