import { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { Plus, PencilSimple, Trash } from "@phosphor-icons/react";
import { toast } from "sonner";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "../../components/ui/dialog";

export default function AdminCategories() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", slug: "", description: "" });

  const load = () => api.get("/categories").then((r) => setItems(r.data || []));
  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm({ name: "", slug: "", description: "" }); setOpen(true); };
  const openEdit = (c) => { setEditing(c); setForm({ name: c.name, slug: c.slug, description: c.description || "" }); setOpen(true); };

  const save = async () => {
    try {
      if (editing) await api.put(`/categories/${editing.id}`, form);
      else await api.post("/categories", form);
      toast.success("Saved");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const del = async (c) => {
    if (!window.confirm(`Delete ${c.name}?`)) return;
    await api.delete(`/categories/${c.id}`);
    toast.success("Deleted");
    load();
  };

  return (
    <div>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="label-caps mb-1">Taxonomy</div>
          <h1 className="text-3xl font-black tracking-tighter">Categories</h1>
        </div>
        <Button onClick={openNew} className="rounded-sm btn-lift" data-testid="admin-new-category-button">
          <Plus size={16} className="mr-2" /> New Category
        </Button>
      </div>

      <div className="border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="text-sm font-medium">{c.name}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{c.slug}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{c.description}</TableCell>
                <TableCell className="text-right space-x-2">
                  <Button size="sm" variant="outline" className="rounded-sm" onClick={() => openEdit(c)}><PencilSimple size={14} /></Button>
                  <Button size="sm" variant="outline" className="rounded-sm" onClick={() => del(c)}><Trash size={14} /></Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="rounded-sm">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit" : "New"} category</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="label-caps">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 rounded-sm" data-testid="cat-form-name" />
            </div>
            <div>
              <Label className="label-caps">Slug (optional)</Label>
              <Input value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} className="mt-2 rounded-sm font-mono" data-testid="cat-form-slug" />
            </div>
            <div>
              <Label className="label-caps">Description</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-2 rounded-sm" data-testid="cat-form-desc" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="rounded-sm" onClick={() => setOpen(false)}>Cancel</Button>
            <Button className="rounded-sm" onClick={save} data-testid="cat-form-save">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
