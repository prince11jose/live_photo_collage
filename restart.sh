#!/bin/bash

# Live Photo Collage - Quick Restart Script
# Stops and immediately restarts the application

echo "🔄 Quick Restart - Live Photo Collage"
echo "====================================="

# Stop existing services
if [ -f ".pids" ] || pgrep -f "python.*app.py" > /dev/null || pgrep -f "npm.*start" > /dev/null; then
    echo "🛑 Stopping existing services..."
    ./stop.sh
    sleep 2
else
    echo "✅ No running services found"
fi

# Start services
echo "🚀 Starting services..."
./start.sh
