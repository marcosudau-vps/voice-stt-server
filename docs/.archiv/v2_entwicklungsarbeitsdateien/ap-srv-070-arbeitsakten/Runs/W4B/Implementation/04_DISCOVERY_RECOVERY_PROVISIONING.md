# Discovery, Recovery and Provisioning

Discovery:

- Searches every configured path before
  `<data-root>/models/stt/fasterwhisper` and
  `<data-root>/models/stt/kroko_asr`.
- Accepts directory candidates and supported direct Kroko model files.
- Keeps read-only locations valid as discovery sources.
- Ignores `.part`/staging content.
- Performs cheap deterministic validation before any actual engine load.

Recovery:

1. Tries eligible configured realtime/final defaults.
2. Tries generic fallbacks by ascending `recovery_priority`, then stable ID.
3. Excludes no-priority products from generic fallback.
4. Uses local candidates regardless of auto-download.
5. Provisions a missing candidate only when effective auto-download and hard
   eligibility both permit it.
6. Stops escalation as soon as all required roles are load-verified.

One model can cover realtime and final. Independently requested optional
models continue after `MINIMUM_READY`; their failures are reported without
removing readiness.

Provisioning:

- Chooses the intended writable target or the guaranteed runtime-store fallback.
- Downloads to a unique sibling `.part` file.
- Verifies observed source identity, exact bytes and SHA-256.
- Activates with `os.replace` only after verification.
- Cleans staging and creates no permanent duplicate cache.

Result: PASS.
