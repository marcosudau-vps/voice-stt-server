# Concurrency, Atomicity and Security

- Manager refresh is serialized and publishes only a fully built candidate
  snapshot.
- Service refresh/scheduler activation is serialized by the W4B refresh lock.
- Failed manager refresh or downstream scheduler activation retains/restores
  registry, role assignment and last-known-good readiness.
- Provisioning uses module-global, target-specific locks so independent manager
  instances converge safely on one final target.
- Unique exclusive `.part` creation and atomic `os.replace` prevent partial
  discovery or activation.
- Hash, byte-count and source mismatches fail before final-path replacement.
- No archive extraction is used. Authoritative filenames must be basenames,
  rejecting separators, dot names and traversal forms.
- Kroko Pro secret values are never stored as metadata. Diagnostics redact
  environment/option secret values, including exception text.
- Health output is path-free; full model status is restricted to the existing
  admin authorization boundary.
- Static callgraph scan found engine network downloads only in the central
  provisioner and no Kroko native build invocation.
- Scope scan found no model blobs, temp downloads, generated logs, credentials
  or Pro keys in the change set.

Result: PASS.
