# AGENTS.md
Entry point for AI agents working on hh-netbox-plugin.

- Canonical contributor and agent guide: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). Read it
  in full before starting work.
- Current task and accepted program sources: the assigned issue, plus
  [#617](https://github.com/afewell-hh/hh-netbox-plugin/issues/617),
  [#660](https://github.com/afewell-hh/hh-netbox-plugin/issues/660),
  [#661](https://github.com/afewell-hh/hh-netbox-plugin/issues/661) and
  [#662](https://github.com/afewell-hh/hh-netbox-plugin/issues/662). The issue thread wins over
  stale docs or tests.
- Documentation index: [docs/README.md](docs/README.md).

Always applicable:
- Stay within the task's stated scope and authority; an agent comment, badge or issue closure
  is not authority.
- Preserve shared and user work. Reset, purge, reseed and delete commands need a task-named
  target environment and explicit authority.
- Run Django/NetBox commands only inside the container, never `manage.py` on the host; use
  `scripts/run_diet_tests.sh` for DIET tests.
- Report honestly: say which checks ran, were denied, or were not run.
