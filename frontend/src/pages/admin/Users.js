import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '../../components/ui/dialog';
import { Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const empty = { name: '', email: '', password: '', role: 'staff' };

export default function AdminUsers() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    return api.get('/admin/users').then(r => setRows(r.data)).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.name || !form.email || form.password.length < 6) return toast.error('Name, email, and a password of at least 6 characters are required');
    setSaving(true);
    try {
      await api.post('/admin/users', form);
      toast.success('Account created');
      setOpen(false);
      setForm(empty);
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create account'); }
    finally { setSaving(false); }
  };

  const changeRole = async (u, role) => {
    try {
      await api.put(`/admin/users/${u.id}`, { role });
      toast.success('Role updated');
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update role'); }
  };

  const del = async (u) => {
    if (!window.confirm(`Remove ${u.email}'s access?`)) return;
    try {
      await api.delete(`/admin/users/${u.id}`);
      toast.success('Account removed');
      await load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to remove account'); }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold">Staff Accounts</h1>
          <p className="text-sm text-muted-foreground">Full admins have access to everything. Staff can only manage orders and customers.</p>
        </div>
        <Button onClick={() => { setForm(empty); setOpen(true); }} className="gap-1" data-testid="admin-new-user"><Plus className="h-4 w-4" />New Account</Button>
      </div>

      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground uppercase bg-muted/40"><tr><th className="px-4 py-2.5">Name</th><th>Email</th><th>Role</th><th></th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={4} className="text-center py-8 text-muted-foreground text-sm">Loading...</td></tr> :
                rows.map(u => (
                  <tr key={u.id} className="border-t border-border">
                    <td className="px-4 py-2.5 font-medium">{u.name}</td>
                    <td className="py-2.5">{u.email}</td>
                    <td className="py-2.5">
                      <Select value={u.role} onValueChange={(v) => changeRole(u, v)}>
                        <SelectTrigger className="w-32" data-testid={`admin-user-role-${u.id}`}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="staff">Staff</SelectItem>
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="py-2.5"><Button size="icon" variant="ghost" onClick={() => del(u)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button></td>
                  </tr>
                ))}
              {!loading && rows.length === 0 && <tr><td colSpan={4} className="text-center py-8 text-muted-foreground text-sm">No accounts</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New Account</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-xs text-muted-foreground">Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><Label className="text-xs text-muted-foreground">Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><Label className="text-xs text-muted-foreground">Password</Label><Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
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
            <Button onClick={create} disabled={saving} data-testid="admin-user-save">{saving ? 'Creating...' : 'Create Account'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
