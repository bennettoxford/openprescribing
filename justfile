set default-list
set dotenv-path := "environment"
set positional-arguments

app_service := "test"
db_service := "db-test"

clean:
    uv venv --clear

check:
    ./scripts/lint.sh

devenv:
    uv pip sync requirements.txt requirements.dev.txt

manage *args:
    uv run openprescribing/manage.py "$@"

migrate *args:
    {{ just_executable() }} manage migrate "$@"

run *args:
    {{ just_executable() }} manage runserver "$@"

test *args:
    #!/usr/bin/env bash
    set -euxo pipefail

    cd openprescribing
    SKIP_NPM_BUILD=1 uv run coverage run manage.py test "$@"

test-functional *args:
    TEST_SUITE=functional {{ just_executable() }} test "$@"

test-nonfunctional *args:
    TEST_SUITE=nonfunctional {{ just_executable() }} test "$@"

start-browserstacklocal:
    BrowserStackLocal --key "$BROWSERSTACK_ACCESS_KEY" --local-identifier "$BROWSERSTACK_LOCAL_IDENTIFIER"

test-browserstack-functional *args:
    #!/usr/bin/env bash
    set -euxo pipefail

    # We can't pass BROWSER as a parameter with a default value, unfortunately, because
    # the first element in args would replace it. This behaviour is counter-intuitive,
    # and may be a bug: there are examples in other justfiles where we don't expect it.
    if [[ -z "${BROWSER:-}" ]]; then
        echo "Error: BROWSER is not set or is empty" >&2
        exit 1
    fi

    USE_BROWSERSTACK=1 {{ just_executable() }} test-functional "$@"

test-docker:
    #!/usr/bin/env bash
    set -euxo pipefail

    # Running the service will replace environment with environment-test, so we backup
    # and rotate environment.
    cp environment environment.bak
    trap 'mv environment.bak environment' EXIT INT TERM

    docker compose run --rm {{ app_service }}

test-docker-functional:
    TEST_SUITE=functional {{ just_executable() }} test-docker

test-docker-nonfunctional:
    TEST_SUITE=nonfunctional {{ just_executable() }} test-docker

assets-build:
    #!/usr/bin/env bash
    set -euxo pipefail

    cd openprescribing/media/js
    npm run build

db:
    docker compose up --detach --wait {{ db_service }}

db-clean:
    docker compose down --volumes {{ db_service }}

db-shell:
    docker compose exec {{ db_service }} psql --username user openprescribing-test
