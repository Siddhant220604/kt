// Turns an admin's picked product photo into something the backend will accept: images travel to
// Mongo as base64 data URI strings, and a phone photo sent as-is blows past the 2MB data-URI cap
// at save time. So anything too big gets scaled down and re-encoded until it fits; anything that
// already fits is kept byte-for-byte, which leaves a small PNG's transparency alone.

const MAX_DIMENSION = 1200;            // longest side of a re-encoded image
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

const canvasToDataUrl = (canvas, quality) => new Promise((res, rej) => {
  canvas.toBlob((blob) => (blob ? res(readAsDataUrl(blob)) : rej(new Error('Could not encode the image'))), 'image/jpeg', quality);
});

// Step the quality down, then the dimensions, until the base64 string fits under the cap. Base64
// carries 3 bytes per 4 characters, hence the 0.75.
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

/**
 * Reads a picked File/Blob and resolves to a data URI small enough to save.
 *
 * Files already under the cap come back untouched. Larger ones are scaled to fit MAX_DIMENSION
 * and re-encoded as JPEG - which has no alpha channel, so they are drawn onto white first rather
 * than letting a transparent PNG turn black.
 *
 * Rejects if the file could not be read, decoded, or encoded.
 */
export async function processProductImage(file) {
  const raw = await readAsDataUrl(file);
  if (raw.length * 0.75 <= MAX_OUTPUT_BYTES) return raw;

  const bitmap = await toBitmap(file);
  const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return encodeUnderCap(canvas);
}
