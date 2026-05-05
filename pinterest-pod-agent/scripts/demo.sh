#!/bin/bash
# One-shot warmup + publish demo for老板验收
# Usage: bash scripts/demo.sh

ROOT="/c/nanobot"
PYTHON="$ROOT/.venv/Scripts/python"
CELERY="$ROOT/.venv/Scripts/celery.exe"
WORKDIR="$ROOT/pinterest-pod-agent"

cd "$WORKDIR"
mkdir -p var/log

echo "=== 1/3 Clearing old state ==="
$PYTHON scripts/_demo_setup.py

echo ""
echo "=== 2/3 Starting worker ==="
nohup $PYTHON $CELERY -A app.celery_app worker -Q publish,media,engagement,trend --loglevel=info --pool=solo --concurrency=1 > var/log/worker.log 2>&1 &
echo "Worker PID: $!"
sleep 4

echo ""
echo "=== 3/3 Dispatching task ==="
PYTHONPATH=. $PYTHON -c "
from app.database import get_sessionmaker
from app.jobs.dispatcher import dispatch_ready_tasks
with get_sessionmaker()() as db:
    r = dispatch_ready_tasks(db)
    print('Dispatched:', r)
"

echo ""
echo "=== Demo running! Showing live logs ==="
echo "=== 浏览器会自动打开，养号 ~8min → 发帖 ~2min ==="
echo ""
tail -f var/log/worker.log
