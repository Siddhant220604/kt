import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api, formatINR } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Plus, Edit, Trash2, X, Image as ImageIcon, Search } from 'lucide-react';
import { toast } from 'sonner';

const empty = { name: '', category_id: '', description: '', short_description: '', size: '', unit: 'piece', price: 0, compare_price: 0, moq: 1, stock: 0, images: [''], specs: {}, featured: false, active: true, tags: [], price_tiers: [] };

const readFileAsDataURL = (file) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });

export default function AdminProducts() {
  const [data, setData] = useState({ items: [] });
  const [loading, setLoading] = useState(true);
  const [cats, setCats] = useState([]);
  const [edit, setEdit] = useState(null);
  const [q, setQ] = useState('');
  const [saving, setSaving] = useState(false);
  const [sp, setSp] = useSearchParams();

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

  const openNew = () => setEdit({ ...empty, category_id: cats[0]?.id || '' });
  const openEdit = (p) => setEdit({ ...empty, ...p, images: p.images && p.images.length ? p.images : [''], specs: p.specs || {}, tags: p.tags || [], price_tiers: p.price_tiers || [] });

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
      const payload = {
        ...edit,
        price: Number(edit.price),
        compare_price: Number(edit.compare_price || 0),
        moq: Number(edit.moq || 1),
        stock: Number(edit.stock || 0),
        price_tiers: (edit.price_tiers || [])
          .filter(t => t.min_qty && t.price)
          .map(t => ({ min_qty: Number(t.min_qty), price: Number(t.price) })),
      };
      if (edit.id) { await api.put(`/products/${edit.id}`, payload); toast.success('Product updated'); }
      else { await api.post('/products', payload); toast.success('Product created'); }
      setEdit(null); await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const del = async (p) => { if (!window.confirm(`Delete "${p.name}"?`)) return; await api.delete(`/products/${p.id}`); toast.success('Deleted'); load(); };

  const addTier = () => setEdit(e => ({ ...e, price_tiers: [...(e.price_tiers || []), { min_qty: '', price: '' }] }));
  const setTier = (i, field, v) => setEdit(e => ({ ...e, price_tiers: e.price_tiers.map((t, idx) => idx === i ? { ...t, [field]: v } : t) }));
  const rmTier = (i) => setEdit(e => ({ ...e, price_tiers: e.price_tiers.filter((_, idx) => idx !== i) }));

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
          <Button onClick={openNew} className="gap-1" data-testid="admin-new-product"><Plus className="h-4 w-4" />New Product</Button>
        </div>
      </div>
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr><th className="px-4 py-2.5">Product</th><th>Category</th><th>Price</th><th>Stock</th><th>MOQ</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {loading ? Array.from({ length: 5 }).map((_, i) => <tr key={i} className="border-t border-border"><td colSpan={7} className="px-4 py-3"><Skeleton className="h-6" /></td></tr>) :
                data.items.map(p => (
                  <tr key={p.id} className="border-t border-border hover:bg-muted/30">
                    <td className="px-4 py-2.5"><div className="flex items-center gap-2"><img src={(p.images && p.images[0]) || 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=100&q=80'} alt="" className="h-10 w-10 rounded object-cover" /><div className="font-medium text-sm line-clamp-1">{p.name}</div></div></td>
                    <td className="py-2.5 text-xs">{cats.find(c => c.id === p.category_id)?.name || '-'}</td>
                    <td className="py-2.5">{formatINR(p.price)}</td>
                    <td className="py-2.5">{p.stock}</td>
                    <td className="py-2.5">{p.moq}</td>
                    <td className="py-2.5">{p.active ? <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 border-emerald-500/20">Active</Badge> : <Badge variant="outline">Draft</Badge>}{p.featured && <Badge className="ml-1 bg-[hsl(var(--brand-marigold))] text-black">Featured</Badge>}</td>
                    <td className="py-2.5"><div className="flex gap-1"><Button size="icon" variant="ghost" onClick={() => openEdit(p)} data-testid={`edit-product-${p.id}`}><Edit className="h-4 w-4" /></Button><Button size="icon" variant="ghost" onClick={() => del(p)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button></div></td>
                  </tr>
                ))}
            </tbody>
          </table>
          {!loading && data.items.length === 0 && <div className="text-center py-8 text-sm text-muted-foreground">No products</div>}
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

              <div><Label className="text-xs text-muted-foreground">Description</Label><Textarea rows={3} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>
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
