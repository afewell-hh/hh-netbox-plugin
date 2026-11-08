# Hedgehog NetBox Plugin (HNP) Documentation Index

This index points to the maintained entry points for HNP, a NetBox plugin. It does not
catalog features or report project status. Several linked guides are dated; the "Status"
notes below say which ones to treat with caution. Where a guide and the source disagree,
approved issue decisions establish intended behavior, and source is implementation
evidence. Unresolved discrepancies must be reconciled, not assumed away.

## For end users

| Need | Start here | Notes |
|------|-----------|-------|
| Install and configure the plugin | [Installation](../INSTALLATION.md), [root README](../README.md#installation) | Setup, version and runtime requirements are not restated here. Follow those files and check them against your NetBox version. |
| Plan a topology (DIET) | [DIET Quick Start](DIET_QUICK_START.md) | Design-time usage path. |
| DIET topology plan YAML | [DIET Topology Plan YAML Reference](DIET_TOPOLOGY_PLAN_YAML_REFERENCE.md) | Reference for the YAML loaded by `apply_diet_test_case`. |
| Shared physical NIC cages (`hnp_nic_cage_map`) | [Schema, absent vs present key, and ingest rules](DIET_TOPOLOGY_PLAN_YAML_REFERENCE.md#mapped-nic-cage-layouts-hnp_nic_cage_map); [native API configuration how-to](DIET_TEST_CASES.md#configuring-a-mapped-nic-type-through-the-native-netbox-api) | Optional metadata on a NIC ModuleType. It is configured only through the native NetBox ModuleType/Profile API and checked with a read-back; YAML ingest only references it. Synthetic behavior only, with no hardware or optical qualification. The how-to is a maintained section inside an otherwise historical scenario page (see below). |
| Portable text interchange | [Paste-only interchange prerequisite](../README.md#paste-only-interchange-prerequisite) | Host-setting prerequisite; not a full interchange usage guide. See [Text interchange](#text-interchange) below. |
| Operational (Kubernetes/fabric) features | [Quick Start](QUICK_START.md), [User Guide](USER_GUIDE.md), [Workflows](WORKFLOWS.md), [Service Account Setup](SERVICE_ACCOUNT_SETUP.md) | Written in mid-2025. They have not been re-verified against the current source. |
| REST API for operational resources | [API Reference](API_REFERENCE.md) | Written in mid-2025. It does not document an interchange REST or GraphQL API. |

## For developers and contributors

| Need | Start here |
|------|-----------|
| Contributor and agent rules (UX-accurate testing, branch and commit conventions, container-based commands) | [Contributing guide](CONTRIBUTING.md) (canonical); [AGENTS.md](../AGENTS.md) and [CLAUDE.md](../CLAUDE.md) are thin entry points to it |
| Testing approach for DIET | [Testing Strategy](TESTING_STRATEGY.md), plus the "Testing commands" section of the [Contributing guide](CONTRIBUTING.md#testing-commands) |
| Local development environment | [Development Environment Setup](../DEVELOPMENT_ENVIRONMENT_SETUP.md), [CONTRIBUTORS.md](../CONTRIBUTORS.md), `scripts/setup_dev_env.sh` |
| DIET design decisions | [DIET Module Documentation](DIET_README.md). It states that design decisions live in GitHub issues, not in repo docs. |

Setup instructions in these files are dated and may overlap. This index does not pick
one as authoritative. The [Contributing guide](CONTRIBUTING.md) is the maintained contributor entry point.

## Current program and accepted direction

Work tracking, architecture and roadmap decisions live in GitHub issues, not in this
file. Issue closure alone is not proof that something is implemented; check the source.

- [#617](https://github.com/afewell-hh/hh-netbox-plugin/issues/617): the active HNP/AID evolution program and its tracking. Current work, status and ticket inventory are there, not here.
- [#660](https://github.com/afewell-hh/hh-netbox-plugin/issues/660), [#661](https://github.com/afewell-hh/hh-netbox-plugin/issues/661) and [#662](https://github.com/afewell-hh/hh-netbox-plugin/issues/662): accepted architecture and roadmap decisions (read each issue's amendments and the corrected dependency table in #662).

Accepted direction:

- Portable design functionality, a NetBox/HNP adapter and UI, and NetBox ownership of deployed DCIM state.

What those decisions did not do:

- They did not select a new language, runtime or service boundary.
- Extraction (T6) is gated.
- HNP remains a NetBox plugin.
- The older standalone AID repository is historical exploration relative to this program. It is not evidence that the new core is deployed there or synchronized with it.
- No completed external AID service is claimed.

## Text interchange

Portable v1 text interchange is implemented as a synchronous core with a paste-only UI.
It is the delivered surface, and the sources are:

- Core: [`netbox_hedgehog/interchange.py`](../netbox_hedgehog/interchange.py) (#675)
- Models: [`netbox_hedgehog/models/interchange.py`](../netbox_hedgehog/models/interchange.py) and migrations `0057`–`0059`
- UI: [`netbox_hedgehog/views/interchange.py`](../netbox_hedgehog/views/interchange.py) (#684), templates in `netbox_hedgehog/templates/netbox_hedgehog/interchange/`, routes under `interchange/` in [`netbox_hedgehog/urls.py`](../netbox_hedgehog/urls.py)
- Host-setting prerequisite: [root README](../README.md#paste-only-interchange-prerequisite)
- Completion and limit records: [#675](https://github.com/afewell-hh/hh-netbox-plugin/issues/675), [#684](https://github.com/afewell-hh/hh-netbox-plugin/issues/684), [#709](https://github.com/afewell-hh/hh-netbox-plugin/issues/709)

Boundaries, as the source states them:

- The UI is paste-only. `urls.py` says upload and API are deliberately absent, and `views/interchange.py` says there is no upload or public API surface.
- This index does not claim a public interchange REST or GraphQL API, or a file-upload release.
- Runtime reaper deployment in the shared environment is not claimed.
- Equivalence evidence (#669) is diagnostic only. No parity claim is made.
- Specifications and test-evidence handoffs, such as [#712](https://github.com/afewell-hh/hh-netbox-plugin/issues/712) and [#719](https://github.com/afewell-hh/hh-netbox-plugin/issues/719), do not by themselves establish implementation or release. See the linked issues for their current acceptance records.

## Historical or superseded material

Do not read these as current architecture or status.

- [`../archive/`](../archive/) and `../project_management/`: older project-management and architecture pages (for example `archive/project_management_old/ARCHITECTURE_OVERVIEW.md`, last updated 2025-07-02).
- [`../ARCHITECTURE_DECISION_NETBOX_CORE_MODELS.md`](../ARCHITECTURE_DECISION_NETBOX_CORE_MODELS.md): a 2025-12-19 proposal marked "Proposed - Awaiting User Confirmation".
- [DIET-140 Architecture Options](DIET-140-ARCHITECTURE-OPTIONS.md), [DIET-140 Research Summary](DIET-140-RESEARCH-SUMMARY.md), [DIET Generation Patterns](DIET-GENERATION-PATTERNS.md) and its [Summary](DIET-GENERATION-PATTERNS-SUMMARY.md), [DIET Test Cases](DIET_TEST_CASES.md): DIET research and design notes. Defer to the issue threads where they conflict.
- The root-level `DEVELOPMENT_GUIDE.md` and `PROJECT_MANAGEMENT.md`, which earlier versions of this index linked, do not exist in the tracked tree. `project_management/DEVELOPMENT_GUIDE.md` and `project_management/ARCHITECTURE.md` exist but have not been verified as current.

## Reference-architecture (RA) pipeline files

[RA Asset Publishing](RA_ASSET_PUBLISHING.md), [RA Pipeline Execution Plan](RA_PIPELINE_EXECUTION_PLAN.md), [RA pilot translation worksheet](ra_pilot_translation_worksheet.md), and the RA variant manifest [catalog](ra_variant_manifest_catalog.yaml) and [template](ra_variant_manifest_template.yaml). These were not reviewed for currency.
