import { removeBackground } from '@imgly/background-removal';

// Turns an admin's raw product photo into an Amazon-style catalog image: subject cut out of
// whatever it was shot against, then centred on a plain white square with even padding.
//
// The cutout runs entirely in the admin's browser (ONNX isnet model via WebAssembly/WebGPU) -
// the backend has no multipart upload endpoint and no image pipeline, images travel to Mongo as
// base64 data URI strings, so doing this server-side would have meant adding ~300MB of model +
// onnxruntime to the FastAPI image for a feature only two people ever touch.
//
// The squaring/padding half matters as much as the cutout: ProductCard renders every image into
// an `aspect-square` box, so photos that arrive at mixed aspect ratios and mixed subject sizes
// look ragged next to each other in the grid no matter how clean the background is.

// Where the model + onnxruntime wasm files are fetched from on first use (~42MB for the model,
// then cached by the browser). This is IMG.LY's official CDN. To self-host instead, mirror
// https://staticimgly.com/@imgly/background-removal-data/1.7.0/dist/ into frontend/public and
// point this at '/bgremoval/' - the manifest there (resources.json) lists every chunk.
const ASSET_PATH = undefined; // undefined = library default (the CDN above)

// 'isnet_quint8' (42MB) | 'isnet_fp16' (84MB) | 'isnet' (168MB). Larger models resolve fine
// edges better; quint8 is the smallest first download and is enough for solid product shapes.
const MODEL = 'isnet_quint8';

const CANVAS_SIZE = 1200;      // output is CANVAS_SIZE x CANVAS_SIZE
const PADDING_RATIO = 0.06;    // whitespace margin around the subject, per side
const ALPHA_THRESHOLD = 12;    // alpha below this counts as background when measuring the subject
const MAX_OUTPUT_BYTES = 900 * 1024;   // stay well under the backend's 2MB data-URI cap
const QUALITY_STEPS = [0.9, 0.82, 0.74, 0.66, 0.55];

export const MAX_INPUT_BYTES = 12 * 1024 * 1024;

// Accepts what an image slot can actually hold: a picked File, a stored base64 data URI, or a
// remote http(s) URL. Remote hosts that don't send CORS headers throw here rather than silently
// tainting a canvas we'd fail to read back later.
const toBlob = async (source) => {
  if (source instanceof Blob) return source;
  let response;
  try {
    response = await fetch(source, { mode: 'cors' });
  } catch (err) {
    throw new Error('Could not fetch that image (the host blocked the request)');
  }
  if (!response.ok) throw new Error(`Could not fetch that image (HTTP ${response.status})`);
  return response.blob();
};

const readAsDataUrl = (blob) => new Promise((res, rej) => {
  const r = new FileReader();
  r.onload = () => res(r.result);
  r.onerror = () => rej(new Error('Could not read the image file'));
  r.readAsDataURL(blob);
});

const toBitmap = async (blob) => {
  if (typeof createImageBitmap === 'function') return createImageBitmap(blob);
  // Safari <15 and friends: go via an <img> and an object URL instead.
  const url = URL.createObjectURL(blob);
  try {
    return await new Promise((res, rej) => {
      const img = new Image();
      img.onload = () => res(img);
      img.onerror = () => rej(new Error('Could not decode the image'));
      img.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
};

// A cutout is only worth keeping if the model committed to it. Measured against real catalog
// photos, a clean cut leaves under 1% of the frame semi-transparent and holds a solid subject;
// a lifestyle shot with no separable subject (product filling the frame, background the same
// tone) came back 32% semi-transparent with 3% solid - fragments, not a subject. Rejecting on
// those two numbers is what stops the backfill from shredding an image it cannot improve.
const MAX_PARTIAL_SHARE = 0.10;   // fraction of the frame left semi-transparent
const MIN_OPAQUE_SHARE = 0.05;    // fraction the model kept solidly

// Tightest box containing pixels the model kept, plus how confident that matte looks. `box` is
// null when the cutout is empty or untrustworthy - the signal to keep the original photo. The
// shares come back either way: when a cut is rejected they are the only evidence of why.
const subjectBounds = (bitmap) => {
  const w = bitmap.width, h = bitmap.height;
  const probe = document.createElement('canvas');
  probe.width = w; probe.height = h;
  const ctx = probe.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bitmap, 0, 0);
  const { data } = ctx.getImageData(0, 0, w, h);

  let top = h, left = w, right = -1, bottom = -1, opaque = 0, partial = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const alpha = data[(y * w + x) * 4 + 3];
      if (alpha > 225) opaque++;
      else if (alpha >= 30) partial++;
      if (alpha < ALPHA_THRESHOLD) continue;
      if (x < left) left = x;
      if (x > right) right = x;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
    }
  }
  const frame = w * h;
  const shares = { opaque: opaque / frame, partial: partial / frame };
  if (right < left || bottom < top) return { box: null, ...shares };
  if (shares.partial > MAX_PARTIAL_SHARE || shares.opaque < MIN_OPAQUE_SHARE) return { box: null, ...shares };
  return { box: { x: left, y: top, w: right - left + 1, h: bottom - top + 1 }, ...shares };
};

// Draw `bitmap`'s `crop` region onto a white square, scaled to fit the padded area and centred.
const composeOnWhite = (bitmap, crop, size) => {
  const canvas = document.createElement('canvas');
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, size, size);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';

  const box = size * (1 - PADDING_RATIO * 2);
  const scale = Math.min(box / crop.w, box / crop.h);
  const dw = crop.w * scale, dh = crop.h * scale;
  ctx.drawImage(bitmap, crop.x, crop.y, crop.w, crop.h, (size - dw) / 2, (size - dh) / 2, dw, dh);
  return canvas;
};

const canvasToDataUrl = (canvas, quality) => new Promise((res, rej) => {
  canvas.toBlob((blob) => (blob ? res(readAsDataUrl(blob)) : rej(new Error('Could not encode the image'))), 'image/jpeg', quality);
});

// The composed square is opaque, so JPEG is both valid and far smaller than PNG here. Step the
// quality down (then the dimensions) until the base64 string fits comfortably under the cap.
const encodeUnderCap = async (canvas) => {
  let current = canvas;
  for (let attempt = 0; attempt < 3; attempt++) {
    for (const quality of QUALITY_STEPS) {
      const dataUrl = await canvasToDataUrl(current, quality);
      if (dataUrl.length * 0.75 <= MAX_OUTPUT_BYTES) return dataUrl;
    }
    const smaller = document.createElement('canvas');
    smaller.width = Math.round(current.width * 0.75);
    smaller.height = Math.round(current.height * 0.75);
    smaller.getContext('2d').drawImage(current, 0, 0, smaller.width, smaller.height);
    current = smaller;
  }
  return canvasToDataUrl(current, 0.5);
};

// The "undo" copy of the upload. Kept verbatim when it already fits, so a small PNG keeps its
// transparency and nothing is recompressed; otherwise scaled down, since a 12MB phone photo
// restored as-is would fail the backend's 2MB data-URI cap at save time.
const capOriginal = async (file) => {
  const raw = await readAsDataUrl(file);
  if (raw.length * 0.75 <= MAX_OUTPUT_BYTES) return raw;

  const bitmap = await toBitmap(file);
  const scale = Math.min(1, CANVAS_SIZE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return encodeUnderCap(canvas);
};

const PROGRESS_LABELS = { fetch: 'Loading background remover', compute: 'Removing background' };

// The WebGPU path (device 'gpu' + the worker proxy, which the library only enables together) is
// the fast one, but it is also the one that breaks: it depends on the driver, the jsep wasm build
// and SharedArrayBuffer, and when any of those is unhappy onnxruntime throws rather than falling
// back. Plain wasm on the main thread has none of those dependencies. Trying it second means a
// machine that cannot run WebGPU still gets its cutout - slowly - instead of silently getting
// none at all, which reads to the admin as "the model found no subject" on every single image.
const ATTEMPTS = [
  { device: 'gpu', proxyToWorker: true },
  { device: 'cpu', proxyToWorker: false },
];

const runMatting = async (file, report) => {
  let lastError = null;
  for (const [index, attempt] of ATTEMPTS.entries()) {
    try {
      return await removeBackground(file, {
        ...attempt,
        model: MODEL,
        publicPath: ASSET_PATH,
        output: { format: 'image/png' },   // PNG keeps the alpha channel we need to trim against
        progress: (key, current, total) => {
          const label = PROGRESS_LABELS[String(key).split(':')[0]] || 'Processing';
          report(label, total ? Math.round((current / total) * 100) : 0);
        },
      });
    } catch (err) {
      lastError = err;
      const next = ATTEMPTS[index + 1];
      if (!next) break;
      console.warn(`[productImage] ${attempt.device} matting failed, retrying on ${next.device}`, err);
    }
  }
  throw lastError;
};

/**
 * Cuts the background out of an image and centres the subject on a white square.
 *
 * `source` is a File/Blob (a fresh upload), a base64 data URI, or a remote http(s) URL - the
 * three things a product image slot can hold.
 *
 * Resolves to `{ dataUrl, original, removed, reason, detail }` where `original` is the image as
 * it came in (so the caller can offer an undo) and `removed` is false when no usable subject
 * came back - in that case `dataUrl` is still squared and padded onto white, just from the
 * original. `reason` says which of the three fallbacks happened, and matters: the model failing
 * outright is an environment problem to fix (it fails for every image, not just this one),
 * while a rejected matte is a judgement about this one photo.
 * Rejects if the source could not be fetched, decoded, or encoded.
 */
export async function processImageSource(source, { onProgress } = {}) {
  const file = await toBlob(source);
  const original = await capOriginal(file);
  const report = (stage, pct) => onProgress?.({ stage, pct });

  let cutout = null;
  let modelError = null;
  try {
    report('Removing background', 0);
    cutout = await runMatting(file, report);
  } catch (err) {
    // Model download blocked, WebGPU/wasm unavailable, out of memory - fall through to squaring
    // the original rather than failing the upload outright. Keep the error: it is the whole
    // diagnosis when the cutout stops working, and it is invisible from the composed output.
    cutout = null;
    modelError = err;
    console.error('[productImage] background removal failed', err);
  }

  report('Finishing', 100);
  const cutBitmap = cutout ? await toBitmap(cutout) : null;
  const measured = cutBitmap ? subjectBounds(cutBitmap) : null;
  const crop = measured?.box || null;
  const removed = Boolean(crop);

  let reason = 'removed', detail = '';
  if (modelError) {
    reason = 'model-failed';
    detail = modelError.message || String(modelError);
  } else if (!removed) {
    reason = 'low-confidence';
    detail = measured
      ? `kept ${(measured.opaque * 100).toFixed(1)}% solid, ${(measured.partial * 100).toFixed(1)}% partial `
        + `(needs >${MIN_OPAQUE_SHARE * 100}% solid and <${MAX_PARTIAL_SHARE * 100}% partial)`
      : 'the cutout could not be measured';
  }

  // A cutout that came back empty means the model kept nothing - square up the original photo
  // instead, since a blank white tile is worse than an untrimmed one.
  const bitmap = removed ? cutBitmap : await toBitmap(file);
  const region = removed ? crop : { x: 0, y: 0, w: bitmap.width, h: bitmap.height };
  const dataUrl = await encodeUnderCap(composeOnWhite(bitmap, region, CANVAS_SIZE));
  return { dataUrl, original, removed, reason, detail };
}

// The upload path is just the Blob case, named for how the admin dialog uses it.
export const processProductImage = processImageSource;
