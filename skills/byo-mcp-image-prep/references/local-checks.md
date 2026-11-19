# Docker-only local checks

These are repeatable observations invoked by the agent, not a hosted checker.
They do not inspect arbitrary application logic or authorize changes.

Adapt commands to the customer's existing shell. Do not install Bash, Python,
Node.js, curl, jq, Azure CLI, or GitHub CLI on the host. Docker commands work in
PowerShell too; use native path and redirection syntax. Resolve absolute paths
with the assistant's existing file tools.

## Plan isolation first

Choose unique names for this run, such as `byoi-<run-id>-net` and
`byoi-<run-id>-candidate`. The examples below use `byoi-demo-*` only for readability;
substitute this run's names and record them. Do not collide with existing resources.

Start on an internal network without credentials. If the server needs public
internet or a private environment file to start, explain the need and request
approval before changing network access or passing that file.

```text
docker network create --internal byoi-demo-net
docker run --detach --name byoi-demo-candidate --network byoi-demo-net --network-alias candidate --cpus 0.5 --memory 1g --pids-limit 128 INPUT_IMAGE
```

`INPUT_IMAGE` is a placeholder for the resolved input. These CPU/memory limits
are sample local settings, not an asserted platform minimum or default.
Do not force a new USER, filesystem layout, or startup arguments for the initial
baseline. Stdio tests need stdin held open (`-i`); an idle stdio process opening
no network port is not a process failure.

## Inspect metadata carefully

```text
docker image inspect INPUT_IMAGE --format "{{.Id}} {{.Os}}/{{.Architecture}}"
```

Inspect entrypoint/CMD and environment-variable names as needed, but do not
save raw metadata or expose any literal credentials. EXPOSE is only metadata.
Resolve tag to digest when available; local-only images have an ID, not an
invented registry digest.

## Build the probe

Build from the installed skill's `scripts` directory, not the user's workspace:

```text
docker build --tag byo-mcp-prep-probe:0.1.0 ABSOLUTE_SKILL_PATH/scripts
```

The helper uses a pinned Python image and only the standard library. No pip or
npm installation is needed. A base-image download/build failure is a tooling
blocker, not evidence that the candidate is incompatible.

## Exercise a native HTTP image

After confirming the actual port/route, run from a separate container:

```text
docker run --rm --network byoi-demo-net --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 64 --memory 256m --cpus 0.5 byo-mcp-prep-probe:0.1.0 --url http://candidate:8080/mcp --timeout 5 --startup-seconds 20 --concurrent-discovery
```

Redirect stdout to the run's `checks-before.json` or `checks-after.json` using the
host shell. The helper exits nonzero when required protocol checks or explicitly
requested concurrency/tool checks fail. `requiredLocalChecksPassed` distinguishes
protocol success from a failed optional tool call; neither overrides agent review.
Preserve
that exit status and the JSON; do not hide failures with `|| true`.

The separate Docker network namespace checks external reachability. The helper
uses the local service path and a representative non-localhost Host header to
simulate a proxy. It preserves MCP protocol/session headers. It does **not**
implement the real platform proxy, OAuth, TLS termination, path-prefix rewrites,
HTTP/2, or ADC sandbox behavior. Report those as unverified, not passed.

The helper:

- Performs a bounded legacy initialization and notification acknowledgment.
- Reads paginated tools, rejecting repeated cursors and excessive output.
- Parses JSON or a matching response event in SSE, without waiting for an
  indefinite POST stream to end.
- Compares inventory fingerprints for direct and proxy-Host requests.
- Optionally runs concurrent discovery on the same session.
- Records GET status/stream headers **without consuming the body**. Thus GET
  completion and the actual hosted readiness probe remain untested.
- Omits upstream bodies, actual session IDs, arguments, URLs, and credentials
  from JSON output.

It does not prove a stateful application's state continuity or isolation by
merely propagating a session header. The agent must design approved,
capability-specific tests for those claims. Sampling, roots, elicitation,
cancellation, bidirectional notifications, reconnects, and shutdown each need
separate evidence or an untested status with a reason.

## Credentials

The user may populate a private Docker environment file locally. Pass it to the
candidate with `--env-file`; do not read or copy it.

For an explicitly retained incoming bearer-token check, the probe can read its
token from its own environment:

```text
docker run --rm --network byoi-demo-net --env-file PRIVATE_INCOMING_AUTH_FILE byo-mcp-prep-probe:0.1.0 --url http://candidate:8080/mcp --auth-token-env PREP_INCOMING_TOKEN
```

This is not a downstream credential. Do not copy the candidate's whole credential
environment into the probe. Do not set placeholder/fake credentials unless the
user explicitly wants an isolated negative test.

If startup requires missing inputs, ask the user to supply them locally or record
startup/protocol tests as blocked. If only a tool needs credentials, keep protocol
results and mark that tool's execution untested.

## Approved smoke calls

Before calling a tool, obtain approval for its name, exact inputs, and possible
effects. Prefer synthetic content and a non-sensitive expected result. The
helper deliberately has no default tool execution.

It requires all three options:

```text
--allow-tool-call --tool-name TOOL_NAME --tool-arguments-file /input/arguments.json
```

Bind only the approved synthetic arguments file read-only into the probe if
needed. Use `--expected-text` only for a non-sensitive content criterion.
A call with no expected content criterion is recorded as **observed**, not
proof that the tool produced the right result. Never save raw tool results.

## Lifecycle and resource checks

With the user's approval, stop/start the same candidate and rerun checks. When
safe, test a new container from the same image to distinguish writable sandbox
state from packaged files. Record both. Do not delete the user's state to test
this. A requested stateful behavior needs an approved state test, not discovery
alone.

Inspect this run's resource use with `docker stats --no-stream`. A failure under
selected limits is evidence only for those limits. Do not "fix" it by changing
the application or silently assigning larger resources.

## Cleanup on every exit path

Stop and remove this run's candidate and any other test containers, then remove
its network. Use exact recorded names. Temporary probes use `--rm`.

Preserve the output image and prep-summary. Do not remove the original image,
unrelated caches, credentials, or networks. If interrupted cleanup cannot finish,
list exact remaining names and cleanup commands.
