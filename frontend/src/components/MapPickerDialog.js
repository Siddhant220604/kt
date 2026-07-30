import React, { useEffect, useRef, useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2, MapPin, Crosshair } from 'lucide-react';
import { api } from '../lib/api';
import { loadGoogleMaps, LUCKNOW_CENTER, MAX_DELIVERY_RADIUS_KM, haversineKm } from '../lib/googleMaps';

const OUTSIDE_MESSAGE = 'Delivery is not available at this address. We currently deliver only within Lucknow.';
// A GPS fix is accurate to tens of metres; an IP-derived one to tens of kilometres. Anything
// past the coarse threshold is not a location, it's a guess at a city.
const COARSE_FIX_METRES = 3000;
const PRECISE_FIX_METRES = 100;

// Drop-a-pin dialog. The customer's typed address gets them to the right street; this gets the
// rider to the right gate. Returns { lat, lng } to the caller on confirm.
export default function MapPickerDialog({ open, onOpenChange, initial, onConfirm }) {
  const mapNodeRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const [pin, setPin] = useState(null);
  const [nearby, setNearby] = useState('');
  const [outside, setOutside] = useState('');
  const [checking, setChecking] = useState(false);
  const [loading, setLoading] = useState(true);
  // `error` means the map itself is unusable and blocks confirming; a geolocation failure is
  // only a failed convenience, so it gets its own state and never blocks the dialog.
  const [error, setError] = useState('');
  const [geoError, setGeoError] = useState('');
  const [locating, setLocating] = useState(false);

  // Look up what sits at the pin, both so the customer can sanity-check it and so a pin outside
  // Lucknow is refused here rather than after they've filled in the rest of the form.
  useEffect(() => {
    if (!pin) return;
    let cancelled = false;
    setNearby('');
    setOutside('');
    // Anything past the delivery radius is refusable without asking Google at all, which also
    // covers pins in the middle of nowhere where the lookup finds no place to name.
    if (haversineKm(pin, LUCKNOW_CENTER) > MAX_DELIVERY_RADIUS_KM) {
      setOutside(OUTSIDE_MESSAGE);
      return;
    }
    setChecking(true);
    const t = setTimeout(() => {
      api.get('/places/reverse', { params: { lat: pin.lat, lng: pin.lng } })
        .then(({ data }) => {
          if (cancelled) return;
          setNearby(data.formatted_address || '');
          setOutside(data.deliverable === false ? (data.reason || OUTSIDE_MESSAGE) : '');
        })
        .catch(() => {})
        .finally(() => { if (!cancelled) setChecking(false); });
    }, 400);
    return () => { cancelled = true; clearTimeout(t); setChecking(false); };
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
    if (!open) {
      mapRef.current = null; markerRef.current = null;
      setPin(null); setNearby(''); setOutside(''); setChecking(false); setGeoError(''); setLocating(false);
    }
  }, [open]);

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      return setGeoError('This browser cannot share your location. Drag the pin instead.');
    }
    // Browsers only expose geolocation on secure origins, and the failure there is silent
    // enough to look like a bug - say so plainly.
    if (!window.isSecureContext) {
      return setGeoError('Your location needs a secure (https) connection. Drag the pin instead.');
    }
    setGeoError('');
    setLocating(true);

    const onFound = ({ coords }) => {
      setLocating(false);
      const here = { lat: coords.latitude, lng: coords.longitude };
      const accuracy = coords.accuracy || 0;

      // With no GPS or WiFi to go on, browsers fall back to locating by IP address, which in
      // India lands on whichever city the ISP routes through - a Lucknow customer on a desktop
      // routinely gets pinned in Delhi. Such a fix reports an accuracy of many kilometres, so
      // refuse it outright: a pin that is confidently wrong is worse than no pin, and it would
      // otherwise trip the "we don't deliver here" message for a customer who is in Lucknow.
      if (accuracy > COARSE_FIX_METRES) {
        setGeoError(
          `Your browser could only locate you to within ${Math.round(accuracy / 1000)} km, which is too rough to deliver to`
          + ' - this usually happens on a desktop or over a VPN. Please drag the pin to your exact spot,'
          + ' or open the site on your phone.',
        );
        return;
      }

      if (mapRef.current && markerRef.current) {
        mapRef.current.setCenter(here);
        mapRef.current.setZoom(17);
        markerRef.current.setPosition(here);
      }
      setPin(here);
      setGeoError(accuracy > PRECISE_FIX_METRES
        ? `Located you to within about ${Math.round(accuracy)} m - drag the pin if it isn't exactly your gate.`
        : '');
    };
    const onFailed = (err) => {
      setLocating(false);
      setGeoError(
        err && err.code === 1 ? 'Location permission was blocked. Allow it in your browser, or drag the pin instead.'
          : err && err.code === 3 ? 'Locating you took too long. Drag the pin instead.'
            : 'Could not read your location. Drag the pin instead.',
      );
    };

    navigator.geolocation.getCurrentPosition(
      onFound,
      // A high-accuracy fix often times out indoors; retry once accepting a coarser position
      // before giving up, since even a rough fix saves the customer panning across the city.
      (err) => {
        if (err && err.code === 3) {
          navigator.geolocation.getCurrentPosition(onFound, onFailed, { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 });
        } else {
          onFailed(err);
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
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
          <button type="button" onClick={useMyLocation} disabled={!!error || locating}
            className="inline-flex items-center gap-1.5 text-primary hover:underline disabled:opacity-40">
            <Crosshair className="h-3.5 w-3.5" /> {locating ? 'Locating…' : 'Use my current location'}
          </button>
          {pin && <span className="text-muted-foreground">{pin.lat.toFixed(5)}, {pin.lng.toFixed(5)}</span>}
        </div>
        {geoError && <div className="text-xs text-amber-600">{geoError}</div>}
        {nearby && !outside && <div className="text-xs text-muted-foreground">Pin is near: {nearby}</div>}
        {outside && (
          <div className="text-sm text-red-600 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
            data-testid="map-picker-outside">
            {outside}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="button" disabled={!pin || !!error || !!outside || checking} data-testid="map-picker-confirm"
            onClick={() => { onConfirm(pin, nearby); onOpenChange(false); }}>
            {checking ? 'Checking…' : 'Confirm location'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
