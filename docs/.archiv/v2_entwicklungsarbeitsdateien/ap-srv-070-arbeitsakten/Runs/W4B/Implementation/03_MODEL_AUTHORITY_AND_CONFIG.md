# Model Authority and Configuration

- Static product facts are represented by frozen `ProductModel` records:
  stable ID, engine, language, license/runtime class, roles, immutable source
  identity, expected file facts, fundamental provisioning eligibility and
  optional recovery priority.
- Mutable `OperatorIntent` contains only enablement, defaults, custom paths,
  auto-download scope and supported priority overrides.
- Operator config cannot create or overwrite hashes, sizes, revisions, rights,
  license class or runtime variant.
- Faster-Whisper models remain locally discoverable/selectable, but are not
  automatically provisioned where immutable byte authority is unavailable.
- Kroko authority reuses the pinned model manifest. Community policy-required
  and Pro-prohibited entries remain hard provisioning blocks where applicable.
- Pro readiness additionally requires compatible Pro runtime and a present
  runtime license prerequisite. Only its boolean presence is retained.
- Effective download intent is exactly:
  `global OR engine OR model`. Hard eligibility is evaluated separately.
- Defaults are conservative: no large download occurs solely at server start.
- The existing `ServerSettings`, YAML loader and CLI remain the sole settings
  authority.

Result: PASS.
