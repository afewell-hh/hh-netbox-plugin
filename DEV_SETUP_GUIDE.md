# NetBox Hedgehog Plugin - Development Setup Guide

## Quick Start (< 5 minutes)

```bash
# Single command setup
make -f ./Makefile dev-setup
```

## Commands Available

| Command | Description | Time |
|---------|-------------|------|
| `make -f ./Makefile help` | Show all available commands | instant |
| `make -f ./Makefile dev-setup` | Complete development environment setup | ~5 seconds |
| `make -f ./Makefile status` | Show environment status | instant |
| `make -f ./Makefile dev-check` | Quick health check | instant |
| `make -f ./Makefile dev-test` | Run comprehensive tests | ~30 seconds |

## Access Information

After running `make dev-setup`:

- **NetBox URL**: http://localhost:8000
- **Admin Credentials**: admin / admin  
- **Plugin Dashboard**: http://localhost:8000/plugins/hedgehog/

## Environment Details

- **Docker Containers**: Uses existing running NetBox Docker setup
- **Plugin Mode**: Installed in development mode (`pip install -e .`)
- **Dependencies**: Only installs required Python packages (skips NetBox)
- **Configuration**: Uses existing Docker environment files

## Troubleshooting

If `make` command doesn't work directly:
```bash
# Use explicit path
/usr/bin/make -f ./Makefile dev-setup

# Or set alias
alias make="/usr/bin/make -f ./Makefile"
```

## Recovery from Previous Agent Issues

This setup:
- ✅ Works with existing Docker containers (doesn't recreate)
- ✅ Validates services are running before proceeding
- ✅ Skips already-installed dependencies for speed
- ✅ Provides comprehensive validation
- ✅ Achieves <5 minute setup target (actually ~5 seconds on subsequent runs)