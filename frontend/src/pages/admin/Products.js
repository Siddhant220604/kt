import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, formatINR, downloadFile, errorMessage } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Plus, Edit, Trash2, X, Image as ImageIcon, Search, Download, Upload, FileSpreadsheet } from 'lucide-react';
import { toast } from 'sonner';

const empty = { name: '', category_id: '', description: '', short_description: '', size: '', unit: 'piece', price: 0, compare_price: 0, moq: 1, stock: 0, images: [''], specsList: [], featured: false, active: true, tags: [], price_tiers: [], sale_price: '', sale_starts_at: '', sale_ends_at: '', variant_group: '', variant_label: '' };

const readFileAsDataURL = (file) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });

export default function AdminProducts() {
  const [data, setData] = useState({ items: [] });
  const [loading, setLoading] = useState(true);
  const [cats, setCats] = useState([]);
  const [edit, setEdit] = useState(null);
  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [saving, setSaving] = useState(false);
  const [sp, setSp] = useSearchParams();
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    const params = { limit: 200 };
    if (q) params.search = q;
    const [{ data: pd }, { data: cd }] = await Promise.all([api.get('/products', { params }), api.get('/categories')]);
    setData(pd);
    setCats(cd);
    setLoading(false);
  }, [q]);
  useEffect(() => { load(); }, [load]);

  const visibleItems = data.items.filter(p => statusFilter === 'all' ? true : statusFilter === 'active' ? p.active : !p.active);

  const openNew = () => setEdit({ ...empty, category_id: cats[0]?.id || '' });
  const openEdit = (p) => setEdit({ ...empty, ...p, images: p.images && p.images.length ? p.images : [''], specsList: Object.entries(p.specs || {}).map(([key, value]) => ({ key, value })), tags: p.tags || [], price_tiers: p.price_tiers || [], sale_price: p.sale_price || '', sale_starts_at: p.sale_starts_at || '', sale_ends_at: p.sale_ends_at || '' });

  // Deep-link support (e.g. from the dashboard's low-stock list): /admin/products?edit=<id>
  // opens straight into that product's edit dialog instead of requiring a manual search + click.
  useEffect(() => {
    const editId = sp.get('edit');
    if (editId && data.items.length) {
      const p = data.items.find(i => i.id === editId);
      if (p) openEdit(p);
      const n = new URLSearchParams(sp); n.delete('edit'); setSp(n, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.items]);

  const save = async () => {
    if (!edit.name || !edit.category_id) return toast.error('Name and category are required');
    setSaving(true);
    try {
      // Whitelisted to exactly the fields the backend's ProductIn model accepts (extra='forbid') -
      // `edit` is seeded from the product list/detail response, which also carries read-only
      // fields like id/created_at/avg_rating/review_count (and, for categories, product_count).
      // Spreading `...edit` straight into the request body sent those along too, and the
      // resulting 422 validation error crashed the whole app when rendered (see errorMessage).
      const payload = {
        name: edit.name,
        slug: edit.slug || undefined,
        category_id: edit.category_id,
        description: edit.description,
        short_description: edit.short_description,
        size: edit.size,
        unit: edit.unit,
        price: Number(edit.price),
        compare_price: Number(edit.compare_price || 0),
        moq: Number(edit.moq || 1),
        stock: Number(edit.stock || 0),
        images: (edit.images || []).filter(Boolean),
        specs: Object.fromEntries((edit.specsList || []).filter(s => s.key.trim()).map(s => [s.key.trim(), s.value])),
        featured: edit.featured,
        active: edit.active,
        tags: edit.tags || [],
        price_tiers: (edit.price_tiers || [])
          .filter(t => t.min_qty && t.price)
          .map(t => ({ min_qty: Number(t.min_qty), price: Number(t.price) })),
        sale_price: edit.sale_price ? Number(edit.sale_price) : null,
        sale_starts_at: edit.sale_starts_at || null,
        sale_ends_at: edit.sale_ends_at || null,
        variant_group: edit.variant_group || '',
        variant_label: edit.variant_label || '',
      };
      if (edit.id) { await api.put(`/products/${edit.id}`, payload); toast.success('Product updated'); }
      else { await api.post('/products', payload); toast.success('Product created'); }
      setEdit(null); await load();
    } catch (e) { toast.error(errorMessage(e, 'Save failed')); }
    finally { setSaving(false); }
  };

  const del = async (p) => { if (!window.confirm(`Delete "${p.name}"?`)) return; await api.delete(`/products/${p.id}`); toast.success('Deleted'); load(); };

  const exportCsv = () => downloadFile('/products/export', {}, `products-${new Date().toISOString().slice(0, 10)}.csv`).catch(() => toast.error('Export failed'));
  const downloadTemplate = () => downloadFile('/products/import/template', {}, 'products-import-template.csv').catch(() => toast.error('Download failed'));

  const importCsv = async (file) => {
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setImporting(true);
    try {
      const { data } = await api.post('/products/import', form);
      setImportResult(data);
      if (data.created || data.updated) toast.success(`Imported: ${data.created} created, ${data.updated} updated`);
      if (data.errors?.length) toast.error(`${data.errors.length} row(s) had errors - see details`);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const addTier = () => setEdit(e => ({ ...e, price_tiers: [...(e.price_tiers || []), { min_qty: '', price: '' }] }));
  const setTier = (i, field, v) => setEdit(e => ({ ...e, price_tiers: e.price_tiers.map((t, idx) => idx === i ? { ...t, [field]: v } : t) }));
  const rmTier = (i) => setEdit(e => ({ ...e, price_tiers: e.price_tiers.filter((_, idx) => idx !== i) }));

  const addSpec = () => setEdit(e => ({ ...e, specsList: [...(e.specsList || []), { key: '', value: '' }] }));
  const setSpec = (i, field, v) => setEdit(e => ({ ...e, specsList: e.specsList.map((s, idx) => idx === i ? { ...s, [field]: v } : s) }));
  const rmSpec = (i) => setEdit(e => ({ ...e, specsList: e.specsList.filter((_, idx) => idx !== i) }));

  const addImage = () => setEdit(e => ({ ...e, images: [...(e.images || []), ''] }));
  const setImage = (i, v) => setEdit(e => ({ ...e, images: e.images.map((x, idx) => idx === i ? v : x) }));
  const rmImage = (i) => setEdit(e => ({ ...e, images: e.images.filter((_, idx) => idx !== i) }));
  const uploadImage = async (i, file) => {
    if (!file) return;
    if (file.size > 1024 * 1024) return toast.error('Image too large. Please use <1MB.');
    const b64 = await readFileAsDataURL(file);
    setImage(i, b64);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold">Products</h1>
          <p className="text-sm text-muted-foreground">Manage your catalog</p>
        </div>
        <div className="flex items-center gap-2">
          <form onSubmit={(e) => { e.preventDefault(); load(); }} className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products" className="pl-9 w-60" />
          </form>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-36" data-testid="admin-product-status-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Draft</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={downloadTemplate} className="gap-1" title="Download a blank CSV to fill in"><FileSpreadsheet className="h-4 w-4" />Template</Button>
          <Button variant="outline" onClick={exportCsv} className="gap-1" data-testid="admin-export-products"><Download className="h-4 w-4" />Export CSV</Button>
          <label className="cursor-pointer">
            <input type="file" accept=".csv" className="hidden" onChange={(e) => { importCsv(e.target.files[0]); e.target.value = ''; }} data-testid="admin-import-products-input" />
            <Button asChild variant="outline" className="gap-1" disabled={importing}><span><Upload className="h-4 w-4" />{importing ? 'Importing...' : 'Import CSV'}</span></Button>
          </label>
          <Button onClick={openNew} className="gap-1" data-testid="admin-new-product"><Plus className="h-4 w-4" />New Product</Button>
        </div>
      </div>

      {importResult && (
        <div className="bg-card border border-border rounded-2xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <div className="font-display font-semibold text-sm">Import Result: {importResult.created} created, {importResult.updated} updated{importResult.errors?.length ? `, ${importResult.errors.length} error(s)` : ''}</div>
            <Button size="sm" variant="ghost" onClick={() => setImportResult(null)}><X className="h-4 w-4" /></Button>
          </div>
          {importResult.errors?.length > 0 && (
            <div className="space-y-1 max-h-40 overflow-auto text-xs text-destructive">
              {importResult.errors.map((e, i) => <div key={i}>Row {e.row}: {e.message}</div>)}
            </div>
          )}
        </div>
      )}
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr><th className="px-4 py-2.5">Product</th><th>Category</th><th>Price</th><th>Stock</th><th>MOQ</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {loading ? Array.from({ length: 5 }).map((_, i) => <tr key={i} className="border-t border-border"><td colSpan={7} className="px-4 py-3"><Skeleton className="h-6" /></td></tr>) :
                visibleItems.map(p => (
                  <tr key={p.id} className="border-t border-border hover:bg-muted/30">
                    <td className="px-4 py-2.5"><div className="flex items-center gap-2"><img src={(p.images && p.images[0]) || 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=100&q=80'} alt="" className="h-10 w-10 rounded object-cover" /><div className="font-medium text-sm line-clamp-1">{p.name}</div></div></td>
                    <td className="py-2.5 text-xs">{cats.find(c => c.id === p.category_id)?.name || '-'}</td>
                    <td className="py-2.5">{formatINR(p.price)}</td>
                    <td className="py-2.5">{p.stock}</td>
                    <td className="py-2.5">{p.moq}</td>
                    <td className="py-2.5">{p.active ? <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 border-emerald-500/20">Active</Badge> : <Badge variant="outline">Draft</Badge>}{p.featured && <Badge className="ml-1 bg-[hsl(var(--brand-marigold))] text-black">Featured</Badge>}{p.sale_price && <Badge variant="outline" className="ml-1 bg-red-500/10 text-red-700 border-red-500/20">Flash sale set</Badge>}</td>
                    <td className="py-2.5"><div className="flex gap-1"><Button size="icon" variant="ghost" onClick={() => openEdit(p)} data-testid={`edit-product-${p.id}`}><Edit className="h-4 w-4" /></Button><Button size="icon" variant="ghost" onClick={() => del(p)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button></div></td>
                  </tr>
                ))}
            </tbody>
          </table>
          {!loading && visibleItems.length === 0 && <div className="text-center py-8 text-sm text-muted-foreground">No products</div>}
        </div>
      </div>

      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-3xl max-h-[92vh] overflow-auto">
          <DialogHeader><DialogTitle>{edit?.id ? 'Edit Product' : 'New Product'}</DialogTitle></DialogHeader>
          {edit && (
            <div className="space-y-3">
              <div className="grid sm:grid-cols-2 gap-3">
                <div><Label className="text-xs text-muted-foreground">Name *</Label><Input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} data-testid="admin-product-name" /></div>
                <div><Label className="text-xs text-muted-foreground">Category *</Label>
                  <Select value={edit.category_id} onValueChange={(v) => setEdit({ ...edit, category_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Choose category" /></SelectTrigger>
                    <SelectContent>{cats.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs text-muted-foreground">Size</Label><Input value={edit.size} onChange={(e) => setEdit({ ...edit, size: e.target.value })} placeholder="12 inch, 250ml" /></div>
                <div><Label className="text-xs text-muted-foreground">Unit</Label><Input value={edit.unit} onChange={(e) => setEdit({ ...edit, unit: e.target.value })} placeholder="pack, piece, kg" /></div>
                <div><Label className="text-xs text-muted-foreground">Price *</Label><Input type="number" value={edit.price} onChange={(e) => setEdit({ ...edit, price: e.target.value })} data-testid="admin-product-price" /></div>
                <div><Label className="text-xs text-muted-foreground">Compare Price</Label><Input type="number" value={edit.compare_price} onChange={(e) => setEdit({ ...edit, compare_price: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">MOQ</Label><Input type="number" value={edit.moq} onChange={(e) => setEdit({ ...edit, moq: e.target.value })} /></div>
                <div><Label className="text-xs text-muted-foreground">Stock</Label><Input type="number" value={edit.stock} onChange={(e) => setEdit({ ...edit, stock: e.target.value })} data-testid="admin-product-stock" /></div>
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-muted-foreground">Bulk Pricing Tiers (optional)</Label>
                  <Button type="button" size="sm" variant="outline" onClick={addTier} data-testid="admin-add-tier"><Plus className="h-3.5 w-3.5 mr-1" />Add tier</Button>
                </div>
                {(edit.price_tiers || []).length === 0 && <div className="text-xs text-muted-foreground mt-1">No tiers - base price applies to all quantities.</div>}
                {(edit.price_tiers || []).map((t, i) => (
                  <div key={i} className="flex items-center gap-2 mt-2">
                    <Input type="number" placeholder="Min qty" value={t.min_qty} onChange={(e) => setTier(i, 'min_qty', e.target.value)} data-testid={`admin-tier-minqty-${i}`} />
                    <span className="text-xs text-muted-foreground shrink-0">units @ Rs.</span>
                    <Input type="number" placeholder="Price" value={t.price} onChange={(e) => setTier(i, 'price', e.target.value)} data-testid={`admin-tier-price-${i}`} />
                    <Button type="button" size="icon" variant="ghost" onClick={() => rmTier(i)} className="text-destructive shrink-0"><X className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>

              <div>
                <Label className="text-xs text-muted-foreground">Size Variants (optional)</Label>
                <p className="text-xs text-muted-foreground mb-2">To show a size selector on the product page (like "6mm / 8mm"), give this product and its other sizes the same Variant Group. Each one keeps its own price, stock and images.</p>
                <div className="grid sm:grid-cols-2 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Variant Group</Label><Input value={edit.variant_group} onChange={(e) => setEdit({ ...edit, variant_group: e.target.value })} placeholder="e.g. eco-straws" /></div>
                  <div><Label className="text-xs text-muted-foreground">This Product's Size Label</Label><Input value={edit.variant_label} onChange={(e) => setEdit({ ...edit, variant_label: e.target.value })} placeholder="e.g. 6 mm" /></div>
                </div>
              </div>

              <div>
                <Label className="text-xs text-muted-foreground">Flash Sale (optional)</Label>
                <p className="text-xs text-muted-foreground mb-2">While the window below is active, shoppers see this price instead of the regular price - no manual toggling, it switches on/off exactly on schedule.</p>
                <div className="grid sm:grid-cols-3 gap-3">
                  <div><Label className="text-xs text-muted-foreground">Sale Price</Label><Input type="number" value={edit.sale_price} onChange={(e) => setEdit({ ...edit, sale_price: e.target.value })} placeholder="e.g. 79" data-testid="admin-product-sale-price" /></div>
                  <div><Label className="text-xs text-muted-foreground">Starts At</Label><Input type="datetime-local" value={edit.sale_starts_at} onChange={(e) => setEdit({ ...edit, sale_starts_at: e.target.value })} /></div>
                  <div><Label className="text-xs text-muted-foreground">Ends At</Label><Input type="datetime-local" value={edit.sale_ends_at} onChange={(e) => setEdit({ ...edit, sale_ends_at: e.target.value })} /></div>
                </div>
              </div>

              <div><Label className="text-xs text-muted-foreground">Description</Label><Textarea rows={3} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>

              <div>
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-muted-foreground">Specifications (optional)</Label>
                  <Button type="button" size="sm" variant="outline" onClick={addSpec} data-testid="admin-add-spec"><Plus className="h-3.5 w-3.5 mr-1" />Add spec</Button>
                </div>
                {(edit.specsList || []).length === 0 && <div className="text-xs text-muted-foreground mt-1">No specifications - the "Specifications" section won't show on the product page.</div>}
                {(edit.specsList || []).map((s, i) => (
                  <div key={i} className="flex items-center gap-2 mt-2">
                    <Input placeholder="Label (e.g. Size)" value={s.key} onChange={(e) => setSpec(i, 'key', e.target.value)} data-testid={`admin-spec-key-${i}`} />
                    <Input placeholder="Value (e.g. 20 inch)" value={s.value} onChange={(e) => setSpec(i, 'value', e.target.value)} data-testid={`admin-spec-value-${i}`} />
                    <Button type="button" size="icon" variant="ghost" onClick={() => rmSpec(i)} className="text-destructive shrink-0"><X className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>

              <div>
                <Label className="text-xs text-muted-foreground">Images (URLs or upload)</Label>
                <div className="space-y-2 mt-1">
                  {edit.images.map((im, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      {im ? <img src={im} className="h-12 w-12 rounded object-cover border border-border" alt="" /> : <div className="h-12 w-12 rounded bg-muted grid place-items-center"><ImageIcon className="h-4 w-4 text-muted-foreground" /></div>}
                      <Input value={im} onChange={(e) => setImage(i, e.target.value)} placeholder="https://..." />
                      <label className="cursor-pointer"><input type="file" accept="image/*" className="hidden" onChange={(e) => uploadImage(i, e.target.files[0])} /><Button asChild variant="outline" size="sm"><span>Upload</span></Button></label>
                      <Button variant="ghost" size="icon" onClick={() => rmImage(i)} className="text-destructive"><X className="h-4 w-4" /></Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={addImage} className="gap-1"><Plus className="h-3 w-3" />Add image</Button>
                </div>
              </div>
              <div className="grid sm:grid-cols-2 gap-3">
                <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={edit.featured} onChange={(e) => setEdit({ ...edit, featured: e.target.checked })} />Featured</label>
                <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} />Active</label>
              </div>
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
            <Button onClick={save} disabled={saving} data-testid="admin-product-save">{saving ? 'Saving...' : 'Save Product'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
