import React, { useCallback, useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const empty = { name: '', email: '', password: '', role: 'staff' };

export default function AdminUsers() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null); // null while hidden, '' for new, else the user's id
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    return api.get('/admin/users').then(r => setRows(r.data)).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const startCreate = () => { setEditingId(''); setForm(empty); };
  const startEdit = (u) => { setEditingId(u.id); setForm({ name: u.name, email: u.email, password: '', role: u.role }); };

  const save = async () => {
    if (!form.name || !form.email) return toast.error('Name and email are required');
    if (!editingId && form.password.length < 6) return toast.error('Password must be at least 6 characters');
    if (editingId && form.password && form.password.length < 6) return toast.error('New password must be at least 6 characters');
    setSaving(true);
    try {
      if (editingId) {
        const payload = { name: form.name, email: form.email, role: form.role };
        if (form.password) payload.password = form.password;
        await api.put(`/admin/users/${editingId}`, payload);
        toast.success('Account updated');
      } else {
        await api.post('/admin/users', form);
        toast.success('Account created');
      }
      setEditingId(null);
      await load();
    } catch (e) { toast.error(errorMessage(e, 'Save failed')); }
    finally { setSaving(false); }
  };

  const del = async (u) => {
    if (!window.confirm(`Remove ${u.email}'s access?`)) return;
    try {
      await api.delete(`/admin/users/${u.id}`);
      toast.success('Account removed');
      await load();
    } catch (e) { toast.error(errorMessage(e, 'Failed to remove account')); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold">Staff Accounts</h1>
          <p className="text-sm text-muted-foreground">Full admins have access to everything. Staff can only manage orders and customers.</p>
        </div>
        <Button onClick={startCreate} className="gap-1" data-testid="admin-new-user"><Plus className="h-4 w-4" />New Account</Button>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto max-h-[70vh] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40 sticky top-0 z-10"><tr><th className="px-4 py-2.5">Name</th><th>Email</th><th>Role</th><th></th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={4} className="text-center py-8 text-muted-foreground text-sm">Loading...</td></tr> :
                rows.map(u => (
                  <tr key={u.id} className="border-t border-border">
                    <td className="px-4 py-2.5 font-medium">{u.name}</td>
                    <td className="py-2.5">{u.email}</td>
                    <td className="py-2.5"><Badge variant="outline" className="capitalize">{u.role}</Badge>{u.is_root && <Badge variant="outline" className="ml-1 bg-amber-500/10 text-amber-700 border-amber-500/20">Protected</Badge>}</td>
                    <td className="py-2.5"><div className="flex gap-1">{u.role === 'staff' && <Button size="icon" variant="ghost" onClick={() => startEdit(u)} data-testid={`admin-user-edit-${u.id}`}><Edit className="h-4 w-4" /></Button>}{!u.is_root && <Button size="icon" variant="ghost" onClick={() => del(u)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>}</div></td>
                  </tr>
                ))}
              {!loading && rows.length === 0 && <tr><td colSpan={4} className="text-center py-8 text-muted-foreground text-sm">No accounts</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={editingId !== null} onOpenChange={(o) => !o && setEditingId(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{editingId ? 'Edit Account' : 'New Account'}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-xs text-muted-foreground">Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><Label className="text-xs text-muted-foreground">Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div>
              <Label className="text-xs text-muted-foreground">{editingId ? 'New Password (leave blank to keep current)' : 'Password'}</Label>
              <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
              {editingId && form.password && <p className="text-xs text-muted-foreground mt-1">This signs the account out everywhere else - they'll need to log in again with the new password.</p>}
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Role</Label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="staff">Staff (orders + customers only)</SelectItem>
                  <SelectItem value="admin">Admin (full access)</SelectItem>
                </SelectContent>
              </Select>
              {form.role === 'staff' && <Badge variant="outline" className="mt-2">Can view/update orders and customers only</Badge>}
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
            <Button onClick={save} disabled={saving} data-testid="admin-user-save">{saving ? 'Saving...' : editingId ? 'Save Changes' : 'Create Account'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
