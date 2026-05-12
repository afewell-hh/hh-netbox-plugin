# tests/test_topology_planning

Integration and unit tests for the DIET topology planning subsystem.

## Bootstrap Contract

The bootstrap inventory contract is enforced by `BootstrapInventoryContractTestCase`
in `test_reference_data_bootstrap.py`.

That class asserts the exact post-seed state that `load_diet_reference_data` must
produce:

| Item | Expected count |
|------|---------------|
| Required DeviceType slugs | 5 present |
| Forbidden DeviceType slugs | 5 absent |
| BreakoutOptions | 16 |
| ModuleTypes | 33 (23 transceivers + 10 NICs) |
| celestica-ds5000 OSFP interface templates | 64 |

If a bootstrap change causes any of these counts to shift, update the contract
test and the spec issue — do not silently adjust the assertion.

`test_reference_data_bootstrap.py` also covers:
- `CanonicalSwitchInventoryTestCase` — Gate 1+2: correct slug and interface types
- `SwitchBayPopulationTestCase` — Gate 3: `populate_transceiver_bays` works post-seed
- `PurgeAndReseedRoundTripTestCase` — Gate 4: purge → reseed round trip
- `LegacyMigrationCoexistenceTestCase` — DIET-556: stale migration-0009 rows are absent after correct bootstrap

## Source-of-Truth Documentation

`test_source_of_truth_docs.py` enforces that:
- 5 required README files exist at specified paths
- Each README contains the governing language pinned by spec #564
- 3 source files contain pointer comments linking to their owning README

## Test Speed

Run targeted tests with `--parallel` during development; run the full suite
sequentially for PRs. See `CLAUDE.md` for exact commands.
