import React, { useState, useEffect, useRef } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, Package, Tags, ShoppingBag, Users, Ticket, Image as ImageIcon, Star, Mail, Settings as SettingsIcon, User, LogOut, Menu, Store, Sun, Moon } from 'lucide-react';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetTrigger } from './ui/sheet';
import { useTheme } from '../lib/theme';
import { logoutAdmin, isTokenExpired } from '../lib/api';

const navItems = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/orders', label: 'Orders', icon: ShoppingBag },
  { to: '/admin/products', label: 'Products', icon: Package },
  { to: '/admin/categories', label: 'Categories', icon: Tags },
  { to: '/admin/customers', label: 'Customers', icon: Users },
  { to: '/admin/coupons', label: 'Coupons', icon: Ticket },
  { to: '/admin/banners', label: 'Banners', icon: ImageIcon },
  { to: '/admin/reviews', label: 'Reviews', icon: Star },
  { to: '/admin/contacts', label: 'Contacts', icon: Mail },
  { to: '/admin/profile', label: 'Profile', icon: User },
  { to: '/admin/settings', label: 'Settings', icon: SettingsIcon },
];

const SidebarContent = ({ onNav }) => {
  const { pathname } = useLocation();
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-4 border-b border-border">
        <Link to="/admin/dashboard" onClick={onNav} className="flex items-center gap-2">
          <span className="h-9 w-9 rounded-xl bg-primary text-primary-foreground grid place-items-center font-display font-bold text-sm">KT</span>
          <div>
            <div className="font-display font-bold text-sm leading-tight">Kiran Traders</div>
            <div className="text-[10px] text-muted-foreground">Admin Panel</div>
          </div>
        </Link>
      </div>
      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon }) => {
          const active = pathname.startsWith(to);
          return (
            <Link key={to} to={to} onClick={onNav} data-testid={`admin-nav-${label.toLowerCase()}`}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}>
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border">
        <Link to="/" onClick={onNav} className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground py-2 px-2">
          <Store className="h-3.5 w-3.5" /> View Store
        </Link>
      </div>
    </div>
  );
};

const AdminLayout = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const { theme, toggle } = useTheme();
  const timeoutRef = useRef(null);

  const logout = () => {
    localStorage.removeItem('kt_admin_token');
    navigate('/admin/login');
  };

  useEffect(() => {
    const INACTIVITY_TIMEOUT = 30 * 60 * 1000;
    const clearTimer = () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const resetTimer = () => {
      clearTimer();
      const token = localStorage.getItem('kt_admin_token');
      if (!token || isTokenExpired(token)) {
        logoutAdmin('Your session has expired. Please login again.');
        return;
      }
      timeoutRef.current = window.setTimeout(() => {
        logoutAdmin('Logged out due to inactivity. Please sign in again.');
      }, INACTIVITY_TIMEOUT);
    };

    const events = ['mousemove', 'keydown', 'scroll', 'touchstart'];
    events.forEach((eventName) => window.addEventListener(eventName, resetTimer, { passive: true }));
    resetTimer();

    return () => {
      clearTimer();
      events.forEach((eventName) => window.removeEventListener(eventName, resetTimer));
    };
  }, []);

  return (
    <div className="min-h-screen flex bg-muted/30">
      <aside className="hidden lg:flex w-64 border-r border-border bg-card flex-col">
        <SidebarContent />
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-border bg-card px-4 flex items-center gap-3">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SidebarContent onNav={() => setOpen(false)} />
            </SheetContent>
          </Sheet>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggle} data-testid="admin-theme-toggle">
              {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={logout} data-testid="admin-logout">
              <LogOut className="h-4 w-4 mr-1" /> Logout
            </Button>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
