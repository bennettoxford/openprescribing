import os
import random
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.options import ArgOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Django 1.11 removes the ability to supply a port range for liveserver tests,
# so we replicate that here.  See: https://code.djangoproject.com/ticket/28212
# and https://code.djangoproject.com/ticket/26011
test_port_range = list(range(6080, 6580))
# Shuffle the ports so that repeated runs locally are unlikely to try to reopen
# a port in the TIME_WAIT state
random.shuffle(test_port_range)
available_test_ports = iter(test_port_range)


def use_browserstack():
    return os.environ.get("GITHUB_ACTIONS") or os.environ.get("USE_BROWSERSTACK")


@unittest.skipIf(
    os.environ.get("TEST_SUITE") == "nonfunctional",
    "nonfunctional tests specified in TEST_SUITE environment variable",
)
class SeleniumTestCase(StaticLiveServerTestCase):
    host = "0.0.0.0"
    display = None

    @classmethod
    def setUpClass(cls):
        cls.port = next(available_test_ports)
        try:
            cls.browser = cls.get_browser()
        except Exception:
            if cls.display:
                cls.display.stop()
            raise
        cls.browser.maximize_window()
        cls.browser.implicitly_wait(1)
        super(SeleniumTestCase, cls).setUpClass()

    @classmethod
    def get_browser(cls):
        if use_browserstack():
            return cls.get_browserstack_browser()
        else:
            if cls.use_xvfb():
                from pyvirtualdisplay import Display

                cls.display = Display(visible=0, size=(1200, 800))
                cls.display.start()
            return cls.get_firefox_driver()

    @classmethod
    def get_browserstack_browser(cls):
        browser, browser_version, browserstack_os, browserstack_os_version = os.environ[
            "BROWSER"
        ].split(":")
        local_identifier = os.environ["BROWSERSTACK_LOCAL_IDENTIFIER"]
        options = ArgOptions()
        options.set_capability("browserName", browser)
        options.set_capability("browserVersion", browser_version)
        options.set_capability(
            "bstack:options",
            {
                "os": browserstack_os,
                "osVersion": browserstack_os_version,
                "resolution": "1600x1200",
                "local": "true",
                "localIdentifier": local_identifier,
                "projectName": os.environ["BROWSERSTACK_PROJECT_NAME"],
                "buildName": os.environ["BROWSERSTACK_BUILD_NAME"],
            },
        )
        username = os.environ["BROWSERSTACK_USERNAME"]
        access_key = os.environ["BROWSERSTACK_ACCESS_KEY"]
        hub_url = "https://%s:%s@hub-cloud.browserstack.com/wd/hub" % (
            username,
            access_key,
        )
        return webdriver.Remote(options=options, command_executor="%s" % hub_url)

    @classmethod
    def use_xvfb(cls):
        if not os.environ.get("SHOW_BROWSER", False):
            return (
                subprocess.call(
                    "type xvfb-run",
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                == 0
            )
        else:
            return False

    @classmethod
    def get_firefox_driver(cls):
        # Newer releases of Ubuntu package Firefox as a Snap, meaning that it comes with
        # sandboxing restrictions that prevent it writing temporary profiles into the
        # default system tmpdir. We workaround this by changing TMPDIR to point to a
        # directory in the project root (which we assume is within the currently running
        # user's home directory). See:
        # https://github.com/mozilla/geckodriver/releases/tag/v0.32.0
        tmpdir = Path(settings.REPO_ROOT) / "tmp"
        tmpdir.mkdir(exist_ok=True)
        orig_tmp = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = str(tmpdir)
        try:
            return webdriver.Firefox(
                service=FirefoxService(
                    log_path="%s/logs/webdriver.log" % settings.REPO_ROOT
                )
            )
        finally:
            if orig_tmp is not None:
                os.environ["TMPDIR"] = orig_tmp
            else:
                del os.environ["TMPDIR"]

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        if cls.display:
            cls.display.stop()
        super(SeleniumTestCase, cls).tearDownClass()

    def _find_and_wait(self, locator_type, locator, waiter):
        wait = 15
        try:
            element = WebDriverWait(self.browser, wait).until(
                waiter((locator_type, locator))
            )
            return element
        except TimeoutException:
            raise AssertionError("Expected to find element %s" % locator)

    def find_by_xpath(self, locator):
        return self._find_and_wait(By.XPATH, locator, EC.presence_of_element_located)

    def find_visible_by_xpath(self, locator):
        return self._find_and_wait(By.XPATH, locator, EC.visibility_of_element_located)

    def find_by_css(self, locator):
        return self._find_and_wait(
            By.CSS_SELECTOR, locator, EC.presence_of_element_located
        )

    def find_visible_by_css(self, locator):
        return self._find_and_wait(
            By.CSS_SELECTOR, locator, EC.visibility_of_element_located
        )
