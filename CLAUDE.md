# AGENTS.md
Guidelines for AI agents working on hh-netbox-plugin.

These rules exist because UI behavior often diverges from what a developer
expects. We prioritize tests that validate real UX flows over isolated unit
tests.

## Principles
- Validate actual UX, not just code paths.
- Prefer NetBox conventions over custom patterns.
- Keep work reviewable: small PRs, clear commits, explicit tests.
- Be honest about risk and test gaps.
- Keep DIET (design-time) code separate from operational code.
- Single source of truth: design decisions live in GitHub issues, not repo docs.

## Required Testing Standard (UX-Accurate TDD)
Unit tests alone are insufficient. Every user-facing change must include
integration tests that simulate real requests and rendering.

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
- Do not mock core generation/update paths in UX flow tests unless an additional
  unmocked integration test covers the same flow.

For validation rules:
- Write negative tests for invalid data.
- Confirm the error message or form error appears in the response.

For filtering logic:
- Create multiple objects and assert only the correct subset is offered.

Regression guardrails:
- If behavior and tests conflict, update tests to match the approved issue.
- Do not “fix” code to satisfy outdated tests or stale docs.
- Example: If issue #123 says “4 be-rail-leaf switches” but tests expect 8,
  update the tests to expect 4 and keep the correct code path.

## NetBox Plugin Conventions
- Use NetBox generic views/forms/tables/templates.
- No Django admin usage for plugin features.
- Enforce RBAC with NetBox ObjectPermission.
- Use NetBox fields and helpers (DynamicModelChoiceField) when REST
  endpoints exist; otherwise use ModelChoiceField and note the limitation.
- Use plugin navigation entries and consistent template structure.

## Required Context (Read First)
- #82 (project analysis), #83 (DIET PRD), #84 (DIET sprint plan).
- Check the current DIET issue for scope and dependencies.
- Treat the issue thread as the source of truth when docs conflict.

## Environment Rules
- Always run Django/NetBox commands inside the container:
  - `cd /home/ubuntu/afewell-hh/netbox-docker`
  - `docker compose exec netbox python manage.py ...`
- Do not run manage.py on the host.
- Plugin code is volume-mounted; most changes do not require a restart.

## Local Dev Workflow (Golden Path)
- Default to local container iteration for speed; use CI only when needed.
- Before intensive dev sessions, reset DIET data to remove stale plans:
  - `scripts/reset_local_dev.sh`
- For a full clean local NetBox reset (occasional, heavier):
  - `scripts/reset_local_dev.sh --full`
- To purge inventory and reseed only DIET baselines:
  - `scripts/reset_local_dev.sh --purge-inventory`
- For targeted cleanup of a single plan:
  - `docker compose exec netbox python manage.py reset_diet_data --plan <plan_id> --no-input`

## Code Review and PR Workflow
- Use a feature branch per issue: `diet-<issue>-<short-desc>`.
- Open a PR before merging; do not commit directly to main.
- Include:
  - Summary of behavior change.
  - Test commands run.
  - Screens/notes for UI if relevant.
- Address review feedback before marking a ticket done.

## Commit and Branch Hygiene
- Keep commits focused and readable.
- Avoid mixing unrelated changes.
- Update tests alongside behavior changes.
- Do not rewrite history unless explicitly requested.
- Use commit message format: `[DIET-XXX] Short description`.

## Testing Commands (common)
- Run targeted tests for the modified feature set.
- Prefer integration tests in `netbox_hedgehog/tests/test_topology_planning/`.
- If adding new UI, add new integration tests near related ones.
- When touching models, create and apply migrations via the container.
- For interactive inspection of the 128-GPU case, use:
  - `docker compose exec netbox python manage.py setup_case_128gpu_odd_ports --clean --generate --report`

## Reporting Requirements
In your final update, include:
- UX flows verified by integration tests.
- Any known gaps or risks.
- Test commands executed (exact).
- Files changed (high level).

## File Organization
- Place DIET models in `netbox_hedgehog/models/topology_planning/`.
- Place DIET views in `netbox_hedgehog/views/topology_planning/`.
- Do not modify operational code unless explicitly required.
- Do not add new planning/spec/research docs in the repo unless explicitly requested.
  Use GitHub issues for design decisions; if a doc is required, put it in `docs/`
  and link it to the issue.

## When In Doubt
- Ask for clarification.
- Err on the side of more integration tests.
