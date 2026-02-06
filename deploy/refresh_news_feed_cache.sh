#!/bin/bash
. /webapps/openprescribing/.venv/bin/activate
# This was recently observed failing & running for 11 days.
# Our cronjob currently re-runs it every 5mins, and it's safe to kill it,
# so let's add `timeout` as an insurance policy.
timeout 4m python /webapps/openprescribing/openprescribing/manage.py refresh_news_feed_cache
