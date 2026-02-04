import os

import dotenv

from .notify_deploy import notify_slack

if __name__ == "__main__":
    env_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "environment"
    )
    dotenv.read_dotenv(env_path, override=True)

    notify_slack("An OpenPrescribing restart just finished.")
