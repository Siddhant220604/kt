import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Truck, ShieldCheck, MessageCircle, Star, ArrowRight, Package, Award, Phone, Sparkles } from 'lucide-react';
import { api } from '../lib/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import ProductCard from '../components/ProductCard';
import { Container, Section, SectionTitle } from '../components/site/Section';
import Seo from '../components/site/Seo';
import { useSettings } from '../lib/settings';

const iconFor = (name) => ({
  'Thermocol Plates': '🍽️', 'Thermocol Bowls': '🍲', 'Carry Bags': '🛍️', 'Plastic Bags': '📦', 'Disposable Glasses': '🥂', 'Packaging Materials': '📦', 'Luggage Bags': '🧳',
}[name] || '📦');

const categoryImages = {
  'Thermocol Plates': 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=600&q=80',
  'Thermocol Bowls': 'https://images.unsplash.com/photo-1584743579083-b331c4adbb15?w=600&q=80',
  'Carry Bags': 'https://images.unsplash.com/photo-1573106456020-5ce9db6d3679?w=600&q=80',
  'Plastic Bags': 'https://images.unsplash.com/photo-1618477388954-7852f32655ec?w=600&q=80',
  'Disposable Glasses': 'https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=600&q=80',
  'Packaging Materials': 'https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=600&q=80',
  'Luggage Bags': 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600&q=80',
};

export default function Home() {
  const { settings } = useSettings();
  const [cats, setCats] = useState([]);
  const [featured, setFeatured] = useState([]);
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, p, b] = await Promise.all([
          api.get('/categories'),
          api.get('/products', { params: { featured: true, limit: 8 } }),
          api.get('/banners'),
        ]);
        setCats(c.data);
        setFeatured(p.data.items || []);
        setBanners(b.data || []);
      } finally { setLoading(false); }
    })();
  }, []);

  const hero = banners[0];
  const wa = `https://wa.me/${settings.whatsapp || '919876543210'}?text=${encodeURIComponent('Hi Kiran Traders, I would like to enquire about wholesale packaging products.')}`;

  return (
    <div>
      <Seo />
      {/* HERO */}
      <section className="hero-radial noise-overlay relative overflow-hidden border-b border-border">
        <Container className="relative z-10 py-14 md:py-20 grid lg:grid-cols-2 gap-10 items-center">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <div className="flex items-center gap-2 mb-4">
              <Badge className="bg-[hsl(var(--brand-marigold))] text-black font-semibold">Since 1996</Badge>
              <Badge variant="outline" className="gap-1"><ShieldCheck className="h-3.5 w-3.5" />GST Invoice</Badge>
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-display font-bold leading-[1.05] tracking-tight text-foreground">
              Wholesale Prices,<br />
              <span className="text-[hsl(var(--brand-terracotta))]">Retail Convenience.</span>
            </h1>
            <p className="mt-4 text-base sm:text-lg text-muted-foreground max-w-xl">
              {hero?.subtitle || 'Thermocol plates, carry bags, disposable glasses, packaging materials and more — delivered across Lucknow.'}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/products"><Button size="lg" className="gap-2" data-testid="hero-browse-products">Browse Products <ArrowRight className="h-4 w-4" /></Button></Link>
              <a href={wa} target="_blank" rel="noreferrer" data-testid="hero-whatsapp-inquiry">
                <Button size="lg" variant="outline" className="gap-2 bg-[hsl(var(--brand-teal))] text-white border-[hsl(var(--brand-teal))] hover:bg-[hsl(var(--brand-teal))]/90 hover:text-white">
                  <MessageCircle className="h-4 w-4" /> WhatsApp Bulk Inquiry
                </Button>
              </a>
            </div>
            <div className="mt-8 flex flex-wrap gap-6 text-sm text-muted-foreground">
              <div className="flex items-center gap-2"><Award className="h-4 w-4 text-[hsl(var(--brand-terracotta))]" />25+ Years of Trust</div>
              <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-[hsl(var(--brand-terracotta))]" />GST Invoice Available</div>
              <div className="flex items-center gap-2"><Package className="h-4 w-4 text-[hsl(var(--brand-terracotta))]" />Wholesale & Retail</div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.1 }}
            className="relative grid grid-cols-2 gap-3">
            <div className="space-y-3">
              <div className="aspect-square rounded-2xl overflow-hidden border border-border bg-card shadow-lg">
                <img src="https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=800&q=80" alt="Thermocol" className="w-full h-full object-cover" />
              </div>
              <div className="aspect-video rounded-2xl overflow-hidden border border-border bg-card shadow-lg">
                <img src="https://images.unsplash.com/photo-1573106456020-5ce9db6d3679?w=800&q=80" alt="Bags" className="w-full h-full object-cover" />
              </div>
            </div>
            <div className="space-y-3 pt-8">
              <div className="aspect-video rounded-2xl overflow-hidden border border-border bg-card shadow-lg">
                <img src="https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=800&q=80" alt="Cups" className="w-full h-full object-cover" />
              </div>
              <div className="aspect-square rounded-2xl overflow-hidden border border-border bg-card shadow-lg">
                <img src="https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&q=80" alt="Luggage" className="w-full h-full object-cover" />
              </div>
            </div>
          </motion.div>
        </Container>
      </section>

      {/* Trust bar */}
      <div className="border-b border-border bg-card">
        <Container>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-5">
            {[
              { icon: Truck, title: 'Fast Delivery', desc: 'Doorstep across Lucknow' },
              { icon: Award, title: 'Fast Dispatch', desc: 'Same-day for local orders' },
              { icon: ShieldCheck, title: 'GST Invoice', desc: 'For all business buyers' },
              { icon: Phone, title: 'Since 1996', desc: 'Wholesale trust in Lucknow' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-[hsl(var(--brand-terracotta))]/10 grid place-items-center">
                  <Icon className="h-5 w-5 text-[hsl(var(--brand-terracotta))]" />
                </div>
                <div>
                  <div className="font-semibold text-sm">{title}</div>
                  <div className="text-xs text-muted-foreground">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </Container>
      </div>

      {/* Categories */}
      <Section>
        <Container>
          <SectionTitle eyebrow="Shop by Category" title="What are you looking for?" subtitle="Complete range of disposables, packaging, and wholesale essentials."
            action={<Link to="/categories"><Button variant="ghost" className="gap-1">View all <ArrowRight className="h-4 w-4" /></Button></Link>} />
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {loading ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-2xl" />) : cats.slice(0, 8).map((c) => (
              <Link key={c.id} to={`/products?category=${c.id}`} data-testid={`category-card-${c.slug}`}
                className="group relative aspect-[4/3] rounded-2xl overflow-hidden border border-border bg-card hover:shadow-lg transition-shadow">
                <img src={categoryImages[c.name] || 'https://images.unsplash.com/photo-1606636661692-255650f47ec9?w=600&q=80'} alt={c.name} className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
                <div className="absolute inset-x-0 bottom-0 p-3.5 text-white">
                  <div className="text-lg">{iconFor(c.name)}</div>
                  <div className="font-display font-semibold text-base leading-tight">{c.name}</div>
                  <div className="text-xs opacity-80">{c.product_count || 0} products</div>
                </div>
              </Link>
            ))}
          </div>
        </Container>
      </Section>

      {/* Featured products */}
      <Section className="bg-muted/30 border-y border-border">
        <Container>
          <SectionTitle eyebrow="Bestsellers" title="Featured Products" subtitle="Handpicked essentials that our regular buyers love."
            action={<Link to="/products"><Button variant="outline" className="gap-1">Shop all <ArrowRight className="h-4 w-4" /></Button></Link>} />
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
            {loading ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-2xl" />) : featured.slice(0, 8).map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        </Container>
      </Section>

      {/* Why choose us */}
      <Section>
        <Container>
          <SectionTitle eyebrow="Why Kiran Traders" title="Serving Lucknow with pride since 1996" subtitle="Nearly three decades of relationships, quality and reliability." center />
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { icon: Award, title: '25+ Years of Trust', desc: 'Established in 1996, serving Lucknow with pride.' },
              { icon: ShieldCheck, title: 'Quality Guaranteed', desc: 'Every product is checked before dispatch. GST-invoiced for businesses.' },
              { icon: Truck, title: 'Fast & Reliable Delivery', desc: 'Same-day dispatch in Lucknow. Pan-India shipping on request.' },
              { icon: Package, title: 'Bulk & Retail Both', desc: 'Small quantities to full-truckload wholesale, all under one roof.' },
              { icon: MessageCircle, title: 'WhatsApp Support', desc: 'Real humans, fast replies. Ask us anything about your order.' },
              { icon: Sparkles, title: 'Fair Pricing', desc: 'Direct-to-buyer wholesale rates. Extra discounts on large orders.' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="bg-card border border-border rounded-2xl p-5 hover:shadow-md transition-shadow">
                <div className="h-10 w-10 rounded-xl bg-[hsl(var(--brand-teal))]/10 grid place-items-center mb-3">
                  <Icon className="h-5 w-5 text-[hsl(var(--brand-teal))]" />
                </div>
                <div className="font-display font-semibold">{title}</div>
                <p className="text-sm text-muted-foreground mt-1">{desc}</p>
              </div>
            ))}
          </div>
        </Container>
      </Section>

      {/* Testimonials */}
      <Section className="bg-muted/30 border-y border-border">
        <Container>
          <SectionTitle eyebrow="What buyers say" title="Loved by caterers, shopkeepers & event planners" center />
          <div className="grid md:grid-cols-3 gap-4">
            {[
              { name: 'Ramesh Sharma', role: 'Caterer, Aliganj', text: 'Reliable supplier of thermocol plates & bowls for the last 12 years. Never disappointed. Fast delivery every time.' },
              { name: 'Sunita Verma', role: 'Retail Shop, Alambagh', text: 'Best wholesale rates in Lucknow for carry bags and disposables. Bhaiya ji is very helpful and honest.' },
              { name: 'Anil Kumar', role: 'Event Manager', text: 'For any bulk requirement I call Kiran Traders first. Quality is consistent and pricing is transparent.' },
            ].map((t) => (
              <div key={t.name} className="bg-card border border-border rounded-2xl p-5">
                <div className="flex items-center gap-1 mb-2">{Array.from({ length: 5 }).map((_, i) => <Star key={i} className="h-4 w-4 fill-[hsl(var(--brand-marigold))] text-[hsl(var(--brand-marigold))]" />)}</div>
                <p className="text-sm">“{t.text}”</p>
                <div className="mt-3 text-sm"><div className="font-semibold">{t.name}</div><div className="text-xs text-muted-foreground">{t.role}</div></div>
              </div>
            ))}
          </div>
        </Container>
      </Section>

      {/* CTA */}
      <Section>
        <Container>
          <div className="rounded-3xl bg-primary text-primary-foreground p-8 md:p-12 grid md:grid-cols-2 gap-6 items-center noise-overlay overflow-hidden relative">
            <div className="relative z-10">
              <div className="text-sm font-semibold text-[hsl(var(--brand-marigold))]">BULK ORDER?</div>
              <h3 className="text-3xl md:text-4xl font-display font-bold mt-1">Get a custom quote in minutes</h3>
              <p className="opacity-90 mt-2 max-w-lg">Message us on WhatsApp with your requirement or call our sales team directly. GST invoicing available.</p>
            </div>
            <div className="flex flex-wrap gap-3 md:justify-end relative z-10">
              <a href={wa} target="_blank" rel="noreferrer"><Button size="lg" className="bg-[hsl(var(--brand-teal))] text-white hover:bg-[hsl(var(--brand-teal))]/90 gap-2" data-testid="cta-whatsapp"><MessageCircle className="h-4 w-4" /> WhatsApp Now</Button></a>
              <a href={`tel:${settings.phone || '+919876543210'}`}><Button size="lg" variant="secondary" className="gap-2" data-testid="cta-call"><Phone className="h-4 w-4" /> Call {settings.phone || '+91 98765 43210'}</Button></a>
            </div>
          </div>
        </Container>
      </Section>
    </div>
  );
}
