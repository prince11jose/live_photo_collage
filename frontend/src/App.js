import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import QRCode from 'qrcode.react';

// Determine backend URL based on environment
const getBackendUrl = () => {
  const currentPort = window.location.port;
  if (currentPort === '3001' || currentPort === '3000') {
    return 'http://localhost:5000';
  }
  return window.location.origin.replace(':' + currentPort, ':5000');
};

const socket = io(getBackendUrl());

function App() {
  const [images, setImages] = useState([]);
  const [uploadUrl, setUploadUrl] = useState('');
  const [backendUrl] = useState(getBackendUrl());

  // Get the upload URL
  useEffect(() => {
    setUploadUrl(`${backendUrl}/upload`);
  }, [backendUrl]);

  // Fetch initial images once on mount
  useEffect(() => {
    const fetchInitialImages = async () => {
      try {
        const response = await fetch(`${backendUrl}/api/images`);
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();
        console.log("Fetched images:", data);
        setImages(data);
        localStorage.setItem('images', JSON.stringify(data));
      } catch (error) {
        console.error("Failed to fetch initial images:", error);
      }
    };

    fetchInitialImages();
  }, [backendUrl]);

  // Listen for new images from the socket once on mount
  useEffect(() => {
    const handleNewImages = (newImages) => {
      if (newImages && newImages.length > 0) {
        console.log("New images received:", newImages);
        setImages(prevImages => {
          const updatedImages = [...prevImages, ...newImages];
          localStorage.setItem('images', JSON.stringify(updatedImages));
          return updatedImages;
        });
      }
    };

    socket.on('new_images', handleNewImages);
    return () => {
      socket.off('new_images', handleNewImages);
    };
  }, []);

  // Load cached images from localStorage once on mount
  useEffect(() => {
    const cachedImages = JSON.parse(localStorage.getItem('images')) || [];
    if (cachedImages.length > 0) {
      setImages(cachedImages);
    }
  }, []);

  return (
    <div className="collage">
      <div className="header">
        <h1>📸 Live Photo Collage</h1>
        <div className="qr-section">
          <div className="qr-container">
            <QRCode 
              value={uploadUrl} 
              size={150}
              level="M"
              includeMargin={true}
            />
            <p className="qr-text">
              <strong>📱 Scan to Upload Photos</strong><br/>
              Use your phone camera to scan this QR code
            </p>
          </div>
        </div>
      </div>
      
      <div className="stats">
        <p>{images.length} photo{images.length !== 1 ? 's' : ''} in collage</p>
      </div>
      
      <div className="image-grid">
        {images.length > 0 ? (
          images.map((url, index) => {
            console.log(`Rendering image: ${url}`);
            return (
              <img
                key={index} // Consider changing this to a unique identifier if available
                src={url}
                alt={`img-${index}`}
                className="image-item"
                loading="lazy" // Lazy load images
                crossOrigin="anonymous" // Add crossOrigin for external images
                onError={(e) => {
                  console.error(`Error loading image: ${url}`); // Log the failed URL
                  e.target.onerror = null;
                  e.target.src = 'https://via.placeholder.com/150'; // Fallback image
                }}
              />
            );
          })
        ) : (
          <div className="empty-state">
            <p>No photos yet! 📱</p>
            <p>Scan the QR code above with your phone to start adding photos</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
