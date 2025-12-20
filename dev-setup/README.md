# Development Setup Files

This directory contains configuration files for the NetBox development environment using Docker.

## Files

### docker-compose.override.yml
Override configuration for the netbox-docker environment. This file:
- Builds a custom Docker image with the plugin
- Mounts the plugin source code as a volume for live reloading
- Enables DEBUG mode for development
- Runs Django's development server instead of production WSGI

**Location to copy:** `/home/ubuntu/afewell-hh/netbox-docker/docker-compose.override.yml`

### Dockerfile-Plugins
Custom Dockerfile that extends the official NetBox image. This file:
- Installs development tools (ipython, django-extensions, coverage)
- Installs the plugin in editable mode
- Leaves plugin source to be mounted as volume

**Location to copy:** `/home/ubuntu/afewell-hh/netbox-docker/Dockerfile-Plugins`

### plugin_requirements.txt
Python package requirements for the plugin. This file:
- Installs the plugin in editable mode from the volume mount
- Can include additional plugin dependencies

**Location to copy:** `/home/ubuntu/afewell-hh/netbox-docker/plugin_requirements.txt`

## Setup Instructions

From the netbox-docker directory:

```bash
cd /home/ubuntu/afewell-hh/netbox-docker

# Copy configuration files
cp /home/ubuntu/afewell-hh/hh-netbox-plugin/dev-setup/docker-compose.override.yml ./
cp /home/ubuntu/afewell-hh/hh-netbox-plugin/dev-setup/Dockerfile-Plugins ./
cp /home/ubuntu/afewell-hh/hh-netbox-plugin/dev-setup/plugin_requirements.txt ./

# Build and start
docker compose build --no-cache
docker compose up -d

# Check logs
docker compose logs -f netbox

# Access NetBox at http://localhost:8000
# Default credentials: admin / admin
```

## How It Works

1. **Volume Mount**: The plugin source code is mounted read-only into the container at:
   ```
   /home/ubuntu/afewell-hh/hh-netbox-plugin → /opt/netbox/netbox/netbox_hedgehog
   ```

2. **Editable Install**: The `plugin_requirements.txt` installs the plugin with `-e` flag, which creates a symlink rather than copying files

3. **Live Reloading**: Django's development server (`runserver`) automatically detects file changes in the mounted volume and reloads

4. **Debug Mode**: `DEBUG=true` enables detailed error pages and better logging

## Troubleshooting

### Plugin not loading

Check that the volume mount is working:
```bash
docker compose exec netbox ls -la /opt/netbox/netbox/netbox_hedgehog
```

Should show your plugin files.

### Changes not reflecting

Restart the NetBox container:
```bash
docker compose restart netbox
```

### Import errors

Check the container logs for Python errors:
```bash
docker compose logs netbox | grep -i error
docker compose logs netbox | grep -i traceback
```

## Development Workflow

With this setup:

1. **Edit files** on the host in `/home/ubuntu/afewell-hh/hh-netbox-plugin/`
2. **Changes are immediately visible** in the container (via volume mount)
3. **Django auto-reloads** when it detects Python file changes
4. **No need to rebuild** unless you change dependencies

See CONTRIBUTORS.md for complete development workflow details.
