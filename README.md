# Live Photo Collage

A real-time event photo wall. A shared screen shows a QR code; guests scan it, snap or pick a photo, and it appears on the board within seconds — no app, no login. Optionally, guests can sign in with Google to download every photo from the event as a zip.

## Architecture

### Backend (Flask, `backend/app.py`)
- Flask + Socket.IO for real-time updates
- Photos are stored on local disk, date-partitioned: `data/photos/YYYY-MM-DD/`
- Upload endpoint for mobile photo submissions (auto-uploads on capture/select)
- `/api/download-all` zips every photo, gated behind Google Sign-In (ID token verification)
- `/api/profile` and `/api/admin/users` record signed-in users (email, name, picture, phone) in a SQLite database (`data/app.db`)

### Frontend (React, `frontend/src/App.js`)
- QR code for mobile upload access
- Live updates via Socket.IO — new photos "develop" into view
- Google Identity Services sign-in + "Download all photos" / "Clear board" / "Manage users" buttons (only shown once `GOOGLE_CLIENT_ID` is configured)
- Profile panel to view/edit the signed-in user's phone number, and Sign Out

## Local development

**Backend**
```bash
cd backend
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
python app.py            # http://localhost:5000
```

**Frontend**
```bash
cd frontend
npm install
npm start                 # http://localhost:3000, proxies /api and /socket.io to :5000
```

## API Endpoints

- `GET /api/images` — current photo URLs
- `POST /api/upload` — upload a photo (mobile)
- `GET /upload` — mobile upload page
- `POST /api/refresh-images` — rescan storage for photos added outside the API
- `GET /api/download-all` — zip of every photo (requires `Authorization: Bearer <Google ID token>`)
- `DELETE /api/clear-photos` — delete every photo (requires `Authorization: Bearer <Google ID token>`)
- `POST /api/profile` — upsert the signed-in user's profile from their Google token, returns the stored record
- `PUT /api/profile` — update the signed-in user's phone number (JSON body: `{"phone": "..."}`)
- `GET /api/admin/users` — list every recorded user profile (requires `Authorization: Bearer <Google ID token>`)
- `GET /api/health`, `GET /api/config`, `GET /api/folder-info`

## Google Sign-In (optional)

Sign-in is only shown once `GOOGLE_CLIENT_ID` is set. To enable it:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an **OAuth 2.0 Client ID** of type **Web application**.
2. Add your site's origin (e.g. `https://photowall.princejose.dev`) as an **Authorized JavaScript origin**.
3. Set `GOOGLE_CLIENT_ID` in `backend/.env` (local) or the `photowall-config` ConfigMap (k8s) to that Client ID.

## Deploying to Kubernetes

Manifests live in `k8s/`: namespace, ConfigMap, backend (Deployment + Service + PVC for `/data/photos`), and frontend (Deployment + NodePort Service; nginx serves the React build and reverse-proxies `/api`, `/upload`, `/photos`, `/socket.io` to the backend Service).

```bash
docker build -t photowall-backend:latest ./backend
docker build -t photowall-frontend:latest ./frontend

# microk8s uses its own containerd, not the host Docker daemon
docker save photowall-backend:latest  | microk8s ctr image import -
docker save photowall-frontend:latest | microk8s ctr image import -

microk8s kubectl apply -f k8s/namespace.yaml
microk8s kubectl apply -f k8s/configmap.yaml -f k8s/backend.yaml -f k8s/frontend.yaml
```

The frontend Service is exposed on NodePort `30105`. Point any reverse proxy / tunnel (e.g. Cloudflare Tunnel) at `http://localhost:30105`.

## License

MIT.
