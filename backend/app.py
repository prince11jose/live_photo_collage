import logging
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import os
import datetime
import requests
import io
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define the scope for the Google Drive API and Drive Activity API
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.activity.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Set log level to DEBUG
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global variable for image URLs and last activity timestamp
image_urls = []
last_activity_timestamp = None

# Configuration
UPLOAD_FOLDER_ID = os.getenv('UPLOAD_FOLDER_ID', '1XnWtpAjglmjA-99zs-ao___16wf7MbKZ')
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))

def get_credentials():
    """Obtain credentials from token.json or via OAuth flow."""
    creds = None
    # Check if the token.json file with credentials exists
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            # Check if the token has expired and refresh if needed
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}. Will re-authenticate.")
                    creds = None
        except Exception as e:
            logger.warning(f"Failed to load existing credentials: {e}. Will re-authenticate.")
            creds = None
    
    if not creds or not creds.valid:
        # Run the OAuth flow to obtain new credentials
        if not os.path.exists('client_secrets.json'):
            raise FileNotFoundError(
                "client_secrets.json not found. Please download OAuth2 credentials "
                "from Google Cloud Console and place them in the backend directory."
            )
        
        flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the new credentials to token.json for future use
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        
        logger.info("New credentials saved to token.json")
    
    return creds

# Google Drive API setup
def get_drive_service():
    """Create the Google Drive service using credentials."""
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds)

def get_drive_activity_service():
    """Create the Google Drive Activity service using credentials."""
    creds = get_credentials()
    return build('driveactivity', 'v2', credentials=creds)

def make_file_public(file_id):
    """Make a file publicly accessible (anyone with the link can view)."""
    try:
        drive_service = get_drive_service()
        permission = {
            'role': 'reader',
            'type': 'anyone'
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        logger.info(f"File {file_id} set to publicly accessible")
        return True
    except Exception as e:
        logger.error(f"Error setting permissions for file {file_id}: {str(e)}")
        return False

def list_images_from_drive(folder_id=None):
    """Fetch images from a specific folder in Google Drive and ensure they are publicly accessible."""
    drive_service = get_drive_service()
    
    # If folder_id is provided, query for images in that folder
    query = "mimeType contains 'image/'"
    if folder_id:
        query += f" and '{folder_id}' in parents"

    results = drive_service.files().list(
        q=query,
        fields="nextPageToken, files(id, name, webContentLink)"
    ).execute()
    
    items = results.get('files', [])
    
    # Ensure all images are publicly accessible
    for file in items:
        make_file_public(file['id'])
    
    # Return direct Google Drive URLs
    return [{"id": file['id'], "url": f"https://drive.google.com/uc?export=view&id={file['id']}"} for file in items]


def create_or_get_upload_folder():
    """Create or get the upload folder in Google Drive with repo name and date structure."""
    try:
        drive_service = get_drive_service()
        
        # First, try to access the configured folder
        if UPLOAD_FOLDER_ID and UPLOAD_FOLDER_ID != '':
            try:
                folder = drive_service.files().get(fileId=UPLOAD_FOLDER_ID).execute()
                logger.info(f"Using existing folder: {folder.get('name', 'Unknown')} (ID: {UPLOAD_FOLDER_ID})")
                return UPLOAD_FOLDER_ID
            except Exception as e:
                logger.warning(f"Configured folder not accessible: {e}")
        
        # Create folder structure: live_photo_collage/YYYY-MM-DD/
        repo_folder_name = "live_photo_collage"
        date_folder_name = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Check if main repo folder exists
        repo_folder_id = None
        query = f"name='{repo_folder_name}' and mimeType='application/vnd.google-apps.folder'"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        
        if folders:
            repo_folder_id = folders[0]['id']
            logger.info(f"Found existing repo folder: {repo_folder_name} (ID: {repo_folder_id})")
        else:
            # Create main repo folder
            repo_metadata = {
                'name': repo_folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            repo_folder = drive_service.files().create(body=repo_metadata, fields='id').execute()
            repo_folder_id = repo_folder.get('id')
            logger.info(f"Created repo folder: {repo_folder_name} (ID: {repo_folder_id})")
        
        # Check if date subfolder exists
        date_folder_id = None
        query = f"name='{date_folder_name}' and '{repo_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        
        if folders:
            date_folder_id = folders[0]['id']
            logger.info(f"Found existing date folder: {date_folder_name} (ID: {date_folder_id})")
        else:
            # Create date subfolder
            date_metadata = {
                'name': date_folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [repo_folder_id]
            }
            date_folder = drive_service.files().create(body=date_metadata, fields='id').execute()
            date_folder_id = date_folder.get('id')
            logger.info(f"Created date folder: {repo_folder_name}/{date_folder_name} (ID: {date_folder_id})")
        
        # Update the .env file with the new folder ID
        try:
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                
                # Update or add the UPLOAD_FOLDER_ID line
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith('UPLOAD_FOLDER_ID='):
                        lines[i] = f'UPLOAD_FOLDER_ID={date_folder_id}\n'
                        updated = True
                        break
                
                if not updated:
                    lines.append(f'UPLOAD_FOLDER_ID={date_folder_id}\n')
                
                with open(env_path, 'w') as f:
                    f.writelines(lines)
                
                logger.info(f"Updated .env file with folder ID: {date_folder_id}")
        except Exception as e:
            logger.warning(f"Could not update .env file: {e}")
        
        return date_folder_id
        
    except Exception as e:
        logger.error(f"Error creating/accessing folder structure: {e}")
        # Fallback to root drive folder
        logger.info("Using root Drive folder as fallback")
        return None

def upload_file_to_drive(file_stream, filename, folder_id):
    """Upload a file to Google Drive and make it publicly accessible."""
    try:
        drive_service = get_drive_service()
        
        file_metadata = {
            'name': filename
        }
        
        # Add parent folder if specified
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaIoBaseUpload(file_stream, mimetype='image/jpeg')
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = file.get('id')
        
        # Make the file publicly accessible (anyone with the link can view)
        try:
            permission = {
                'role': 'reader',
                'type': 'anyone'
            }
            drive_service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            logger.info(f"File {file_id} set to publicly accessible")
        except Exception as perm_error:
            logger.error(f"Error setting permissions for file {file_id}: {str(perm_error)}")
        
        logger.info(f"File uploaded successfully. File ID: {file_id}")
        return file_id
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return None

# Upload endpoint for mobile photos
@app.route('/api/upload', methods=['POST'])
def upload_photo():
    """API endpoint to upload photos from mobile devices."""
    try:
        if 'photo' not in request.files:
            return jsonify({"error": "No photo file provided"}), 400
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"photo_{timestamp}_{unique_id}.jpg"
        
        # Get or create upload folder
        upload_folder_id = create_or_get_upload_folder()
        
        # Upload to Google Drive
        file_stream = io.BytesIO(file.read())
        file_id = upload_file_to_drive(file_stream, filename, upload_folder_id)
        
        if file_id:
            # Add to current image list and notify clients (use direct Google Drive URL)
            new_image_url = f"https://drive.google.com/uc?export=view&id={file_id}"
            image_urls.append(new_image_url)
            
            # Notify all clients of the new image
            socketio.emit('new_images', [new_image_url])
            
            return jsonify({
                "status": "success",
                "message": "Photo uploaded successfully",
                "file_id": file_id,
                "url": new_image_url,
                "folder_id": upload_folder_id
            }), 200
        else:
            return jsonify({"error": "Failed to upload photo"}), 500
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# Test page for debugging images
@app.route('/test')
def test_page():
    """Serve test page for debugging image display."""
    with open('test.html', 'r') as f:
        html_content = f.read()
    return html_content

# Mobile upload page
@app.route('/upload')
def upload_page():
    """Serve mobile upload page."""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Photo Upload</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 500px;
                margin: 0 auto;
                padding: 20px;
                background: #f0f0f0;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                text-align: center;
            }
            h1 {
                color: #333;
                margin-bottom: 30px;
            }
            .upload-area {
                border: 2px dashed #007bff;
                border-radius: 10px;
                padding: 40px 20px;
                margin: 20px 0;
                background: #f8f9ff;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .upload-area:hover {
                border-color: #0056b3;
                background: #e3f2fd;
            }
            .upload-area.dragover {
                border-color: #28a745;
                background: #e8f5e8;
            }
            #fileInput {
                display: none;
            }
            .btn {
                background: #007bff;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 10px;
                transition: background 0.3s ease;
            }
            .btn:hover {
                background: #0056b3;
            }
            .btn:disabled {
                background: #6c757d;
                cursor: not-allowed;
            }
            .status {
                margin: 20px 0;
                padding: 10px;
                border-radius: 5px;
                display: none;
            }
            .status.success {
                background: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .status.error {
                background: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .preview {
                max-width: 100%;
                max-height: 300px;
                margin: 20px 0;
                border-radius: 10px;
                display: none;
            }
            .capture-btn {
                background: #28a745;
                margin: 10px 0;
            }
            .capture-btn:hover {
                background: #218838;
            }
            .folder-info {
                background: #e3f2fd;
                border: 1px solid #2196f3;
                border-radius: 8px;
                padding: 10px;
                margin-bottom: 20px;
                text-align: center;
                font-size: 14px;
                color: #1976d2;
            }
            .folder-info p {
                margin: 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📸 Upload Your Photo</h1>
            <div id="folderInfo" class="folder-info">
                <p>📁 Uploading to: <span id="folderPath">Loading...</span></p>
            </div>
            <div id="uploadArea" class="upload-area">
                <p>📱 Tap to take a photo or select from gallery</p>
                <p style="font-size: 14px; color: #666;">Supported: JPG, PNG</p>
            </div>
            
            <input type="file" id="fileInput" accept="image/*" capture="environment">
            <img id="preview" class="preview" alt="Preview">
            
            <div>
                <button id="captureBtn" class="btn capture-btn">📷 Take Photo</button>
                <button id="uploadBtn" class="btn" disabled>Upload Photo</button>
            </div>
            
            <div id="status" class="status"></div>
        </div>

        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const preview = document.getElementById('preview');
            const uploadBtn = document.getElementById('uploadBtn');
            const captureBtn = document.getElementById('captureBtn');
            const status = document.getElementById('status');
            const folderPath = document.getElementById('folderPath');
            let selectedFile = null;

            // Load folder information
            async function loadFolderInfo() {
                try {
                    const response = await fetch('/api/folder-info');
                    const data = await response.json();
                    if (response.ok) {
                        folderPath.textContent = data.path || 'Google Drive';
                    } else {
                        folderPath.textContent = 'Google Drive';
                    }
                } catch (error) {
                    folderPath.textContent = 'Google Drive';
                }
            }

            // Load folder info on page load
            loadFolderInfo();

            // Click handlers
            uploadArea.addEventListener('click', () => fileInput.click());
            captureBtn.addEventListener('click', () => fileInput.click());

            // File selection
            fileInput.addEventListener('change', handleFileSelect);

            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    handleFileSelect({ target: { files: files } });
                }
            });

            function handleFileSelect(event) {
                const file = event.target.files[0];
                if (file && file.type.startsWith('image/')) {
                    selectedFile = file;
                    
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        preview.src = e.target.result;
                        preview.style.display = 'block';
                        uploadBtn.disabled = false;
                    };
                    reader.readAsDataURL(file);
                    
                    showStatus('Photo selected successfully!', 'success');
                } else {
                    showStatus('Please select a valid image file.', 'error');
                }
            }

            uploadBtn.addEventListener('click', uploadPhoto);

            async function uploadPhoto() {
                if (!selectedFile) return;

                uploadBtn.disabled = true;
                uploadBtn.textContent = 'Uploading...';
                
                const formData = new FormData();
                formData.append('photo', selectedFile);

                try {
                    const response = await fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });

                    const result = await response.json();

                    if (response.ok) {
                        showStatus('Photo uploaded successfully! It will appear in the collage.', 'success');
                        // Reset form
                        fileInput.value = '';
                        preview.style.display = 'none';
                        selectedFile = null;
                        setTimeout(() => {
                            window.close(); // Close mobile browser tab
                        }, 2000);
                    } else {
                        showStatus(`Upload failed: ${result.error}`, 'error');
                    }
                } catch (error) {
                    showStatus('Upload failed. Please try again.', 'error');
                }

                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload Photo';
            }

            function showStatus(message, type) {
                status.textContent = message;
                status.className = `status ${type}`;
                status.style.display = 'block';
                
                if (type === 'success') {
                    setTimeout(() => {
                        status.style.display = 'none';
                    }, 3000);
                }
            }
        </script>
    </body>
    </html>
    '''

# Get folder info endpoint
@app.route('/api/folder-info', methods=['GET'])
def get_folder_info():
    """Get information about the current upload folder structure."""
    try:
        current_folder_id = create_or_get_upload_folder()
        
        if not current_folder_id:
            return jsonify({
                "folder_structure": "root",
                "folder_id": None,
                "path": "Google Drive Root"
            })
        
        drive_service = get_drive_service()
        
        # Get current folder info
        current_folder = drive_service.files().get(fileId=current_folder_id).execute()
        folder_name = current_folder.get('name', 'Unknown')
        
        # Try to get parent folder info
        parents = current_folder.get('parents', [])
        parent_name = "Google Drive Root"
        
        if parents:
            try:
                parent_folder = drive_service.files().get(fileId=parents[0]).execute()
                parent_name = parent_folder.get('name', 'Unknown')
            except:
                pass
        
        folder_path = f"{parent_name}/{folder_name}" if parent_name != "Google Drive Root" else folder_name
        
        return jsonify({
            "folder_structure": "live_photo_collage/YYYY-MM-DD",
            "folder_id": current_folder_id,
            "path": folder_path,
            "current_date_folder": folder_name,
            "parent_folder": parent_name
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "folder_structure": "error"
        }), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        current_folder_id = create_or_get_upload_folder()
        folder_info = "Unknown"
        
        if current_folder_id:
            try:
                drive_service = get_drive_service()
                folder = drive_service.files().get(fileId=current_folder_id).execute()
                folder_info = f"live_photo_collage/{folder.get('name', 'Unknown')}"
            except:
                folder_info = f"Folder ID: {current_folder_id}"
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "images_count": len(image_urls),
            "upload_folder": folder_info,
            "folder_id": current_folder_id or "root"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }), 500

# Authentication endpoint
@app.route('/api/auth', methods=['POST'])
def authenticate():
    """Trigger authentication and load initial images."""
    global image_urls
    try:
        # This will trigger the OAuth flow if needed
        creds = get_credentials()
        if creds and creds.valid:
            # Load images after successful authentication
            image_urls = [img['url'] for img in list_images_from_drive(folder_id=UPLOAD_FOLDER_ID)]
            logger.info(f"Authentication successful. Loaded {len(image_urls)} images.")
            return jsonify({
                "status": "success",
                "message": "Authentication successful",
                "images_count": len(image_urls)
            })
        else:
            return jsonify({"error": "Authentication failed"}), 401
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Serve image URLs
@app.route('/api/images', methods=['GET'])
def get_images():
    """API to fetch current image URLs."""
    logger.debug(f"Fetching current image URLs {image_urls}")
    return jsonify(image_urls)

# Proxy for serving Google Drive images
@app.route('/proxy/image/<image_id>', methods=['GET'])
def proxy_image(image_id):
    """Fetch and serve an image from Google Drive."""
    # Get the file's metadata to determine the correct mimetype
    drive_service = get_drive_service()
    file_metadata = drive_service.files().get(fileId=image_id, fields='mimeType').execute()
    mimetype = file_metadata.get('mimeType', 'image/jpeg')  # Fallback to image/jpeg if not found
    url = f"https://drive.google.com/uc?id={image_id}&export=download"
    response = requests.get(url)
    if response.status_code == 200:
        return send_file(io.BytesIO(response.content), mimetype=mimetype)
    else:
        return "Image not found", 404


# Fetch recent activity for files in Google Drive
def get_drive_activity(start_time=None, folder_id=None):
    """Fetch recent activity for files in Google Drive."""
    drive_activity_service = get_drive_activity_service()
    
    # Build the request to fetch activities
    request_body = {
        'ancestorName': f'items/{folder_id}',
        'pageSize': 10,
    }
    
    # If start_time is provided, filter activities that happened after this time
    if start_time:
        request_body['filter'] = f"time >= {start_time.isoformat()}Z"
    
    # Call the Drive Activity API
    response = drive_activity_service.activity().query(body=request_body).execute()
    
    return response.get('activities', [])

def extract_image_urls_from_activities(activities):
    """Extract image URLs from the Drive activity response."""
    new_image_urls = []
    
    for activity in activities:
        # Each activity can have multiple actions
        for action in activity.get('primaryActionDetail', {}).values():
            for target in activity.get('targets', []):
                # Check if the target is a file and if it is an image
                if 'file' in target:
                    mime_type = target['file'].get('mimeType', '')
                    if mime_type.startswith('image/'):
                        # Use the file's ID to construct the web content link
                        file_id = target['file']['id']
                        web_content_link = f"/proxy/image/{file_id}"  # Use proxy link
                        new_image_urls.append(web_content_link)
    
    return new_image_urls

@app.route('/api/refresh-images', methods=['POST'])
def refresh_images():
    """API to refresh image list from Google Drive based on Drive activity and notify clients."""
    global image_urls, last_activity_timestamp

    try:
        # Fetch activities since the last activity timestamp
        folder_id = request.json.get('folder_id') if request.json else UPLOAD_FOLDER_ID
        activities = get_drive_activity(last_activity_timestamp, folder_id)

        unique_new_urls = []

        # If there are new activities, update image URLs
        if activities:
            logger.debug("New activity detected. Processing image updates.")
            
            # Extract new image URLs from the activities
            new_urls = extract_image_urls_from_activities(activities)
            
            # Check if there are new image URLs that are not already in the list
            unique_new_urls = [url for url in new_urls if url not in image_urls]
            
            if unique_new_urls:
                image_urls.extend(unique_new_urls)
                logger.debug(f"New image URLs added: {unique_new_urls}")
                socketio.emit('new_images', unique_new_urls)  # Notify clients of new images

            # Update the last_activity_timestamp to the latest found activity timestamp
            last_activity_timestamp = datetime.datetime.utcnow()

        return jsonify({"status": "Checked for new images", "new_urls": unique_new_urls if unique_new_urls else []})
    
    except Exception as e:
        logger.error(f"Error refreshing images: {str(e)}")
        return jsonify({"error": "Failed to refresh images"}), 500

if __name__ == '__main__':
    # Try to preload images on startup, but don't fail if authentication isn't ready
    try:
        logger.info("Attempting to load initial images...")
        # Get or create the upload folder
        actual_folder_id = create_or_get_upload_folder()
        
        # Preload images on startup
        if actual_folder_id:
            image_urls = [img['url'] for img in list_images_from_drive(folder_id=actual_folder_id)]
            logger.info(f"Loaded {len(image_urls)} initial images from folder {actual_folder_id}")
        else:
            # Load from root folder if no specific folder
            image_urls = [img['url'] for img in list_images_from_drive()]
            logger.info(f"Loaded {len(image_urls)} initial images from root folder")
            
    except FileNotFoundError as e:
        logger.error(f"Setup incomplete: {e}")
        logger.error("Please run setup first and configure Google Drive credentials")
        image_urls = []
    except Exception as e:
        logger.warning(f"Could not load initial images: {e}")
        logger.warning("Server will start anyway. Images will load after authentication.")
        image_urls = []
    
    logger.info("Starting the application server...")
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, allow_unsafe_werkzeug=True)
