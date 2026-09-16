# NetBox Hedgehog Plugin

A NetBox plugin for managing Hedgehog fabric Custom Resource Definitions (CRDs) with a self-service catalog interface.

## Features

- **Self-Service Catalog**: Web-based interface for creating and managing Hedgehog fabric CRDs
- **Inventory Management**: Track and monitor all fabric resources with status indicators
- **Kubernetes Integration**: Bi-directional synchronization with Kubernetes clusters
- **Multi-Fabric Support**: Manage multiple Hedgehog fabrics from a single NetBox instance
- **Real-Time Status**: Monitor CRD status and health with automatic updates

## Supported CRDs

### VPC API CRDs
- External
- ExternalAttachment  
- ExternalPeering
- IPv4Namespace
- VPC
- VPCAttachment
- VPCPeering

### Wiring API CRDs
- Connection
- Server
- Switch
- SwitchGroup
- VLANNamespace

## Installation

1. Install the plugin:
```bash
pip install netbox-hedgehog
```

2. Add to NetBox configuration:
```python
PLUGINS = [
    'netbox_hedgehog',
]

PLUGINS_CONFIG = {
    'netbox_hedgehog': {
        'kubernetes_config_file': '/path/to/kubeconfig',
        'sync_interval': 300,  # seconds
    }
}
```

3. Run migrations:
```bash
python manage.py migrate netbox_hedgehog
```

## Configuration

The plugin supports the following configuration options:

- `kubernetes_config_file`: Path to Kubernetes config file (optional)
- `sync_interval`: Interval for automatic synchronization in seconds (default: 300)
- `enable_webhooks`: Enable webhook notifications (default: True)

### Paste-only interchange prerequisite

The paste-only interchange UI has a configurable encoded-body maximum of 10 MiB
by default. Configure the NetBox host setting to at least that value before
enabling the UI; the plugin checks this at startup/`manage.py check` and will
fail loudly rather than changing a host-wide security control:

```python
# NetBox configuration (not PLUGINS_CONFIG)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
```

If `PLUGINS_CONFIG['netbox_hedgehog']['interchange_import_limits']`
raises `max_encoded_body_bytes`, raise the host setting to the same or a larger
value and restart NetBox. A deliberately lower host setting is rejected and is
never overridden by the plugin.

## Usage

### Managing Fabrics

1. Navigate to **Plugins > Hedgehog > Fabrics**
2. Click **Add Fabric** to create a new fabric configuration
3. Configure Kubernetes cluster connection details

### Creating CRDs

1. Go to **Plugins > Hedgehog > Catalog**
2. Select the CRD type you want to create
3. Fill out the dynamic form
4. Click **Apply to Kubernetes** to deploy

### Monitoring Status

The plugin provides real-time status monitoring for all CRDs:
- 🟢 **Live**: Resource is healthy in Kubernetes
- 🟡 **Syncing**: Resource is being synchronized
- 🔴 **Error**: Resource has errors or conflicts

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and contribution guidelines.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Support

For support and questions, please visit [https://hedgehog.cloud/support](https://hedgehog.cloud/support).
