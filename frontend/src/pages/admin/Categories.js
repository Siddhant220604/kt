import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const empty = { name: '', description: '', icon: 'Package', image: '', order: 0 };

export default function AdminCategories() {
  const [cats, setCats] = useState([]);
  const [edit, setEdit] = useState(null);

  const load = () => api.get('/categories').then(r => setCats(r.data));
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!edit.name) return toast.error('Name required');
    try {
      // Whitelisted to what CategoryIn accepts (extra='forbid') - the category list response
      // also carries read-only fields (id, created_at, product_count) that aren't part of the
      // model, and sending them along caused every edit (never a new category) to fail.
      const payload = { name: edit.name, slug: edit.slug || undefined, description: edit.description, icon: edit.icon, image: edit.image, order: Number(edit.order || 0) };
      if (edit.id) await api.put(`/categories/${edit.id}`, payload); else await api.post('/categories', payload);
      toast.success('Saved'); setEdit(null); load();
    } catch (e) { toast.error(errorMessage(e, 'Failed')); }
  };

  const del = async (c) => {
    if (!window.confirm(`Delete "${c.name}"?`)) return;
    try { await api.delete(`/categories/${c.id}`); toast.success('Deleted'); load(); }
    catch (e) { toast.error(errorMessage(e, 'Failed to delete category')); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Categories</h1>
          <p className="text-sm text-muted-foreground">{cats.length} categories</p>
        </div>
        <Button onClick={() => setEdit(empty)} className="gap-1" data-testid="admin-new-category"><Plus className="h-4 w-4" />New</Button>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {cats.map(c => (
          <div key={c.id} className="bg-card border border-border rounded-2xl p-4 flex items-start gap-3">
            <div className="h-12 w-12 rounded-xl bg-primary/10 grid place-items-center text-lg">{c.name?.[0]}</div>
            <div className="flex-1 min-w-0">
              <div className="font-medium">{c.name}</div>
              <div className="text-xs text-muted-foreground line-clamp-2">{c.description}</div>
              <div className="text-[10px] text-muted-foreground mt-1">{c.product_count || 0} products</div>
            </div>
            <div className="flex gap-1">
              <Button size="icon" variant="ghost" onClick={() => setEdit(c)}><Edit className="h-4 w-4" /></Button>
              <Button size="icon" variant="ghost" onClick={() => del(c)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{edit?.id ? 'Edit Category' : 'New Category'}</DialogTitle></DialogHeader>
          {edit && (
            <div className="space-y-3">
              <div><Label className="text-xs text-muted-foreground">Name *</Label><Input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} data-testid="admin-cat-name" /></div>
              <div><Label className="text-xs text-muted-foreground">Description</Label><Textarea rows={2} value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>
              <div><Label className="text-xs text-muted-foreground">Order (sort)</Label><Input type="number" value={edit.order} onChange={(e) => setEdit({ ...edit, order: Number(e.target.value) })} /></div>
            </div>
          )}
          <DialogFooter><DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose><Button onClick={save} data-testid="admin-cat-save">Save</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
