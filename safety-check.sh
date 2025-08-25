#!/bin/bash

# Live Photo Collage - Safety Check Script
# This script helps identify what processes might be affected by our stop script

echo "🔍 Live Photo Collage - Process Safety Check"
echo "============================================"
echo ""

echo "📋 Current Live Photo Collage processes:"
echo "Backend (Python):"
pgrep -f "python.*app\.py" 2>/dev/null | while read pid; do
    ps -p $pid -o pid,ppid,command | tail -n +2
done || echo "  No backend processes found"

echo ""
echo "Frontend (React):"
pgrep -f "node.*react-scripts.*start" 2>/dev/null | while read pid; do
    ps -p $pid -o pid,ppid,command | tail -n +2
done || echo "  No frontend processes found"

echo ""
echo "🔍 Port usage:"
echo "Port 5000:"
lsof -Pi :5000 -sTCP:LISTEN 2>/dev/null | tail -n +2 || echo "  Port 5000 is free"

echo ""
echo "Port 3001:"
lsof -Pi :3001 -sTCP:LISTEN 2>/dev/null | tail -n +2 || echo "  Port 3001 is free"

echo ""
echo "🖥️ VS Code related processes (should NOT be affected by stop script):"
ps aux | grep -i code | grep -v grep | head -5 || echo "  No VS Code processes found"

echo ""
echo "📁 PID files:"
if [ -f ".pids" ]; then
    echo "  .pids file exists:"
    cat .pids
else
    echo "  No .pids file found"
fi

if [ -f ".backend_pid" ]; then
    echo "  .backend_pid file exists:"
    cat .backend_pid
else
    echo "  No .backend_pid file found"
fi

if [ -f ".frontend_pid" ]; then
    echo "  .frontend_pid file exists:"
    cat .frontend_pid
else
    echo "  No .frontend_pid file found"
fi

echo ""
echo "✅ Safety check complete"
