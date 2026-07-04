import React from 'react';
import { Award, ShieldCheck, Users, Truck, MapPin, Phone, Clock, Star } from 'lucide-react';
import { Container, Section, SectionTitle } from '../components/site/Section';
import { Badge } from '../components/ui/badge';
import { useSettings } from '../lib/settings';

export default function About() {
  const { settings } = useSettings();
  return (
    <div>
      <div className="hero-radial noise-overlay border-b border-border">
        <Container className="relative z-10 py-14 md:py-20">
          <Badge className="bg-[hsl(var(--brand-marigold))] text-black mb-4">Since 2004</Badge>
          <h1 className="text-4xl md:text-5xl font-display font-bold">Kiran Traders — Lucknow's Trusted Wholesale Partner</h1>
          <p className="text-lg text-muted-foreground mt-4 max-w-3xl">
            From a small wholesale shop on Nadan Mahal Road, we've grown by providing quality products, dependable service, and honest pricing to businesses across Uttar Pradesh.
          </p>
        </Container>
      </div>
      <Section>
        <Container>
          <div className="grid md:grid-cols-2 gap-10 items-start">
            <div>
              <h2 className="text-2xl font-display font-bold">Our Story</h2>
              <p className="mt-4 text-muted-foreground">Founded in 2004, Kiran Traders started with a simple promise: supply quality disposable and packaging products at wholesale prices, on time, every time. Two decades later, that promise still guides everything we do.</p>
              <p className="mt-3 text-muted-foreground">Today we serve caterers, halwais, retail shopkeepers, event managers, corporate offices, and small businesses across Lucknow, Kanpur, Sitapur, Barabanki, and beyond.</p>
              <div className="mt-6 grid grid-cols-3 gap-4">
                <div className="bg-card border border-border rounded-xl p-4 text-center"><div className="text-3xl font-display font-bold text-[hsl(var(--brand-terracotta))]">20+</div><div className="text-xs text-muted-foreground">Years</div></div>
                <div className="bg-card border border-border rounded-xl p-4 text-center"><div className="text-3xl font-display font-bold text-[hsl(var(--brand-terracotta))]">10K+</div><div className="text-xs text-muted-foreground">Orders</div></div>
                <div className="bg-card border border-border rounded-xl p-4 text-center"><div className="text-3xl font-display font-bold text-[hsl(var(--brand-terracotta))]">5.0</div><div className="text-xs text-muted-foreground">Rating</div></div>
              </div>
            </div>
            <div>
              <div className="aspect-video rounded-2xl overflow-hidden border border-border">
                <img src="https://images.unsplash.com/photo-1705846973668-0e9ed382ea8f?w=1200&q=80" alt="About" className="w-full h-full object-cover" />
              </div>
            </div>
          </div>
        </Container>
      </Section>
      <Section className="bg-muted/30 border-y border-border">
        <Container>
          <SectionTitle title="Mission & Vision" center />
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-card border border-border rounded-2xl p-6">
              <Award className="h-8 w-8 text-[hsl(var(--brand-terracotta))] mb-3" />
              <h3 className="font-display font-bold text-xl">Our Mission</h3>
              <p className="mt-2 text-muted-foreground">To be the most reliable wholesale supplier of packaging & disposable essentials in Uttar Pradesh — combining honest pricing, quality products, and dependable service.</p>
            </div>
            <div className="bg-card border border-border rounded-2xl p-6">
              <Star className="h-8 w-8 text-[hsl(var(--brand-teal))] mb-3" />
              <h3 className="font-display font-bold text-xl">Our Vision</h3>
              <p className="mt-2 text-muted-foreground">To grow with our customers — helping small businesses succeed with high-quality packaging that supports their brand and reduces their costs.</p>
            </div>
          </div>
        </Container>
      </Section>
      <Section>
        <Container>
          <SectionTitle title="Visit Our Store" center />
          <div className="grid md:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3"><MapPin className="h-5 w-5 text-[hsl(var(--brand-terracotta))]" /><div><div className="font-semibold">Address</div><div className="text-sm text-muted-foreground">{settings.address || 'Sector K, 805-D, Aashiyana, Lucknow, UP 226012'}</div></div></div>
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3"><Phone className="h-5 w-5 text-[hsl(var(--brand-terracotta))]" /><div><div className="font-semibold">Phone</div><div className="text-sm text-muted-foreground">{settings.phone || '+91 98765 43210'}</div></div></div>
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3"><Clock className="h-5 w-5 text-[hsl(var(--brand-terracotta))]" /><div><div className="font-semibold">Hours</div><div className="text-sm text-muted-foreground">{settings.hours || 'Mon-Wed, Fri-Sun 10-8 | Thu Closed'}</div></div></div>
          </div>
        </Container>
      </Section>
    </div>
  );
}
