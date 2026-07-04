import React, { useState } from 'react';
import { Container, Section } from '../components/site/Section';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { MapPin, Phone, Mail, Clock, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { useSettings } from '../lib/settings';

export default function Contact() {
  const { settings } = useSettings();
  const [form, setForm] = useState({ name: '', email: '', mobile: '', subject: '', message: '' });
  const [sending, setSending] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      await api.post('/contact', form);
      toast.success('Message sent! We’ll get back to you shortly.');
      setForm({ name: '', email: '', mobile: '', subject: '', message: '' });
    } catch (e) { toast.error('Failed to send message'); }
    finally { setSending(false); }
  };

  return (
    <Section>
      <Container>
        <h1 className="text-3xl md:text-4xl font-display font-bold">Contact Us</h1>
        <p className="text-muted-foreground mt-1">We reply within business hours. For fastest response, WhatsApp us.</p>
        <div className="mt-8 grid lg:grid-cols-[1fr,380px] gap-6">
          <form onSubmit={submit} className="bg-card border border-border rounded-2xl p-6 space-y-3">
            <div className="grid sm:grid-cols-2 gap-3">
              <div><Label className="text-xs text-muted-foreground">Name *</Label><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="contact-name" /></div>
              <div><Label className="text-xs text-muted-foreground">Mobile *</Label><Input required value={form.mobile} onChange={(e) => setForm({ ...form, mobile: e.target.value.replace(/[^0-9]/g, '') })} maxLength={10} data-testid="contact-mobile" /></div>
            </div>
            <div><Label className="text-xs text-muted-foreground">Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
            <div><Label className="text-xs text-muted-foreground">Subject</Label><Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Bulk inquiry, custom order, etc." /></div>
            <div><Label className="text-xs text-muted-foreground">Message *</Label><Textarea required rows={5} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} data-testid="contact-message" /></div>
            <Button type="submit" disabled={sending} data-testid="contact-submit">{sending ? 'Sending...' : 'Send Message'}</Button>
          </form>
          <div className="space-y-3">
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3">
              <MapPin className="h-5 w-5 text-[hsl(var(--brand-terracotta))] mt-0.5" />
              <div><div className="font-semibold">Address</div><div className="text-sm text-muted-foreground">{settings.address}</div></div>
            </div>
            <a href={`tel:${settings.phone}`} className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3 hover:bg-muted/40 transition">
              <Phone className="h-5 w-5 text-[hsl(var(--brand-terracotta))] mt-0.5" />
              <div><div className="font-semibold">Call</div><div className="text-sm text-muted-foreground">{settings.phone}</div></div>
            </a>
            <a href={`https://wa.me/${settings.whatsapp}`} target="_blank" rel="noreferrer" className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3 hover:bg-muted/40 transition" data-testid="contact-whatsapp">
              <MessageCircle className="h-5 w-5 text-[hsl(var(--brand-teal))] mt-0.5" />
              <div><div className="font-semibold">WhatsApp</div><div className="text-sm text-muted-foreground">Fastest response</div></div>
            </a>
            <a href={`mailto:${settings.email}`} className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3 hover:bg-muted/40 transition">
              <Mail className="h-5 w-5 text-[hsl(var(--brand-terracotta))] mt-0.5" />
              <div><div className="font-semibold">Email</div><div className="text-sm text-muted-foreground">{settings.email}</div></div>
            </a>
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3">
              <Clock className="h-5 w-5 text-[hsl(var(--brand-terracotta))] mt-0.5" />
              <div><div className="font-semibold">Business Hours</div><div className="text-sm text-muted-foreground">{settings.hours}</div></div>
            </div>
          </div>
        </div>
        <div className="mt-8">
          <div className="font-display font-semibold mb-3">Find us on Google Maps</div>
          <div className="rounded-2xl overflow-hidden border border-border">
            <iframe title="Kiran Traders Map" src="https://www.google.com/maps?q=Aashiyana%2C+Lucknow%2C+Uttar+Pradesh&output=embed" className="w-full h-72 md:h-96" loading="lazy"></iframe>
          </div>
        </div>
      </Container>
    </Section>
  );
}
