#!/bin/bash

# Live Photo Collage Startup Script

echo "🚀 Starting Live Photo Collage Application"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "⚠️  Port $port is already in use"
        return 1
    fi
    return 0
}

# Check required ports
echo "🔍 Checking ports..."
if ! check_port 5000; then
    echo "❌ Backend port 5000 is in use. Please stop the service using that port."
    exit 1
fi

if ! check_port 3001; then
    echo "⚠️  Frontend port 3001 is in use. Will try to start anyway."
fi

# Check if Python virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Python virtual environment not found. Please run: python -m venv .venv"
    exit 1
fi

# Check if node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ Node modules not found. Please run: cd frontend && npm install"
    exit 1
fi

# Check if Google credentials exist
if [ ! -f "backend/client_secrets.json" ]; then
    echo "❌ Google OAuth credentials not found!"
    echo "📝 Please:"
    echo "   1. Go to Google Cloud Console"
    echo "   2. Create OAuth2 credentials (Desktop application)"
    echo "   3. Download as 'client_secrets.json'"
    echo "   4. Place in backend/ directory"
    exit 1
fi

echo "✅ All checks passed!"
echo ""

# Start backend
echo "🔧 Starting backend server..."
cd backend
./../.venv/bin/python app.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Check if backend started successfully
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "❌ Backend failed to start. Check the logs above."
    exit 1
fi

echo "✅ Backend started (PID: $BACKEND_PID)"

# Start frontend
echo "🎨 Starting frontend server..."
cd frontend
PORT=3001 npm start &
FRONTEND_PID=$!
cd ..

echo "✅ Frontend starting (PID: $FRONTEND_PID)"
echo ""
echo "🎉 Application is starting up!"
echo "📱 Frontend: http://localhost:3001"
echo "🔧 Backend: http://localhost:5000"
echo ""
echo "📱 To upload photos:"
echo "   1. Open http://localhost:3001 in your browser"
echo "   2. Scan the QR code with your phone"
echo "   3. Take photos and upload them"
echo "   4. Watch them appear in real-time!"
echo ""
echo "🛑 To stop the application, press Ctrl+C"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping application..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Application stopped"
    exit 0
}

# Set trap to cleanup on exit
trap cleanup INT TERM

# Wait for user to stop
wait
