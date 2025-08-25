#!/bin/bash

# Live Photo Collage - Stop Script
# This script stops both the backend and frontend services safely

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "Stopping Live Photo Collage services..."

# Stop services using PID file if it exists
if [ -f ".pids" ]; then
    print_status "Found PID file, stopping services gracefully..."
    read BACKEND_PID FRONTEND_PID < .pids
    
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        # First try graceful shutdown
        kill -TERM $BACKEND_PID 2>/dev/null || true
        sleep 2
        # If still running, force kill
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill -KILL $BACKEND_PID 2>/dev/null || true
        fi
        print_success "Backend stopped (PID: $BACKEND_PID)"
    else
        print_warning "Backend PID $BACKEND_PID not running"
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        # First try graceful shutdown
        kill -TERM $FRONTEND_PID 2>/dev/null || true
        sleep 2
        # If still running, force kill
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill -KILL $FRONTEND_PID 2>/dev/null || true
        fi
        print_success "Frontend stopped (PID: $FRONTEND_PID)"
    else
        print_warning "Frontend PID $FRONTEND_PID not running"
    fi
    
    rm .pids
    print_status "PID file removed"
else
    # Fallback: kill by specific process patterns (more precise)
    print_warning "PID file not found, attempting to stop by process name..."
    
    # Stop backend - be very specific about the pattern
    BACKEND_PIDS=$(pgrep -f "python.*app\.py" 2>/dev/null | grep -v grep || true)
    if [ ! -z "$BACKEND_PIDS" ]; then
        echo "$BACKEND_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # Force kill any remaining
        BACKEND_PIDS=$(pgrep -f "python.*app\.py" 2>/dev/null | grep -v grep || true)
        if [ ! -z "$BACKEND_PIDS" ]; then
            echo "$BACKEND_PIDS" | xargs kill -KILL 2>/dev/null || true
        fi
        print_success "Backend processes stopped"
    else
        print_warning "No backend processes found"
    fi
    
    # Stop frontend - be very specific about the pattern
    FRONTEND_PIDS=$(pgrep -f "node.*react-scripts.*start" 2>/dev/null | grep -v grep || true)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo "$FRONTEND_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # Force kill any remaining
        FRONTEND_PIDS=$(pgrep -f "node.*react-scripts.*start" 2>/dev/null | grep -v grep || true)
        if [ ! -z "$FRONTEND_PIDS" ]; then
            echo "$FRONTEND_PIDS" | xargs kill -KILL 2>/dev/null || true
        fi
        print_success "Frontend processes stopped"
    else
        print_warning "No frontend processes found"
    fi
fi

# Clean up any additional PID files
rm -f .backend_pid .frontend_pid 2>/dev/null || true

# Only check ports, don't force kill (safer approach)
print_status "Checking port status..."

# Check port 5000 (backend)
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PORT_PROCESS=$(lsof -Pi :5000 -sTCP:LISTEN | tail -n +2 | awk '{print $1, $2}' | head -1)
    print_warning "Port 5000 still in use by: $PORT_PROCESS"
    print_warning "If this is not our app, you may need to stop it manually"
else
    print_success "Port 5000 is free"
fi

# Check port 3001 (frontend)
if lsof -Pi :3001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PORT_PROCESS=$(lsof -Pi :3001 -sTCP:LISTEN | tail -n +2 | awk '{print $1, $2}' | head -1)
    print_warning "Port 3001 still in use by: $PORT_PROCESS"
    print_warning "If this is not our app, you may need to stop it manually"
else
    print_success "Port 3001 is free"
fi

print_success "Live Photo Collage services have been stopped safely."
echo ""
print_status "Note: This script now uses safer process termination to avoid affecting other applications."
