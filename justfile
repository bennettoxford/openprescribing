set default-list
set dotenv-path := "environment"
set positional-arguments

app_service := "test"
db_service := "postgis"

_environment:
    #!/usr/bin/env bash
    set -euo pipefail

    if [[ ! -f "environment" ]]; then
        echo 'I did not find `environment`, so I will create it from `environment-sample`. Please edit `environment` and rerun the just recipe.'
        cp environment-sample environment
        exit 1
    fi

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

# Start the web app and database containers
start-docker:
    #!/usr/bin/env bash
    set -euo pipefail

    # Running the service will replace environment with environment-test, so we backup
    # and rotate environment. We also remove all containers (including dependant
    # containers) and volumes when this recipe exits to avoid accumulating them over
    # time.
    cleanup() {
        mv environment.bak environment
        docker compose down
    }
    trap 'cleanup' EXIT INT TERM
    cp environment environment.bak
    docker compose run --rm --service-ports dev

test *args: _environment db
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing
    uv run coverage run manage.py test "$@"

test-functional *args:
    #!/usr/bin/env bash
    set -euo pipefail

    check_status() {
        if [[ $? -ne 0 ]]; then
            echo 'Error: See TESTING.md for information about why this recipe might have failed.'
        fi
    }
    # Run check_status, even though we set -e (if a command fails, then exit Bash).
    trap 'check_status' EXIT INT TERM

    TEST_SUITE=functional {{ just_executable() }} test "$@"

test-nonfunctional *args:
    TEST_SUITE=nonfunctional {{ just_executable() }} test "$@"

_check-browserstacklocal-binary:
    #!/usr/bin/env bash
    set -euo pipefail

    if ! command -v BrowserStackLocal --version >/dev/null 2>&1; then
        echo 'Error: BrowserStackLocal was not found on your PATH.'
        echo 'You can download it from https://www.browserstack.com/docs/local-testing/releases-and-downloads'
        exit 1
    fi

@start-browserstacklocal: _check-browserstacklocal-binary
    # The force flag kills other instances of the BrowserStackLocal daemon with the same
    # local-identifier. At most, one instance should exist if a previous BrowserStack
    # recipe failed.
    @BrowserStackLocal \
    --daemon start \
    --force \
    --key "$BROWSERSTACK_ACCESS_KEY" \
    --local-identifier "$BROWSERSTACK_LOCAL_IDENTIFIER"

stop-browserstacklocal: _check-browserstacklocal-binary
    BrowserStackLocal --daemon stop --local-identifier "$BROWSERSTACK_LOCAL_IDENTIFIER"

_check-browser-env-var:
    #!/usr/bin/env bash
    set -euo pipefail

    # We can't pass BROWSER as a parameter with a default value, unfortunately, because
    # the first element in args would replace it. This behaviour is counter-intuitive,
    # and may be a bug: there are examples in other justfiles where we don't expect it.
    if [[ -z "${BROWSER:-}" ]]; then
        echo "Error: BROWSER is not set or is empty." >&2
        exit 1
    fi

test-browserstack-functional *args: _check-browser-env-var start-browserstacklocal && stop-browserstacklocal
    USE_BROWSERSTACK=1 {{ just_executable() }} test-functional "$@"

test-docker-browserstack-functional: _check-browser-env-var start-browserstacklocal && stop-browserstacklocal
    # USE_BROWSERSTACK isn't passed to the service, but GITHUB_ACTIONS is. Either is
    # used to determine whether the functional tests are run with the BrowserStack local
    # agent (openprescribing.frontend.tests.functional.selenium_base.use_browserstack).
    GITHUB_ACTIONS=1 {{ just_executable() }} test-docker-functional

test-docker: _environment
    #!/usr/bin/env bash
    set -euo pipefail

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

assets-install:
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing/media/js
    npm install -g browserify
    npm install -g jshint
    npm install -g less
    npm install

assets-build:
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing/media/js
    npm run build

db:
    docker compose up --detach --wait {{ db_service }}

# Remove an existing database container, and its associated network and volume
@db-clean:
    # need not depend on db, because a down without a previous up is a no-op
    @docker compose down --volumes {{ db_service }}

db-shell: db
    docker compose exec {{ db_service }} psql --username user openprescribing-test

# Build the base and test images
[confirm("This will remove the existing base and test images. Do you wish to continue? (y/n)")]
build-images:
    #!/usr/bin/env bash
    set -euxo pipefail

    base_image=ghcr.io/bennettoxford/openprescribing-py312-base:latest
    test_image=ghcr.io/bennettoxford/openprescribing-py312-test:latest

    # First, remove the existing images, if they exist. We want to be sure that we're
    # building the new test image on the new base image, and not on the old base image.
    for image in "$base_image" "$test_image"; do
        if docker image inspect "$image" >/dev/null 2>&1; then
            docker image rm "$image"
        fi
    done

    # Now, build the images. We use `buildx build` rather than `compose build`, because
    # the services are missing build configurations. The dot sets the build context to
    # the current directory.

    # Build the new base image. This corresponds to the test-production service.
    docker buildx build --file Dockerfile --tag "$base_image" .

    # Build the new test image. This corresponds to the test service.
    docker buildx build --file Dockerfile-test --tag "$test_image" .

# Push the base and test images to GHCR
[confirm("This will push the base and test images to GHCR. Do you wish to continue? (y/n)")]
push-images:
    docker image push ghcr.io/bennettoxford/openprescribing-py312-base:latest
    docker image push ghcr.io/bennettoxford/openprescribing-py312-test:latest
