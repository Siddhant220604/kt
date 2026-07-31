import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { processImageSource } from '../../lib/productImage';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Loader2, Download, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

// Backfills the background removal over images that were uploaded before that step existed.
// Runs the same pipeline as a fresh upload, one image at a time, in the admin's own browser.
//
// This rewrites live catalog data, so the backup download is not optional - it happens before
// the first write and the run cannot be started without it. Restoring is a matter of pasting a
// saved data URI back into the product's image field.

// Only the fields ProductIn accepts (extra='forbid'); the list response also carries read-only
// ones like id/created_at/avg_rating that would 422 the whole request. Mirrors the whitelist in
// pages/admin/Products.js save().
const toPayload = (p, images) => ({
  name: p.name,
  slug: p.slug || undefined,
  category_id: p.category_id,
  description: p.description,
  short_description: p.short_description,
  size: p.size,
  unit: p.unit,
  price: Number(p.price),
  compare_price: Number(p.compare_price || 0),
  moq: Number(p.moq || 1),
  stock: Number(p.stock || 0),
  images,
  specs: p.specs || {},
  featured: p.featured,
  active: p.active,
  tags: p.tags || [],
  price_tiers: (p.price_tiers || []).map(t => ({ min_qty: Number(t.min_qty), price: Number(t.price) })),
  sale_price: p.sale_price ? Number(p.sale_price) : null,
  sale_starts_at: p.sale_starts_at || null,
  sale_ends_at: p.sale_ends_at || null,
  variant_group: p.variant_group || '',
  variant_label: p.variant_label || '',
});

export default function ImageCleanupDialog({ open, onOpenChange, onDone }) {
  const [products, setProducts] = useState(null);
  const [backedUp, setBackedUp] = useState(false);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [progress, setProgress] = useState({ index: 0, total: 0, label: '', stage: '' });
  const [results, setResults] = useState({ cleaned: 0, untouched: 0, failed: [] });
  const stopRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/products', { params: { limit: 500 } });
      setProducts((data.items || []).filter(p => (p.images || []).filter(Boolean).length));
    } catch (e) {
      toast.error(errorMessage(e, 'Could not load products'));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    stopRef.current = false;
    setProducts(null); setBackedUp(false); setRunning(false); setDone(false);
    setResults({ cleaned: 0, untouched: 0, failed: [] });
    load();
  }, [open, load]);

  const slotCount = (products || []).reduce((n, p) => n + p.images.filter(Boolean).length, 0);

  const downloadBackup = () => {
    const backup = {
      exported_at: new Date().toISOString(),
      note: 'Product images as they were before the background-removal backfill. To restore one, paste its string back into that product\'s image field in the admin panel.',
      products: (products || []).map(p => ({ id: p.id, name: p.name, images: p.images })),
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = `product-images-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setBackedUp(true);
    toast.success('Backup downloaded - keep this file until you are happy with the result');
  };

  const run = async () => {
    setRunning(true);
    stopRef.current = false;
    let cleaned = 0, untouched = 0;
    const failed = [];
    let seen = 0;

    for (const product of products) {
      if (stopRef.current) break;
      const slots = product.images.map(im => im);   // preserve empty slots and their positions
      let changed = false;

      for (let i = 0; i < slots.length; i++) {
        if (stopRef.current) break;
        const src = slots[i];
        if (!src) continue;
        seen++;
        setProgress({ index: seen, total: slotCount, label: product.name, stage: 'Starting' });
        try {
          const { dataUrl, removed } = await processImageSource(src, {
            onProgress: ({ stage, pct }) => setProgress(pr => ({ ...pr, stage: pct ? `${stage} ${pct}%` : stage })),
          });
          // Only overwrite when the model actually produced a subject it was confident about.
          // Anything else stays exactly as it is - a live catalog image is not worth replacing
          // with a worse one just to make the run look complete.
          if (removed) { slots[i] = dataUrl; changed = true; cleaned++; }
          else untouched++;
        } catch (e) {
          failed.push({ name: product.name, reason: e?.message || 'Processing failed' });
        }
      }

      if (!changed) continue;
      try {
        await api.put(`/products/${product.id}`, toPayload(product, slots));
      } catch (e) {
        failed.push({ name: product.name, reason: errorMessage(e, 'Save failed') });
      }
    }

    setResults({ cleaned, untouched, failed });
    setRunning(false);
    setDone(true);
    onDone?.();
  };

  const pct = progress.total ? Math.round((progress.index / progress.total) * 100) : 0;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!running) onOpenChange(v); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Clean up existing image backgrounds</DialogTitle></DialogHeader>

        {products === null && <div className="py-8 grid place-items-center"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>}

        {products !== null && !running && !done && (
          <div className="space-y-4 text-sm">
            <p><strong>{slotCount}</strong> image{slotCount === 1 ? '' : 's'} across <strong>{products.length}</strong> product{products.length === 1 ? '' : 's'} will be cut out and centred on a white square, the same way new uploads are.</p>
            <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-2">
              <div className="flex items-start gap-2"><AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-[hsl(var(--brand-marigold))]" /><span>This replaces the images on your live store. Download the backup first - it is the only way back.</span></div>
              <Button variant="outline" size="sm" onClick={downloadBackup} className="gap-1" data-testid="cleanup-backup"><Download className="h-3 w-3" />{backedUp ? 'Download backup again' : 'Download backup'}</Button>
            </div>
            <p className="text-muted-foreground text-xs">Roughly {Math.ceil(slotCount * 7 / 60)}-{Math.ceil(slotCount * 12 / 60)} minutes. Keep this tab open and in the foreground; you can stop part-way and whatever finished stays saved.</p>
          </div>
        )}

        {running && (
          <div className="space-y-3 py-2">
            <div className="text-sm font-medium truncate">{progress.label}</div>
            <div className="text-xs text-muted-foreground">{progress.stage} &middot; image {progress.index} of {progress.total}</div>
            <div className="h-2 rounded bg-muted overflow-hidden"><div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} /></div>
          </div>
        )}

        {done && (
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-green-600" /><span><strong>{results.cleaned}</strong> cleaned up{results.untouched ? `, ${results.untouched} left alone (no clear subject to cut out)` : ''}.</span></div>
            {results.failed.length > 0 && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
                <div className="font-medium mb-1">{results.failed.length} could not be processed:</div>
                <ul className="text-xs text-muted-foreground space-y-0.5 max-h-40 overflow-auto">
                  {results.failed.map((f, i) => <li key={i}>{f.name} - {f.reason}</li>)}
                </ul>
                <p className="text-xs mt-2">These were left exactly as they were.</p>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {!running && !done && <Button onClick={run} disabled={!backedUp || !slotCount} data-testid="cleanup-start">{backedUp ? `Clean up ${slotCount} image${slotCount === 1 ? '' : 's'}` : 'Download the backup first'}</Button>}
          {running && <Button variant="outline" onClick={() => { stopRef.current = true; }}>Stop after this image</Button>}
          {done && <Button onClick={() => onOpenChange(false)}>Close</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
