import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const empty = { title: '', subtitle: '', image: '', link: '/products', cta_text: 'Shop Now', active: true, order: 0 };

export default function AdminBanners() {
  const [rows, setRows] = useState([]);
  const [edit, setEdit] = useState(null);
  const load = () => api.get('/banners/all').then(r => setRows(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    try {
      // Whitelisted to what BannerIn accepts (extra='forbid') - the banner list response also
      // carries read-only fields (id, created_at) that aren't part of the model, and sending
      // them along caused every edit (never a new banner) to fail.
      const payload = { title: edit.title, subtitle: edit.subtitle, image: edit.image, link: edit.link, cta_text: edit.cta_text, active: edit.active, order: Number(edit.order || 0) };
      if (edit.id) await api.put(`/banners/${edit.id}`, payload); else await api.post('/banners', payload);
      toast.success('Saved'); setEdit(null); load();
    } catch (e) { toast.error(errorMessage(e, 'Failed')); }
  };
  const del = async (b) => { if (!window.confirm('Delete banner?')) return; await api.delete(`/banners/${b.id}`); load(); };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-display font-bold">Banners</h1><p className="text-sm text-muted-foreground">{rows.length} banners</p></div>
        <Button onClick={() => setEdit(empty)} className="gap-1"><Plus className="h-4 w-4" />New Banner</Button>
      </div>
      <div className="grid gap-3">
        {rows.map(b => (
          <div key={b.id} className="bg-card border border-border rounded-2xl overflow-hidden flex flex-col md:flex-row">
            {b.image && <img src={b.image} alt="" className="h-40 md:h-auto md:w-64 object-cover" />}
            <div className="p-4 flex-1">
              <div className="font-display font-semibold">{b.title}</div>
              <div className="text-sm text-muted-foreground">{b.subtitle}</div>
              <div className="text-xs text-muted-foreground mt-1">Link: {b.link} • Order: {b.order} • {b.active ? 'Active' : 'Inactive'}</div>
            </div>
            <div className="p-4 flex md:flex-col gap-2">
              <Button size="sm" variant="outline" onClick={() => setEdit(b)}><Edit className="h-4 w-4" /></Button>
              <Button size="sm" variant="outline" onClick={() => del(b)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{edit?.id ? 'Edit Banner' : 'New Banner'}</DialogTitle></DialogHeader>
          {edit && (
            <div className="space-y-3">
              <div><Label>Title</Label><Input value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></div>
              <div><Label>Subtitle</Label><Textarea rows={2} value={edit.subtitle} onChange={(e) => setEdit({ ...edit, subtitle: e.target.value })} /></div>
              <div><Label>Image URL</Label><Input value={edit.image} onChange={(e) => setEdit({ ...edit, image: e.target.value })} placeholder="https://..." /></div>
              <div><Label>Link</Label><Input value={edit.link} onChange={(e) => setEdit({ ...edit, link: e.target.value })} /></div>
              <div><Label>CTA Text</Label><Input value={edit.cta_text} onChange={(e) => setEdit({ ...edit, cta_text: e.target.value })} /></div>
              <div><Label>Order</Label><Input type="number" value={edit.order} onChange={(e) => setEdit({ ...edit, order: Number(e.target.value) })} /></div>
              <label className="flex items-center gap-2"><input type="checkbox" checked={edit.active} onChange={(e) => setEdit({ ...edit, active: e.target.checked })} />Active</label>
            </div>
          )}
          <DialogFooter><DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose><Button onClick={save}>Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
