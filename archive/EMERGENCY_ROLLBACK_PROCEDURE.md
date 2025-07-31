# EMERGENCY ROLLBACK PROCEDURE
**Created**: 2025-07-25 07:57:38
**Purpose**: Restore NetBox to exact working state before CSS changes

## Current Working State (BEFORE CSS Changes)
- **Container**: netbox-docker-netbox-1 using netbox-hedgehog:latest
- **Image ID**: 7956e55af217 
- **Status**: Up, healthy, accessible at http://localhost:8000
- **Backup Image**: netbox-hedgehog:backup-before-css-20250725-075738

## IMMEDIATE ROLLBACK COMMANDS
If anything goes wrong, execute these commands in order:

```bash
# 1. Stop containers
cd /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker
sudo docker compose down

# 2. Restore backup image to latest tag
sudo docker tag netbox-hedgehog:backup-before-css-20250725-075738 netbox-hedgehog:latest

# 3. Restart containers
sudo docker compose up -d

# 4. Wait for health check
sleep 60

# 5. Verify restoration
curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:8000/plugins/hedgehog/fabrics/
```

## Current Configuration Files
- **plugins.py**: Clean, no EOF issues
- **docker-compose.override.yml**: Uses netbox-hedgehog:latest image with port 8000:8080

## Verification Commands
```bash
# Check container status
sudo docker ps | grep netbox

# Check image is correct
sudo docker images | grep netbox-hedgehog

# Test functionality
curl http://localhost:8000/plugins/hedgehog/fabrics/
```

## Expected Working State
- HTTP 200 response from http://localhost:8000/plugins/hedgehog/fabrics/
- Container shows "healthy" status
- No errors in docker logs

## Emergency Contact
- Git commit with working state: Latest commit in feature/css-consolidation-readability
- Working directory: /home/ubuntu/cc/hedgehog-netbox-plugin/gitignore/netbox-docker