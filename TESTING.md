# Testing

There are two types of test: functional and non-functional.

## Functional tests

The functional tests use Selenium to make requests to a [Django live server][].
They can be run locally or in a container,
with or without BrowserStackLocal (see below).
BrowserStackLocal is always run in a container.
Let's consider the four cases.
The functional tests can be run:

* locally with BrowserStackLocal: `just test-browserstack-functional`
  The functional tests are run against the web browser given by `BROWSER` (see below).
* in a container with BrowserStackLocal: `just docker-test-browserstack-functional`
  The functional tests are run against the web browser given by `BROWSER` (see below).
* locally without BrowserStackLocal: `just test-functional`
  The functional tests are run against the local Firefox web browser.
* in a container without BrowserStackLocal: `just docker-test-functional`
  The functional tests are run against the container's Firefox web browser.

Of these, the "in a container with BrowserStackLocal" case is how the functional tests are run in CI.

### BrowserStackLocal

[BrowserStackLocal][] is BrowserStack's local agent.
It sits between a Django live server and BrowserStackCloud.
See "[How Local Testing works][]" for more information about BrowserStackLocal,
including useful and interesting infrastructure and data flow diagrams.

To run the functional tests with BrowserStackLocal:

* sign in to <https://www.browserstack.com/> with Google;
* register for the open source program at <https://www.browserstack.com/open-source>;
* copy your username and access key from the settings page;
* paste your username and access key into a `.env` file:

  ```sh
  BROWSERSTACK_USERNAME=
  BROWSERSTACK_ACCESS_KEY=
  ```

You may wish to set `BROWSER` in the `.env` file,
where `BROWSER` is of the form `<browser name>:<browser version>:<OS name>:<OS version>`.
For example:

* `'Edge:latest:Windows:10'`
* `'Firefox:latest:OS X:Catalina'`

See the "[Select browsers and devices][]" page for values.
See `.github/workflows/main.yml` for values used in CI.

[BrowserStackLocal]: https://www.browserstack.com/docs/automate/selenium/local-testing-introduction?fw-lang=python
[Django live server]: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#django.test.LiveServerTestCase
[How Local Testing works]: https://www.browserstack.com/docs/local-testing/how-local-testing-works
[Select browsers and devices]: https://www.browserstack.com/docs/automate/selenium/select-browsers-and-devices

### Running the functional tests locally with BrowserStackLocal

Running the functional tests locally with BrowserStackLocal uses *host mode networking*,
a networking mode where a container,
in this case the container running BrowserStackLocal,
shares the host machine's network namespace.

On a Linux machine, the host machine *is* the Linux machine.
The functional tests and the container running BrowserStackLocal use the same network namespace.
The functional tests execute correctly.

On a macOS machine, the host machine isn't the macOS machine;
the host machine is a Linux virtual machine running on the macOS machine.
The functional tests use the macOS machine's network namespace and
the container running BrowserStackLocal uses the Linux virtual machine's network namespace.
The functional tests don't execute correctly.

Some container runtimes support Linux-like host mode networking on macOS.
As of November 2026, these include:

* [Docker Desktop][] v4.34 and later, but not by default
* [OrbStack][] v0.7.0 and later

See the "[Host network driver][]" page
for more information about enabling host mode networking in Docker Desktop.

Some, unfortunately, don't.
As of November 2026, these include:

* [Colima][]

[Colima]: https://colima.run/
[Docker Desktop]: https://www.docker.com/products/docker-desktop/
[Host network driver]: https://docs.docker.com/engine/network/drivers/host/
[OrbStack]: https://orbstack.dev/

## Non-functional tests

The non-functional tests can be run locally or in a container:

* locally: `just test-nonfunctional`
* in a container: `just docker-test-nonfunctional`

Of these, the "in a container" case is how the non-functional tests are run in CI.

The non-functional tests are a mix of fast unit tests and slow integration tests,
which access BigQuery and Google Cloud Storage.

To run the integration tests:

* install the [Google Cloud Command Line Interface][] (gcloud CLI)
* authenticate: `gcloud auth application-default login`
* set the billing and quota project: `gcloud auth application-default set-quota-project ebmdatalabtest`

To run only the unit tests:

```sh
just test-nonfunctional --exclude-tag integration
```

To run only the integration tests:

```sh
just test-nonfunctional --tag integration
```

It's possible to be more selective by passing any number of [test labels][] to `test-nonfunctional`.

[Google Cloud Command Line Interface]: https://cloud.google.com/cli
[test labels]: https://docs.djangoproject.com/en/stable/topics/testing/overview/#running-tests
