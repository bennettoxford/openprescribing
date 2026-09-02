set default-list
set dotenv-load

browserstacklocal_service := "browserstacklocal"
dev_service := "dev"
postgis_service := "postgis"
test_service := "test"

# These just variables are exported to recipes as environment variables. The values of
# the DB_* just/environment variables come from the postgis service (see
# docker-compose.yml).
export BROWSERSTACK_BUILD_NAME := ""
export BROWSERSTACK_LOCAL_IDENTIFIER := ""
export BROWSERSTACK_PROJECT_NAME := ""
export DB_NAME := "openprescribing-test"
export DB_PASS := "pass"
export DB_USER := "user"
export DJANGO_SETTINGS_MODULE := "openprescribing.settings.local"
export MAILGUN_API_KEY := "mailgun_api_key"
export MAILGUN_WEBHOOK_PASS := "mailgun_webhook_pass"
export MAILGUN_WEBHOOK_USER := "mailgun_webhook_user"
export SECRET_KEY := "secret_key"

# Remove an existing virtual environment
clean:
    uv venv --clear

# Run the code quality checks but don't modify any files
check:
    ./scripts/lint.sh

# Install development requirements into the virtual environment
devenv:
    echo 'pip' | uv pip sync - requirements.txt requirements.dev.txt

compile-requirements:
    uv run pip-compile --upgrade --no-header requirements.in

compile-dev-requirements:
    uv run pip-compile --upgrade --no-header requirements.dev.in

# Run `manage.py`
manage *args: db
    uv run openprescribing/manage.py {{ args }}

# Run `manage.py migrate`
migrate *args:
    {{ just_executable() }} manage migrate {{ args }}

# Run `manage.py runserver`
run *args:
    {{ just_executable() }} manage runserver {{ args }}

# Start the web app and database containers
start-docker:
    #!/usr/bin/env bash
    set -euo pipefail

    # Unlike `up`, `run` doesn't create the ports that are specified by
    # docker-compose.yml by default. These ports are needed for connecting to the Django
    # development web server, so we pass `--service-ports` to create them.
    docker compose run --rm --service-ports {{ dev_service }}

# Run the tests (see TESTING.md)
test *args: db
    #!/usr/bin/env bash
    set -euo pipefail

    export DJANGO_SETTINGS_MODULE=openprescribing.settings.test
    export GOOGLE_APPLICATION_CREDENTIALS=google-credentials.json
    cd openprescribing
    uv run coverage run manage.py test {{ args }}

# Run the functional tests (see TESTING.md)
test-functional *args:
    TEST_SUITE=functional {{ just_executable() }} test {{ args }}

# Run the non-functional tests (see TESTING.md)
test-nonfunctional *args:
    TEST_SUITE=nonfunctional {{ just_executable() }} test {{ args }}

# Start BrowserStack's local agent (see TESTING.md)
browserstacklocal:
    docker compose up --detach --wait {{ browserstacklocal_service }}

# Run the functional tests using BrowserStack's local agent (see TESTING.md)
test-browserstack-functional *args: browserstacklocal
    USE_BROWSERSTACK=1 {{ just_executable() }} test-functional {{ args }}

# Run the functional tests in a container using BrowserStack's local agent (see TESTING.md)
test-docker-browserstack-functional:
    USE_BROWSERSTACK=1 {{ just_executable() }} test-docker-functional

# Run the tests in a container (see TESTING.md)
test-docker:
    docker compose run --rm {{ test_service }}

# Run the functional tests in a container (see TESTING.md)
test-docker-functional:
    TEST_SUITE=functional {{ just_executable() }} test-docker

# Run the non-functional tests in a container (see TESTING.md)
test-docker-nonfunctional:
    TEST_SUITE=nonfunctional {{ just_executable() }} test-docker

# Install the Node.js dependencies
assets-install:
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing/media/js
    npm install -g browserify
    npm install -g jshint
    npm install -g less
    npm install

# Build the Node.js assets
assets-build:
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing/media/js
    npm run build

# Start the database container
db:
    docker compose up --detach --wait {{ postgis_service }}

# Remove an existing database container, and its associated network and volume
@db-clean:
    # need not depend on db, because a down without a previous up is a no-op
    @docker compose down --volumes {{ postgis_service }}

# Access a database shell running inside the database container
db-shell: db
    docker compose exec {{ postgis_service }} bash -c 'psql --username "$POSTGRES_USER" "$POSTGRES_DB"'

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
