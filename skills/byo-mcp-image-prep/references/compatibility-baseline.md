# Local compatibility baseline

Baseline: **0.1-preview**. Skill version: **0.1.0**.

This is a provisional, public-source baseline for preparation, not an official
platform contract. No production deployment/version is asserted. Update it
when verified platform requirements change; version the test expectations with
the baseline. Do not silently replace it with agent assumptions.

Internal platform revisions, if used by maintainers, must remain in an approved
private record. Do not copy private code, repository links, identifiers, logs,
or configuration into this public package.

## Platform-facing expectations

| Area | Baseline and confidence |
|---|---|
| Image address | A published, fully qualified OCI registry reference is the deployment input. Platform pull authorization is separate from local Docker authentication. |
| Architecture | Target Linux AMD64 for this preview. This is the tested target, not proof that the platform forbids all other architectures. |
| Startup | A packaged unattended startup must expose the intended HTTP service. ENTRYPOINT and CMD are both valid Docker concepts; no evidence here establishes that CMD is unsupported. |
| Transport | Prepare native Streamable HTTP or an explicitly approved stdio bridge. A Docker image that only speaks stdio is not an HTTP endpoint merely because it declares EXPOSE. |
| Binding | The service must be reachable outside its own network namespace. A reachable interface or approved forwarding adapter is needed for loopback-only applications. |
| Route and port | Deployment inputs must match the actual service. Neither port 8080, path /mcp, a separate /health route, nor a shell is mandatory for every server. |
| Proxy | Test representative non-localhost Host headers and preservation of MCP request/response headers. This is a simulation, not full platform-proxy conformance. |
| Sessions | Stateful MCP uses server-issued Mcp-Session-Id and follow-up headers. Test session behavior; do not promise per-user/chat isolation or sandbox affinity from header propagation alone. |
| Authentication | Incoming MCP auth and downstream auth are independent. Do not assume the user's laptop login becomes available in the container. |
| Readiness | Exact current hosted probe behavior is unverified in this public baseline. Record GET headers/completion separately; do not require HTTP 200, reject all 202/400/405 responses, or rewrite the MCP endpoint to a fake health response. |
| Resources | Use the user's intended CPU/memory constraints and a bounded startup budget. Defaults in a checker are local test settings, not platform guarantees. |

## What a local pass does not establish

- Cloud egress addresses, allowlists, private connectivity or DNS.
- Support for a particular downstream non-HTTP protocol or inspection mode.
- Downstream credentials, scopes, data permissions or user delegation.
- Private-registry pull integration or geographic availability.
- Platform capacity, cold-start budgets, or a particular deployed release.
- Full equivalence of arbitrary application behavior.

These are explicit limitations, not reasons to label a local check passed.

## Public sources

- [Container Apps Sandboxes overview](https://learn.microsoft.com/azure/container-apps/sandboxes-overview)
- [Sandbox ports and external binding](https://sandboxes.azure.com/docs/sandboxes/sandbox/ports)
- [Sandbox disk images](https://sandboxes.azure.com/docs/sandboxes/disk-images)
- [Sandbox networking and egress](https://sandboxes.azure.com/docs/sandboxes/sandbox/egress)
- [MCP Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle)

Sources describe different boundaries: sandbox capabilities are not automatically
exposed by Connector Namespace BYOI. Read sources critically and disclose gaps.

## Promoting a baseline

Record which expectation changed, the public evidence or owner-approved public
statement, corresponding tests, and whether old results need retesting. Keep
historical reports bound to the baseline they actually used. Do not claim
automatic knowledge of a newer platform version.
