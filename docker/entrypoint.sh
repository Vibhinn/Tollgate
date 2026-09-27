#!/bin/sh
set -e

if [ -f "config.yaml" ]; then
    exec uvicorn main:app --app-dir /app --host 0.0.0.0 --port 13000
fi

echo ""
echo "  No config.yaml found in this container's /data volume."
echo "  Run the setup wizard first:"
echo ""
echo "    docker exec -it <container> tollgate init"
echo ""
echo "  Idling until then - re-run this container after init to start the gateway."
exec tail -f /dev/null
