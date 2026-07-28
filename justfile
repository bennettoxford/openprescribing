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

manage *args: db
    uv run openprescribing/manage.py "$@"

migrate *args:
    {{ just_executable() }} manage migrate "$@"

run *args:
    {{ just_executable() }} manage runserver "$@"

test *args: db
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

_BROWSER:
    #!/usr/bin/env bash
    set -euxo pipefail

    # We can't pass BROWSER as a parameter with a default value, unfortunately, because
    # the first element in args would replace it. This behaviour is counter-intuitive,
    # and may be a bug: there are examples in other justfiles where we don't expect it.
    if [[ -z "${BROWSER:-}" ]]; then
        echo "Error: BROWSER is not set or is empty" >&2
        exit 1
    fi

test-browserstack-functional *args: _BROWSER
    USE_BROWSERSTACK=1 {{ just_executable() }} test-functional "$@"

test-docker-browserstack-functional: _BROWSER
    # USE_BROWSERSTACK isn't passed to the service, but GITHUB_ACTIONS is. Either is
    # used to determine whether the functional tests are run with the BrowserStack local
    # agent (openprescribing.frontend.tests.functional.selenium_base.use_browserstack).
    GITHUB_ACTIONS=1 {{ just_executable() }} test-docker-functional

test-docker:
    #!/usr/bin/env bash
    set -euxo pipefail

    # Running the service will replace environment with environment-test, so we backup
    # and rotate environment.
    cp environment environment.bak
    trap 'mv environment.bak environment' EXIT INT TERM

    # Unlike `up`, `run` doesn't create the ports that are specified by
    # docker-compose.yml by default. These ports are needed for running the functional
    # tests with the BrowserStack local agent, so we pass `--service-ports` to create
    # them.
    docker compose run --rm --service-ports {{ app_service }}

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
    # need not depend on db, because a down without a previous up is a no-op
    docker compose down --volumes {{ db_service }}

db-shell: db
    docker compose exec {{ db_service }} psql --username user openprescribing-test
