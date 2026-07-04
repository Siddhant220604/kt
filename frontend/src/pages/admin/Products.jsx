import { useEffect, useState } from "react";
import { api, formatApiError } from "../../lib/api";
import { money } from "../../lib/product";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../../components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../components/ui/table";
import { Badge } from "../../components/ui/badge";
import { Plus, PencilSimple, Trash, UploadSimple } from "@phosphor-icons/react";
import { toast } from "sonner";

const EMPTY = {
  name: "", description: "", category_id: "", sku: "", unit: "carton",
  base_price: 0, moq: 1, stock: 0,
  price_tiers: [{ min_qty: 1, price: 0 }],
  images: [], is_active: true,
};

export default function AdminProducts() {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);

  const load = async () => {
    const [p, c] = await Promise.all([
      api.get("/products?limit=500"),
      api.get("/categories"),
    ]);
    setItems(p.data.items || []);
    setCategories(c.data || []);
  };

  useEffect(() => { load(); }, []);

  const openNew = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (p) => {
    setEditing(p);
    setForm({ ...p, price_tiers: p.price_tiers?.length ? p.price_tiers : [{ min_qty: 1, price: p.base_price }] });
    setOpen(true);
  };

  const save = async () => {
    try {
      const payload = {
        ...form,
        base_price: Number(form.base_price),
        moq: Number(form.moq),
        stock: Number(form.stock),
        price_tiers: form.price_tiers.map((t) => ({ min_qty: Number(t.min_qty), price: Number(t.price) })),
      };
      if (editing) await api.put(`/products/${editing.id}`, payload);
      else await api.post("/products", payload);
      toast.success("Product saved");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const del = async (p) => {
    if (!window.confirm(`Delete ${p.name}?`)) return;
    await api.delete(`/products/${p.id}`);
    toast.success("Deleted");
    load();
  };

  const uploadImage = async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/uploads", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setForm((f) => ({ ...f, images: [...(f.images || []), data.storage_path] }));
      toast.success("Image uploaded");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || "Upload failed");
    }
  };

  const setTier = (idx, key, val) => {
    setForm((f) => {
      const tiers = [...f.price_tiers];
      tiers[idx] = { ...tiers[idx], [key]: val };
      return { ...f, price_tiers: tiers };
    });
  };
  const addTier = () => setForm((f) => ({ ...f, price_tiers: [...f.price_tiers, { min_qty: 1, price: 0 }] }));
  const removeTier = (idx) => setForm((f) => ({ ...f, price_tiers: f.price_tiers.filter((_, i) => i !== idx) }));

  return (
    <div>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="label-caps mb-1">Catalog</div>
          <h1 className="text-3xl font-black tracking-tighter">Products</h1>
        </div>
        <Button onClick={openNew} className="rounded-sm btn-lift" data-testid="admin-new-product-button">
          <Plus size={16} className="mr-2" /> New Product
        </Button>
      </div>

      <div className="border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Base Price</TableHead>
              <TableHead>MOQ</TableHead>
              <TableHead>Stock</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-mono text-xs">{p.sku}</TableCell>
                <TableCell className="text-sm">{p.name}</TableCell>
                <TableCell className="text-sm">{categories.find((c) => c.id === p.category_id)?.name || "—"}</TableCell>
                <TableCell className="font-mono">{money(p.base_price)}</TableCell>
                <TableCell className="font-mono">{p.moq}</TableCell>
                <TableCell className="font-mono">{p.stock}</TableCell>
                <TableCell>
                  <Badge variant={p.is_active ? "default" : "outline"} className="rounded-sm">
                    {p.is_active ? "active" : "inactive"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right space-x-2">
                  <Button size="sm" variant="outline" className="rounded-sm" onClick={() => openEdit(p)} data-testid={`admin-edit-${p.sku}`}>
                    <PencilSimple size={14} />
                  </Button>
                  <Button size="sm" variant="outline" className="rounded-sm" onClick={() => del(p)} data-testid={`admin-delete-${p.sku}`}>
                    <Trash size={14} />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto rounded-sm">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit product" : "New product"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label className="label-caps">Name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-2 rounded-sm" data-testid="prod-form-name" />
            </div>
            <div>
              <Label className="label-caps">SKU</Label>
              <Input value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} className="mt-2 rounded-sm font-mono" data-testid="prod-form-sku" />
            </div>
            <div>
              <Label className="label-caps">Category</Label>
              <Select value={form.category_id} onValueChange={(v) => setForm({ ...form, category_id: v })}>
                <SelectTrigger className="mt-2 rounded-sm" data-testid="prod-form-category">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="label-caps">Unit</Label>
              <Input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} className="mt-2 rounded-sm" data-testid="prod-form-unit" />
            </div>
            <div>
              <Label className="label-caps">Base Price</Label>
              <Input type="number" step="0.01" value={form.base_price} onChange={(e) => setForm({ ...form, base_price: e.target.value })} className="mt-2 rounded-sm font-mono" data-testid="prod-form-price" />
            </div>
            <div>
              <Label className="label-caps">MOQ</Label>
              <Input type="number" value={form.moq} onChange={(e) => setForm({ ...form, moq: e.target.value })} className="mt-2 rounded-sm font-mono" data-testid="prod-form-moq" />
            </div>
            <div>
              <Label className="label-caps">Stock</Label>
              <Input type="number" value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} className="mt-2 rounded-sm font-mono" data-testid="prod-form-stock" />
            </div>
            <div className="md:col-span-2">
              <Label className="label-caps">Description</Label>
              <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-2 rounded-sm" data-testid="prod-form-desc" />
            </div>

            <div className="md:col-span-2">
              <div className="flex items-center justify-between">
                <Label className="label-caps">Price Tiers</Label>
                <Button size="sm" variant="outline" className="rounded-sm" onClick={addTier} type="button">
                  <Plus size={12} className="mr-1" /> Add tier
                </Button>
              </div>
              <div className="mt-2 space-y-2">
                {form.price_tiers.map((t, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex-1">
                      <Input type="number" placeholder="Min qty" value={t.min_qty} onChange={(e) => setTier(i, "min_qty", e.target.value)} className="rounded-sm font-mono" />
                    </div>
                    <div className="flex-1">
                      <Input type="number" step="0.01" placeholder="Price" value={t.price} onChange={(e) => setTier(i, "price", e.target.value)} className="rounded-sm font-mono" />
                    </div>
                    <Button size="sm" variant="outline" className="rounded-sm" onClick={() => removeTier(i)} type="button">
                      <Trash size={12} />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            <div className="md:col-span-2">
              <Label className="label-caps">Images</Label>
              <div className="mt-2 flex flex-wrap gap-2">
                {form.images.map((im, i) => (
                  <div key={i} className="relative group">
                    <img
                      src={im.startsWith("http") ? im : `${process.env.REACT_APP_BACKEND_URL}/api/files/${im}`}
                      alt=""
                      className="h-20 w-20 object-cover border border-border"
                    />
                    <button
                      onClick={() => setForm({ ...form, images: form.images.filter((_, x) => x !== i) })}
                      type="button"
                      className="absolute -top-1 -right-1 bg-destructive text-destructive-foreground p-0.5 rounded-full opacity-0 group-hover:opacity-100"
                    >
                      <Trash size={10} />
                    </button>
                  </div>
                ))}
                <label className="flex h-20 w-20 cursor-pointer items-center justify-center border border-dashed border-border text-muted-foreground hover:border-primary hover:text-primary" data-testid="prod-form-upload">
                  <UploadSimple size={16} />
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && uploadImage(e.target.files[0])}
                  />
                </label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" className="rounded-sm" onClick={() => setOpen(false)}>Cancel</Button>
            <Button className="rounded-sm" onClick={save} data-testid="prod-form-save">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
