import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { useSettings } from '../../lib/settings';

const readFileAsDataURL = (file) => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });

export default function AdminSettings() {
  const { settings: s, reload } = useSettings();
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  useEffect(() => { setForm(s || {}); }, [s]);

  const upd = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/settings', {
        business_name: form.business_name,
        tagline: form.tagline,
        address: form.address,
        phone: form.phone,
        whatsapp: form.whatsapp,
        email: form.email,
        hours: form.hours,
        gstin: form.gstin,
        cgst_rate: Number(form.cgst_rate || 0),
        sgst_rate: Number(form.sgst_rate || 0),
        shipping_flat: Number(form.shipping_flat || 0),
        free_shipping_above: Number(form.free_shipping_above || 0),
      });
      toast.success('Settings saved'); reload();
    } catch (e) { toast.error('Save failed'); }
    finally { setSaving(false); }
  };

  const uploadQR = async (file) => {
    if (!file) return;
    if (file.size > 512 * 1024) return toast.error('QR too large. Please use <512KB.');
    const b64 = await readFileAsDataURL(file);
    upd('upi_qr', b64);
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <div><h1 className="text-2xl font-display font-bold">Settings</h1><p className="text-sm text-muted-foreground">Business info & payment details</p></div>
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <div className="font-display font-semibold">Business</div>
        <div className="grid sm:grid-cols-2 gap-3">
          <div><Label>Business Name</Label><Input value={form.business_name || ''} onChange={(e) => upd('business_name', e.target.value)} /></div>
          <div><Label>Tagline</Label><Input value={form.tagline || ''} onChange={(e) => upd('tagline', e.target.value)} /></div>
          <div className="sm:col-span-2"><Label>Address</Label><Input value={form.address || ''} onChange={(e) => upd('address', e.target.value)} /></div>
          <div><Label>Phone</Label><Input value={form.phone || ''} onChange={(e) => upd('phone', e.target.value)} /></div>
          <div><Label>WhatsApp (with country code, no +)</Label><Input value={form.whatsapp || ''} onChange={(e) => upd('whatsapp', e.target.value)} /></div>
          <div><Label>Email</Label><Input value={form.email || ''} onChange={(e) => upd('email', e.target.value)} /></div>
          <div><Label>GSTIN</Label><Input value={form.gstin || ''} onChange={(e) => upd('gstin', e.target.value)} /></div>
          <div className="sm:col-span-2"><Label>Business Hours</Label><Input value={form.hours || ''} onChange={(e) => upd('hours', e.target.value)} /></div>
        </div>
      </div>
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <div className="font-display font-semibold">Shipping & Tax</div>
        <div className="grid sm:grid-cols-4 gap-3">
          <div><Label>CGST Rate (%)</Label><Input type="number" value={form.cgst_rate ?? ''} onChange={(e) => upd('cgst_rate', e.target.value)} /></div>
          <div><Label>SGST Rate (%)</Label><Input type="number" value={form.sgst_rate ?? ''} onChange={(e) => upd('sgst_rate', e.target.value)} /></div>
          <div><Label>Shipping (Flat)</Label><Input type="number" value={form.shipping_flat ?? ''} onChange={(e) => upd('shipping_flat', e.target.value)} /></div>
          <div><Label>Free shipping above</Label><Input type="number" value={form.free_shipping_above ?? ''} onChange={(e) => upd('free_shipping_above', e.target.value)} /></div>
        </div>
      </div>
      <div><Button onClick={save} disabled={saving} data-testid="admin-settings-save">{saving ? 'Saving...' : 'Save Settings'}</Button></div>
    </div>
  );
}
