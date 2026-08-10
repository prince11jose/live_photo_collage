import React, { useState, useEffect, useRef, useCallback } from 'react';
import QRCode from 'qrcode.react';
import io from 'socket.io-client';
import './App.css';

const DEVELOP_MS = 2000;
const TILE_GAP = 4;

// Pick the rows/cols that fill a box of the given size with the largest possible
// tiles and no leftover scroll, for a given tile count.
function fitTilesToBox(count, width, height) {
  if (count <= 0 || width <= 0 || height <= 0) return null;

  let best = null;
  for (let cols = 1; cols <= count; cols++) {
    const rows = Math.ceil(count / cols);
    const cellW = (width - (cols - 1) * TILE_GAP) / cols;
    const cellH = (height - (rows - 1) * TILE_GAP) / rows;
    if (cellW <= 0 || cellH <= 0) continue;
    const area = cellW * cellH;
    if (!best || area > best.area) {
      best = { cols, rows, cellW, cellH, area };
    }
  }
  return best;
}

function ApertureIcon(props) {
  return (
    <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <circle cx="24" cy="24" r="21" stroke="currentColor" strokeWidth="2" opacity="0.35" />
      {[0, 60, 120, 180, 240, 300].map((deg) => (
        <path
          key={deg}
          d="M24 24 L24 7 A17 17 0 0 1 37.7 15.5 Z"
          fill="currentColor"
          opacity="0.85"
          transform={`rotate(${deg} 24 24)`}
        />
      ))}
      <circle cx="24" cy="24" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function CameraOutlineIcon(props) {
  return (
    <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <rect x="6" y="18" width="52" height="36" rx="6" stroke="currentColor" strokeWidth="2.5" />
      <path d="M20 18l4-8h16l4 8" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx="32" cy="37" r="11" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="32" cy="37" r="4" fill="currentColor" />
      <circle cx="49" cy="26" r="1.8" fill="currentColor" />
    </svg>
  );
}

function decodeGoogleCredential(token) {
  try {
    const payload = token.split('.')[1];
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decodeURIComponent(escape(json)));
  } catch (err) {
    return null;
  }
}

function Photo({ url, index }) {
  const [broken, setBroken] = useState(false);
  return (
    <div className="polaroid__frame">
      <img
        src={url}
        alt={`#${index + 1}`}
        loading="lazy"
        style={broken ? { opacity: 0.25 } : undefined}
        onError={() => setBroken(true)}
      />
    </div>
  );
}

function App() {
  const [images, setImages] = useState([]);
  const [freshUrls, setFreshUrls] = useState(() => new Set());
  const [imagesLoading, setImagesLoading] = useState(false);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [restoringSession, setRestoringSession] = useState(() => !!localStorage.getItem('idToken'));
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const [config, setConfig] = useState({ title: 'Live Photo Collage' });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [user, setUser] = useState(null);
  const [idToken, setIdToken] = useState(null);
  const [signInError, setSignInError] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [phoneInput, setPhoneInput] = useState('');
  const [savingPhone, setSavingPhone] = useState(false);
  const [showUsers, setShowUsers] = useState(false);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState(null);
  const googleBtnRef = useRef(null);
  const gridRef = useRef(null);
  const socketRef = useRef(null);
  const idTokenRef = useRef(null);
  const joinedBoardRef = useRef(null);
  const [gridBox, setGridBox] = useState({ width: 0, height: 0 });

  useEffect(() => {
    idTokenRef.current = idToken;
  }, [idToken]);

  const loadImages = useCallback(async (token, boardId) => {
    setImagesLoading(true);
    try {
      const response = await fetch('/api/images', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setImages(data);
      setError(null);
      localStorage.setItem(`images_${boardId}`, JSON.stringify(data));
    } catch (err) {
      setError(err.message || 'Could not reach the server.');
      const cached = JSON.parse(localStorage.getItem(`images_${boardId}`)) || [];
      if (cached.length > 0) setImages(cached);
    } finally {
      setImagesLoading(false);
    }
  }, []);

  const leaveCurrentBoard = () => {
    if (joinedBoardRef.current && socketRef.current) {
      socketRef.current.emit('leave_board', { board: joinedBoardRef.current });
    }
    joinedBoardRef.current = null;
  };

  const signInWithToken = useCallback(async (token, { silent } = {}) => {
    const profile = decodeGoogleCredential(token);
    if (!profile) {
      if (silent) localStorage.removeItem('idToken');
      return;
    }

    try {
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      leaveCurrentBoard();
      localStorage.setItem('idToken', token);
      setIdToken(token);
      setUser({
        name: profile.name,
        picture: profile.picture,
        email: profile.email,
        phone: data.phone || '',
        isAdmin: !!data.isAdmin,
        boardId: data.boardId,
      });
      setPhoneInput(data.phone || '');
      setSignInError(null);
      setDownloadError(null);

      socketRef.current?.emit('join_board', { token });
      joinedBoardRef.current = data.boardId;

      loadImages(token, data.boardId);
    } catch (err) {
      if (silent) {
        // Stored session is stale (expired/revoked) - fall back to the sign-in button quietly.
        localStorage.removeItem('idToken');
      } else {
        setSignInError('Could not verify your sign-in with the server. Try again.');
      }
    }
  }, [loadImages]);

  const handleCredentialResponse = useCallback((response) => {
    signInWithToken(response.credential);
  }, [signInWithToken]);

  // Restore a previous sign-in (e.g. after opening the fullscreen view in a new
  // tab) from the token saved on the last successful sign-in.
  useEffect(() => {
    const stored = localStorage.getItem('idToken');
    if (!stored) return;
    signInWithToken(stored, { silent: true }).finally(() => setRestoringSession(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initialize Google Sign-In once the client ID and GIS script are available
  useEffect(() => {
    if (!config.googleClientId || user) return;

    const initGsi = () => {
      if (!window.google || !googleBtnRef.current) return;
      window.google.accounts.id.initialize({
        client_id: config.googleClientId,
        callback: handleCredentialResponse,
      });
      window.google.accounts.id.renderButton(googleBtnRef.current, {
        theme: 'filled_black',
        size: 'large',
        shape: 'pill',
        text: 'signin',
      });
    };

    if (window.google) {
      initGsi();
    } else {
      const timer = setInterval(() => {
        if (window.google) {
          clearInterval(timer);
          initGsi();
        }
      }, 300);
      return () => clearInterval(timer);
    }
  }, [config.googleClientId, user, handleCredentialResponse]);

  const signOut = () => {
    if (window.google) window.google.accounts.id.disableAutoSelect();
    leaveCurrentBoard();
    localStorage.removeItem('idToken');
    setUser(null);
    setIdToken(null);
    setImages([]);
    setFreshUrls(new Set());
    setShowProfile(false);
    setShowUsers(false);
    setPhoneInput('');
    setError(null);
  };

  const savePhone = async () => {
    setSavingPhone(true);
    try {
      const response = await fetch('/api/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${idToken}` },
        body: JSON.stringify({ phone: phoneInput.trim() }),
      });
      if (response.ok) {
        const data = await response.json();
        setUser((prev) => (prev ? { ...prev, phone: data.phone || '' } : prev));
      }
    } catch (err) {
      // leave the input as-is so the user can retry
    } finally {
      setSavingPhone(false);
    }
  };

  const loadUsers = async () => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const response = await fetch('/api/admin/users', {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setUsers(await response.json());
    } catch (err) {
      setUsersError(err.message || 'Could not load users.');
    } finally {
      setUsersLoading(false);
    }
  };

  const toggleUsers = () => {
    const next = !showUsers;
    setShowUsers(next);
    if (next) loadUsers();
  };

  const downloadAllPhotos = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const response = await fetch('/api/download-all', {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'live-photo-collage.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message || 'Download failed. Try again.');
    } finally {
      setDownloading(false);
    }
  };

  const clearBoard = async () => {
    if (!window.confirm('Delete every photo from your board? This cannot be undone.')) return;
    setClearing(true);
    setDownloadError(null);
    try {
      const response = await fetch('/api/clear-photos', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${response.status}`);
      }
      setImages([]);
      setFreshUrls(new Set());
      if (user) localStorage.removeItem(`images_${user.boardId}`);
    } catch (err) {
      setDownloadError(err.message || 'Could not clear the board. Try again.');
    } finally {
      setClearing(false);
    }
  };

  const markFresh = (urls) => {
    if (!urls || urls.length === 0) return;
    setFreshUrls((prev) => {
      const next = new Set(prev);
      urls.forEach((u) => next.add(u));
      return next;
    });
    setTimeout(() => {
      setFreshUrls((prev) => {
        const next = new Set(prev);
        urls.forEach((u) => next.delete(u));
        return next;
      });
    }, DEVELOP_MS);
  };

  const enterBrowserFullscreen = () => {
    const fullscreenUrl = `${window.location.pathname}?fullscreen=true`;
    const newWindow = window.open(fullscreenUrl, '_blank');

    if (newWindow) {
      newWindow.focus();
      setTimeout(() => {
        window.confirm(
          'Fullscreen view opened in a new tab.\n\n' +
          'Press F11 (or your browser\'s fullscreen option) to fill the screen.\n' +
          'Tip: Ctrl+Shift+F does this from the main page too.'
        );
      }, 1000);
    } else {
      alert(
        'Your browser blocked the popup. Open this link manually, then press F11:\n\n' + fullscreenUrl
      );
    }
  };

  // Socket connection for live updates - joins no room until the user signs in
  useEffect(() => {
    const socket = io(window.location.origin, {
      transports: ['websocket', 'polling'],
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      setError(null);
      if (idTokenRef.current) socket.emit('join_board', { token: idTokenRef.current });
    });

    socket.on('disconnect', () => setConnected(false));

    socket.on('connect_error', () => setError('Connection to server failed'));

    socket.on('new_images', (newImages) => {
      if (newImages && newImages.length > 0) {
        setImages((prev) => {
          const updated = [...prev, ...newImages];
          if (joinedBoardRef.current) {
            localStorage.setItem(`images_${joinedBoardRef.current}`, JSON.stringify(updated));
          }
          return updated;
        });
        markFresh(newImages);
      }
    });

    socket.on('board_cleared', () => {
      setImages([]);
      setFreshUrls(new Set());
    });

    return () => socket.disconnect();
  }, []);

  // Config fetch
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('/api/config');
        if (response.ok) setConfig(await response.json());
      } catch (err) {
        // keep default title
      } finally {
        setConfigLoaded(true);
      }
    };
    fetchConfig();
  }, []);

  // Fullscreen query param
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    setIsFullscreen(urlParams.get('fullscreen') === 'true');
  }, []);

  // Track the grid's available space so fullscreen mode can size tiles to fit
  // every photo on one screen with no scrolling.
  useEffect(() => {
    if (!isFullscreen || !gridRef.current) return;

    const measure = () => {
      const el = gridRef.current;
      if (el) setGridBox({ width: el.clientWidth, height: el.clientHeight });
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(gridRef.current);
    return () => observer.disconnect();
  }, [isFullscreen, images.length]);

  const tileLayout = isFullscreen ? fitTilesToBox(images.length, gridBox.width, gridBox.height) : null;

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyPress = (event) => {
      if (!isFullscreen && ((event.ctrlKey && event.shiftKey && event.key === 'F') || event.key === 'F11')) {
        event.preventDefault();
        window.location.href = `${window.location.pathname}?fullscreen=true`;
      }
    };
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [isFullscreen]);

  const refreshImages = () => {
    if (!idToken || !user) return;
    loadImages(idToken, user.boardId);
  };

  if (!configLoaded || restoringSession) {
    return (
      <div className="loading-screen">
        <ApertureIcon style={{ width: 44, height: 44 }} />
        <span className="dot">loading&hellip;</span>
      </div>
    );
  }

  if (!user) {
    return (
      <div className={`gate ${isFullscreen ? 'gate--fullscreen' : ''}`}>
        <ApertureIcon style={{ width: 40, height: 40 }} />
        <h1>{config.title}</h1>
        {config.googleClientId ? (
          <>
            <p className="gate__copy">Sign in with Google to view your private board.</p>
            <div ref={googleBtnRef} />
            {signInError && <p className="gate__error">{signInError}</p>}
          </>
        ) : (
          <p className="gate__error">
            Google Sign-In isn't configured on this server yet. Ask the admin to set GOOGLE_CLIENT_ID.
          </p>
        )}
      </div>
    );
  }

  const uploadUrl = `${window.location.origin}/upload?board=${user.boardId}`;

  return (
    <div className={`collage ${isFullscreen ? 'is-fullscreen' : ''}`}>
      {!isFullscreen && (
        <>
          <header className="marquee">
            <div className="marquee__brand">
              <ApertureIcon />
              <h1 className="marquee__title">{config.title}</h1>
            </div>
            <div className="marquee__status">
              <span className={`dot ${connected ? 'is-live' : ''}`} />
              {connected ? 'Live' : 'Reconnecting'}
            </div>
          </header>

          <div className="ticket">
            <div className="ticket__stub">
              <QRCode value={uploadUrl} size={128} level="M" includeMargin={false} />
            </div>
            <div className="ticket__body">
              <span className="ticket__eyebrow">Admit one &middot; no app required</span>
              <h2 className="ticket__headline">Add your shot</h2>
              <p className="ticket__copy">
                Scan with your phone's camera. Your photo develops right on this board, live.
              </p>
            </div>
          </div>

          {error && (
            <div className="banner">
              <p>{error}</p>
              <button className="btn" onClick={refreshImages}>Retry</button>
            </div>
          )}

          <div className="controls">
            <div className="controls__count">
              <strong>{images.length}</strong> photo{images.length !== 1 ? 's' : ''} on your board
            </div>
            <div className="controls__actions">
              <button className="btn btn--primary" onClick={refreshImages} disabled={imagesLoading}>
                {imagesLoading ? 'Checking…' : 'Refresh'}
              </button>
              <button className="btn" onClick={enterBrowserFullscreen}>Fullscreen</button>
              <a
                className="btn btn--link"
                href={`${window.location.pathname}?fullscreen=true`}
                target="_blank"
                rel="noopener noreferrer"
                title="Open fullscreen view in a new tab (then press F11)"
              >
                direct link
              </a>
            </div>
          </div>

          <div className="account-row">
            <button className="account-row__identity" onClick={() => setShowProfile((v) => !v)}>
              <img className="account-row__avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />
              <span className="account-row__name">{user.name}</span>
            </button>
            <button className="btn btn--primary" onClick={downloadAllPhotos} disabled={downloading}>
              {downloading ? 'Zipping…' : 'Download all photos'}
            </button>
            <button className="btn btn--danger" onClick={clearBoard} disabled={clearing || images.length === 0}>
              {clearing ? 'Clearing…' : 'Clear board'}
            </button>
            {user.isAdmin && (
              <button className="btn" onClick={toggleUsers}>
                {showUsers ? 'Hide users' : 'Manage users'}
              </button>
            )}
            <button className="btn btn--link" onClick={signOut}>Sign out</button>
          </div>

          {showProfile && (
            <div className="profile-panel">
              <div className="profile-panel__row">
                <img className="profile-panel__avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />
                <div>
                  <div className="profile-panel__name">{user.name}</div>
                  <div className="profile-panel__email">{user.email}</div>
                </div>
              </div>
              <label className="profile-panel__field">
                <span>Phone number</span>
                <div className="profile-panel__phone-row">
                  <input
                    type="tel"
                    value={phoneInput}
                    onChange={(e) => setPhoneInput(e.target.value)}
                    placeholder="Add a phone number"
                  />
                  <button
                    className="btn btn--primary"
                    onClick={savePhone}
                    disabled={savingPhone || phoneInput.trim() === (user.phone || '')}
                  >
                    {savingPhone ? 'Saving…' : 'Save'}
                  </button>
                </div>
              </label>
            </div>
          )}

          {user.isAdmin && showUsers && (
            <div className="users-panel">
              {usersLoading ? (
                <p className="users-panel__status">Loading users…</p>
              ) : usersError ? (
                <p className="users-panel__status">{usersError}</p>
              ) : users.length === 0 ? (
                <p className="users-panel__status">No one has signed in yet.</p>
              ) : (
                <table className="users-panel__table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Last seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.email}>
                        <td>{u.name}</td>
                        <td>{u.email}</td>
                        <td>{u.phone || '—'}</td>
                        <td>{new Date(u.lastSeen).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {downloadError && (
            <div className="banner">
              <p>{downloadError}</p>
            </div>
          )}

          <div className="hint">Ctrl+Shift+F for fullscreen</div>
        </>
      )}

      {isFullscreen && (
        <div className="fs-title">
          <h1>{config.title}</h1>
        </div>
      )}

      <div className="board">
        <div
          className="board__grid"
          ref={gridRef}
          style={
            tileLayout
              ? {
                  gridTemplateColumns: `repeat(${tileLayout.cols}, ${tileLayout.cellW}px)`,
                  gridAutoRows: `${tileLayout.cellH}px`,
                  gap: `${TILE_GAP}px`,
                }
              : undefined
          }
        >
          {images.length > 0 ? (
            images.map((url, index) => (
              <div key={url + index} className={`polaroid ${freshUrls.has(url) ? 'is-developing' : ''}`}>
                {!isFullscreen && (
                  <>
                    <span className="polaroid__pin" />
                    <span className="image-index">#{index + 1}</span>
                    <div className="polaroid__caption">{`shot ${index + 1}`}</div>
                  </>
                )}
                <Photo url={url} index={index} />
              </div>
            ))
          ) : (
            <div className="board__empty">
              <CameraOutlineIcon className="board__empty-icon" />
              <h3>{isFullscreen ? "Nothing's up yet" : 'Waiting for the first shot'}</h3>
              <p>
                {isFullscreen
                  ? 'Photos appear here the moment someone uploads.'
                  : "Scan the code above with your phone. Your photo shows up here in seconds — no app, no login."}
              </p>
              {!isFullscreen && (
                <div className="controls__actions">
                  <button className="btn btn--primary" onClick={refreshImages}>Check again</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
