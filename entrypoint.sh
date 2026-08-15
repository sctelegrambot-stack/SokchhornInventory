#!/bin/sh
mkdir -p /app/data
for f in inventory.db lang_prefs.json; do
    if [ -f "/app/data/$f" ]; then
        ln -sf "/app/data/$f" "/app/$f"
    elif [ -f "/app/$f" ]; then
        mv "/app/$f" "/app/data/$f"
        ln -sf "/app/data/$f" "/app/$f"
    fi
done
mkdir -p /app/data/exports
[ -d /app/exports ] && rmdir /app/exports 2>/dev/null
ln -sf /app/data/exports /app/exports
# Start bot in background, dashboard in foreground
python main.py &
exec gunicorn webapp:app -b 0.0.0.0:${PORT:-5000} --workers 1 --threads 2