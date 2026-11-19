"""Opt-in synthetic bridge smoke test. Never point this at a customer server."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import time

from probe import Client, inventory_fingerprint


EXPECTED_TOOLS = [
    {"name": "counter", "description": "Increment a synthetic in-memory counter.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "echo", "description": "Return synthetic text.",
     "inputSchema": {"type": "object",
                     "properties": {"text": {"type": "string"}},
                     "required": ["text"]}},
]


def new_session(url):
    client = Client(url)
    deadline = time.monotonic() + 10
    while True:
        try:
            result = client.rpc("initialize", 1, {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "synthetic-bridge-check", "version": "1"},
            })
            break
        except ConnectionRefusedError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)
    assert result["serverInfo"]["name"] == "byoi-synthetic-stdio-fixture", result
    assert client.session, "Stateful bridge did not return a session ID."
    client.rpc("notifications/initialized")
    assert inventory_fingerprint(client.tools()) == inventory_fingerprint(EXPECTED_TOOLS), (
        "The bridge changed the synthetic server's advertised tool inventory.")
    return client


def counter(client, request_id):
    result = client.rpc("tools/call", request_id, {
        "name": "counter", "arguments": {},
    })
    assert not result.get("isError"), result
    return int(result["content"][0]["text"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--synthetic-fixture-approved", action="store_true", required=True)
    arguments = parser.parse_args()
    first = new_session(arguments.url)
    second = new_session(arguments.url)
    assert first.session != second.session, "Two clients received the same session ID."
    assert counter(first, 10) == 1
    assert counter(first, 11) == 2, "Same-session process state was not preserved."
    assert counter(second, 12) == 1, "Separate sessions shared stdio process state."
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda request_id: counter(first, request_id), [20, 21]))
    assert sorted(results) == [3, 4], "Concurrent responses/state were not preserved."
    echo = first.rpc("tools/call", 30, {
        "name": "echo", "arguments": {"text": "synthetic conversion preserved"},
    })
    assert echo["content"][0]["text"] == "synthetic conversion preserved"
    print(json.dumps({
        "adapter": "supergateway 4.2.2",
        "protocol": "2025-03-26",
        "fixtureOnly": True,
        "passed": ["initialization", "notification_ack", "tool_inventory",
                   "same_session_state", "separate_session_state",
                   "concurrent_requests", "synthetic_tool_result"],
        "untested": {
            "cancellation": "fixture has no long-running operation",
            "server_initiated_notifications": "fixture does not emit them",
            "reconnect_and_expiry": "no lifecycle scenario was run",
            "hosted_routing": "no cloud deployment is performed",
        },
    }, indent=2))


if __name__ == "__main__":
    main()
