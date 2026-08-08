# Live Photo Collage

A multi-user private photo wall. Each person who signs in with Google gets their own board with a unique QR code; guests scan it and upload straight to that board with no app and no login of their own. Only the board's owner (and admins) can view, download, or clear its photos — no one's photos are visible to any other user.

## Architecture

### Backend (Flask, `backend/app.py`)
- Flask + Socket.IO for real-time updates, one private Socket.IO room per board (`board_id` = the owner's Google `sub`)
- Photos are stored on local disk, date-partitioned: `data/photos/YYYY-MM-DD/`; ownership of each photo is tracked in a SQLite `photos` table (`data/app.db`)
- `POST /api/upload` accepts uploads with no login, but requires a valid `board` id (embedded in the QR code) naming an existing board to upload into
- `/api/images`, `/api/download-all`, and `/api/clear-photos` all require Google Sign-In and only ever return/act on the caller's own board
- `/api/profile` and `/api/admin/users` record signed-in users (email, name, picture, phone) in SQLite

### Frontend (React, `frontend/src/App.js`)
- Sign in with Google to view your board — nothing is shown until you sign in
- QR code (tied to your board) for guest mobile uploads
- Live updates via Socket.IO, scoped to your board's room — new photos "develop" into view
- "Download all photos" / "Clear board" buttons for your own board; "Manage users" for admins
- Profile panel to view/edit your phone number, and Sign Out

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

- `GET /api/images` — the signed-in user's own board photos (requires `Authorization: Bearer <Google ID token>`)
- `POST /api/upload` — upload a photo (mobile, no login); requires a `board` form field naming an existing board
- `GET /upload?board=<id>` — mobile upload page for a specific board (the QR code encodes this URL)
- `POST /api/refresh-images` — admin-only: claim any photos found on disk but not yet attributed to a board
- `GET /api/download-all` — zip of the caller's own board's photos (requires Google Sign-In)
- `DELETE /api/clear-photos` — delete the caller's own board's photos (requires Google Sign-In)
- `POST /api/profile` — upsert the signed-in user's profile/board from their Google token, returns the stored record (including `boardId`)
- `PUT /api/profile` — update the signed-in user's phone number (JSON body: `{"phone": "..."}`)
- `GET /api/admin/users` — list every registered user/board (requires an email in `ADMIN_EMAILS`, returns 403 otherwise)
- `GET /api/health`, `GET /api/config`, `GET /api/folder-info`

## Google Sign-In (required)

Every board is owned by a Google account, so `GOOGLE_CLIENT_ID` must be set for the app to be usable at all:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an **OAuth 2.0 Client ID** of type **Web application**.
2. Add your site's origin (e.g. `https://photowall.princejose.dev`) as an **Authorized JavaScript origin**.
3. Set `GOOGLE_CLIENT_ID` in `backend/.env` (local) or the `photowall-config` ConfigMap (k8s) to that Client ID.
4. Set `ADMIN_EMAILS` (comma-separated) to the email address(es) that should see the "Manage users" directory across all boards, and that inherit any pre-existing/legacy photos on first sign-in.

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
