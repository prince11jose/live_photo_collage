#!/bin/bash

# Live Photo Collage - Setup Script
# This script sets up the development environment for the first time

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}🔧 Live Photo Collage Setup${NC}"
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
}

print_header

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

print_status "🔍 Checking system requirements..."

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.8 or later."
    exit 1
else
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_success "✅ Python $PYTHON_VERSION found"
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 16 or later."
    exit 1
else
    NODE_VERSION=$(node --version)
    print_success "✅ Node.js $NODE_VERSION found"
fi

# Check npm
if ! command -v npm &> /dev/null; then
    print_error "npm is not installed. Please install npm."
    exit 1
else
    NPM_VERSION=$(npm --version)
    print_success "✅ npm $NPM_VERSION found"
fi

echo ""

# Create necessary directories
print_status "📁 Creating project directories..."
mkdir -p logs
mkdir -p backend/uploads
print_success "✅ Directories created"

# Setup Python virtual environment
print_status "� Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    print_success "✅ Virtual environment created"
else
    print_success "✅ Virtual environment already exists"
fi

# Install Python dependencies
print_status "📦 Installing Python dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
print_success "✅ Python dependencies installed"

# Install Node.js dependencies
print_status "📦 Installing Node.js dependencies..."
cd frontend
npm install
print_success "✅ Node.js dependencies installed"
cd ..

# Create .env template if it doesn't exist
if [ ! -f "backend/.env" ]; then
    print_status "📝 Creating environment configuration template..."
    cat > backend/.env << EOF
# Google Drive Configuration
UPLOAD_FOLDER_ID=your_google_drive_folder_id_here

# Application Configuration
FLASK_ENV=development
FLASK_DEBUG=true

# Optional: Custom upload directory (relative to backend/)
# UPLOAD_DIR=uploads
EOF
    print_success "✅ Environment template created at backend/.env"
    print_warning "Please update backend/.env with your Google Drive folder ID"
else
    print_success "✅ Environment file already exists"
fi

echo ""
print_success "🎉 Setup complete!"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo ""
echo "1. Set up Google Drive API credentials:"
echo "   ${BLUE}• Go to Google Cloud Console (https://console.cloud.google.com/)${NC}"
echo "   ${BLUE}• Create a project and enable Drive API${NC}"
echo "   ${BLUE}• Create OAuth2 credentials (Desktop application)${NC}"
echo "   ${BLUE}• Download as 'client_secrets.json'${NC}"
echo "   ${BLUE}• Place in backend/ directory${NC}"
echo ""
echo "2. Configure your Google Drive:"
echo "   ${BLUE}• Create a folder in Google Drive for photo uploads${NC}"
echo "   ${BLUE}• Copy the folder ID from the URL${NC}"
echo "   ${BLUE}• Update UPLOAD_FOLDER_ID in backend/.env${NC}"
echo ""
echo "3. Start the application:"
echo "   ${GREEN}./start.sh${NC}"
echo ""
echo -e "${BLUE}📚 For detailed instructions, see README.md${NC}"
echo ""

# Check if Google credentials exist
if [ ! -f "backend/client_secrets.json" ]; then
    print_warning "⚠️ Google Drive credentials not found yet"
    print_status "The app will work in local mode until you add Google Drive integration"
else
    print_success "✅ Google Drive credentials found"
fi

echo ""
print_status "🚀 Ready to run: ./start.sh"
