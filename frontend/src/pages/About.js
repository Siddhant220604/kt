import React from 'react';
import { Award, ShieldCheck, Users, Truck, MapPin, Phone, Clock, Star } from 'lucide-react';
import { Container, Section, SectionTitle } from '../components/site/Section';
import Seo from '../components/site/Seo';
import { Badge } from '../components/ui/badge';
import { useSettings } from '../lib/settings';

// Qualitative points only — the copy elsewhere on this page already backs each one.
const HIGHLIGHTS = [
  { icon: Award, title: 'Honest Wholesale Pricing', note: 'Straight rates, no hidden markups.' },
  { icon: ShieldCheck, title: 'Quality You Can Trust', note: 'Stock we would use ourselves.' },
  { icon: Users, title: 'Built for Businesses', note: 'Caterers, halwais, shops and offices.' },
  { icon: Truck, title: 'Lucknow Delivery', note: 'Dependable dispatch across the city.' },
];

export default function About() {
  const { settings } = useSettings();
  const bannerImg = settings.about_hero_image;
  return (
    <div>
      <Seo title="About Us" description="Kiran Traders - Lucknow's trusted wholesale packaging partner since 1996. Thermocol plates, carry bags, disposables & more." />
      <div className={`relative overflow-hidden noise-overlay border-b border-border ${bannerImg ? '' : 'hero-radial'}`}>
        {bannerImg && (
          <>
            <img src={bannerImg} alt="" aria-hidden="true" className="absolute inset-0 w-full h-full object-cover" />
            {/* The shopfront photo is busy and light, so the copy needs its own scrim to stay legible. */}
            <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/70 to-black/45" />
          </>
        )}
        <Container className="relative z-10 py-14 md:py-20">
          <Badge className="bg-[hsl(var(--brand-marigold))] text-black mb-4">Since 1996</Badge>
          <h1 className={`text-4xl md:text-5xl font-display font-bold ${bannerImg ? 'text-white' : ''}`}>Kiran Traders — Lucknow's Trusted Wholesale Partner</h1>
          <p className={`text-lg mt-4 max-w-3xl ${bannerImg ? 'text-white/85' : 'text-muted-foreground'}`}>
            From a small wholesale shop on Nadan Mahal Road, we've grown by providing quality products, dependable service, and honest pricing to businesses across Uttar Pradesh.
          </p>
        </Container>
      </div>
      <Section>
        <Container>
          <div className="grid md:grid-cols-2 gap-10 items-center">
            <div className="flex flex-col justify-center">
              <h2 className="text-3xl font-display font-bold">Our Story</h2>
              <p className="mt-5 text-lg text-muted-foreground leading-relaxed">Founded in 1996, Kiran Traders started with a simple promise: supply quality disposable and packaging products at wholesale prices, on time, every time. Nearly three decades later, that promise still guides everything we do.</p>
              <p className="mt-4 text-lg text-muted-foreground leading-relaxed">Today we serve caterers, halwais, retail shopkeepers, event managers, corporate offices, and small businesses across Lucknow. Delivery available within Lucknow only.</p>
              <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2 bg-card border border-border rounded-xl p-6 text-center"><div className="text-4xl font-display font-bold text-[hsl(var(--brand-terracotta))]">25+</div><div className="text-sm text-muted-foreground mt-1">Years in Business</div></div>
                {HIGHLIGHTS.map(({ icon: Icon, title, note }) => (
                  <div key={title} className="bg-card border border-border rounded-xl p-5">
                    <Icon className="h-6 w-6 text-[hsl(var(--brand-terracotta))] mb-2.5" />
                    <div className="font-semibold leading-snug">{title}</div>
                    <div className="text-sm text-muted-foreground mt-1 leading-snug">{note}</div>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <img
                src={settings.about_image || 'https://images.unsplash.com/photo-1705846973668-0e9ed382ea8f?w=1200&q=80'}
                alt="About"
                className="w-full h-auto max-w-md mx-auto rounded-2xl border border-border shadow-lg"
              />
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
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3"><Phone className="h-5 w-5 text-[hsl(var(--brand-terracotta))]" /><div><div className="font-semibold">Phone</div><div className="text-sm text-muted-foreground">{settings.phone || '+91 9044057739'}</div></div></div>
            <div className="bg-card border border-border rounded-2xl p-5 flex items-start gap-3"><Clock className="h-5 w-5 text-[hsl(var(--brand-terracotta))]" /><div><div className="font-semibold">Hours</div><div className="text-sm text-muted-foreground">{settings.hours || 'Mon-Wed, Fri-Sun 10-8 | Thu Closed'}</div></div></div>
          </div>
        </Container>
      </Section>
    </div>
  );
}
