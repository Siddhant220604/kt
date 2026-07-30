// Loads the Google Maps JavaScript API once per page, shared by every map on the site.
// The browser key is separate from the backend's server key and should be referrer-restricted
// in the Google Cloud console - it is visible to anyone who opens the page.
export const MAPS_BROWSER_KEY = process.env.REACT_APP_GOOGLE_MAPS_KEY || '';

const CALLBACK_NAME = '__ktGoogleMapsReady';
const AUTH_MESSAGE = 'Google rejected this Maps key. Check that Maps JavaScript API is enabled and that this site is allowed under the key\'s website restrictions.';

let loader = null;
let authFailed = false;

export const mapsAvailable = () => !!MAPS_BROWSER_KEY;

// Google calls this globally when the key itself is refused (wrong referrer, API not enabled,
// billing off). Without it the map just sits blank with no explanation.
window.gm_authFailure = () => {
  authFailed = true;
  loader = Promise.reject(new Error(AUTH_MESSAGE));
  // Nothing may be awaiting this rejection yet; swallow the unhandled warning.
  loader.catch(() => {});
};

// Which way the classes are reachable depends on how the API booted: a direct script tag with a
// callback exposes them straight on google.maps, while the dynamic loader only installs
// importLibrary and populates the namespace on demand. Handle both rather than betting on one.
const resolveClasses = async () => {
  if (authFailed) throw new Error(AUTH_MESSAGE);
  const maps = window.google && window.google.maps;
  if (!maps) throw new Error('Google Maps failed to initialise');

  if (maps.Map && maps.Marker) return { Map: maps.Map, Marker: maps.Marker };

  if (typeof maps.importLibrary === 'function') {
    const [mapsLib, markerLib] = await Promise.all([
      maps.importLibrary('maps'),
      maps.importLibrary('marker'),
    ]);
    const Map = mapsLib.Map || maps.Map;
    const Marker = markerLib.Marker || maps.Marker;
    if (Map && Marker) return { Map, Marker };
  }
  throw new Error('Google Maps loaded without the map classes');
};

export const loadGoogleMaps = () => {
  if (!MAPS_BROWSER_KEY) return Promise.reject(new Error('Google Maps browser key is not configured'));
  if (loader) return loader;
  if (window.google && window.google.maps) {
    loader = resolveClasses();
    return loader;
  }

  loader = new Promise((resolve, reject) => {
    // Let a later attempt retry rather than caching the failure forever.
    const fail = (err) => { loader = null; reject(err); };

    window[CALLBACK_NAME] = () => {
      resolveClasses().then(resolve, fail);
      delete window[CALLBACK_NAME];
    };

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(MAPS_BROWSER_KEY)}`
      + `&v=weekly&libraries=marker&loading=async&callback=${CALLBACK_NAME}`;
    script.async = true;
    script.onerror = () => fail(new Error('Could not load Google Maps'));
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
