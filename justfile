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
export BROWSERSTACK_PROJECT_NAME := ""
export DB_NAME := "openprescribing-test"
export DB_PASS := "pass"
export DB_USER := "user"
export DJANGO_SETTINGS_MODULE := "openprescribing.settings.local"
export MAILGUN_API_KEY := "mailgun_api_key"
export MAILGUN_WEBHOOK_PASS := "mailgun_webhook_pass"
export MAILGUN_WEBHOOK_USER := "mailgun_webhook_user"
export SECRET_KEY := "secret_key"

# Local recipes
# --------------------------------------------------------------------------------------

# Clear an existing, or create a new, virtual environment
clear:
    uv venv --clear

# Run the code quality checks but don't modify any files
check: devenv _check-docker-compose
    ./scripts/lint.sh

_check-docker-compose:
    docker compose config --quiet

# Install development requirements into the virtual environment
devenv: clear
    uv pip sync requirements.txt requirements.dev.txt

_compile-requirements extension:
    uv pip compile \
      --quiet \
      --upgrade \
      --no-header \
      --unsafe-package setuptools \
      --no-strip-extras \
      --output-file requirements{{ extension }}.txt requirements{{ extension }}.in

# Compile (but don't install) requirements for the production environment
compile-prod-requirements: (_compile-requirements "")

# Compile (but don't install) requirements for the development environment
compile-dev-requirements: (_compile-requirements ".dev")

# Run `manage.py`
manage *args: db devenv
    uv run openprescribing/manage.py {{ args }}

# Run `manage.py migrate`
migrate *args:
    {{ just_executable() }} manage migrate {{ args }}

# Run `manage.py runserver`
run *args:
    {{ just_executable() }} manage runserver {{ args }}

# Run with Gunicorn for development and testing
[env("DJANGO_SETTINGS_MODULE", "openprescribing.settings.production")]
[env("GUNICORN_LOG_LEVEL", "info")]
[env("GUNICORN_NUM_WORKERS", "1")]
[env("GUNICORN_TIMEOUT", "30")]
[env("OTEL_EXPORTER_OTLP_ENDPOINT", "https://api.honeycomb.io")]
[env("PORT", "8000")]
[env("VIRTUALENV_PATH", ".venv")]
run-gunicorn: db
    bin/gunicorn_start

# Run the tests (see TESTING.md)
[env("DJANGO_SETTINGS_MODULE", "openprescribing.settings.test")]
[group("Testing")]
test *args: db devenv
    cd openprescribing && uv run coverage run manage.py test {{ args }}

# Run the functional tests (see TESTING.md)
[env("TEST_SUITE", "functional")]
[group("Testing")]
test-functional *args:
    {{ just_executable() }} test {{ args }}

# Run the non-functional tests (see TESTING.md)
[env("TEST_SUITE", "nonfunctional")]
[group("Testing")]
test-nonfunctional *args:
    {{ just_executable() }} test {{ args }}

# Run the functional tests using BrowserStack's local agent (see TESTING.md)
[env("USE_BROWSERSTACK", "1")]
[group("Testing")]
test-browserstack-functional *args: browserstacklocal
    BROWSERSTACK_LOCAL_IDENTIFIER={{ env("BROWSERSTACK_LOCAL_IDENTIFIER", "") }} \
    {{ just_executable() }} test-functional {{ args }}

# Install the Node.js dependencies
[group("Assets")]
assets-install:
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing/media/js
    npm install -g browserify
    npm install -g jshint
    npm install -g less
    npm install

# Build the Node.js assets
[group("Assets")]
assets-build:
    #!/usr/bin/env bash
    set -euo pipefail

    cd openprescribing/media/js
    npm run build

# Docker recipes
# --------------------------------------------------------------------------------------

# Start the database container
[group("Services")]
db:
    docker compose up --detach --wait {{ postgis_service }}

# Remove an existing database container, and its associated network and volume
[group("Services")]
@db-clean:
    # need not depend on db, because a down without a previous up is a no-op
    @docker compose down --volumes {{ postgis_service }}

# Access a database shell running inside the database container
[group("Services")]
db-shell: db
    docker compose exec {{ postgis_service }} bash -c 'psql --username "$POSTGRES_USER" "$POSTGRES_DB"'

# Start BrowserStack's local agent (see TESTING.md)
[group("Services")]
browserstacklocal:
    docker compose up --detach --wait {{ browserstacklocal_service }}

# Start a development container
docker-devenv:
    # Unlike `up`, `run` doesn't create the ports that are specified by
    # docker-compose.yml by default. These ports are needed for connecting to the Django
    # development web server, so we pass `--service-ports` to create them.
    docker compose run --rm --service-ports {{ dev_service }}

# Run the tests in a container (see TESTING.md)
[group("Testing")]
docker-test:
    #!/usr/bin/env bash
    set -euxo pipefail

    # The test service expects credentials for BigQuery/GCS to be in
    # /code/google-credentials.json on the guest, which maps to google-credentials.json
    # on the host. We're not going to change this, at least not now. When running
    # locally, however, we don't want a user to copy credentials and we don't want
    # google-credentials.json to remain on the host for longer than necessary, for fear
    # of them ending up in Git or an image.
    DST_ADC_PATH=google-credentials.json
    if [[ -f "$DST_ADC_PATH" ]]; then
        # We're probably running in CI.
        echo "Using credentials in $DST_ADC_PATH"
    else
        # We're probably running locally.
        SRC_ADC_PATH="$(gcloud info --format='value(config.paths.global_config_dir)')/application_default_credentials.json"
        echo "Copying credentials from $SRC_ADC_PATH to $DST_ADC_PATH"
        trap 'rm "$DST_ADC_PATH"' EXIT INT TERM
        cp $SRC_ADC_PATH $DST_ADC_PATH
    fi

    docker compose run --rm --quiet-pull {{ test_service }}

# Run the functional tests in a container (see TESTING.md)
[env("TEST_SUITE", "functional")]
[group("Testing")]
docker-test-functional:
    {{ just_executable() }} docker-test

# Run the non-functional tests in a container (see TESTING.md)
[env("TEST_SUITE", "nonfunctional")]
[group("Testing")]
docker-test-nonfunctional:
    {{ just_executable() }} docker-test

# Run the functional tests in a container using BrowserStack's local agent (see TESTING.md)
[env("USE_BROWSERSTACK", "1")]
[group("Testing")]
docker-test-browserstack-functional:
    {{ just_executable() }} docker-test-functional

# Build the base and test images
[confirm("This will remove the existing base and test images. Do you wish to continue? (y/n)")]
[group("Images")]
docker-build-images:
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
[group("Images")]
docker-push-images:
    docker image push ghcr.io/bennettoxford/openprescribing-py312-base:latest
    docker image push ghcr.io/bennettoxford/openprescribing-py312-test:latest
