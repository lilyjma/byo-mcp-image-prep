"""Regression checks for observable failures, bounds and secret-free output."""

import io
import json
import os
import socket
import sys
import threading
import time
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from probe import Client, ProbeError, inventory_fingerprint, main, read_message, run_checks


SECRET = "not-a-real-credential-do-not-report"
TOOL = {"name": "echo", "inputSchema": {"type": "object"}}


class Fixture(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def respond(self, status, result=None, session=None, sse=False):
        body = json.dumps(result).encode() if result is not None else b""
        if sse:
            body = b": keepalive\n\n" + b"event: message\ndata: " + body + b"\n\n"
        self.send_response(status)
        self.send_header("Content-Type", "text/event-stream" if sse else
                         "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.close_connection = True
        if session:
            self.send_header("Mcp-Session-Id", session)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.respond(202, sse=True)

    def do_POST(self):
        message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/locked":
            self.respond(401, {"secret": SECRET})
            return
        if self.path == "/host-only" and "hosting-proxy" in self.headers["Host"]:
            self.respond(403, {"secret": SECRET})
            return
        if self.path == "/slow":
            time.sleep(0.15)
        method = message["method"]
        session = None
        if method == "notifications/initialized":
            if self.path == "/bad-ack":
                self.respond(200)
            else:
                self.respond(202)
            return
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            }
            session = "fixture-session"
        else:
            if self.headers.get("Mcp-Session-Id") != "fixture-session":
                self.respond(400, {"secret": SECRET})
                return
            if method == "tools/list":
                result = {"tools": [TOOL]}
                if self.path == "/paged" and "cursor" not in message.get("params", {}):
                    result = {"tools": [], "nextCursor": "page2"}
                if self.path == "/cursor-loop":
                    result = {"tools": [], "nextCursor": "same"}
                if self.path == "/bad-tools":
                    result = {"tools": "not-an-array"}
                if self.path == "/changed-inventory" and "hosting-proxy" in self.headers["Host"]:
                    result = {"tools": [{"name": "different", "inputSchema": {}}]}
                if self.path == "/session-switch":
                    session = "different-session"
            else:
                result = {"content": [{"type": "text", "text": "hello"}]}
                if self.path == "/tool-error":
                    result = {"isError": True, "content": [{"type": "text", "text": SECRET}]}
        response = {"jsonrpc": "2.0", "id": message["id"], "result": result}
        if self.path == "/bad-id":
            response["id"] = 9999
        if self.path == "/oversize":
            response["padding"] = SECRET * 1000
        self.respond(200, response, session, sse=self.path == "/sse")


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def client(self, path="/mcp", timeout=1, maximum=1048576):
        return Client("http://127.0.0.1:" + str(self.server.server_port) + path,
                      timeout=timeout, maximum=maximum)

    def test_json_and_sse_sessions_discovery_and_pagination(self):
        for path in ("/mcp", "/sse", "/paged"):
            with self.subTest(path=path):
                result = run_checks(self.client(path), startup_seconds=0,
                                    concurrent=True)
                self.assertTrue(result["requiredLocalChecksPassed"], result)
                self.assertEqual(result["toolCount"], 1)
                self.assertTrue(result["sessionHeaderObserved"])
                self.assertEqual(result["getObservation"]["httpStatus"], 202)
                self.assertEqual(result["getObservation"]["responseCompletion"],
                                 "untested_headers_only")
                self.assertTrue(any(check["check"] == "cancellation" and
                                    check["status"] == "untested" and check["reason"]
                                    for check in result["checks"]))

    def test_protocol_and_host_failures_do_not_become_passes(self):
        cases = {
            "/locked": ("initialize", "http_status_401"),
            "/host-only": ("proxy_host", "http_status_403"),
            "/bad-ack": ("initialized_notification",
                         "unexpected_notification_acknowledgment"),
            "/bad-id": ("initialize", "unexpected_json_rpc_response_id"),
            "/cursor-loop": ("tools_discovery", "invalid_or_repeated_tools_cursor"),
            "/bad-tools": ("tools_discovery", "tools_array_missing"),
            "/changed-inventory": ("proxy_host", "inventory_changed_with_proxy_host"),
            "/session-switch": ("tools_discovery", "session_id_changed_during_follow_up"),
        }
        for path, (name, reason) in cases.items():
            with self.subTest(path=path):
                result = run_checks(self.client(path), startup_seconds=0)
                self.assertFalse(result["requiredLocalChecksPassed"], result)
                check = next(check for check in result["checks"] if check["check"] == name)
                self.assertEqual(check["status"], "fail")
                self.assertEqual(check["reason"], reason)
                self.assertNotIn(SECRET, json.dumps(result))

    def test_response_deadline_and_size_are_bounded(self):
        for client, expected in (
            (self.client("/slow", timeout=0.03), "request_timed_out"),
            (self.client("/oversize", maximum=1024), "response_size_limit_exceeded"),
        ):
            result = run_checks(client, startup_seconds=0)
            self.assertFalse(result["requiredLocalChecksPassed"])
            self.assertEqual(result["checks"][0]["reason"], expected)
            self.assertNotIn(SECRET, json.dumps(result))

    def test_closed_stream_without_response_is_not_a_pass(self):
        class Response:
            def getheader(self, _name, _default=""):
                return "text/event-stream"

            def read1(self, _size):
                return b""
        with socket.socket() as connection:
            with self.assertRaisesRegex(ProbeError, "matching_json_rpc"):
                read_message(Response(), connection, 1, 1, 1024)

    def test_heartbeats_do_not_extend_the_wall_clock_deadline(self):
        class Response:
            def getheader(self, _name, _default=""):
                return "text/event-stream"

            def read1(self, _size):
                time.sleep(0.01)
                return b": heartbeat\n\n"
        start = time.monotonic()
        with socket.socket() as connection:
            with self.assertRaisesRegex(ProbeError, "response_deadline"):
                read_message(Response(), connection, 1, 0.04, 100000)
        self.assertLess(time.monotonic() - start, 0.5)

    def test_inventory_order_is_irrelevant_but_schema_changes_are_not(self):
        second = {"name": "other", "inputSchema": {}}
        self.assertEqual(inventory_fingerprint([TOOL, second]),
                         inventory_fingerprint([second, TOOL]))
        changed = {"name": "echo", "inputSchema": {"type": "string"}}
        self.assertNotEqual(inventory_fingerprint([TOOL]),
                            inventory_fingerprint([changed]))

    def test_tool_error_and_content_assertion_are_meaningful(self):
        result = run_checks(self.client(), startup_seconds=0, tool_name="echo",
                            tool_arguments={}, expected_text="hello")
        self.assertEqual(next(check for check in result["checks"]
                              if check["check"] == "approved_tool_call")["status"], "pass")
        for path, text in (("/mcp", "missing"), ("/tool-error", "hello")):
            result = run_checks(self.client(path), startup_seconds=0,
                                tool_name="echo", tool_arguments={}, expected_text=text)
            check = next(check for check in result["checks"]
                         if check["check"] == "approved_tool_call")
            self.assertEqual(check["status"], "fail")
            self.assertNotIn(SECRET, json.dumps(result))

    def test_tool_execution_requires_explicit_cli_options(self):
        with patch.object(sys, "argv", ["probe", "--url", "http://candidate/mcp",
                                      "--tool-name", "echo"]):
            with patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main()
        self.assertEqual(error.exception.code, 2)

    def test_missing_auth_is_reported_without_reading_or_printing_values(self):
        with patch.object(sys, "argv", ["probe", "--url", "http://candidate/mcp",
                                      "--auth-token-env", "MISSING_TOKEN"]):
            with patch.dict(os.environ, {}, clear=True), patch("sys.stdout", new=io.StringIO()) as output:
                self.assertEqual(main(), 1)
                result = json.loads(output.getvalue())
        self.assertEqual(result["reason"], "incoming_auth_runtime_configuration_required")

    def test_explicit_smoke_failure_sets_nonzero_exit_without_erasing_protocol_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "arguments.json")
            with open(path, "w", encoding="utf-8") as output:
                output.write("{}")
            url = "http://127.0.0.1:" + str(self.server.server_port) + "/tool-error"
            arguments = [
                "probe", "--url", url, "--allow-tool-call", "--tool-name", "echo",
                "--tool-arguments-file", path, "--expected-text", "hello",
            ]
            with patch.object(sys, "argv", arguments), patch("sys.stdout", new=io.StringIO()) as output:
                self.assertEqual(main(), 1)
                result = json.loads(output.getvalue())
        self.assertTrue(result["requiredLocalChecksPassed"])
        self.assertEqual(result["requestedChecksFailed"], ["approved_tool_call"])
        self.assertNotIn(SECRET, json.dumps(result))

    def test_credential_bearing_urls_are_rejected(self):
        for url in ("http://user:secret@candidate/mcp", "http://candidate/mcp?token=secret"):
            with self.assertRaisesRegex(ProbeError, "without_credentials"):
                Client(url)


if __name__ == "__main__":
    unittest.main()
