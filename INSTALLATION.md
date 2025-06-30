# Hedgehog NetBox Plugin - Installation Guide

## Proven Installation Process

This guide documents the tested and working installation process for the Hedgehog NetBox Plugin.

### Prerequisites
- NetBox 4.3+ running in Docker
- Docker compose setup
- Plugin files in accessible directory

### Installation Steps

1. **Configure Plugin in NetBox**
   ```python
   # In netbox-docker/configuration/plugins.py
   PLUGINS = ["netbox_hedgehog"]
   
   PLUGINS_CONFIG = {
       "netbox_hedgehog": {
           "kubernetes_config_file": None,
           "sync_interval": 300,
           "enable_webhooks": True,
           "max_concurrent_syncs": 5,
           "debug_mode": True,
       }
   }
   ```

2. **Copy Plugin Files to Container**
   ```bash
   cd netbox-docker/
   sudo docker compose cp ../netbox_hedgehog/ netbox:/opt/netbox/netbox/
   ```

3. **Restart NetBox**
   ```bash
   sudo docker compose restart netbox
   ```

4. **Verify Installation**
   - Check plugin appears in Admin → Plugins
   - Navigate to Hedgehog menu in main interface
   - Test page navigation

### Troubleshooting

- **URL Pattern Errors**: Ensure all navigation links reference existing URL patterns
- **Template Errors**: Verify all templates extend base/layout.html correctly  
- **Import Errors**: Check all view imports are available
- **Container Issues**: Use `sudo docker compose logs netbox` to debug

### Current Functionality

The plugin provides:
- Dashboard with overview
- Fabric Management interface
- VPC Management interface  
- Network Topology visualization
- Proper NetBox integration and styling

### Architecture

- **URLs**: Simple TemplateView-based routing
- **Templates**: NetBox-styled templates with proper navigation
- **Navigation**: Organized menu with sections
- **Models**: Ready for integration (not yet active)