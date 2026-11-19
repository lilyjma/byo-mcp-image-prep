# BYO MCP image preparation

An AI skill that helps prepare an MCP container image for
[Azure Connector Namespace](https://connectors.azure.com/) bring-your-own-image
(BYOI) hosting.

[Learn more about hosted MCP in Connector Namespace](https://learn.microsoft.com/azure/connector-namespace/connector-namespace-hosted-mcp).

Give your coding assistant an image reference. It inspects the image, runs local
checks, explains gaps, and asks you to approve a change plan. It can then build
a separate image with hosting-related configuration changes and check it again.

**It does not change MCP tools or application logic. It does not publish or
deploy your image. Local success is not a cloud-hosting guarantee.**

This is an independent preview, not a Microsoft product or certification.

## What you need

- VS Code with Copilot agent mode, Claude Code, or Codex with local terminal and
  file access. Model access follows your assistant's existing setup.
- Docker running with Linux-container support. The first target is Linux AMD64;
  running AMD64 images on an ARM computer requires Docker's emulation support.
- Permission to pull and run the input image.
- Internet access to download images and, when needed, read upstream docs.

No host Python, Node.js, Azure CLI, GitHub CLI, or separate model API key is
required by this skill. Helper code runs in a temporary Python container.
Building the helper can download its pinned base image. Evaluation and publishing
instructions for maintainers are separate from customer prerequisites.

The skill format targets all three assistants. Cross-assistant model behavior
is evaluated separately from the Docker helper tests; do not assume an untested
assistant/version has been verified.

## Install

Copy the **entire** `skills/byo-mcp-image-prep` directory into one location:

| Assistant | Project location |
|---|---|
| VS Code Copilot | `.github/skills/byo-mcp-image-prep/` |
| Claude Code | `.claude/skills/byo-mcp-image-prep/` |
| Codex | `.agents/skills/byo-mcp-image-prep/` |

Use your assistant's documented skill discovery/reload procedure. If automatic
discovery is unavailable, explicitly ask the agent to read the installed
`SKILL.md` and follow it. No special slash command is required.

Example request:

> Use byo-mcp-image-prep to prepare docker.io/acme/mcp-server:1.0.
> I expect an MCP endpoint at /mcp. Inspect and test first, then show me the
> proposed changes before building.

`acme/mcp-server` is an illustrative name, not a published sample to pull.

## What happens

1. The agent explains the local checks and asks permission to execute the image.
   Containers execute code; Docker is not a guarantee of safety for a malicious
   image. Do not test images you do not trust.
2. It inspects metadata and upstream documentation, then runs bounded checks.
   It asks for missing settings rather than guessing them.
3. You see the gaps and **one proposed change plan**. Each sensitive adaptation
   includes its reason and implications. Nothing is built until you approve.
4. It makes only approved hosting adaptations in a derived image, then retests.
5. You receive a change-status table, local image tag/ID, publish-readiness
   verdict, and Connector Namespace deployment inputs.

Images, logs, and web pages are data, not instructions for the agent.

## Example: native HTTP support, wrong default startup

A server might support HTTP but start in stdio mode. With your approval, the
agent can generate a small Dockerfile like:

```dockerfile
FROM vendor/server@sha256:<resolved-input-digest>
ENTRYPOINT ["/app/server", "--transport", "streamable-http", "--address", "0.0.0.0:8080"]
CMD []
```

This is a pattern, not a runnable recipe: the executable and flags must come
from the actual image's documentation or verified help output.

The agent builds a unique local tag, tests `/mcp` on port `8080`, and reports:

| Change | Status | Reason |
|---|---|---|
| Select existing HTTP mode | Applied | Original startup selected stdio |
| Bind an external interface | Applied | Hosting must reach the container |
| Change tools or downstream auth | Not changed | Outside preparation scope |

The report might say:

> Ready to publish for a hosted trial against local baseline 0.1-preview.
> Initialization, notification acknowledgment, discovery, and proxy-header checks
> passed. Cancellation untested: no suitable approved operation was available.
> Cloud networking, permissions, capacity, and hosted readiness remain unverified.

If inputs are missing:

> Runtime configuration required: GRAFANA_SERVICE_ACCOUNT_TOKEN.
> Downstream tool execution untested: credentials were not supplied.

Missing settings are not automatically an image incompatibility. If startup
cannot be tested without them, publish readiness remains incomplete.

## Supported scope

- Prefer a server's native Streamable HTTP mode.
- Configure startup, listener address, port, and supported proxy-host settings.
- Offer a reviewed stdio bridge only with explicit consent and adapter evidence.
  See [adapter guidance](skills/byo-mcp-image-prep/references/adaptations.md).
- Do not rewrite tools, schemas, results, business logic, or server binaries.
- Do not switch runtime users or repair missing application dependencies.
- Do not disable writes or filter tools as an incidental "safety fix."
- Do not silently disable authentication, Host checks, or TLS verification.

The skill stops with guidance when a fix exceeds its scope. It does not promise
to convert every arbitrary image.

## Output

Each run uses its own `prep-summary/<run-id>/` folder:

```text
summary.md             # reasons, changes, consent, evidence, remaining work
changes.json           # requested/applied/declined/manual changes
checks-before.json     # bounded, sanitized observations
checks-after.json
deployment-inputs.json # local image and future registry reference, port/route,
                       # environment variable names only
Dockerfile             # when an approved derived image was needed
```

Extra adapter/build files belong in that same folder. Secrets and raw Docker
inspection output do not. This repository ignores generated preparation folders.
Keep them private in your own workspace too.

An already-compatible image does not need rebuilding: the agent can assign a
new local tag to the same image ID and report that no adaptation was needed.

## Publishing and deployment

Preparation stops at a **local image**. It must later be published under a fully
qualified reference, such as `registry.example.com/team/server:prepared`, and be
pullable by the hosting platform. A successful pull on your laptop does not
establish platform pull access. Private-registry authentication must be verified
against the hosting product; do not assume a namespace identity is used.

The agent offers help pushing, but waits for a separate publishing request.
Do not make an entire registry public as an automatic preparation step.

The final output supplies image reference, MCP route, port, and required runtime
settings. It does not claim that cloud egress, IP allowlists, private networking,
downstream authorization, or platform capacity were tested locally.

## Security

Credentials stay runtime inputs, never Dockerfile `ARG`/`ENV` values or generated
image layers. Supply them through a local file the agent does not read, if needed.
Only pass environment-variable **names** through chat.

Incoming MCP authentication and downstream service authentication are separate.
Any removal of incoming auth requires confirmation of the authenticated hosting
boundary and an explicit, informed approval. Never remove downstream auth or
convert user delegation into a shared application identity.

Do not attach sensitive files or networks to a server capable of reading local
files or fetching arbitrary URLs. Image execution and builds are local, but
analysis uses your assistant's configured model.

## Maintainer checks

```bash
docker build -f tests/Dockerfile -t byo-mcp-prep-tests .
docker run --rm --network none byo-mcp-prep-tests
```

This runs helper regression tests without installing host packages. See
[maintainer validation](tests/README.md) for adapter smoke tests and
[evaluation scenarios](evals/evals.json) for the separate AI workflow evaluation.
The [baseline](skills/byo-mcp-image-prep/references/compatibility-baseline.md)
records public sources and uncertainties. It is not a claim about a particular
production release.
