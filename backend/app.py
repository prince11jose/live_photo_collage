import logging
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from PIL import Image, ImageOps
import os
import datetime
import uuid
import io
import shutil
import sqlite3
import zipfile
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration
PHOTOS_DIR = os.getenv('PHOTOS_DIR') or os.path.join(os.path.dirname(__file__), 'data', 'photos')
# Full-resolution copies, kept only for the zip download - never served to the board itself
ORIGINALS_DIR = os.getenv('ORIGINALS_DIR') or os.path.join(os.path.dirname(PHOTOS_DIR), 'originals')
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
# Guests upload with no login. Cap the board at this many photos until someone has signed in
# with Google at least once (see any_admin_signed_in) - then the cap is lifted for good.
UPLOAD_LIMIT_UNSIGNED = int(os.getenv('UPLOAD_LIMIT_UNSIGNED', 15))
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
DB_PATH = os.getenv('DB_PATH') or os.path.join(os.path.dirname(PHOTOS_DIR), 'app.db')
# Emails allowed to view the user list (which exposes everyone's email/phone). Everyone who
# signs in can still download/clear photos - this allow-list only gates the user-directory view.
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv('ADMIN_EMAILS', '').split(',') if e.strip()}
# Long-edge cap for the board's display copy - plenty sharp on a large screen, far lighter to load
DISPLAY_MAX_DIM = int(os.getenv('DISPLAY_MAX_DIM', 1600))
SAVE_FORMATS = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.gif': 'GIF', '.webp': 'WEBP'}

os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(ORIGINALS_DIR, exist_ok=True)

# Tracks URLs already broadcast/served so /api/refresh-images can diff new arrivals
known_urls = set()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            google_sub TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            name TEXT,
            picture TEXT,
            phone TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()


def bearer_token():
    auth_header = request.headers.get('Authorization', '')
    return auth_header.split('Bearer ', 1)[1] if auth_header.startswith('Bearer ') else None


def verify_google_token(token):
    """Verify a Google Identity Services ID token. Returns the decoded payload or None."""
    if not GOOGLE_CLIENT_ID or not token:
        return None
    try:
        return google_id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        logger.warning(f"Google token rejected: {e}")
        return None


def is_admin(payload):
    return bool(payload) and payload.get('email', '').lower() in ADMIN_EMAILS


def any_admin_signed_in():
    """True once at least one person has ever signed in with Google on this board."""
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    return count > 0


def today_folder():
    return datetime.datetime.now().strftime('%Y-%m-%d')


def list_all_photos():
    """Scan PHOTOS_DIR for images, oldest to newest, and return their URL paths."""
    entries = []
    if not os.path.isdir(PHOTOS_DIR):
        return []

    for date_name in sorted(os.listdir(PHOTOS_DIR)):
        date_path = os.path.join(PHOTOS_DIR, date_name)
        if not os.path.isdir(date_path):
            continue
        for filename in os.listdir(date_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            file_path = os.path.join(date_path, filename)
            entries.append({
                'url': f'/photos/{date_name}/{filename}',
                'mtime': os.path.getmtime(file_path),
            })

    entries.sort(key=lambda e: e['mtime'])
    return [e['url'] for e in entries]


# Serve uploaded photos
@app.route('/photos/<date_folder>/<filename>', methods=['GET'])
def serve_photo(date_folder, filename):
    return send_from_directory(os.path.join(PHOTOS_DIR, date_folder), filename)


def process_upload(file_storage, ext):
    """Bake in EXIF rotation and produce two copies of an upload:
    a full-resolution original (for the zip download) and a resized display
    copy (for the board). Falls back to the raw bytes if Pillow can't decode it.
    """
    data = file_storage.read()
    save_format = SAVE_FORMATS.get(ext, 'JPEG')

    try:
        image = Image.open(io.BytesIO(data))
        if ext in ('.jpg', '.jpeg'):
            image = ImageOps.exif_transpose(image)
        if save_format == 'JPEG' and image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        orig_buf = io.BytesIO()
        orig_kwargs = {'quality': 95} if save_format == 'JPEG' else {}
        image.save(orig_buf, format=save_format, **orig_kwargs)

        display = image.copy()
        display.thumbnail((DISPLAY_MAX_DIM, DISPLAY_MAX_DIM), Image.LANCZOS)
        disp_buf = io.BytesIO()
        disp_kwargs = {'quality': 82, 'optimize': True} if save_format == 'JPEG' else {}
        display.save(disp_buf, format=save_format, **disp_kwargs)

        return orig_buf.getvalue(), disp_buf.getvalue()
    except Exception as e:
        logger.warning(f"Could not process image, storing original bytes for both copies: {e}")
        return data, data


# Upload endpoint for mobile photos
@app.route('/api/upload', methods=['POST'])
def upload_photo():
    """API endpoint to upload photos from mobile devices, saved to local storage."""
    try:
        if 'photo' not in request.files:
            return jsonify({"error": "No photo file provided"}), 400

        file = request.files['photo']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if len(known_urls) >= UPLOAD_LIMIT_UNSIGNED and not any_admin_signed_in():
            return jsonify({
                "error": f"Upload limit reached ({UPLOAD_LIMIT_UNSIGNED} photos). "
                         "Ask the host to sign in with Google on the display screen to allow more uploads."
            }), 403

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = '.jpg'

        date_folder = today_folder()
        date_path = os.path.join(PHOTOS_DIR, date_folder)
        orig_date_path = os.path.join(ORIGINALS_DIR, date_folder)
        os.makedirs(date_path, exist_ok=True)
        os.makedirs(orig_date_path, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"photo_{timestamp}_{unique_id}{ext}"

        original_bytes, display_bytes = process_upload(file, ext)

        with open(os.path.join(orig_date_path, filename), 'wb') as f:
            f.write(original_bytes)
        with open(os.path.join(date_path, filename), 'wb') as f:
            f.write(display_bytes)

        new_image_url = f"/photos/{date_folder}/{filename}"
        known_urls.add(new_image_url)

        socketio.emit('new_images', [new_image_url])

        return jsonify({
            "status": "success",
            "message": "Photo uploaded successfully",
            "url": new_image_url,
            "folder": date_folder
        }), 200

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


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
            </div>

            <div id="status" class="status"></div>
        </div>

        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const preview = document.getElementById('preview');
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
                        folderPath.textContent = data.path || 'this event';
                    } else {
                        folderPath.textContent = 'this event';
                    }
                } catch (error) {
                    folderPath.textContent = 'this event';
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
                    };
                    reader.readAsDataURL(file);

                    uploadPhoto(file);
                } else {
                    showStatus('Please select a valid image file.', 'error');
                }
            }

            async function uploadPhoto(file) {
                showStatus('Uploading photo...', 'success');

                const formData = new FormData();
                formData.append('photo', file);

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


# Folder info endpoint
@app.route('/api/folder-info', methods=['GET'])
def get_folder_info():
    """Get information about today's local storage folder."""
    date_folder = today_folder()
    return jsonify({
        "storage": "local",
        "folder_structure": "photos/YYYY-MM-DD",
        "path": f"photos/{date_folder}",
        "current_date_folder": date_folder
    })


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        images = list_all_photos()
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "images_count": len(images),
            "storage": "local",
            "photos_dir": PHOTOS_DIR
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }), 500


# Configuration endpoint
@app.route('/api/config', methods=['GET'])
def get_config():
    """Get application configuration."""
    return jsonify({
        "title": os.getenv('COLLAGE_TITLE', 'Live Photo Collage'),
        "version": "2.0.0",
        "googleClientId": GOOGLE_CLIENT_ID,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


# Download every photo as a single zip, gated behind Google Sign-In
@app.route('/api/download-all', methods=['GET'])
def download_all():
    """Zip and return every photo on the board. Requires a valid Google ID token."""
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Google Sign-In is not configured on this server"}), 503

    payload = verify_google_token(bearer_token())
    if not payload:
        return jsonify({"error": "Sign in with Google to download photos"}), 401

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for date_name in sorted(os.listdir(ORIGINALS_DIR)) if os.path.isdir(ORIGINALS_DIR) else []:
            date_path = os.path.join(ORIGINALS_DIR, date_name)
            if not os.path.isdir(date_path):
                continue
            for filename in os.listdir(date_path):
                if os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS:
                    zf.write(os.path.join(date_path, filename), arcname=f"{date_name}/{filename}")

    buffer.seek(0)
    logger.info(f"Photo archive downloaded by {payload.get('email', 'unknown user')}")
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"live-photo-collage_{datetime.datetime.now().strftime('%Y%m%d')}.zip"
    )


# Wipe every photo from the board, gated behind Google Sign-In
@app.route('/api/clear-photos', methods=['DELETE'])
def clear_photos():
    """Delete every stored photo and tell connected clients to clear their board."""
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "Google Sign-In is not configured on this server"}), 503

    payload = verify_google_token(bearer_token())
    if not payload:
        return jsonify({"error": "Sign in with Google to clear the board"}), 401

    removed = len(list_all_photos())

    for directory in (PHOTOS_DIR, ORIGINALS_DIR):
        if not os.path.isdir(directory):
            continue
        for date_name in os.listdir(directory):
            date_path = os.path.join(directory, date_name)
            if os.path.isdir(date_path):
                shutil.rmtree(date_path)

    known_urls.clear()
    socketio.emit('board_cleared')
    logger.info(f"Board cleared ({removed} photos) by {payload.get('email', 'unknown user')}")

    return jsonify({"status": "cleared", "removed": removed})


def user_to_dict(row):
    return {
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
        "phone": row["phone"],
        "firstSeen": row["first_seen"],
        "lastSeen": row["last_seen"],
    }


# Record/refresh a user's profile on Google sign-in and return the stored record
@app.route('/api/profile', methods=['POST'])
def upsert_profile():
    """Upsert the signed-in user's profile (email/name/picture from the Google token)."""
    payload = verify_google_token(bearer_token())
    if not payload:
        return jsonify({"error": "Sign in with Google first"}), 401

    sub = payload['sub']
    email = payload.get('email', '')
    name = payload.get('name', '')
    picture = payload.get('picture', '')
    now = datetime.datetime.utcnow().isoformat()

    conn = get_db()
    conn.execute('''
        INSERT INTO users (google_sub, email, name, picture, phone, first_seen, last_seen)
        VALUES (?, ?, ?, ?, NULL, ?, ?)
        ON CONFLICT(google_sub) DO UPDATE SET
            email = excluded.email,
            name = excluded.name,
            picture = excluded.picture,
            last_seen = excluded.last_seen
    ''', (sub, email, name, picture, now, now))
    conn.commit()
    row = conn.execute('SELECT * FROM users WHERE google_sub = ?', (sub,)).fetchone()
    conn.close()

    return jsonify({**user_to_dict(row), "isAdmin": is_admin(payload)})


# Update the signed-in user's phone number
@app.route('/api/profile', methods=['PUT'])
def update_profile():
    """Update the phone number for the signed-in user's profile."""
    payload = verify_google_token(bearer_token())
    if not payload:
        return jsonify({"error": "Sign in with Google first"}), 401

    phone = (request.get_json(silent=True) or {}).get('phone', '').strip()
    sub = payload['sub']

    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE google_sub = ?', (sub,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Sign in again before updating your profile"}), 404

    conn.execute('UPDATE users SET phone = ? WHERE google_sub = ?', (phone, sub))
    conn.commit()
    row = conn.execute('SELECT * FROM users WHERE google_sub = ?', (sub,)).fetchone()
    conn.close()

    return jsonify({**user_to_dict(row), "isAdmin": is_admin(payload)})


# List every user who has ever signed in, restricted to ADMIN_EMAILS
@app.route('/api/admin/users', methods=['GET'])
def list_users():
    """List all recorded user profiles. Requires a valid Google ID token belonging to an admin."""
    payload = verify_google_token(bearer_token())
    if not payload:
        return jsonify({"error": "Sign in with Google to view users"}), 401
    if not is_admin(payload):
        return jsonify({"error": "You don't have access to the user list"}), 403

    conn = get_db()
    rows = conn.execute('SELECT * FROM users ORDER BY last_seen DESC').fetchall()
    conn.close()

    return jsonify([user_to_dict(row) for row in rows])


# Serve image URLs
@app.route('/api/images', methods=['GET'])
def get_images():
    """API to fetch current image URLs from local storage."""
    try:
        images = list_all_photos()
        known_urls.update(images)
        return jsonify(images)
    except Exception as e:
        logger.error(f"Error listing images: {str(e)}")
        return jsonify([])


# Rescan storage for photos added outside the upload API and notify clients
@app.route('/api/refresh-images', methods=['POST'])
def refresh_images():
    """Rescan local storage and notify clients of any photos not seen before."""
    try:
        current = list_all_photos()
        new_urls = [url for url in current if url not in known_urls]

        if new_urls:
            known_urls.update(new_urls)
            socketio.emit('new_images', new_urls)

        return jsonify({"status": "Checked for new images", "new_urls": new_urls})

    except Exception as e:
        logger.error(f"Error refreshing images: {str(e)}")
        return jsonify({"error": "Failed to refresh images"}), 500


if __name__ == '__main__':
    known_urls.update(list_all_photos())
    logger.info(f"Loaded {len(known_urls)} existing photos from {PHOTOS_DIR}")
    logger.info("Starting the application server...")
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, allow_unsafe_werkzeug=True)
