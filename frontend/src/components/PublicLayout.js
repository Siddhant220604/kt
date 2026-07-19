import React, { useState, useEffect } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { ShoppingCart, Search, Menu, Heart, Phone, MessageCircle, MapPin, Truck, Sun, Moon, Clock, Package, Home as HomeIcon, User } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Sheet, SheetContent, SheetTrigger } from './ui/sheet';
import { Badge } from './ui/badge';
import LogoMark from './LogoMark';
import { useCart } from '../lib/cart';
import { useWishlist } from '../lib/wishlist';
import { useTheme } from '../lib/theme';
import { useSettings } from '../lib/settings';
import { api } from '../lib/api';

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About' },
  { to: '/track', label: 'Track Order' },
  { to: '/contact', label: 'Contact' },
];

const Header = () => {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const { count } = useCart();
  const { ids } = useWishlist();
  const { theme, toggle } = useTheme();
  const { settings } = useSettings();

  const submit = (e) => {
    e.preventDefault();
    if (q.trim()) navigate(`/products?search=${encodeURIComponent(q.trim())}`);
    setOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="bg-primary text-primary-foreground text-xs">
        <div className="max-w-7xl mx-auto px-4 py-1.5 flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5"><Truck className="h-3.5 w-3.5" /> Bulk order discounts — WhatsApp us</span>
          <span className="hidden sm:flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {settings.hours || 'Mon-Wed, Fri-Sun 10-8 | Thu Closed'}</span>
          <a href={`tel:${settings.phone || '+919876543210'}`} className="hidden md:flex items-center gap-1.5 hover:underline"><Phone className="h-3.5 w-3.5" /> {settings.phone || '+91 98765 43210'}</a>
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="h-16 flex items-center gap-3">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" data-testid="mobile-menu-button">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72">
              <Link to="/" className="flex items-center gap-2 font-display font-bold text-xl" onClick={() => setOpen(false)}>
                <LogoMark className="h-9 w-9 shrink-0" />
                <span>Kiran Traders</span>
              </Link>
              <form onSubmit={submit} className="mt-6">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products..." className="pl-9 h-11" data-testid="mobile-search-input" />
                </div>
              </form>
              <nav className="mt-6 flex flex-col gap-1">
                {navLinks.map((n) => (
                  <Link key={n.to} to={n.to} onClick={() => setOpen(false)} className="py-2.5 px-3 rounded-lg hover:bg-muted font-body">
                    {n.label}
                  </Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>

          <Link to="/" data-testid="logo-link" className="flex items-center gap-2">
            <LogoMark className="h-10 w-10 shrink-0" />
            <div className="leading-tight">
              <div className="font-display font-bold text-lg text-foreground">Kiran Traders</div>
              <div className="text-[10px] text-muted-foreground hidden sm:block">Since 1996 • Lucknow</div>
            </div>
          </Link>

          <form onSubmit={submit} className="hidden lg:flex flex-1 max-w-2xl mx-6">
            <div className="relative w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search thermocol plates, carry bags, disposables..." className="pl-10 h-11 rounded-xl bg-muted/40" data-testid="search-input" />
            </div>
          </form>

          <nav className="hidden lg:flex items-center gap-4 mr-2">
            {navLinks.map((n) => (
              <Link key={n.to} to={n.to} className="text-sm font-body hover:text-primary transition-colors">{n.label}</Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={toggle} data-testid="theme-toggle" aria-label="Toggle theme">
              {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>
            <Link to="/account" data-testid="account-link">
              <Button variant="ghost" size="icon"><User className="h-5 w-5" /></Button>
            </Link>
            <Link to="/wishlist" data-testid="wishlist-link">
              <Button variant="ghost" size="icon" className="relative">
                <Heart className="h-5 w-5" />
                {ids.length > 0 && <Badge className="absolute -top-0.5 -right-0.5 h-5 min-w-[20px] px-1 flex items-center justify-center bg-[hsl(var(--brand-marigold))] text-black">{ids.length}</Badge>}
              </Button>
            </Link>
            <Link to="/cart" data-testid="cart-link">
              <Button variant="ghost" size="icon" className="relative">
                <ShoppingCart className="h-5 w-5" />
                {count > 0 && <Badge className="absolute -top-0.5 -right-0.5 h-5 min-w-[20px] px-1 flex items-center justify-center bg-[hsl(var(--brand-marigold))] text-black" data-testid="cart-count-badge">{count}</Badge>}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </header>
  );
};

const Footer = () => {
  const { settings } = useSettings();
  const [footerCats, setFooterCats] = useState([]);
  useEffect(() => {
    api.get('/categories').then(r => setFooterCats((r.data || []).slice(0, 5))).catch(() => {});
  }, []);
  return (
    <footer className="mt-16 border-t border-border bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 grid grid-cols-1 md:grid-cols-4 gap-8">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <LogoMark className="h-10 w-10 shrink-0" />
            <div className="font-display font-bold text-lg">Kiran Traders</div>
          </div>
          <p className="text-sm text-muted-foreground">Wholesale & Retail packaging essentials. Trusted in Lucknow since 1996.</p>
          <div className="mt-4 flex items-center gap-2">
            <a href={`https://wa.me/${settings.whatsapp || '919876543210'}`} target="_blank" rel="noreferrer" data-testid="footer-whatsapp" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[hsl(var(--brand-teal))] text-white text-sm"><MessageCircle className="h-4 w-4" /> WhatsApp</a>
            <a href={`tel:${settings.phone || '+919876543210'}`} data-testid="footer-call" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm"><Phone className="h-4 w-4" /> Call</a>
          </div>
        </div>
        <div>
          <h4 className="font-display font-semibold mb-3">Explore</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li><Link to="/products" className="hover:text-foreground">All Products</Link></li>
            <li><Link to="/about" className="hover:text-foreground">About Us</Link></li>
            <li><Link to="/track" className="hover:text-foreground">Track Order</Link></li>
            <li><Link to="/contact" className="hover:text-foreground">Contact</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="font-display font-semibold mb-3">Categories</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            {footerCats.map(c => (
              <li key={c.id}>
                <Link to={`/products?category=${c.id}`} className="hover:text-foreground">{c.name}</Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="font-display font-semibold mb-3">Contact</h4>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-start gap-2"><MapPin className="h-4 w-4 mt-0.5 shrink-0" />{settings.address || 'Sector K, 805-D, Aashiyana, Lucknow, UP'}</li>
            <li className="flex items-center gap-2"><Phone className="h-4 w-4" />{settings.phone || '+91 98765 43210'}</li>
            <li className="flex items-center gap-2"><Clock className="h-4 w-4" />{settings.hours || 'Mon-Wed, Fri-Sun 10-8'}</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border py-4 text-center text-xs text-muted-foreground">
        &copy; {new Date().getFullYear()} Kiran Traders. All rights reserved. GSTIN: {settings.gstin || '09AAAAA0000A1Z5'}
      </div>
    </footer>
  );
};

const MobileBottomBar = () => {
  const { settings } = useSettings();
  const { count } = useCart();
  return (
    <div className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-background/95 backdrop-blur border-t border-border">
      <div className="grid grid-cols-4 h-14">
        <Link to="/" className="flex flex-col items-center justify-center text-xs gap-0.5"><HomeIcon className="h-5 w-5" />Home</Link>
        <Link to="/products" className="flex flex-col items-center justify-center text-xs gap-0.5"><Package className="h-5 w-5" />Shop</Link>
        <a href={`https://wa.me/${settings.whatsapp || '919876543210'}`} target="_blank" rel="noreferrer" className="flex flex-col items-center justify-center text-xs gap-0.5 text-[hsl(var(--brand-teal))]" data-testid="mobile-whatsapp-cta"><MessageCircle className="h-5 w-5" />WhatsApp</a>
        <Link to="/cart" className="flex flex-col items-center justify-center text-xs gap-0.5 relative">
          <ShoppingCart className="h-5 w-5" />Cart
          {count > 0 && <span className="absolute top-1 right-6 h-4 min-w-4 px-1 grid place-items-center text-[10px] rounded-full bg-[hsl(var(--brand-marigold))] text-black">{count}</span>}
        </Link>
      </div>
    </div>
  );
};

const ScrollToTop = () => {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }); }, [pathname]);
  return null;
};

const PublicLayout = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <ScrollToTop />
      <Header />
      <main className="flex-1 pb-16 lg:pb-0">
        <Outlet />
      </main>
      <Footer />
      <MobileBottomBar />
    </div>
  );
};

export default PublicLayout;
