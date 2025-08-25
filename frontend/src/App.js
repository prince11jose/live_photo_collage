import React, { useState, useEffect } from 'react';
import QRCode from 'qrcode.react';
import io from 'socket.io-client';
import './App.css';

// Custom component for handling Google Drive images with fallbacks
function DriveImage({ url, index, style, onMouseOver, onMouseOut, onLoad }) {
  const [currentUrl, setCurrentUrl] = useState(url);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [hasErrored, setHasErrored] = useState(false);

  // Helper function to get alternative Google Drive URL formats
  const getGoogleDriveImageUrl = (originalUrl) => {
    if (originalUrl.includes('drive.google.com/uc?export=view&id=')) {
      const fileId = originalUrl.split('id=')[1];
      return {
        primary: originalUrl,
        fallback1: `https://drive.google.com/thumbnail?id=${fileId}&sz=w400-h400`,
        fallback2: `https://lh3.googleusercontent.com/d/${fileId}`,
        fallback3: `https://drive.google.com/file/d/${fileId}/view`
      };
    }
    return { primary: originalUrl };
  };

  const urlFormats = getGoogleDriveImageUrl(url);
  const urlArray = Object.values(urlFormats);

  const handleImageError = () => {
    console.error(`Failed to load image (attempt ${loadAttempt + 1}): ${currentUrl}`);
    setHasErrored(true);
    
    if (loadAttempt < urlArray.length - 1) {
      const nextUrl = urlArray[loadAttempt + 1];
      console.log(`Trying fallback URL: ${nextUrl}`);
      setCurrentUrl(nextUrl);
      setLoadAttempt(prev => prev + 1);
    } else {
      console.error(`All URL formats failed for image ${index + 1}`);
    }
  };

  const handleImageLoad = (e) => {
    console.log(`Successfully loaded image (attempt ${loadAttempt + 1}): ${currentUrl}`);
    setHasErrored(false);
    if (onLoad) onLoad(e);
  };

  return (
    <img
      src={currentUrl}
      alt={`Collage Photo ${index + 1}`}
      referrerPolicy="no-referrer"
      crossOrigin="anonymous"
      style={style}
      onError={handleImageError}
      onLoad={handleImageLoad}
      onMouseOver={onMouseOver}
      onMouseOut={onMouseOut}
      title={hasErrored ? 'Image failed to load' : `Photo ${index + 1}`}
    />
  );
}

function App() {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const [config, setConfig] = useState({ title: 'Live Photo Collage' });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [imageMetadata, setImageMetadata] = useState({});

  const backendUrl = 'http://localhost:5000';
  const uploadUrl = `${backendUrl}/upload`;

  console.log('App rendering...', { images: images.length, loading, error, connected });

  // Initialize socket connection
  useEffect(() => {
    const socket = io(backendUrl, {
      transports: ['websocket', 'polling']
    });

    socket.on('connect', () => {
      console.log('Socket connected');
      setConnected(true);
      setError(null);
    });

    socket.on('disconnect', () => {
      console.log('Socket disconnected');
      setConnected(false);
    });

    socket.on('connect_error', (err) => {
      console.error('Socket connection error:', err);
      setError('Connection to server failed');
    });

    socket.on('new_images', (newImages) => {
      console.log('New images received:', newImages);
      if (newImages && newImages.length > 0) {
        setImages(prevImages => {
          const updatedImages = [...prevImages, ...newImages];
          localStorage.setItem('images', JSON.stringify(updatedImages));
          return updatedImages;
        });
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [backendUrl]);

  // Fetch initial images
  useEffect(() => {
    const fetchImages = async () => {
      try {
        console.log('Fetching images from backend...');
        const response = await fetch(`${backendUrl}/api/images`);
        
        if (response.ok) {
          const data = await response.json();
          console.log('Fetched data:', data);
          setImages(data);
          localStorage.setItem('images', JSON.stringify(data));
        } else {
          throw new Error(`HTTP ${response.status}`);
        }
      } catch (err) {
        console.error('Fetch error:', err);
        setError(err.message);
        
        // Fallback to cached images
        const cachedImages = JSON.parse(localStorage.getItem('images')) || [];
        if (cachedImages.length > 0) {
          console.log('Using cached images:', cachedImages);
          setImages(cachedImages);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchImages();
  }, [backendUrl]);

  // Fetch config
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch(`${backendUrl}/api/config`);
        if (response.ok) {
          const configData = await response.json();
          setConfig(configData);
        }
      } catch (err) {
        console.error('Config fetch error:', err);
      }
    };

    fetchConfig();
  }, [backendUrl]);

  // Check for fullscreen query parameter
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    setIsFullscreen(urlParams.get('fullscreen') === 'true');
  }, []);

  // Helper function to handle image load and determine aspect ratio
  const handleImageLoad = (url, index, imgElement) => {
    const aspectRatio = imgElement.naturalWidth / imgElement.naturalHeight;
    const orientation = aspectRatio > 1.2 ? 'landscape' : aspectRatio < 0.8 ? 'portrait' : 'square';
    
    setImageMetadata(prev => ({
      ...prev,
      [url]: {
        aspectRatio,
        orientation,
        width: imgElement.naturalWidth,
        height: imgElement.naturalHeight
      }
    }));
  };

  // Function to get dynamic grid item styles
  const getImageContainerStyle = (url, index) => {
    const metadata = imageMetadata[url];
    if (!metadata) {
      return { gridColumn: 'span 1', gridRow: 'span 1' };
    }

    const { orientation, aspectRatio } = metadata;
    
    if (isFullscreen) {
      // In fullscreen mode, give more space to interesting aspect ratios
      if (orientation === 'landscape' && aspectRatio > 1.5) {
        return { gridColumn: 'span 2', gridRow: 'span 1' };
      } else if (orientation === 'portrait' && aspectRatio < 0.6) {
        return { gridColumn: 'span 1', gridRow: 'span 2' };
      }
    }
    
    return { gridColumn: 'span 1', gridRow: 'span 1' };
  };

  // Function to get dynamic image styles
  const getImageStyle = (url) => {
    const metadata = imageMetadata[url];
    const baseStyle = {
      width: '100%',
      borderRadius: '12px',
      transition: 'transform 0.3s ease, box-shadow 0.3s ease',
      objectFit: 'cover'
    };

    if (!metadata) {
      return { ...baseStyle, height: '250px' };
    }

    const { orientation, aspectRatio } = metadata;
    
    if (isFullscreen) {
      // In fullscreen, let images show their natural proportions more
      if (orientation === 'landscape') {
        return { ...baseStyle, height: '200px', maxHeight: '300px' };
      } else if (orientation === 'portrait') {
        return { ...baseStyle, height: '300px', maxHeight: '500px' };
      } else {
        return { ...baseStyle, height: '250px' };
      }
    } else {
      // Regular mode - more uniform sizing
      return { ...baseStyle, height: '250px' };
    }
  };

  const refreshImages = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${backendUrl}/api/images`);
      if (response.ok) {
        const data = await response.json();
        setImages(data);
        localStorage.setItem('images', JSON.stringify(data));
        setError(null);
      }
    } catch (err) {
      console.error('Refresh error:', err);
      setError('Failed to refresh images');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="collage" style={{padding: '20px', textAlign: 'center'}}>
        <h1>📸 {config.title}</h1>
        <div style={{color: '#666', fontSize: '18px'}}>Loading images...</div>
      </div>
    );
  }

  return (
    <div className="collage" style={{
      padding: isFullscreen ? '10px' : '20px', 
      maxWidth: isFullscreen ? '100vw' : '1200px', 
      margin: '0 auto',
      minHeight: isFullscreen ? '100vh' : 'auto'
    }}>
      {!isFullscreen && (
        <>
          <div className="header" style={{textAlign: 'center', marginBottom: '30px'}}>
            <h1 style={{color: '#333', marginBottom: '20px'}}>📸 {config.title}</h1>
            
            {/* Connection Status */}
            <div style={{
              display: 'inline-block',
              padding: '5px 10px',
              borderRadius: '15px',
              fontSize: '12px',
              marginBottom: '15px',
              background: connected ? '#d4edda' : '#f8d7da',
              color: connected ? '#155724' : '#721c24'
            }}>
              {connected ? '🟢 Connected' : '🔴 Disconnected'}
            </div>

            {error && (
              <div style={{
                color: '#721c24',
                background: '#f8d7da',
                padding: '10px',
                borderRadius: '5px',
                marginBottom: '15px',
                border: '1px solid #f5c6cb'
              }}>
                ⚠️ {error}
                <button 
                  onClick={refreshImages}
                  style={{
                    background: '#17a2b8',
                    color: 'white',
                    border: 'none',
                    padding: '5px 10px',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    marginLeft: '10px',
                    fontSize: '12px'
                  }}
                >
                  🔄 Retry
                </button>
              </div>
            )}
            
            {/* QR Code Section */}
            <div style={{
              margin: '20px auto',
              padding: '20px',
              background: 'white',
              borderRadius: '12px',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              maxWidth: '500px'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '25px',
                flexWrap: 'wrap'
              }}>
                <QRCode 
                  value={uploadUrl} 
                  size={150}
                  level="M"
                  includeMargin={true}
                />
                <div style={{textAlign: 'left'}}>
                  <p style={{margin: 0, fontWeight: 'bold', fontSize: '16px', color: '#007bff'}}>
                    📱 Scan to Upload Photos
                  </p>
                  <p style={{margin: '8px 0 0 0', fontSize: '14px', color: '#666', lineHeight: '1.4'}}>
                    Use your phone camera to scan this QR code and start uploading photos to the collage
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Stats and Controls */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(255, 255, 255, 0.9)',
            padding: '15px 20px',
            borderRadius: '10px',
            marginBottom: '20px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}>
            <div style={{color: '#333', fontSize: '16px', fontWeight: '500'}}>
              {images.length} photo{images.length !== 1 ? 's' : ''} in collage
            </div>
            <div style={{display: 'flex', gap: '10px'}}>
              <button 
                onClick={refreshImages}
                disabled={loading}
                style={{
                  background: loading ? '#6c757d' : '#28a745',
                  color: 'white',
                  border: 'none',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  transition: 'background 0.3s ease'
                }}
              >
                {loading ? '⏳ Loading...' : '🔄 Refresh'}
              </button>
              <button 
                onClick={() => window.open(`${window.location.pathname}?fullscreen=true`, '_blank')}
                style={{
                  background: '#007bff',
                  color: 'white',
                  border: 'none',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                📺 Fullscreen
              </button>
            </div>
          </div>
        </>
      )}

      {isFullscreen && (
        <div style={{textAlign: 'center', marginBottom: '20px', position: 'relative'}}>
          <h1 style={{color: '#333', fontSize: '2.5rem', margin: '10px 0'}}>{config.title}</h1>
          <button 
            onClick={() => window.location.href = window.location.pathname}
            style={{
              background: '#007bff',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '14px',
              position: 'absolute',
              top: '10px',
              right: '10px'
            }}
          >
            Exit Fullscreen
          </button>
        </div>
      )}

      {/* Image Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isFullscreen 
          ? 'repeat(auto-fill, minmax(300px, 1fr))' 
          : 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: isFullscreen ? '15px' : '20px',
        gridAutoRows: 'min-content'
      }}>
        {images.length > 0 ? (
          images.map((url, index) => (
            <div 
              key={index} 
              style={{
                position: 'relative',
                overflow: 'hidden',
                borderRadius: '12px',
                boxShadow: '0 6px 20px rgba(0,0,0,0.15)',
                transition: 'transform 0.3s ease',
                ...getImageContainerStyle(url, index)
              }}
            >
              <DriveImage
                url={url}
                index={index}
                style={getImageStyle(url)}
                onMouseOver={(e) => {
                  e.target.style.transform = 'scale(1.05)';
                  e.target.parentElement.style.transform = 'translateY(-5px)';
                }}
                onMouseOut={(e) => {
                  e.target.style.transform = 'scale(1)';
                  e.target.parentElement.style.transform = 'translateY(0)';
                }}
                onLoad={(e) => handleImageLoad(url, index, e.target)}
              />
              <div style={{
                position: 'absolute',
                top: '10px',
                right: '10px',
                background: 'rgba(0,0,0,0.7)',
                color: 'white',
                padding: '6px 10px',
                borderRadius: '15px',
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                #{index + 1}
              </div>
            </div>
          ))
        ) : (
          <div style={{
            gridColumn: '1 / -1',
            textAlign: 'center',
            padding: isFullscreen ? '40px 20px' : '60px 20px',
            background: 'rgba(255, 255, 255, 0.9)',
            borderRadius: '15px',
            boxShadow: '0 6px 20px rgba(0,0,0,0.1)'
          }}>
            <div style={{fontSize: '48px', marginBottom: '20px'}}>📱</div>
            <h3 style={{color: '#333', marginBottom: '10px'}}>No photos yet!</h3>
            {!isFullscreen && (
              <>
                <p style={{color: '#666', marginBottom: '20px', fontSize: '16px'}}>
                  Scan the QR code above with your phone to start uploading photos to the collage.
                  Photos will appear here in real-time!
                </p>
                <button 
                  onClick={refreshImages}
                  style={{
                    background: '#007bff',
                    color: 'white',
                    border: 'none',
                    padding: '12px 24px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: '500'
                  }}
                >
                  🔄 Check for Photos
                </button>
              </>
            )}
            {isFullscreen && (
              <p style={{color: '#666', fontSize: '18px'}}>
                Photos will appear here as they are uploaded
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
