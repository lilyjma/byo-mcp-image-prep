# Preparation records and final response

Create `prep-summary/<unique-run-id>/`. Never replace a prior run. Keep secret
files outside this folder and every build context.

## summary.md

Include:

1. **Outcome:** ready-to-publish-for-trial, incomplete, or blocked.
2. **Identity:** input reference and digest/ID; output local tag and image ID;
   skill/baseline versions; Docker OS/architecture; test date.
3. **Approved plan:** changes, why needed, implications, and a short record of
   actual user consent. Do not manufacture approval.
4. **Changes:** proposed/applied/not-needed/declined/manual, evidence, and reason.
5. **Checks:** pass/fail/untested/observed, brief reason, sanitized evidence,
   timing, limits, and whether original or output was checked.
6. **Functional preservation:** original image unchanged, server binaries/tools
   not edited, inventory/schema comparison if available. State limits honestly.
7. **Untested:** each capability with its own reason. For example, "Cancellation
   untested: no suitable approved long-running operation was available."
8. **Deployment inputs:** future fully qualified image reference, route, port,
   environment names and purpose, credential-injection instructions.
9. **Cleanup:** exact resources created, cleanup outcome, preserved image/files.
10. **Next step:** publication/platform pull access needed; offer help pushing
    or self-service instructions, without pushing/deploying automatically.

Do not put private platform-source details in a public report or repository.

## changes.json

```json
{
  "changes": [
    {
      "change": "Select documented native HTTP transport",
      "status": "applied",
      "reason": "Input startup selected stdio",
      "approval": "Approved in the adaptation plan"
    }
  ]
}
```

## deployment-inputs.json

```json
{
  "localImage": "example-prepared:unique-run",
  "publishedImage": null,
  "mcpRoute": "/mcp",
  "port": 8080,
  "environment": [
    {"name": "SERVICE_TOKEN", "secret": true, "required": true}
  ],
  "publicationRequired": true,
  "platformPullAccessVerified": false
}
```

Do not insert a made-up registry, publish an image, or put credentials in this
file. If the user supplies a target registry, show the proposed reference as
not yet published. Do not offer a local-only tag as a deployable registry URL.

## Readiness decision

- **ready-to-publish-for-trial:** approved plan applied (or no adaptation needed);
  required external-listener, initialization, acknowledgment, discovery, and
  proxy-header checks passed; no unresolved hosting blocker.
- **incomplete:** required inputs, supported execution environment, or evidence
  are missing. Say what can be done without them.
- **blocked:** observed required failure or needed change outside approved scope.

GET readiness is advisory in this baseline. Optional downstream checks,
cancellation, bidirectional notifications, and state semantics may remain
untested, but each needs a reason. A skipped mandatory check cannot count as a
pass or support a ready verdict. A check passing once does not prove reliability.

The helper's JSON is evidence, not permission to build or a final publish verdict.
After a failure/retry preserve both observations; do not erase intermittent issues.

## Chat handoff

Keep it short:

| Change | Status | Reason |
|---|---|---|

Then show the local image, verdict, deployment inputs, location of the detailed
summary, and material limitations. End by offering publication help or
self-service instructions. Do not claim hosted readiness or downstream access
was verified locally.
