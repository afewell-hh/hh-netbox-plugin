# Contributing to hh-netbox-plugin (contributors and AI agents)

This is the single canonical contributor and agent workflow for HNP. The root
[AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md) are thin entry points that point
here. It is a workflow guide, not an architecture manual; see the
[documentation index](README.md) for current-architecture and historical material.

These rules exist because UI behavior often diverges from what a developer expects. We
prioritize tests that validate real UX flows over isolated unit tests.

## Principles
- Validate actual UX, not just code paths.
- Prefer NetBox conventions over custom patterns.
- Keep work reviewable: small PRs, clear commits, explicit tests.
- Be honest about risk and test gaps.
- Keep DIET (design-time) code separate from operational code.
- Single source of truth: design decisions live in GitHub issues, not repo docs.

## Task, context and authority
- The current task assignment, plus the accepted program decisions in
  [#617](https://github.com/afewell-hh/hh-netbox-plugin/issues/617),
  [#660](https://github.com/afewell-hh/hh-netbox-plugin/issues/660),
  [#661](https://github.com/afewell-hh/hh-netbox-plugin/issues/661) and
  [#662](https://github.com/afewell-hh/hh-netbox-plugin/issues/662), define the work.
  Read each issue's amendments. Do not copy mutable program or CI status into repo docs.
- #82 (project analysis), #83 (DIET PRD) and #84 (DIET sprint plan) are historical
  background; consult them where relevant to DIET, but they do not override the current
  task or accepted decisions.
- Check the current issue for scope and dependencies. The issue thread is the source of
  truth when docs conflict. Issue closure alone is not proof that something is implemented.
- Those decisions did not select a new language, runtime or service boundary, and they do
  not waive any gate (for example T6 extraction or #711/#715/#716/#719).
- Before editing, confirm the sources and capabilities the task needs are accessible. A
  complete, source-bound requirements packet supplied by the lead may stand in for
  dependency context; an unverified summary cannot silently change accepted rules. If
  required context is unavailable, stop before editing and report the gap. Do not guess
  that missing access is a permission error, and do not broaden permissions.
- Shared and user work, and previews, are preserved by default.

### Roles
- **Lead**: owns scope, dispatch, verification arrangement, acceptance and authorized
  integration.
- **Source worker**: implements exactly one scoped task.
- **Independent reviewer**: a cross-model reviewer who assesses requirements and defects
  and grants no merge authority.
- Each role's assignment must be explicit in the task. Agent comments, badges and issue
  closure are not authority by themselves. Routine authorized handoffs need no customer
  relay. Same-account GitHub use is supported. The lead confirms actual dispatch
  acknowledgement rather than assuming bot-to-bot delivery.
- Do not run blanket automatic repair loops, replay operations of uncertain outcome, or
  start duplicate writers. Budgets and stop conditions are set per task.
- Monitoring while a lead session is active is distinct from a configured persistent
  scheduler. Runtime ownership and workspace are distinct; a session restart does not
  imply reconfiguration.
- These are project workflow expectations, not claims of runtime enforcement.

### Source worker handoff
Return the exact base and head, the diff limited to allowed paths, a per-criterion
handoff, checks performed / denied / unrun, documentation updated, and known limits.

## Required testing standard (UX-accurate TDD)
Unit tests alone are insufficient. Every user-facing change must include integration tests
that simulate real requests and rendering.

Minimum test coverage for any UI flow:
- List view loads (200).
- Add form loads (200).
- Valid POST creates object and redirects (302).
- Detail view renders expected data and template.
- Edit workflow updates object.
- Delete workflow removes object.
- Permission enforcement:
  - Without permission -> 403 or access denied.
  - With NetBox ObjectPermission -> success.

Integration test fidelity:
- Do not mock core generation/update paths in UX flow tests unless an additional unmocked
  integration test covers the same flow.

For validation rules:
- Write negative tests for invalid data.
- Confirm the error message or form error appears in the response.

For filtering logic:
- Create multiple objects and assert only the correct subset is offered.

Regression guardrails:
- If behavior and tests conflict, update tests to match the approved issue.
- Do not "fix" code to satisfy outdated tests or stale docs.
- Example: If issue #123 says "4 be-rail-leaf switches" but tests expect 8, update the
  tests to expect 4 and keep the correct code path.

## NetBox plugin conventions
- Use NetBox generic views/forms/tables/templates.
- No Django admin usage for plugin features.
- Enforce RBAC with NetBox ObjectPermission.
- Use NetBox fields and helpers (`DynamicModelChoiceField`) when REST endpoints exist;
  otherwise use `ModelChoiceField` and note the limitation.
- Use plugin navigation entries and consistent template structure.

## Environment rules
- Always run Django/NetBox commands inside the container:
  - `cd /home/ubuntu/afewell-hh/netbox-docker`
  - `docker compose exec netbox python manage.py ...`
- Do not run `manage.py` on the host.
- Plugin code is volume-mounted; most changes do not require a restart.
- **Prerequisite: the plugin must be registered in the netbox-docker config.**
  `netbox-docker/configuration/plugins.py` must contain `PLUGINS = ["netbox_hedgehog"]`
  (merge it with any other plugins already listed; do not overwrite them). Without it,
  tests fail with `RuntimeError: HedgehogFabric not in INSTALLED_APPS`.
  `scripts/setup_dev_env.sh` can apply it, but running it or editing configuration is a
  change to the environment: do it only when the task names that environment and
  authorizes it. This guide grants no implicit install, setup or configuration permission.

### GitHub-hosted workers
Agents running as GitHub workers do not run project tests, setup, installers, containers,
database operations or credential/cloud-consuming programs merely because this guide
mentions them. Executable tests go to existing CI or to a separately authorized
environment. Tool permission prefixes and instruction text are not a sandbox.

## Local development workflow
- Prefer local container iteration for speed where an authorized environment exists; use
  CI when needed or when no such environment is authorized.
- Run the cheapest relevant checks early, but keep every gate the task requires and
  existing branch protection. Never label skipped, failed or unrun checks as passing.

### Destructive reset and cleanup (explicit authorization required)
Shared and user work and previews are preserved by default. The commands below delete or
reseed data. They are references, not startup steps, and must not be run routinely.
Before using any of them, the task must name the target environment and grant authority
for it, and that environment must be isolated. The same condition covers any recipe
containing `--clean`.

- `scripts/reset_local_dev.sh`: reset DIET data to remove stale plans.
- `scripts/reset_local_dev.sh --full`: full clean local NetBox reset (heavier).
- `scripts/reset_local_dev.sh --purge-inventory`: purge inventory and reseed only DIET
  baselines.
- `docker compose exec netbox python manage.py reset_diet_data --plan <plan_id> --no-input`:
  targeted cleanup of a single plan.
- `docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean --generate --report`:
  interactive inspection of the 128-GPU case; `--clean` is destructive.

## Code review and PR workflow
- Use a feature branch per issue: `diet-<issue>-<short-desc>` (or the branch named by the
  task).
- Open a PR before merging; do not commit directly to main.
- Include:
  - Summary of behavior change.
  - Test commands run.
  - Screens/notes for UI if relevant.
- Address review feedback before marking a ticket done.
- Exact-head review and checks must match the candidate head. Connector bug review is
  supplemental when full acceptance-criteria assessment is required.

## Commit and branch hygiene
- Keep commits focused and readable.
- Avoid mixing unrelated changes.
- Update tests alongside behavior changes.
- Do not rewrite history unless explicitly requested.
- Use commit message format: `[DIET-XXX] Short description`.

## Testing commands
- Run targeted tests for the modified feature set.
- Prefer integration tests in `netbox_hedgehog/tests/test_topology_planning/`.
- If adding new UI, add new integration tests near related ones.
- When touching models, create and apply migrations via the container.

`scripts/run_diet_tests.sh` is the supported local DIET test command. It explicitly selects
the test-only `DietTestRunner`, which refuses non-test databases before applying the
DIET-643 autovacuum guard. Do not replace it with a production `TEST_RUNNER` setting or
pass a different `--testrunner` value, and do not call `manage.py test` directly in its
place.

### Parallel vs sequential
`--parallel N` creates isolated per-worker test databases and is useful for targeted
development runs. Use N <= available CPUs / 2.

```bash
# Targeted dev-cycle run
scripts/run_diet_tests.sh \
  netbox_hedgehog.tests.test_topology_planning.test_unified_generate_update \
  netbox_hedgehog.tests.test_topology_planning.test_form_validation \
  --keepdb --parallel 4

# Full regression sweep (for waivers/PRs): always sequential
# --parallel fails with pickling errors when pre-existing failures exist
scripts/run_diet_tests.sh \
  netbox_hedgehog.tests.test_topology_planning \
  --keepdb --exclude-tag=slow --timing --durations 0
```

**Rule:** `--parallel` is for green targeted runs only. The full regression sweep must stay
sequential so failure tracebacks can be captured reliably.

The suite size and runtime change over time and are not recorded here. Use `--timing` and
`--durations` output from an actual run as evidence, and state in reports which tests were
and were not run.

## Reporting requirements
In your final update, include:
- UX flows verified by integration tests.
- Any known gaps or risks.
- Test commands executed (exact), including checks denied or not run.
- Files changed (high level).

## File organization and documentation
- Place DIET models in `netbox_hedgehog/models/topology_planning/`.
- Place DIET views in `netbox_hedgehog/views/topology_planning.py`. Keep DIET code separate
  from operational code; do not move existing code.
- Do not modify operational code unless explicitly required.
- Update documentation together with code. Update existing canonical pages first; add a
  new page only for a distinct purpose, and link it from the [documentation index](README.md).
- Do not add new planning/spec/research/status docs in the repo unless explicitly
  requested. Use GitHub issues for design decisions and temporal plans or status; if a doc
  is required, put it in `docs/` and link it to the issue.

## When in doubt
- Ask for clarification.
- Err on the side of more integration tests.
