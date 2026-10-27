"""Wait up to 30 seconds for postgres to be available.

This is useful when running in docker, as the first time we create a
postgres volume it takes a few seconds to become ready.

"""

import os
import time

import dotenv
import psycopg2

if __name__ == "__main__":
    env_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "environment"
    )

    dotenv.read_dotenv(env_path)
    elapsed = 0
    while elapsed < 30:
        try:
            psycopg2.connect(
                host=os.environ["DB_HOST"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASS"],
                database=os.environ["DB_NAME"],
            )
            break
        except psycopg2.OperationalError:
            if elapsed == 0:
                print("Waiting for postgres to start...")
            time.sleep(1)
            elapsed += 1
