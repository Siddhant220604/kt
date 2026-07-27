import React, { useCallback, useEffect, useState } from 'react';

// Ratio mismatch below this is close enough to a full frame that the bars are
// invisible — no point layering a blurred copy behind it.
const GAP_THRESHOLD = 0.02;

// With object-contain the photo is letterboxed whenever its aspect ratio differs
// from the frame's. Returns how much of the frame the bars take up (0 = fills it).
const gapRatio = (el) => {
  const fw = el.clientWidth, fh = el.clientHeight;
  if (!fw || !fh || !el.naturalWidth || !el.naturalHeight) return 0;
  const frame = fw / fh;
  const natural = el.naturalWidth / el.naturalHeight;
  return 1 - Math.min(frame, natural) / Math.max(frame, natural);
};

/**
 * Image that fits inside its frame (object-contain), backed by a blurred copy of
 * itself only when it can't fill that frame. Must sit inside a `relative` parent.
 */
const FramedImage = ({ src, alt, fallback, className = '', ...imgProps }) => {
  const [resolvedSrc, setResolvedSrc] = useState(src);
  // Which src we measured, and whether it left a gap — tracked together so a
  // pending swap never shows the previous photo's verdict.
  const [measured, setMeasured] = useState({ src: null, gap: false });

  useEffect(() => { setResolvedSrc(src); }, [src]);

  const measure = useCallback((el) => {
    if (el) setMeasured({ src: resolvedSrc, gap: gapRatio(el) > GAP_THRESHOLD });
  }, [resolvedSrc]);

  // Cached images can already be complete before onLoad would fire, so measure on mount too.
  const ref = useCallback((el) => { if (el && el.complete) measure(el); }, [measure]);

  const showBackdrop = measured.src === resolvedSrc && measured.gap;

  return (
    <>
      {showBackdrop && (
        <img src={resolvedSrc} alt="" aria-hidden="true"
          className="absolute inset-0 w-full h-full object-cover scale-110 blur-2xl opacity-60" />
      )}
      <img ref={ref} src={resolvedSrc} alt={alt}
        onLoad={(e) => measure(e.currentTarget)}
        onError={() => { if (fallback && resolvedSrc !== fallback) setResolvedSrc(fallback); }}
        className={`relative w-full h-full object-contain ${className}`}
        {...imgProps} />
    </>
  );
};

export default FramedImage;
