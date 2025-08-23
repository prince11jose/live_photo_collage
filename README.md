# Live Photo Collage

A real-time photo collage application that automatically displays photos uploaded to Google Drive, featuring QR code integration for easy mobile photo uploads.

## Features

- 📸 **Real-time Photo Collage**: Displays photos from Google Drive in a responsive grid layout
- 📱 **QR Code Upload**: Scan QR code with mobile device to access upload interface
- 🔄 **Live Updates**: New photos appear instantly using WebSocket connections
- 📱 **Mobile Optimized**: Mobile-friendly upload interface with camera integration
- ☁️ **Google Drive Integration**: Direct upload to Google Drive with OAuth authentication
- 📁 **Organized Storage**: Automatic folder structure: `live_photo_collage/YYYY-MM-DD/`

## Architecture

### Backend (Flask)
- Flask server with Socket.IO for real-time updates
- Google Drive API integration for file operations
- OAuth2 authentication for secure access
- Upload endpoint for mobile photo submissions
- Image proxy for serving Google Drive content

### Frontend (React)
- React application with responsive design
- QR code generation for mobile access
- Real-time updates via Socket.IO
- CSS Grid layout that auto-adjusts as photos are added

## Setup Instructions

### Prerequisites
- Python 3.8+ 
- Node.js 14+
- Google Cloud Project with Drive API enabled
- Google OAuth2 credentials

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Google Drive API**:
   - Create a Google Cloud Project
   - Enable Google Drive API and Google Drive Activity API
   - Create OAuth2 credentials (Desktop application)
   - Download credentials as `client_secrets.json` and place in backend directory

4. **Configure environment**:
   - Update `.env` file with your Google Drive folder ID
   - The folder ID can be found in the Google Drive URL when viewing the folder

5. **Start the backend**:
   ```bash
   python app.py
   ```

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Start the frontend**:
   ```bash
   npm start
   ```

### First Time Setup

1. **Authentication**: When you first run the backend, it will open a browser window for Google OAuth authentication
2. **Folder Access**: Ensure the Google account has access to the specified Drive folder
3. **Testing**: Upload a test photo to verify the integration works

## Usage

1. **Start both backend and frontend servers**
2. **Open the frontend in a browser** (usually http://localhost:3000)
3. **Scan the QR code** with a mobile device
4. **Take or select photos** on the mobile upload page
5. **Watch photos appear** in real-time on the collage

## Mobile Upload Flow

1. **QR Code**: Main screen displays QR code
2. **Mobile Access**: Scan QR code to open upload interface
3. **Photo Capture**: Use camera or select from gallery
4. **Upload**: Photo uploads directly to Google Drive
5. **Live Update**: Photo appears on collage immediately

## Configuration

### Environment Variables (Backend)

- `UPLOAD_FOLDER_ID`: Google Drive folder ID for uploads
- `FLASK_HOST`: Server host (default: 0.0.0.0)
- `FLASK_PORT`: Server port (default: 5000)

### Google Drive Setup

The application automatically creates an organized folder structure in your Google Drive:

```
📁 Google Drive Root
└── 📁 live_photo_collage/
    └── 📁 2025-08-23/          (Today's date)
        ├── 📷 photo_001.jpg
        ├── 📷 photo_002.jpg
        └── 📷 ...
```

**First Time Setup:**
1. The app will automatically create the `live_photo_collage` main folder
2. A new date folder (YYYY-MM-DD) is created each day
3. All photos uploaded on a specific date go into that day's folder
4. The `.env` file is automatically updated with the current folder ID

**Manual Configuration (Optional):**
1. Create your own folder structure in Google Drive
2. Copy the folder ID from the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
3. Update the `UPLOAD_FOLDER_ID` in `.env`

## API Endpoints

- `GET /api/images`: Fetch current image list
- `POST /api/upload`: Upload new photo (mobile)
- `GET /upload`: Mobile upload interface
- `POST /api/refresh-images`: Manually refresh image list

## Technical Details

### Real-time Updates
- Uses Socket.IO for bidirectional communication
- Backend monitors Google Drive activity
- New uploads trigger immediate frontend updates

### Image Handling
- Images served via proxy to avoid CORS issues
- Lazy loading for performance
- Responsive grid layout with CSS Grid
- Fallback images for failed loads

### Security
- OAuth2 authentication with Google
- CORS configuration for cross-origin requests
- Secure file upload with validation

## Troubleshooting

### Common Issues

1. **Authentication Errors**: 
   - Ensure `client_secrets.json` is present
   - Check Google Cloud Console API permissions
   - Verify OAuth2 credentials are for "Desktop application"

2. **Upload Failures**:
   - Check folder permissions in Google Drive
   - Verify folder ID in configuration
   - Ensure Drive API quota isn't exceeded

3. **Images Not Loading**:
   - Check Google Drive folder accessibility
   - Verify image proxy endpoint
   - Check browser console for CORS errors

### Development

- **Backend logs**: Check terminal running Flask app
- **Frontend logs**: Check browser developer console
- **Network issues**: Verify ports 3000 and 5000 are available

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.
