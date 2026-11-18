# W5-R04 — 03 Reference Comparison

`marcosudau-vps/admin_portal_workspaces` is the reference for the **release
philosophy** (prompt section 3), not a template to copy. This document records,
property by property, what VoiceSTT adopts, what it keeps that is stronger, and
where it deliberately differs.

## 1. Properties adopted from admin_portal_workspaces

| Reference property | How W5-R04 realises it in VoiceSTT |
| --- | --- |
| CI on the exact release-candidate SHA | `release-candidate.yml` is `workflow_dispatch` only and checks out the dispatched ref; the candidate manifest binds `sourceCommit` and `sourceTree`, and publication refuses any other identity. |
| Release tag only after deterministic tests/build/CI | `git_tag` is the first step of `release-publish.yml`, and the publish workflow is only reachable after a qualified candidate exists and the `release` environment approval is granted. |
| GitHub Actions performs publishing | Both new workflows run on GitHub-hosted runners; no operator machine is part of release authority. |
| Docker Hub mandatory | `dockerhub` is a mandatory `PUBLISH` step in the canonical graph for **both** Free and Pro; there is no path that skips it. |
| GHCR uses `GITHUB_TOKEN` | The `ghcr` and `aliases` jobs use the workflow-provided `GITHUB_TOKEN` with `packages: write`. No long-lived GHCR PAT. |
| Exact Docker Hub image published first | Graph order is `DOCKERHUB_PUBLISHED -> GHCR_PUBLISHED`; the engine cannot run them the other way round. |
| `docker buildx imagetools create` promotes the exact manifest instead of rebuilding | `GHCRAdapter.publish()` promotes the Docker Hub manifest **by digest**. No second production build exists anywhere in the graph. |
| Digest equality verified | `remote_checks.check_registry_image` compares the remote manifest digest with the digest recorded in the candidate manifest; every registry step is post-verified by the engine. |
| Movable aliases only after exact artifacts exist in both registries | `aliases` is a separate step whose `from_state` is `EXTERNAL_VERIFIED`, which is only reachable once Docker Hub **and** GHCR exact identities verified. |
| GitHub Release created last | `github_release` follows `ALIASES_PUBLISHED`; `final_verification` and `COMPLETE` follow it. |
| Incomplete releases resume under the same version | Already a VoiceSTT strength; retained and strengthened (see section 2). |
| Exact SemVer tags never silently overwritten | Registry adapters raise `ConflictError` on any existing-but-different exact tag; the Git tag adapter does the same and never force-pushes or moves a tag. |
| Third-party Actions pinned to immutable commit SHAs | Every `uses:` in all three workflows is pinned to a full 40-character commit SHA, and a guard test fails the build if a tag reference is reintroduced. |

## 2. VoiceSTT strengths that MUST NOT be lost — and were not

| VoiceSTT strength | Status after W5-R04 |
| --- | --- |
| Explicit RC manifest | Retained and extended (schema v2 adds registry digests, staging references and candidate/run identity). |
| Exact source commit + tree identity | Retained; additionally bound into the candidate manifest, the release state and the production build manifests. |
| Wheel/sdist SHA256 binding | Retained; the sdist is now produced by the candidate orchestrator rather than assumed. |
| Kroko Free/Pro fingerprint and artifact SHA256 authority | Retained unchanged as authority; the Linux fingerprint is now *stronger* because the builder container is part of it. |
| Separate Free/Pro production image identities | Retained; both are mandatory in every publication step and alias step. |
| Explicit state machine | Retained as the single canonical authority. Workflows call it; they never reimplement it. |
| `MATCH / ABSENT / CONFLICT / UNKNOWN` fail-closed remote verification | Retained for every surface, including the two new steps (aliases, promotion). |
| Verification before write and post-write verification | Retained; unchanged engine semantics. |
| Same-version resume | Retained and strengthened by candidate binding. |
| Conflict = STOP, never overwrite | Retained. |
| Dry-run and real publication share the same operation graph | Retained; `stop_after` is the only new axis and it applies identically in both modes. |
| No public version bump because a publication step failed | Retained; `prepare-next-version` remains a separate, explicit, non-publish command. |

## 3. Deliberate differences from the reference

| Difference | Reason |
| --- | --- |
| VoiceSTT publishes to **PyPI** as well | VoiceSTT is a Python distribution; the reference has no PyPI surface. Trusted Publishing (OIDC) is used so no PyPI token exists in the repository. |
| VoiceSTT has a **private staging registry** between qualification and publication | The reference rebuilds nothing but also qualifies and publishes in one pass. VoiceSTT's approval boundary sits between them, so the qualified OCI manifests must survive across workflow runs without a rebuild. |
| VoiceSTT keeps a **Python state machine** rather than shell ordering | Prompt sections 10 and 31: one canonical graph for dry-run, real publication and resume. Workflow YAML only supplies credentials, permissions and the `--until` boundary. |
| VoiceSTT has a **Free/Pro product split** | Every registry step operates on both variants and treats "one variant published, one not" as an unfinished step, never as success. |
| The Git tag is created **before** the first public artifact | Prompt section 15 supersedes the reference's ordering as well as VoiceSTT's previous ordering: once `2.0.0` exists on PyPI the version is publicly reserved, so the immutable source anchor must already exist. |
