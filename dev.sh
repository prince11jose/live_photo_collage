#!/bin/bash

# Live Photo Collage - Development Helper
# Quick commands for development workflow

case "$1" in
    "status")
        echo "🔍 Live Photo Collage Status"
        echo "=============================="
        echo ""
        if [ -f ".pids" ]; then
            read BACKEND_PID FRONTEND_PID < .pids
            echo "📋 PID File Found:"
            echo "   Backend PID:  $BACKEND_PID"
            echo "   Frontend PID: $FRONTEND_PID"
            echo ""
            if ps -p $BACKEND_PID > /dev/null 2>&1; then
                echo "✅ Backend is running (PID: $BACKEND_PID)"
            else
                echo "❌ Backend is not running"
            fi
            if ps -p $FRONTEND_PID > /dev/null 2>&1; then
                echo "✅ Frontend is running (PID: $FRONTEND_PID)"
            else
                echo "❌ Frontend is not running"
            fi
        else
            echo "📋 No PID file found"
        fi
        echo ""
        
        # Check ports
        if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "🔧 Port 5000 (Backend): ✅ In use"
        else
            echo "🔧 Port 5000 (Backend): ❌ Available"
        fi
        
        if lsof -Pi :3001 -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "🎨 Port 3001 (Frontend): ✅ In use"
        else
            echo "🎨 Port 3001 (Frontend): ❌ Available"
        fi
        echo ""
        
        # Show recent logs
        if [ -d "logs" ]; then
            echo "📝 Recent log activity:"
            echo "   Backend log:  $(ls -la logs/backend.log 2>/dev/null | awk '{print $6, $7, $8}' || echo 'Not found')"
            echo "   Frontend log: $(ls -la logs/frontend.log 2>/dev/null | awk '{print $6, $7, $8}' || echo 'Not found')"
        fi
        ;;
        
    "logs")
        if [ "$2" = "backend" ]; then
            echo "📝 Backend logs (Press Ctrl+C to exit):"
            tail -f logs/backend.log
        elif [ "$2" = "frontend" ]; then
            echo "📝 Frontend logs (Press Ctrl+C to exit):"
            tail -f logs/frontend.log
        else
            echo "📝 Combined logs (Press Ctrl+C to exit):"
            tail -f logs/*.log 2>/dev/null || echo "No log files found"
        fi
        ;;
        
    "safety")
        ./safety-check.sh
        ;;
        
    "clean")
        echo "🧹 Cleaning development environment..."
        # Stop services
        if [ -f ".pids" ]; then
            ./stop.sh
        fi
        # Clean logs
        rm -f logs/*.log
        rm -f .pids .backend_pid .frontend_pid
        # Clean temporary files
        find . -name "*.pyc" -delete
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        echo "✅ Development environment cleaned"
        ;;
        
    "urls")
        echo "🌐 Live Photo Collage URLs"
        echo "=========================="
        echo ""
        echo "📱 Frontend:      http://localhost:3001"
        echo "🔧 Backend API:   http://localhost:5000"
        echo "📷 Upload URL:    http://localhost:5000/upload"
        echo "🩺 Health Check:  http://localhost:5000/api/health"
        echo "📊 API Images:    http://localhost:5000/api/images"
        echo ""
        ;;
        
    *)
        echo "🛠️  Live Photo Collage - Development Helper"
        echo "============================================="
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  status    - Show application status"
        echo "  safety    - Run safety check (show processes that might be affected)"
        echo "  logs      - Show live logs (all)"
        echo "  logs backend   - Show backend logs only"
        echo "  logs frontend  - Show frontend logs only"
        echo "  clean     - Clean development environment"
        echo "  urls      - Show all application URLs"
        echo ""
        echo "Examples:"
        echo "  $0 status"
        echo "  $0 safety"
        echo "  $0 logs backend"
        echo "  $0 clean"
        echo ""
        ;;
esac
