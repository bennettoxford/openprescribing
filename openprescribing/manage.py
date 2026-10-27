#!/usr/bin/env python
import os
import re
import sys

import dotenv

if __name__ == "__main__":
    # We can't do read_dotenv('../environment') because that assumes that when
    # manage.py we are in its current directory, which isn't the case for cron
    # jobs.
    env_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "environment"
    )

    dotenv.read_dotenv(env_path, override=True)

    if len(sys.argv) > 1:
        if sys.argv[1] == "test" or re.match(r"generate_\w+_fixtures", sys.argv[1]):
            os.environ["DJANGO_SETTINGS_MODULE"] = "openprescribing.settings.test"
        elif sys.argv[1] == "run_pipeline_e2e_tests":
            os.environ["DJANGO_SETTINGS_MODULE"] = "openprescribing.settings.e2etest"

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
