#!/bin/bash
# Ensure NetBox Hedgehog sync infrastructure is running properly

echo "=== NetBox Hedgehog Sync Infrastructure Setup ==="

# Check if RQ workers are running
RQ_WORKER_COUNT=$(sudo docker exec netbox-docker-netbox-1 ps aux | grep -c "rqworker" | grep -v grep)
RQ_SCHEDULER_COUNT=$(sudo docker exec netbox-docker-netbox-1 ps aux | grep -c "rqscheduler" | grep -v grep)

echo "Current RQ workers: $RQ_WORKER_COUNT"
echo "Current RQ scheduler: $RQ_SCHEDULER_COUNT"

# Start RQ workers if not running
if [ "$RQ_WORKER_COUNT" -eq 0 ]; then
    echo "Starting RQ worker..."
    sudo docker exec -d netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py rqworker
    echo "✅ RQ worker started"
else
    echo "✅ RQ worker already running"
fi

# Start RQ scheduler if not running
if [ "$RQ_SCHEDULER_COUNT" -eq 0 ]; then
    echo "Starting RQ scheduler..."
    sudo docker exec -d netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py rqscheduler
    echo "✅ RQ scheduler started"
else
    echo "✅ RQ scheduler already running"
fi

# Deploy correct signals.py if needed
echo "Checking signals.py..."
SIGNALS_SIZE=$(sudo docker exec netbox-docker-netbox-1 wc -l /opt/netbox/netbox/netbox_hedgehog/signals.py | awk '{print $1}')
if [ "$SIGNALS_SIZE" -lt 100 ]; then
    echo "Deploying correct signals.py (found minimal $SIGNALS_SIZE line version)..."
    sudo docker cp /home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/signals.py netbox-docker-netbox-1:/opt/netbox/netbox/netbox_hedgehog/signals.py
    sudo docker exec -u root netbox-docker-netbox-1 chown unit:unit /opt/netbox/netbox/netbox_hedgehog/signals.py
    echo "✅ Correct signals.py deployed"
    
    echo "Restarting NetBox..."
    sudo docker restart netbox-docker-netbox-1
    sleep 10
else
    echo "✅ signals.py is correct ($SIGNALS_SIZE lines)"
fi

# Bootstrap periodic sync
echo "Bootstrapping periodic sync..."
sudo docker exec netbox-docker-netbox-1 python /opt/netbox/netbox/manage.py start_periodic_sync --bootstrap -v 2

echo ""
echo "=== Sync Infrastructure Status ==="
sudo docker exec netbox-docker-netbox-1 ps aux | grep -E "rq|scheduler" | grep -v grep

echo ""
echo "✅ Sync infrastructure setup complete"