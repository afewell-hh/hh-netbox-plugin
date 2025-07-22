# Migration Instructions for Real-Time Monitoring Features

## Problem
After adding real-time monitoring features, you're getting this error:
```
column netbox_hedgehog_hedgehogfabric.watch_enabled does not exist
```

This is because we added new database fields but haven't applied the migrations yet.

## Solution

### Option 1: Docker Environment (Most Likely)

If you're running NetBox in Docker, run these commands:

```bash
# Apply the migration
docker-compose exec netbox python manage.py migrate netbox_hedgehog

# Or if using docker run:
docker exec -it <netbox-container-name> python manage.py migrate netbox_hedgehog

# Restart NetBox services
docker-compose restart netbox netbox-worker
```

### Option 2: Local Installation

If NetBox is installed locally:

```bash
# Navigate to NetBox directory
cd /opt/netbox

# Apply the migration
python manage.py migrate netbox_hedgehog

# Restart NetBox services
sudo systemctl restart netbox netbox-rq
```

### Option 3: Manual Verification

To verify the migration was created correctly:

```bash
# List available migrations
docker-compose exec netbox python manage.py showmigrations netbox_hedgehog

# Should show:
# netbox_hedgehog
#  [X] 0001_initial
#  [X] 0002_remaining_models
#  ...
#  [ ] 0016_add_realtime_monitoring_fields  <- This should be unapplied
```

After running the migration command, this should show:
```
#  [X] 0016_add_realtime_monitoring_fields  <- Now applied
```

## New Fields Added

The migration adds these real-time monitoring fields to HedgehogFabric:

- `watch_enabled` (BooleanField) - Enable/disable real-time watching
- `watch_crd_types` (JSONField) - List of CRD types to monitor  
- `watch_status` (CharField) - Current watch status (inactive/starting/active/error/stopped)
- `watch_started_at` (DateTimeField) - When watching was started
- `watch_last_event` (DateTimeField) - Last event timestamp
- `watch_event_count` (PositiveIntegerField) - Total events processed
- `watch_error_message` (TextField) - Last error message

## After Migration

Once the migration is applied successfully:

1. **All NetBox pages should load normally**
2. **Real-time monitoring features will be available**
3. **You can test the Kubernetes watch integration:**
   ```bash
   docker-compose exec netbox python manage.py test_k8s_watch --fabric-id 1
   ```

## Troubleshooting

If you still get errors after migration:

1. **Check migration status:**
   ```bash
   docker-compose exec netbox python manage.py showmigrations netbox_hedgehog
   ```

2. **Check for any migration conflicts:**
   ```bash
   docker-compose exec netbox python manage.py migrate --plan
   ```

3. **Restart all NetBox services:**
   ```bash
   docker-compose restart
   ```

4. **Check NetBox logs:**
   ```bash
   docker-compose logs netbox
   ```

## Success Confirmation

After successful migration, you should be able to:
- ✅ Access all NetBox and HNP pages without errors
- ✅ See new real-time monitoring fields in fabric admin/detail pages
- ✅ Use the new WebSocket real-time features
- ✅ Test Kubernetes watch integration

Let me know if you need help with any of these steps!