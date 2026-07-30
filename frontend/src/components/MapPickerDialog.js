import React, { useEffect, useRef, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2, MapPin, Crosshair } from 'lucide-react';
import { api } from '../lib/api';
import { loadGoogleMaps, LUCKNOW_CENTER } from '../lib/googleMaps';

// Drop-a-pin dialog. The customer's typed address gets them to the right street; this gets the
// rider to the right gate. Returns { lat, lng } to the caller on confirm.
export default function MapPickerDialog({ open, onOpenChange, initial, onConfirm }) {
  const mapNodeRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const [pin, setPin] = useState(null);
  const [nearby, setNearby] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Look up what sits at the pin so the customer can sanity-check it before confirming.
  useEffect(() => {
    if (!pin) return;
    let cancelled = false;
    setNearby('');
    const t = setTimeout(() => {
      api.get('/places/reverse', { params: { lat: pin.lat, lng: pin.lng } })
        .then(({ data }) => { if (!cancelled) setNearby(data.formatted_address || ''); })
        .catch(() => {});
    }, 400);
    return () => { cancelled = true; clearTimeout(t); };
  }, [pin]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError('');

    loadGoogleMaps().then(({ Map, Marker }) => {
      if (cancelled || !mapNodeRef.current) return;
      const start = (initial && initial.lat != null && initial.lng != null)
        ? { lat: Number(initial.lat), lng: Number(initial.lng) }
        : LUCKNOW_CENTER;

      const map = new Map(mapNodeRef.current, {
        center: start,
        zoom: (initial && initial.lat != null) ? 17 : 13,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        clickableIcons: false,
      });
      const marker = new Marker({ position: start, map, draggable: true });
      marker.addListener('dragend', (e) => setPin({ lat: e.latLng.lat(), lng: e.latLng.lng() }));
      map.addListener('click', (e) => {
        marker.setPosition(e.latLng);
        setPin({ lat: e.latLng.lat(), lng: e.latLng.lng() });
      });

      mapRef.current = map;
      markerRef.current = marker;
      setPin(start);
      setLoading(false);
    }).catch((err) => {
      if (!cancelled) { setError(err.message || 'Could not load the map'); setLoading(false); }
    });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Drop the map instance when the dialog closes so reopening rebuilds it against a fresh node.
  useEffect(() => {
    if (!open) { mapRef.current = null; markerRef.current = null; setPin(null); setNearby(''); }
  }, [open]);

  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const here = { lat: coords.latitude, lng: coords.longitude };
        if (mapRef.current && markerRef.current) {
          mapRef.current.setCenter(here);
          mapRef.current.setZoom(17);
          markerRef.current.setPosition(here);
        }
        setPin(here);
      },
      () => setError('Could not read your location. Drag the pin instead.'),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><MapPin className="h-4 w-4" /> Pin your exact location</DialogTitle>
        </DialogHeader>
        <div className="text-xs text-muted-foreground -mt-2">
          Tap the map or drag the pin to your gate, so the delivery rider reaches the right spot.
        </div>

        <div className="relative rounded-xl overflow-hidden border border-border bg-muted/40" style={{ height: 340 }}>
          <div ref={mapNodeRef} className="absolute inset-0" data-testid="map-picker-canvas" />
          {loading && !error && (
            <div className="absolute inset-0 grid place-items-center bg-background/70 text-sm text-muted-foreground">
              <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading map…</span>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 grid place-items-center bg-background/90 p-4 text-center text-sm text-red-600">{error}</div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
          <button type="button" onClick={useMyLocation} disabled={!!error}
            className="inline-flex items-center gap-1.5 text-primary hover:underline disabled:opacity-40">
            <Crosshair className="h-3.5 w-3.5" /> Use my current location
          </button>
          {pin && <span className="text-muted-foreground">{pin.lat.toFixed(5)}, {pin.lng.toFixed(5)}</span>}
        </div>
        {nearby && <div className="text-xs text-muted-foreground">Pin is near: {nearby}</div>}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="button" disabled={!pin || !!error} data-testid="map-picker-confirm"
            onClick={() => { onConfirm(pin, nearby); onOpenChange(false); }}>
            Confirm location
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
