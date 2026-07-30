// Loads the Google Maps JavaScript API once per page, shared by every map on the site.
// The browser key is separate from the backend's server key and should be referrer-restricted
// in the Google Cloud console - it is visible to anyone who opens the page.
export const MAPS_BROWSER_KEY = process.env.REACT_APP_GOOGLE_MAPS_KEY || '';

let loader = null;

export const mapsAvailable = () => !!MAPS_BROWSER_KEY;

export const loadGoogleMaps = () => {
  if (!MAPS_BROWSER_KEY) return Promise.reject(new Error('Google Maps browser key is not configured'));
  if (window.google && window.google.maps) return Promise.resolve(window.google.maps);
  if (loader) return loader;

  loader = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(MAPS_BROWSER_KEY)}&v=weekly&loading=async`;
    script.async = true;
    script.onload = () => {
      if (window.google && window.google.maps) resolve(window.google.maps);
      else reject(new Error('Google Maps failed to initialise'));
    };
    script.onerror = () => {
      // Let a later attempt retry rather than caching the failure forever.
      loader = null;
      reject(new Error('Could not load Google Maps'));
    };
    document.head.appendChild(script);
  });
  return loader;
};

// Kiran Traders' delivery area, used to centre a map that has no pin yet.
export const LUCKNOW_CENTER = { lat: 26.8467, lng: 80.9462 };

export const mapsDirectionsUrl = (lat, lng) =>
  `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;

export const mapsPlaceUrl = (lat, lng) =>
  `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
