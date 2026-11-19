# Maintainer validation

These commands use Docker only. They are developer checks, not a customer's
preparation workflow.

## Helper and package regressions

From the repository root:

```bash
docker build -f tests/Dockerfile -t byo-mcp-prep-tests .
docker run --rm --network none byo-mcp-prep-tests
```

Tests replay connection failures, Host rejection, bad notification acknowledgments,
JSON and SSE responses, repeated cursors, changed sessions/schemas, output limits,
timeouts and missing inputs. Error bodies deliberately contain a synthetic secret
that must not appear in reports. This tests that failures can actually fail.

## Pinned adapter smoke test

This calls only tools in the synthetic fixture: it never connects to a real
service. It checks Supergateway 4.2.2, not arbitrary future versions.

```bash
docker build -f tests/fixtures/Dockerfile.bridge -t byo-mcp-prep-bridge-fixture .
docker network create --internal byoi-bridge-test-net
docker run -d --name byoi-bridge-test --network byoi-bridge-test-net --network-alias bridge byo-mcp-prep-bridge-fixture
docker run --rm --network byoi-bridge-test-net --entrypoint python byo-mcp-prep-tests /tests/check_bridge.py --url http://bridge:8080/mcp --synthetic-fixture-approved
docker stop byoi-bridge-test
docker rm byoi-bridge-test
docker network rm byoi-bridge-test-net
```

Use unique names if these resources already exist. Clean up after failures too.
Expected: separate session IDs, same-session counter continuity, independent
second-session counter, concurrent correlated responses, unchanged fixture tool
schemas, and unchanged echo result.

Negative control: start a second fixture with `--toolPrefix altered_` appended
to its Docker command, and point the smoke test at it. The tool-inventory check
must fail. Do not retain tool-prefixing in a customer adaptation.

Cancellation, server-to-client notifications, session expiry/reconnect,
real downstream services, and actual cloud hosting are **not** established by
this smoke test.

## AI workflow evaluation

`evals/evals.json` has two scenarios:

1. Native HTTP adaptation and proxy-host consent, while preserving write tools.
2. Missing credentials and an unsupported bridge runtime, requiring honest
   untested/incomplete output and manual handoff.

Run each in a fresh agent context with the skill installed and once without it.
Do not actually execute the hypothetical customer's image. Save outputs and
grading outside this repository in a sibling evaluation workspace. Use the same
prompt and model settings for both conditions. Record unavailable measurements
as unknown, never as fabricated timings/tokens.

These are instruction-following scenario evaluations, not proof that all
versions of VS Code, Claude Code, or Codex have been tested. Cross-client
installation/discovery needs separate validation in those products.
