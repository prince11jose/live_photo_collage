#!/bin/bash

# Live Photo Collage Setup Script

echo "🔧 Live Photo Collage - First Time Setup"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

echo "📦 Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

echo "📦 Installing Python dependencies..."
.venv/bin/pip install -r backend/requirements.txt

echo "📦 Installing Node.js dependencies..."
cd frontend
npm install
cd ..

echo "🔧 Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Set up Google Drive API credentials:"
echo "   - Go to Google Cloud Console"
echo "   - Create a project and enable Drive API"
echo "   - Create OAuth2 credentials (Desktop application)"
echo "   - Download as 'client_secrets.json'"
echo "   - Place in backend/ directory"
echo ""
echo "2. Configure your Google Drive folder:"
echo "   - Create a folder in Google Drive for photo uploads"
echo "   - Copy the folder ID from the URL"
echo "   - Update UPLOAD_FOLDER_ID in backend/.env"
echo ""
echo "3. Run the application:"
echo "   ./start.sh"
echo ""
echo "🎉 Setup complete! Read README.md for detailed instructions."
