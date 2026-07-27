import React, { useEffect, useState } from 'react';
import { api, errorMessage } from '../../lib/api';
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
        shop_lat: Number(form.shop_lat || 0),
        shop_lng: Number(form.shop_lng || 0),
        hero_image_1: form.hero_image_1,
        hero_image_2: form.hero_image_2,
        hero_image_3: form.hero_image_3,
        hero_image_4: form.hero_image_4,
        about_image: form.about_image,
        about_hero_image: form.about_hero_image,
      });
      toast.success('Settings saved'); reload();
    } catch (e) { toast.error(errorMessage(e, 'Save failed')); }
    finally { setSaving(false); }
  };

  const uploadQR = async (file) => {
    if (!file) return;
    if (file.size > 512 * 1024) return toast.error('QR too large. Please use <512KB.');
    const b64 = await readFileAsDataURL(file);
    upd('upi_qr', b64);
  };

  const uploadImage = async (key, file) => {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) return toast.error('Image too large. Please use under 2MB.');
    const b64 = await readFileAsDataURL(file);
    upd(key, b64);
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
          <div><Label>Shipping (Flat fallback)</Label><Input type="number" value={form.shipping_flat ?? ''} onChange={(e) => upd('shipping_flat', e.target.value)} /></div>
          <div><Label>Free shipping above</Label><Input type="number" value={form.free_shipping_above ?? ''} onChange={(e) => upd('free_shipping_above', e.target.value)} /></div>
        </div>
      </div>
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <div className="font-display font-semibold">Shop Location (for distance-based delivery)</div>
        <p className="text-xs text-muted-foreground">Used to calculate delivery charges (₹20/km driving distance) and to enforce the Lucknow-only, 25km delivery radius. Get exact coordinates from Google Maps (right-click a location → the lat/lng shown at the top).</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <div><Label>Shop Latitude</Label><Input type="number" step="any" value={form.shop_lat ?? ''} onChange={(e) => upd('shop_lat', e.target.value)} /></div>
          <div><Label>Shop Longitude</Label><Input type="number" step="any" value={form.shop_lng ?? ''} onChange={(e) => upd('shop_lng', e.target.value)} /></div>
        </div>
      </div>
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <div className="font-display font-semibold">Homepage Images</div>
        <p className="text-xs text-muted-foreground">Shown in the hero image collage on the homepage. PNG/JPEG/WEBP, under 2MB each.</p>
        <div className="grid sm:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="space-y-2">
              <Label>Hero Image {n}</Label>
              <div className="aspect-square rounded-xl overflow-hidden border border-border bg-muted">
                {form[`hero_image_${n}`] ? (
                  <img src={form[`hero_image_${n}`]} alt={`Hero ${n}`} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">No image</div>
                )}
              </div>
              <Input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => uploadImage(`hero_image_${n}`, e.target.files[0])} />
            </div>
          ))}
        </div>
      </div>
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <div className="font-display font-semibold">About Page Images</div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Banner Background</Label>
            <p className="text-xs text-muted-foreground">Sits behind the heading at the top of the About page. A wide shot works best. PNG/JPEG/WEBP, under 2MB.</p>
            <div className="aspect-video rounded-xl overflow-hidden border border-border bg-muted">
              {form.about_hero_image ? (
                <img src={form.about_hero_image} alt="About banner" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">No image</div>
              )}
            </div>
            <Input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => uploadImage('about_hero_image', e.target.files[0])} />
          </div>
          <div className="space-y-2">
            <Label>Our Story Photo</Label>
            <p className="text-xs text-muted-foreground">Shown next to "Our Story" further down the page. PNG/JPEG/WEBP, under 2MB.</p>
            <div className="aspect-video rounded-xl overflow-hidden border border-border bg-muted">
              {form.about_image ? (
                <img src={form.about_image} alt="About" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-muted-foreground">No image</div>
              )}
            </div>
            <Input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => uploadImage('about_image', e.target.files[0])} />
          </div>
        </div>
      </div>
      <div><Button onClick={save} disabled={saving} data-testid="admin-settings-save">{saving ? 'Saving...' : 'Save Settings'}</Button></div>
    </div>
  );
}
