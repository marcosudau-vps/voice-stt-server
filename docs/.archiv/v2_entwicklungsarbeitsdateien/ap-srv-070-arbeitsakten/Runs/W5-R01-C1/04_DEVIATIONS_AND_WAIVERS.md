# AP-SRV-070 / W5-R01-C1 - Deviations and Waivers

## AW-01

- **Original finding:** W5P-G03 ("archive plan before implementation")
  was violated in W5-R01 - the dated archive plan
  (`docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-06_W5_R01_PLAN.md`)
  was written after implementation had already begun, not before it.
- **Status:** `ACCEPTED BY COORDINATOR`
- **Action:** No historical rewrite. No earlier plan timestamp was faked.
  No attempt was made to retroactively make W5P-G03 PASS. The plan's
  *content* was, and remains, complete and accurate for what was actually
  built - only the sequencing (plan-before-code) was violated. This
  correction run's own `docs/.archiv/.../2026-09-06_W5_R01_UMSETZUNGSVERGLEICH.md`
  updates record what W5-R01 (corrected) actually delivers, without
  pretending the original stub-`publish()` state ever appeared in Git
  history - it did not, because that commit was never pushed and this
  correction amends it in place rather than adding a second commit (see
  section 2.4 of the correction prompt and `02_CORRECTION_REPORT.md`).
  Process discipline (plan strictly before implementation) applies again
  starting with W5-R02/W6.
- **Remaining release blocker:** None from AW-01. It is a historical
  process finding only, with no product or release-safety consequence.

## New deviations introduced during W5-R01-C1

None. Every change in this correction run is additive/corrective within
the scope defined in prompt section 5 (the real publication engine, its
adapters, resume/conflict/barrier tests, and the directly affected
documentation). No existing W5-R01 test was weakened or deleted to obtain
a PASS - two existing tests
(`tests/unit/test_release_remote_checks.py::RegistryConflictTests::test_absent_tag_is_safe_to_publish`
and `::test_runner_never_receives_a_push_or_tag_command`) were adjusted to
use a realistic Docker "no such manifest" stderr message instead of an
empty one, because `check_registry_image()` was tightened in this
correction to distinguish a genuinely absent tag from an unreachable/
missing Docker tool (previously any non-zero exit was treated as ABSENT,
which could have silently misreported "safe to publish" when the tool
simply could not be run) - see `02_CORRECTION_REPORT.md` "Conflict safety".
The assertion each test makes (absent tag -> safe to publish; the runner
receives exactly one `docker manifest inspect` call) is unchanged; only the
fixture's realism improved, and a new test
(`test_unavailable_tool_fails_closed_instead_of_claiming_absent`) was added
alongside it to cover the corrected behavior explicitly.

Similarly, `release_tooling.pipeline.dry_run()`'s signature changed from
`dry_run(state)` to `dry_run(state, manifest, adapters=None)` because the
Root Review blocker this run fixes requires dry-run to walk the same
operation graph as real publication (which needs a manifest and adapters
to check identities against) - this is the mandated redesign from prompt
section 7, not an unrelated behavior change. The corresponding tests in
`tests/unit/test_release_pipeline.py` were updated to the new signature
while preserving every original guarantee (full plan from PREPARED, shorter
plan on resume, zero writes, empty plan at COMPLETE) plus stronger,
dynamic zero-write proof via poisoned fake adapters (previously only a
static signature-introspection check).
