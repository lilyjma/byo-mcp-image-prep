"""Bounded local HTTP MCP observations. Runs in Docker; no third-party packages."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit


BASELINE = "0.1-preview"
REQUIRED = (
    "initialize",
    "initialized_notification",
    "tools_discovery",
    "proxy_host",
)
SUPPORTED_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")


class ProbeError(Exception):
    """Carries a safe diagnostic category, never an upstream body or secret."""


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise ProbeError("response_deadline_exceeded")
    return seconds


def read_message(response, connection_socket, request_id, timeout, maximum):
    """Read one matching JSON-RPC response, including finite or open SSE streams."""
    deadline = time.monotonic() + timeout
    content_type = response.getheader("Content-Type", "").split(";")[0].strip()
    if content_type not in ("application/json", "text/event-stream"):
        raise ProbeError("unsupported_response_content_type")
    collected = b""
    received = 0
    while True:
        connection_socket.settimeout(remaining(deadline))
        chunk = response.read1(min(4096, maximum - received + 1))
        received += len(chunk)
        if received > maximum:
            raise ProbeError("response_size_limit_exceeded")
        if not chunk:
            raise ProbeError("matching_json_rpc_response_not_received")
        collected += chunk
        if content_type == "application/json":
            try:
                message = json.loads(collected)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(message, dict) or message.get("id") != request_id:
                raise ProbeError("unexpected_json_rpc_response_id")
            return message
        collected = collected.replace(b"\r\n", b"\n")
        while b"\n\n" in collected:
            event, collected = collected.split(b"\n\n", 1)
            payload = b"\n".join(
                line[5:].lstrip(b" ") for line in event.split(b"\n")
                if line.startswith(b"data:")
            )
            if not payload:
                continue
            try:
                message = json.loads(payload)
            except (ValueError, UnicodeDecodeError) as error:
                raise ProbeError("invalid_sse_json") from error
            if isinstance(message, dict) and message.get("id") == request_id:
                return message


def inventory_fingerprint(tools):
    """Compare advertised tools, not arbitrary business behavior."""
    if not isinstance(tools, list):
        raise ProbeError("tools_array_missing")
    indexed = {}
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ProbeError("invalid_tool_entry")
        if not isinstance(tool.get("inputSchema"), dict):
            raise ProbeError("tool_input_schema_missing")
        if tool["name"] in indexed:
            raise ProbeError("duplicate_tool_name")
        indexed[tool["name"]] = tool
    canonical = json.dumps(indexed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class Client:
    def __init__(self, url, timeout=5, maximum=1048576, protocol="2025-03-26",
                 token=None):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ProbeError("use_local_http_url_without_credentials_or_query")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path or "/"
        self.timeout = timeout
        self.maximum = maximum
        self.protocol = protocol
        self.token = token
        self.session = None

    def request(self, method, payload=None, host_header=None):
        connection = http.client.HTTPConnection(
            self.host, self.port, timeout=self.timeout)
        headers = {
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol,
        }
        if host_header:
            headers["Host"] = host_header
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = None
        if payload is not None:
            body = json.dumps(payload).encode()
            if len(body) > self.maximum:
                raise ProbeError("request_size_limit_exceeded")
            headers["Content-Type"] = "application/json"
        try:
            connection.request(method, self.path, body=body, headers=headers)
            connection_socket = connection.sock
            response = connection.getresponse()
            if method == "GET":
                # This is deliberately headers-only, not a hosted readiness verdict.
                return {
                    "httpStatus": response.status,
                    "eventStream": response.getheader(
                        "Content-Type", "").startswith("text/event-stream"),
                    "responseCompletion": "untested_headers_only",
                }
            if not 200 <= response.status < 300:
                raise ProbeError("http_status_" + str(response.status))
            if "id" not in payload:
                if response.status not in (202, 204):
                    raise ProbeError("unexpected_notification_acknowledgment")
                return None
            message = read_message(
                response, connection_socket, payload["id"], self.timeout,
                self.maximum)
            if message.get("jsonrpc") != "2.0":
                raise ProbeError("invalid_json_rpc_version")
            if "error" in message:
                raise ProbeError("server_returned_json_rpc_error")
            if not isinstance(message.get("result"), dict):
                raise ProbeError("json_rpc_result_missing")
            response_session = response.getheader("Mcp-Session-Id")
            if response_session:
                if self.session and response_session != self.session:
                    raise ProbeError("session_id_changed_during_follow_up")
                if len(response_session) > 1024:
                    raise ProbeError("session_header_size_limit_exceeded")
                self.session = response_session
            return message["result"]
        finally:
            connection.close()

    def rpc(self, method, request_id=None, params=None, host_header=None):
        payload = {"jsonrpc": "2.0", "method": method}
        if request_id is not None:
            payload["id"] = request_id
        if params is not None:
            payload["params"] = params
        return self.request("POST", payload, host_header)

    def tools(self, host_header=None):
        tools = []
        cursor = None
        seen = set()
        for page in range(32):
            params = {"cursor": cursor} if cursor else {}
            result = self.rpc("tools/list", 100 + page, params, host_header)
            entries = result.get("tools")
            if not isinstance(entries, list):
                raise ProbeError("tools_array_missing")
            tools.extend(entries)
            if len(tools) > 10000:
                raise ProbeError("tool_count_limit_exceeded")
            cursor = result.get("nextCursor")
            if cursor is None:
                inventory_fingerprint(tools)
                return tools
            if not isinstance(cursor, str) or not cursor or cursor in seen:
                raise ProbeError("invalid_or_repeated_tools_cursor")
            seen.add(cursor)
        raise ProbeError("tools_pagination_limit_exceeded")


def safe_reason(error):
    if isinstance(error, ProbeError):
        return str(error)
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "request_timed_out"
    return "local_connection_or_protocol_error"


def run_checks(client, proxy_host="hosting-proxy.invalid", startup_seconds=20,
               concurrent=False, tool_name=None, tool_arguments=None,
               expected_text=None):
    report = {
        "baselineVersion": BASELINE,
        "scope": "local_only_not_hosted_certification",
        "checks": [],
        "inventoryFingerprint": None,
    }

    def record(name, function, status="pass"):
        start = time.monotonic()
        try:
            value = function()
            report["checks"].append({
                "check": name, "status": status,
                "reason": "observed_success" if status == "pass" else
                          "observation_not_a_platform_guarantee",
                "durationSeconds": round(time.monotonic() - start, 3),
            })
            return True, value
        except (ProbeError, OSError, http.client.HTTPException, ValueError) as error:
            report["checks"].append({
                "check": name, "status": "fail", "reason": safe_reason(error),
                "durationSeconds": round(time.monotonic() - start, 3),
            })
            return False, None

    def initialize():
        deadline = time.monotonic() + startup_seconds
        while True:
            try:
                result = client.rpc("initialize", 1, {
                    "protocolVersion": client.protocol,
                    "capabilities": {},
                    "clientInfo": {"name": "byo-mcp-image-prep", "version": "0.1.0"},
                })
                break
            except ConnectionRefusedError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        negotiated = result.get("protocolVersion")
        if negotiated not in SUPPORTED_VERSIONS:
            raise ProbeError("negotiated_protocol_not_tested_by_this_helper")
        if not isinstance(result.get("serverInfo"), dict):
            raise ProbeError("server_info_missing")
        if not isinstance(result.get("capabilities"), dict):
            raise ProbeError("server_capabilities_missing")
        client.protocol = negotiated
        report["negotiatedProtocolVersion"] = negotiated
        report["sessionHeaderObserved"] = bool(client.session)

    initialized, _ = record("initialize", initialize)
    tools = None
    if initialized:
        record("initialized_notification",
               lambda: client.rpc("notifications/initialized"))
        passed, tools = record("tools_discovery", client.tools)
        if passed:
            report["inventoryFingerprint"] = inventory_fingerprint(tools)
            report["toolCount"] = len(tools)

            def proxy_check():
                proxied_tools = client.tools(proxy_host)
                if inventory_fingerprint(proxied_tools) != report["inventoryFingerprint"]:
                    raise ProbeError("inventory_changed_with_proxy_host")
            record("proxy_host", proxy_check)
        observed, get_result = record(
            "get_readiness_observation",
            lambda: client.request("GET", host_header=proxy_host), "observed")
        if observed:
            report["getObservation"] = get_result

    if concurrent and tools is not None:
        def discovery():
            fingerprint = inventory_fingerprint(client.tools(proxy_host))
            if fingerprint != report["inventoryFingerprint"]:
                raise ProbeError("inventory_changed_during_concurrent_discovery")

        def concurrent_check():
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(discovery) for _ in range(2)]
                for future in futures:
                    future.result()
        record("concurrent_discovery", concurrent_check)

    if tool_name and tools is not None:
        def tool_check():
            if not any(tool["name"] == tool_name for tool in tools):
                raise ProbeError("approved_tool_not_advertised")
            result = client.rpc("tools/call", 500, {
                "name": tool_name, "arguments": tool_arguments,
            }, proxy_host)
            if result.get("isError"):
                raise ProbeError("tool_reported_error")
            content = result.get("content")
            if not isinstance(content, list):
                raise ProbeError("tool_content_missing")
            if expected_text is not None:
                text = "\n".join(
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and isinstance(item.get("text"), str))
                if expected_text not in text:
                    raise ProbeError("expected_tool_content_missing")
        record("approved_tool_call", tool_check,
               "pass" if expected_text is not None else "observed")

    present = {check["check"] for check in report["checks"]}
    for name in REQUIRED:
        if name not in present:
            report["checks"].append({
                "check": name, "status": "untested",
                "reason": "blocked_by_earlier_check",
            })
    for name, reason in (
        ("session_state_and_isolation", "requires_approved_stateful_scenario"),
        ("cancellation", "requires_approved_long_running_operation"),
        ("server_initiated_notifications", "no_capability_specific_scenario_run"),
        ("cloud_connectivity_and_hosted_readiness", "outside_local_test_scope"),
    ):
        report["checks"].append({"check": name, "status": "untested", "reason": reason})
    if not tool_name:
        report["checks"].append({
            "check": "tool_execution", "status": "untested",
            "reason": "no_explicitly_approved_tool_and_inputs",
        })
    report["requiredLocalChecksPassed"] = all(
        next(check for check in report["checks"] if check["check"] == name)["status"]
        == "pass" for name in REQUIRED)
    report["requestedChecksFailed"] = [
        check["check"] for check in report["checks"]
        if check["status"] == "fail" and check["check"] in (
            *REQUIRED, "concurrent_discovery", "approved_tool_call")
    ]
    report["agentReviewStillRequired"] = True
    return report


def positive_seconds(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 120:
        raise argparse.ArgumentTypeError("Use a finite value between 0 and 120.")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Local Docker HTTP service URL")
    parser.add_argument("--proxy-host", default="hosting-proxy.invalid")
    parser.add_argument("--protocol-version", choices=SUPPORTED_VERSIONS,
                        default="2025-03-26")
    parser.add_argument("--timeout", type=positive_seconds, default=5)
    parser.add_argument("--startup-seconds", type=positive_seconds, default=20)
    parser.add_argument("--max-response-bytes", type=int, default=1048576)
    parser.add_argument("--auth-token-env", help="Name of an env var, not its value")
    parser.add_argument("--concurrent-discovery", action="store_true")
    parser.add_argument("--allow-tool-call", action="store_true")
    parser.add_argument("--tool-name")
    parser.add_argument("--tool-arguments-file")
    parser.add_argument("--expected-text", help="Non-sensitive smoke-test criterion")
    arguments = parser.parse_args()
    if not 1024 <= arguments.max_response_bytes <= 8388608:
        parser.error("--max-response-bytes must be between 1024 and 8388608")
    if (arguments.tool_name or arguments.tool_arguments_file or arguments.expected_text
            or arguments.allow_tool_call):
        if not (arguments.allow_tool_call and arguments.tool_name
                and arguments.tool_arguments_file):
            parser.error("Tool execution requires --allow-tool-call, --tool-name "
                         "and --tool-arguments-file after user approval.")
    try:
        token = None
        if arguments.auth_token_env:
            token = os.environ.get(arguments.auth_token_env)
            if not token:
                raise ProbeError("incoming_auth_runtime_configuration_required")
        tool_arguments = None
        if arguments.tool_arguments_file:
            path = Path(arguments.tool_arguments_file)
            if path.stat().st_size > arguments.max_response_bytes:
                raise ProbeError("tool_arguments_size_limit_exceeded")
            tool_arguments = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(tool_arguments, dict):
                raise ProbeError("tool_arguments_must_be_an_object")
        client = Client(arguments.url, arguments.timeout,
                        arguments.max_response_bytes, arguments.protocol_version, token)
        report = run_checks(
            client, arguments.proxy_host, arguments.startup_seconds,
            arguments.concurrent_discovery, arguments.tool_name, tool_arguments,
            arguments.expected_text)
        print(json.dumps(report, indent=2))
        return 0 if (report["requiredLocalChecksPassed"]
                     and not report["requestedChecksFailed"]) else 1
    except (ProbeError, OSError, ValueError, http.client.HTTPException) as error:
        print(json.dumps({
            "baselineVersion": BASELINE, "requiredLocalChecksPassed": False,
            "reason": safe_reason(error), "agentReviewStillRequired": True,
        }, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
