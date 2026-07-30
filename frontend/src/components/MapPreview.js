import React, { useEffect, useRef, useState } from 'react';
import { loadGoogleMaps, mapsAvailable } from '../lib/googleMaps';

// Read-only map showing a single dropped pin - used on the admin order page so whoever is
// dispatching can see where the delivery actually goes before opening full Maps.
export default function MapPreview({ lat, lng, height = 200, zoom = 16, className = '' }) {
  const nodeRef = useRef(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!mapsAvailable() || lat == null || lng == null) return;
    let cancelled = false;
    loadGoogleMaps().then((maps) => {
      if (cancelled || !nodeRef.current) return;
      const position = { lat: Number(lat), lng: Number(lng) };
      const map = new maps.Map(nodeRef.current, {
        center: position,
        zoom,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        clickableIcons: false,
      });
      new maps.Marker({ position, map });
    }).catch((err) => {
      if (!cancelled) setError(err.message || 'Map unavailable');
    });
    return () => { cancelled = true; };
  }, [lat, lng, zoom]);

  if (lat == null || lng == null) return null;
  if (!mapsAvailable()) return null;

  return (
    <div className={`relative rounded-xl overflow-hidden border border-border bg-muted/40 ${className}`} style={{ height }}>
      <div ref={nodeRef} className="absolute inset-0" />
      {error && <div className="absolute inset-0 grid place-items-center text-xs text-muted-foreground px-3 text-center">{error}</div>}
    </div>
  );
}
