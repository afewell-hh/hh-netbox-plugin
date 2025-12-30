# DIET Module Documentation

**All DIET design decisions and planning live in GitHub issues.**

This ensures:
- Single source of truth (no stale docs)
- Changes are timestamped and linked to PRs
- Discussions are preserved with context

## Key Issues

**Foundation:**
- [#82](https://github.com/githedgehog/hh-netbox-plugin/issues/82) - Project Analysis & Architecture
- [#83](https://github.com/githedgehog/hh-netbox-plugin/issues/83) - DIET PRD
- [#84](https://github.com/githedgehog/hh-netbox-plugin/issues/84) - DIET Sprint Plan

**Core Features:**
- [#117](https://github.com/githedgehog/hh-netbox-plugin/issues/117) - Fix Hardcoded Port Counts
- [#118](https://github.com/githedgehog/hh-netbox-plugin/issues/118) - Zone-Based Speed Derivation
- [#119](https://github.com/githedgehog/hh-netbox-plugin/issues/119) - Uplink Capacity from Zones
- [#127](https://github.com/githedgehog/hh-netbox-plugin/issues/127) - Unified Generate/Update Devices

**Test Cases:**
- [#123](https://github.com/githedgehog/hh-netbox-plugin/issues/123) - 128-GPU Mixed Topology Test

## Operational Docs (in this repo)

- [DIET_QUICK_START.md](DIET_QUICK_START.md) - How to use DIET module
- [DIET_TEST_CASES.md](DIET_TEST_CASES.md) - Test scenarios and setup

## For Contributors

When working on DIET features:
1. **Read the relevant GitHub issue** - it's the source of truth
2. **Do NOT create planning docs** in the repo (specs/, root, etc.)
3. **Update issues** with implementation notes as comments
4. See [AGENTS.md](../AGENTS.md) for full contributor guidelines
