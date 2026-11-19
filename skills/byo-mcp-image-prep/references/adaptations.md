# Agent adaptation guidance

This is agent-facing guidance. The customer README explains installation and
usage. Do not memorize a server-name allowlist: investigate the specific image,
version, help output and official docs.

## Prefer a small native adaptation

Find an existing HTTP option and configure it in a derived image. Example:

```dockerfile
FROM vendor/server@sha256:<resolved-digest>
ENTRYPOINT ["/verified/executable", "--documented-http-flag", "--host", "0.0.0.0", "--port", "8080"]
CMD []
```

This is schematic, not a runnable Dockerfile. Use only verified commands.
Docker ENTRYPOINT and CMD combine: inspect both before replacing either.
Explicitly clear an inherited CMD only when the approved new entrypoint replaces
its purpose. Preserve required original arguments, environment, user and
working directory. Do not assume Docker CMD is unsupported by hosting.

Some images need only environment configuration, not rebuilding. Offer an
unchanged-image/local-tag result with the correct deployment inputs in that case.

Native configuration examples to research, not unconditional recipes:

- Grafana: select `streamable-http`, configure address, inspect Host restrictions.
- MarkItDown: documented `--http`, `--host`, and `--port`.
- Playwright: documented environment settings for port, bind address, and hosts.
- MongoDB: documented HTTP transport and non-loopback-binding opt-in.

Confirm the selected release supports each option. Do not add read-only flags
or suppress tools unless those were already part of the input configuration.

## Incoming auth and Host rules: explicit consent

Explain the two independent boundaries:

1. Namespace authentication controls incoming callers.
2. The server's runtime credentials control downstream access.

Only offer to disable a second incoming check after the user confirms the
deployment is reachable exclusively through an authenticated namespace path,
and after verifying the server has a supported option. Otherwise keep it and
report the integration/configuration needed. Never disable TLS verification,
remove downstream auth, or change delegated user access into app-only access.

For Host validation, prefer documented explicit expected-host rules. If the
actual platform hostname is unknown, explain that a local synthetic host is
only a simulation. A wildcard requires explicit consent and a trusted hosting
boundary. Do not broadly enable browser origins just because Host failed.

## Loopback-only servers

First look for a supported external-binding option. If none exists, explain
an optional forwarding helper:

```text
external interface:configured port -> original loopback listener
```

The helper adds a process, runtime assets, signals, and failure modes. Obtain
consent. Verify readiness, child-process liveness, streaming, shutdown, ports,
and resource use. If the image cannot support the helper without application
dependency repair, user changes, or an incompatible base, stop for manual work.

Do not install socat by default or assume every image contains a shell.

## Stdio-to-HTTP: optional reviewed bridge

Native HTTP remains preferable. Offer bridging only after explaining:

> This server speaks stdio. The adapter exposes HTTP without changing its tools.
> It introduces HTTP sessions, child-process management, concurrency and
> notification/cancellation behavior. Local tests do not establish cloud routing
> or per-user isolation. Session-aware routing requires stable MCP session IDs;
> a stateless adapter cannot be promised a persistent sandbox.

The MVP evaluation candidate is
[Supergateway](https://github.com/supercorp-ai/supergateway), MIT, **4.2.2**:

```text
docker.io/supercorp/supergateway@sha256:5fd78fb79ffce27812313e5da9b3b3d0bc034267e131961f1140f4a4e0179d3a
```

Its documentation supports:

```text
supergateway --stdio "VERIFIED_STATIC_COMMAND" --outputTransport streamableHttp --stateful --host 0.0.0.0 --port 8080 --streamableHttpPath /mcp
```

Local synthetic-fixture validation on 2026-11-19 passed initialization,
notification acknowledgment, unchanged tool inventory, same-session state,
independent second-session state, concurrent requests, and an echo result using
legacy MCP 2025-03-26. Cancellation, server-initiated notifications,
expiry/reconnect, and hosted routing were not tested by that fixture.

Never put credentials in the command. Do not execute it on the host or construct
a shell string blindly from image metadata. Verify quoting, arguments,
environment and executable paths inside the candidate.

### Packaging boundary

For an input that **already contains a compatible Node runtime**, a multi-stage
build can copy the pinned bridge package and its own dependencies into a new,
separate directory, then run its launcher with the original stdio command.
Verify the actual release paths and Node requirements first. Preserve the
application files and user. This is adapter packaging, not permission to repair
the application's dependencies.

The supplied bridge fixture tests establish only the behaviors stated in their
results. They are not blanket validation of any user image or every MCP feature.
Rerun the same relevant checks on each actual derived image and compare the
original stdio tool inventory where safely measurable.

If the input lacks a compatible adapter runtime, do not switch its base, copy
an arbitrary Node binary, or install an application toolchain automatically.
Explain the required manual packaging and return control to the user.

### Bridge evidence required

- Original stdio startup and tool inventory are understood.
- Initialization returns an MCP session ID; follow-ups keep it.
- The same session retains its child-process state.
- Two sessions do not share the state expected to be isolated.
- Concurrent requests preserve response IDs and results.
- Relevant notifications, cancellation, reconnect and shutdown are tested,
  or explicitly untested with reasons.
- No tool filtering, prefixing, argument rewriting or result transformation.

Do not select transport flags alone and declare bridging verified. Adapters can
change transport behavior even when server code and tool schemas are unchanged.

## Readiness is not a license to rewrite MCP

Do not replace an MCP GET with a fake 200, move the MCP route to /health, buffer
an unbounded stream, or suppress errors just to make a local check pass.
Record status, timing, media type, and whether response completion was tested.
If a known current hosting requirement conflicts with the server, explain the
conflict and options; otherwise report that hosted readiness remains unverified.

## Always hand off

Application dependency repair, unsupported ABI/architecture, runtime-user
changes, functional/tool changes, undocumented flags, missing binary evidence,
or a bridge whose behavior cannot be validated: stop, report the gap, preserve
the original image, and give the user actionable next steps.
