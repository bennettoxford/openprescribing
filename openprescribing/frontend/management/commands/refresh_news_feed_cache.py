import datetime

import requests
from django.core.cache import cache
from django.core.management.base import BaseCommand

FEED_URL = "https://www.bennett.ox.ac.uk/blog/index.json"


class Command(BaseCommand):
    help = f"Fetch and cache news items from:\n{FEED_URL}"

    def handle(self, *args, **options):
        response = requests.get(FEED_URL)
        response.raise_for_status()
        feed_data = response.json()
        items = [
            format_news_item(**item)
            for item in feed_data["posts"]
            if is_openprescribing_news_item(**item)
        ]
        cache.set("news_feed", items, timeout=60 * 60 * 24 * 365)


def is_openprescribing_news_item(*, categories, tags, **kwargs):
    if not categories or "OpenPrescribing" not in categories:
        return False
    if not tags or "news" not in tags:
        return False
    return True


def format_news_item(*, date, **kwargs):
    return {
        "date": datetime.datetime.fromisoformat(date),
        **kwargs,
    }
