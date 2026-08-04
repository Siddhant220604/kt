import React, { useEffect, useRef, useState } from 'react';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { MapPin, Check } from 'lucide-react';
import { api } from '../lib/api';
import { mapsAvailable, mapsPlaceUrl } from '../lib/googleMaps';
import MapPickerDialog from './MapPickerDialog';

const newSessionToken = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;

// Address Line 1 + "Select on map", shared by checkout and the account page.
//
// `value` holds the address fields; `onChange` receives a partial patch. Line 1 has to come from
// a Google suggestion rather than free text - a typo'd street geocodes somewhere plausible but
// wrong, and the customer only finds out when the delivery doesn't arrive. `verified` reflects
// that, and the caller uses it to gate submission.
export default function AddressPicker({ value, onChange, verified, onVerifiedChange, testIdPrefix = 'address' }) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const sessionRef = useRef(newSessionToken());
  // Set when Line 1 changes programmatically (suggestion picked, saved address applied) so the
  // change doesn't immediately trigger a fresh suggestions lookup for text we just wrote.
  const programmaticRef = useRef(false);

  const line1 = value.address_line1 || '';

  useEffect(() => {
    if (programmaticRef.current) { programmaticRef.current = false; return; }
    const q = line1.trim();
    if (q.length < 3) { setSuggestions([]); setOpen(false); return; }
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get('/places/autocomplete', { params: { q, session: sessionRef.current } });
        setSuggestions(data.suggestions || []);
        setOpen((data.suggestions || []).length > 0);
      } catch {
        setSuggestions([]);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [line1]);

  const pick = async (s) => {
    setOpen(false);
    setSuggestions([]);
    programmaticRef.current = true;
    try {
      const { data } = await api.get(`/places/details/${s.place_id}`, { params: { session: sessionRef.current } });
      // A Places session ends at the first details call - start a fresh one for the next search.
      sessionRef.current = newSessionToken();
      onChange({
        address_line1: data.address_line1 || s.description || s.main_text,
        city: data.city || value.city,
        state: data.state || value.state,
        pincode: /^\d{6}$/.test(data.pincode || '') ? data.pincode : value.pincode,
        lat: data.lat ?? null,
        lng: data.lng ?? null,
      });
    } catch {
      onChange({ address_line1: s.description || s.main_text });
    }
    onVerifiedChange(true);
  };

  const hasPin = value.lat != null && value.lng != null;

  return (
    <>
      <div className="sm:col-span-2 relative">
        <Label className="text-xs text-muted-foreground">Address Line 1 *</Label>
        <Input
          required
          autoComplete="off"
          value={line1}
          aria-invalid={!!line1 && !verified}
          placeholder="Start typing to search your address"
          onChange={(e) => { onVerifiedChange(false); onChange({ address_line1: e.target.value, lat: null, lng: null }); }}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          data-testid={`${testIdPrefix}-line1-input`}
        />
        {open && suggestions.length > 0 && (
          <div className="absolute z-20 left-0 right-0 top-full mt-1 bg-card border border-border rounded-xl shadow-lg overflow-hidden"
            data-testid={`${testIdPrefix}-suggestions`}>
            {suggestions.map(s => (
              <button key={s.place_id} type="button"
                onMouseDown={(e) => { e.preventDefault(); pick(s); }}
                className="w-full text-left px-3 py-2.5 hover:bg-muted flex items-start gap-2 border-b border-border/50 last:border-b-0">
                <MapPin className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                <span className="min-w-0">
                  <span className="block text-sm font-medium truncate">{s.main_text}</span>
                  <span className="block text-xs text-muted-foreground truncate">{s.secondary_text}</span>
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="mt-1.5 flex items-center justify-between gap-2 flex-wrap">
          {verified
            ? <span className="text-xs text-emerald-600 inline-flex items-center gap-1"><Check className="h-3 w-3" /> Address confirmed</span>
            : <span className="text-xs text-muted-foreground">Pick your address from the suggestions</span>}
          {mapsAvailable() && (
            <button type="button" onClick={() => setMapOpen(true)}
              className="text-xs text-primary hover:underline inline-flex items-center gap-1"
              data-testid={`${testIdPrefix}-select-on-map`}>
              <MapPin className="h-3.5 w-3.5" /> {hasPin ? 'Change location on map' : 'Select on map'}
            </button>
          )}
        </div>

        {hasPin && (
          <div className="mt-1 text-[11px] text-muted-foreground">
            Pinned at {Number(value.lat).toFixed(5)}, {Number(value.lng).toFixed(5)} ·{' '}
            <a href={mapsPlaceUrl(value.lat, value.lng)} target="_blank" rel="noreferrer" className="text-primary hover:underline">view</a>
          </div>
        )}
      </div>

      <MapPickerDialog
        open={mapOpen}
        onOpenChange={setMapOpen}
        initial={hasPin ? { lat: value.lat, lng: value.lng } : null}
        onConfirm={(pin, place) => {
          // A dropped pin is a deliberate confirmation of where to deliver, so it counts as
          // verification on its own - including when the customer skipped the suggestions.
          //
          // The pin also knows its own PIN code, so take it from there rather than making the
          // customer type it - the code that belongs to the spot they pointed at beats the one
          // they remember. Only when the lookup actually returned one; a pin in a gap between
          // named places doesn't get to blank out a code they already have.
          const pincode = /^\d{6}$/.test(place?.pincode || '') ? place.pincode : value.pincode;
          onChange({
            lat: pin.lat,
            lng: pin.lng,
            address_line1: line1.trim() || place?.formatted_address || '',
            pincode,
          });
          onVerifiedChange(true);
        }}
      />
    </>
  );
}
