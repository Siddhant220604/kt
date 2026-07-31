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

// Tightest box containing pixels the model kept. Returns null when the cutout came back empty,
// which is the signal that the model found no subject and we should keep the original photo.
const subjectBounds = (bitmap) => {
  const w = bitmap.width, h = bitmap.height;
  const probe = document.createElement('canvas');
  probe.width = w; probe.height = h;
  const ctx = probe.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bitmap, 0, 0);
  const { data } = ctx.getImageData(0, 0, w, h);

  let top = h, left = w, right = -1, bottom = -1;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (data[(y * w + x) * 4 + 3] < ALPHA_THRESHOLD) continue;
      if (x < left) left = x;
      if (x > right) right = x;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
    }
  }
  if (right < left || bottom < top) return null;
  return { x: left, y: top, w: right - left + 1, h: bottom - top + 1 };
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

/**
 * Cuts the background out of `file` and centres the subject on a white square.
 *
 * Resolves to `{ dataUrl, original, removed }` where `original` is the untouched upload (so the
 * caller can offer an undo) and `removed` is false when the model found no subject - in that
 * case `dataUrl` is still squared and padded onto white, just from the original photo.
 * Rejects only if the file itself could not be read or encoded.
 */
export async function processProductImage(file, { onProgress } = {}) {
  const original = await capOriginal(file);
  const report = (stage, pct) => onProgress?.({ stage, pct });

  let cutout = null;
  try {
    report('Removing background', 0);
    cutout = await removeBackground(file, {
      model: MODEL,
      device: 'gpu',           // falls back to wasm on CPU automatically when WebGPU is absent
      proxyToWorker: true,
      publicPath: ASSET_PATH,
      output: { format: 'image/png' },   // PNG keeps the alpha channel we need to trim against
      progress: (key, current, total) => {
        const label = PROGRESS_LABELS[String(key).split(':')[0]] || 'Processing';
        report(label, total ? Math.round((current / total) * 100) : 0);
      },
    });
  } catch (err) {
    // Model download blocked, WebGPU/wasm unavailable, out of memory - fall through to squaring
    // the original rather than failing the upload outright.
    cutout = null;
  }

  report('Finishing', 100);
  const cutBitmap = cutout ? await toBitmap(cutout) : null;
  const crop = cutBitmap ? subjectBounds(cutBitmap) : null;
  const removed = Boolean(crop);

  // A cutout that came back empty means the model kept nothing - square up the original photo
  // instead, since a blank white tile is worse than an untrimmed one.
  const source = removed ? cutBitmap : await toBitmap(file);
  const region = removed ? crop : { x: 0, y: 0, w: source.width, h: source.height };
  const dataUrl = await encodeUnderCap(composeOnWhite(source, region, CANVAS_SIZE));
  return { dataUrl, original, removed };
}
