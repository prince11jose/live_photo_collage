#!/bin/bash

# Live Photo Collage - Unified Startup Script
# This script starts both the backend and frontend services with comprehensive error handling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Global variables
BACKEND_PID=""
FRONTEND_PID=""
LOGS_DIR="logs"
START_TIME=$(date)

# Print functions
print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}🚀 Live Photo Collage Startup${NC}"
    echo -e "${PURPLE}================================${NC}"
    echo ""
}

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
    echo ""
}

# Function to check if a port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=0
    
    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        attempt=$((attempt + 1))
        printf "."
        sleep 2
    done
    echo ""
    print_error "$service_name failed to start within expected time"
    return 1
}

# Function to cleanup on exit
cleanup() {
    echo ""
    print_status "🛑 Stopping application..."
    
    if [ ! -z "$BACKEND_PID" ] && ps -p $BACKEND_PID > /dev/null 2>&1; then
        kill -TERM $BACKEND_PID 2>/dev/null || true
        sleep 1
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            kill -KILL $BACKEND_PID 2>/dev/null || true
        fi
        print_success "🔧 Backend stopped (PID: $BACKEND_PID)"
    fi
    
    if [ ! -z "$FRONTEND_PID" ] && ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill -TERM $FRONTEND_PID 2>/dev/null || true
        sleep 1
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            kill -KILL $FRONTEND_PID 2>/dev/null || true
        fi
        print_success "🎨 Frontend stopped (PID: $FRONTEND_PID)"
    fi
    
    # Clean up any remaining processes more safely
    BACKEND_PIDS=$(pgrep -f "python.*app\.py" 2>/dev/null | grep -v grep || true)
    if [ ! -z "$BACKEND_PIDS" ]; then
        echo "$BACKEND_PIDS" | xargs kill -TERM 2>/dev/null || true
    fi
    
    FRONTEND_PIDS=$(pgrep -f "node.*react-scripts.*start" 2>/dev/null | grep -v grep || true)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo "$FRONTEND_PIDS" | xargs kill -TERM 2>/dev/null || true
    fi
    
    # Remove PID file
    rm -f .pids
    
    echo ""
    print_success "✅ Application stopped cleanly"
    exit 0
}

# Set trap to cleanup on exit
trap cleanup INT TERM EXIT

# Main script starts here
print_header

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    print_error "❌ Please run this script from the project root directory"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

# Check prerequisites
print_status "🔍 Checking prerequisites..."

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    print_error "Virtual environment not found."
    print_status "Please run: python -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    print_warning "Node modules not found. Installing dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Check Google credentials (warning only, not fatal)
if [ ! -f "backend/client_secrets.json" ]; then
    print_warning "client_secrets.json not found in backend directory."
    print_warning "Google Drive integration may not work until you add the credentials file."
    echo ""
fi

print_success "✅ Prerequisites check completed"
echo ""

# Port management
print_status "🔍 Checking and managing ports..."

# Backend port (5000)
if ! check_port 5000; then
    print_warning "Port 5000 is in use. Attempting to free it..."
    # Be more specific about what we kill
    BACKEND_PIDS=$(pgrep -f "python.*app\.py" 2>/dev/null | grep -v grep || true)
    if [ ! -z "$BACKEND_PIDS" ]; then
        echo "$BACKEND_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # Force kill if still running
        BACKEND_PIDS=$(pgrep -f "python.*app\.py" 2>/dev/null | grep -v grep || true)
        if [ ! -z "$BACKEND_PIDS" ]; then
            echo "$BACKEND_PIDS" | xargs kill -KILL 2>/dev/null || true
        fi
    fi
    sleep 1
    if ! check_port 5000; then
        print_error "Could not free port 5000. Please manually stop the conflicting service."
        print_status "Use: lsof -i :5000 to see what's using the port"
        exit 1
    fi
    print_success "✅ Port 5000 is now available"
else
    print_success "✅ Port 5000 is available"
fi

# Frontend port (3001)
if ! check_port 3001; then
    print_warning "Port 3001 is in use. Attempting to free it..."
    # Be more specific about what we kill
    FRONTEND_PIDS=$(pgrep -f "node.*react-scripts.*start" 2>/dev/null | grep -v grep || true)
    if [ ! -z "$FRONTEND_PIDS" ]; then
        echo "$FRONTEND_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # Force kill if still running
        FRONTEND_PIDS=$(pgrep -f "node.*react-scripts.*start" 2>/dev/null | grep -v grep || true)
        if [ ! -z "$FRONTEND_PIDS" ]; then
            echo "$FRONTEND_PIDS" | xargs kill -KILL 2>/dev/null || true
        fi
    fi
    sleep 1
    if ! check_port 3001; then
        print_warning "Port 3001 still in use. Frontend will attempt to use next available port."
    else
        print_success "✅ Port 3001 is now available"
    fi
else
    print_success "✅ Port 3001 is available"
fi

echo ""

# Start backend
print_status "🔧 Starting backend server..."
cd backend

# Start backend with proper logging
print_status "📝 Backend logs: $LOGS_DIR/backend.log"
source ../.venv/bin/activate
python app.py > "../$LOGS_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > ../.backend_pid

cd ..

# Wait for backend to be ready
if wait_for_service "http://localhost:5000/api/health" "Backend API"; then
    print_success "✅ Backend started successfully (PID: $BACKEND_PID)"
else
    print_error "❌ Backend failed to start. Check logs: tail -f $LOGS_DIR/backend.log"
    exit 1
fi

echo ""

# Start frontend
print_status "🎨 Starting frontend server..."
cd frontend

# Start frontend with proper logging
print_status "📝 Frontend logs: $LOGS_DIR/frontend.log"
PORT=3001 npm start > "../$LOGS_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > ../.frontend_pid

cd ..

# Wait for frontend to be ready (with longer timeout for React compilation)
print_status "⏳ Waiting for React to compile (this may take a moment)..."
if wait_for_service "http://localhost:3001" "Frontend"; then
    print_success "✅ Frontend started successfully (PID: $FRONTEND_PID)"
else
    print_warning "⚠️ Frontend may still be starting. Check logs if needed: tail -f $LOGS_DIR/frontend.log"
fi

# Save PIDs for stop script
echo "$BACKEND_PID $FRONTEND_PID" > .pids

echo ""
print_success "🎉 Live Photo Collage is now running!"
echo ""
echo -e "${GREEN}📱 Frontend:${NC}     http://localhost:3001"
echo -e "${GREEN}🔧 Backend API:${NC}  http://localhost:5000"
echo -e "${GREEN}📷 Upload URL:${NC}   http://localhost:5000/upload"
echo -e "${GREEN}📊 Health Check:${NC} http://localhost:5000/api/health"
echo ""
echo -e "${BLUE}📝 Logs:${NC}"
echo "   Backend:  tail -f $LOGS_DIR/backend.log"
echo "   Frontend: tail -f $LOGS_DIR/frontend.log"
echo "   Combined: tail -f $LOGS_DIR/*.log"
echo ""
echo -e "${YELLOW}📱 To use the photo collage:${NC}"
echo "   1. Open http://localhost:3001 in your browser"
echo "   2. Scan the QR code with your phone camera"
echo "   3. Upload photos from your mobile device"
echo "   4. Watch them appear in real-time on the collage!"
echo ""
echo -e "${YELLOW}🛑 To stop:${NC} Press Ctrl+C or run ./stop.sh"
echo ""

# Show startup summary
print_status "🕐 Started at: $START_TIME"
print_status "💾 Process IDs saved to: .pids"
print_status "📂 Logs directory: $LOGS_DIR/"
echo ""

# Option to show live logs
read -p "🔍 Show live logs? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "📊 Showing live logs (Press Ctrl+C to detach, services will continue running)..."
    echo ""
    
    # Remove the EXIT trap temporarily for log viewing
    trap - EXIT
    trap 'echo ""; print_status "🔍 Detached from logs. Services are still running."; print_status "🛑 To stop services: ./stop.sh"; exit 0' INT TERM
    
    tail -f "$LOGS_DIR"/*.log 2>/dev/null || {
        print_warning "Could not tail logs. Services are running in background."
        print_status "Check logs manually: tail -f $LOGS_DIR/backend.log $LOGS_DIR/frontend.log"
    }
else
    print_status "🔍 Services running in background. Check logs with: tail -f $LOGS_DIR/*.log"
    print_status "🛑 To stop services: ./stop.sh"
    
    # Remove EXIT trap since we're not managing the processes interactively
    trap - EXIT
fi
