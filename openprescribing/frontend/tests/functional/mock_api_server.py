import logging
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import requests

FIXTURES_BASE = "frontend/tests/fixtures/functional/"
logger = logging.getLogger(__name__)


def _load_json(name):
    return open("%s/%s.json" % (FIXTURES_BASE, name), "r").read()


class MockApiRequestHandler(BaseHTTPRequestHandler):
    """This Mock API server was the minimum necessary to support some
    basic map tests.

    It now needs refactoring so that the tests can specify the data
    under test, via some kind of IPC

    """

    def log_message(self, format, *args):
        logger.info(format % args)

    def do_GET(self):
        o = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(o.query)
        data = {}
        if "/spending_by_org" in o.path and "ccg" in q.get("org_type", ""):
            code = q.get("code")[0]
            if code == "2.12":
                data = _load_json("spending_by_ccg_denom")
            elif code == "0212000AA":
                data = _load_json("spending_by_ccg_num")
        if "/spending_by_org" in o.path and "practice" in q.get("org_type", ""):
            # for SmallListTest
            data = (
                '[{"items":9000000.0,"actual_cost":1026.22,"setting":4,'
                '"row_name":"THE GREEN PRACTICE","date":"2012-02-01",'
                '"row_id":"6","ccg":"11H","quantity":966.0},'
                '{"items":23.0,"actual_cost":1026.22,"setting":4,'
                '"row_name":"THE YELLOW PRACTICE","date":"2012-02-01",'
                '"row_id":"7","ccg":"11H","quantity":966.0},'
                '{"items":23.0,"actual_cost":1026.22,"setting":4,'
                '"row_name":"THE PINK PRACTICE","date":"2012-02-01",'
                '"row_id":"10","ccg":"11H","quantity":966.0},'
                '{"items":23.0,"actual_cost":1026.22,"setting":4,'
                '"row_name":"THE BLUE PRACTICE","date":"2012-02-01",'
                '"row_id":"7","ccg":"11H","quantity":966.0},'
                '{"items":23.0,"actual_cost":1026.22,"setting":4,'
                '"row_name":"THE RED PRACTICE","date":"2012-02-01",'
                '"row_id":"7","ccg":"11H","quantity":966.0}]'
            )
        elif "/bnf_code" in o.path:
            code = q.get("q")[0]
            if code.startswith("0212000AA"):
                data = _load_json("bnf_code_num")
            elif code.startswith("2.12"):
                data = _load_json("bnf_code_denom")
        elif "/org_details" in o.path:
            # for SmallListTest
            data = (
                '[{"date":"2012-02-01","row_id":"6",'
                '"total_list_size":1,"row_name":"THE GREEN PRACTICE"},'
                '{"date":"2012-02-01","row_id":"7","total_list_size":10000,'
                '"row_name":"THE YELLOW PRACTICE"},'
                '{"date":"2012-02-01","row_id":"10","total_list_size":10000,'
                '"row_name":"THE PINK PRACTICE"},'
                '{"date":"2012-02-01","row_id":"8","total_list_size":10000,'
                '"row_name":"THE BLUE PRACTICE"},'
                '{"date":"2012-02-01","row_id":"9","total_list_size":10000,'
                '"row_name":"THE RED PRACTICE"}]'
            )
        elif "/org_code" in o.path:
            data = (
                '[{"ccg":"11H","code":"6","type":"practice",'
                '"name":"THE GREEN PRACTICE","id":"6"}]'
            )
        elif "/org_location" in o.path:
            data = _load_json("org_location_ccg")
        elif "/measure_by_sicbl/" in o.path:
            code = q.get("tags", "")
            measure = q.get("measure", "")
            if not measure and "core" not in code:
                # Testing tag omission...
                data = '{"measures": []}'
            else:
                data = _load_json("measure_by_ccg")
        elif "/measure/" in o.path:
            data = _load_json("measure")
        if data:
            self.send_response(requests.codes.ok)
        else:
            logger.error("Unhandled path %s" % self.path)
            self.send_response(requests.codes.not_found)
            data = str(data)
        self.send_header("Content-Type", "application/json")
        self.send_header("access-control-allow-origin", "*")
        self.end_headers()
        self.wfile.write(data.encode("utf8"))
        return


class MockApiServer(object):
    def __init__(self, port=None):
        if port is None:
            port = urllib.parse.urlparse(os.environ["API_HOST"]).port
        self.port = port

    def start(self):
        mock_server = HTTPServer(("0.0.0.0", self.port), MockApiRequestHandler)
        self.mock_server_thread = Thread(target=mock_server.serve_forever)
        self.mock_server_thread.setDaemon(True)
        self.mock_server_thread.start()
        logger.info("Started mock API server on port %s" % self.port)

    @classmethod
    def api_port(cls):
        """A port suitable for running the API."""
        return 6060
