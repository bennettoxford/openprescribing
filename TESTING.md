# Testing

There are two types of test: functional and non-functional.

## Functional tests

The functional tests use Selenium to make requests to a [Django live server][].
They can be run locally (the host system) or in a container (the guest system),
with or without BrowserStackLocal (see below).
BrowserStackLocal is always run in a container.
Let's consider the four cases.
Functional tests can be run:

* locally with BrowserStackLocal: `just test-browserstack-functional`
  The functional tests are run against the web browser given by `BROWSER` (see below).
* in a container with BrowserStackLocal: `just test-docker-browserstack-functional`
  The functional tests are run against the web browser given by `BROWSER` (see below).
* locally without BrowserStackLocal: `just test-functional`
  The functional tests are run against the local Firefox web browser.
* in a container without BrowserStackLocal: `just test-docker-functional`
  The functional tests are run against the container's Firefox web browser.

Of these, the "in a container with BrowserStackLocal" case is how functional tests are run in CI.

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
