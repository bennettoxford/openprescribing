import os
import subprocess

from django.conf import settings
from django.test.runner import DiscoverRunner
from frontend.tests.functional.mock_api_server import MockApiServer


class AssetBuildingTestRunner(DiscoverRunner):
    """A custom test runner, to support:

    * Building JS and CSS assets when running functional tests
    * Only running functional tests when TEST_SUITE environment says so
    * Custom settings to support running in Browserstack
    * Starting a mock API server
    """

    # We must run the test server on a port supported by Browserstack
    os.environ["DJANGO_LIVE_TEST_SERVER_ADDRESS"] = "0.0.0.0:6080-6580"

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        if os.environ.get("TEST_SUITE", "") == "functional" and len(test_labels) == 0:
            test_labels = ["frontend.tests.functional"]
        return super(AssetBuildingTestRunner, self).build_suite(
            test_labels, extra_tests, **kwargs
        )

    def setup_test_environment(self):
        # Get a free port for starting a mock API server
        os.environ["API_HOST"] = "http://localhost:%s" % MockApiServer.api_port()

        # Before we load any func tests, ensure we've got assets built
        npm_cmd = "mkdir -p ../../static/js && npm run build"
        if (
            "SKIP_NPM_BUILD" not in os.environ
            and os.environ.get("TEST_SUITE", "") != "nonfunctional"
        ):
            subprocess.check_call(
                npm_cmd, shell=True, cwd=settings.APPS_ROOT + "/media/js"
            )
        if not os.environ.get("BROWSER"):
            # Default test environment for Browserstack
            os.environ["BROWSER"] = "firefox:latest:Windows 10"
        # I had previously tried patching the API methods, but patching
        # is not a thread-safe operation: the methods are set in the
        # global namespace, and a LiveServerTestCase (of which this is a
        # subclass) starts a new server in a subprocess.
        if os.environ.get("TEST_SUITE", "") != "nonfunctional":
            MockApiServer().start()
        super(AssetBuildingTestRunner, self).setup_test_environment()
