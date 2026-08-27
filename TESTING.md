# Testing

There are two types of test: functional and non-functional.

## Functional tests

The functional tests use Selenium to make requests to a [Django live server][].
They can be run locally (the host system) or in a container (the guest system),
with or without BrowserStackLocal (see below).
Let's consider the four cases.
Functional tests can be run:

* locally with BrowserStackLocal: `just test-browserstack-functional`
* in a container with BrowserStackLocal: `just test-docker-browserstack-functional`
* locally without BrowserStackLocal: `just test-functional`
* in a container without BrowserStackLocal: `just test-docker-functional`

Of these, the "in a container with BrowserStackLocal" case is how functional tests are run in CI.

### BrowserStackLocal

[BrowserStackLocal][] is BrowserStack's local agent.
It sits between a Django live server and BrowserStackCloud.

To run the functional tests with BrowserStackLocal:

* sign in to <https://www.browserstack.com/> with Google;
* register for the open source program at <https://www.browserstack.com/open-source>;
* copy your username and access key from the Settings page;
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

See the "[Select browsers and devices][]" page in the BrowserStack documentation for values.
See `.github/workflows/main.yml` for values used in CI.

### Django live server and `0.0.0.0`

The functional tests use `SeleniumTestCase`, which inherits from `LiveServerTestCase`.
`LiveServerTestCase` starts a [Django live server][] on setup and stops it on teardown.
`LiveServerTestCase.host` is used as a server bind address *and* as a client destination address.
By default, `LiveServerTestCase.host` is `localhost`.
However, `SeleniumTestCase.host` is `0.0.0.0`.

When used as a server bind address, `0.0.0.0` means "all local interfaces".
When used as a client destination address, `0.0.0.0` is invalid.
However, it's important to know that:

* on some systems, requests to connect to `0.0.0.0` are treated as requests to connect to `localhost`,
  if a server is bound on the system.
* BrowserStackLocal seems to do the same.
* a server should bind to `0.0.0.0` in a container,
  such that it can be easily reached from the host system.

Let's consider the four cases again.
Functional tests can be run:

* locally with BrowserStackLocal.
  Either the system or BrowserStackLocal maps `0.0.0.0` to `localhost`.
  A connection is established.
* in a container with BrowserStackLocal.
  As above.
  A connection is established.
* locally without BrowserStackLocal.
  The system may or may not map `0.0.0.0` to `localhost`.
  A connection may or may not be established.
* in a container without BrowserStackLocal.
  As above, remembering that "local" means "local to the container",
  rather than "local to the host system".
  A connection may or may not be established.

Relying on either the system or BrowserStackLocal to map `0.0.0.0` to `localhost` is unwise,
but not doing so means modifying the functional tests.

[BrowserStackLocal]: https://www.browserstack.com/docs/automate/selenium/local-testing-introduction?fw-lang=python
[Django live server]: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#django.test.LiveServerTestCase
[Select browsers and devices]: https://www.browserstack.com/docs/automate/selenium/select-browsers-and-devices
