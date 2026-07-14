import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { Toaster } from './components/ui/sonner';
import { CartProvider } from './lib/cart';
import { WishlistProvider } from './lib/wishlist';
import { ThemeProvider } from './lib/theme';
import { SettingsProvider } from './lib/settings';
import PublicLayout from './components/PublicLayout';
import AdminLayout from './components/AdminLayout';
import ProtectedRoute from './components/ProtectedRoute';
import CustomerProtectedRoute from './components/CustomerProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

// Public
const Home = lazy(() => import('./pages/Home'));
const About = lazy(() => import('./pages/About'));
const Products = lazy(() => import('./pages/Products'));
const ProductDetail = lazy(() => import('./pages/ProductDetail'));
const Cart = lazy(() => import('./pages/Cart'));
const Checkout = lazy(() => import('./pages/Checkout'));
const OrderSuccess = lazy(() => import('./pages/OrderSuccess'));
const OrderTracking = lazy(() => import('./pages/OrderTracking'));
const Contact = lazy(() => import('./pages/Contact'));
const Wishlist = lazy(() => import('./pages/Wishlist'));
const SignIn = lazy(() => import('./pages/SignIn'));
const SignUp = lazy(() => import('./pages/SignUp'));
const Account = lazy(() => import('./pages/Account'));
const NotFound = lazy(() => import('./pages/NotFound'));

// Admin
const AdminLogin = lazy(() => import('./pages/admin/Login'));
const AdminDashboard = lazy(() => import('./pages/admin/Dashboard'));
const AdminProfile = lazy(() => import('./pages/admin/Profile'));
const AdminProducts = lazy(() => import('./pages/admin/Products'));
const AdminOrders = lazy(() => import('./pages/admin/Orders'));
const AdminOrderDetail = lazy(() => import('./pages/admin/OrderDetail'));
const AdminCategories = lazy(() => import('./pages/admin/Categories'));
const AdminCustomers = lazy(() => import('./pages/admin/Customers'));
const AdminCoupons = lazy(() => import('./pages/admin/Coupons'));
const AdminBanners = lazy(() => import('./pages/admin/Banners'));
const AdminReviews = lazy(() => import('./pages/admin/Reviews'));
const AdminContacts = lazy(() => import('./pages/admin/Contacts'));
const AdminSettings = lazy(() => import('./pages/admin/Settings'));
const AdminAuditLog = lazy(() => import('./pages/admin/AuditLog'));

const Loading = () => (
  <div className="flex items-center justify-center min-h-[60vh]">
    <div className="h-10 w-10 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
  </div>
);

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
      <HelmetProvider>
      <ThemeProvider>
        <SettingsProvider>
          <CartProvider>
            <WishlistProvider>
              <BrowserRouter>
                <Suspense fallback={<Loading />}>
                  <Routes>
                    <Route element={<PublicLayout />}>
                      <Route path="/" element={<Home />} />
                      <Route path="/about" element={<About />} />
                      <Route path="/products" element={<Products />} />
                      <Route path="/products/:idOrSlug" element={<ProductDetail />} />
                      <Route path="/cart" element={<Cart />} />
                      <Route path="/order-success/:orderId" element={<OrderSuccess />} />
                      <Route path="/track" element={<OrderTracking />} />
                      <Route path="/track/:orderId" element={<OrderTracking />} />
                      <Route path="/contact" element={<Contact />} />
                      <Route path="/wishlist" element={<Wishlist />} />
                      <Route path="/signin" element={<SignIn />} />
                      <Route path="/signup" element={<SignUp />} />
                      <Route element={<CustomerProtectedRoute />}>
                        <Route path="/checkout" element={<Checkout />} />
                        <Route path="/account" element={<Account />} />
                      </Route>
                    </Route>
                    <Route path="/admin/login" element={<AdminLogin />} />
                    <Route element={<ProtectedRoute />}>
                      <Route element={<AdminLayout />}>
                        <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
                        <Route path="/admin/dashboard" element={<AdminDashboard />} />
                        <Route path="/admin/orders" element={<AdminOrders />} />
                        <Route path="/admin/orders/:oid" element={<AdminOrderDetail />} />
                        <Route path="/admin/products" element={<AdminProducts />} />
                        <Route path="/admin/categories" element={<AdminCategories />} />
                        <Route path="/admin/customers" element={<AdminCustomers />} />
                        <Route path="/admin/coupons" element={<AdminCoupons />} />
                        <Route path="/admin/banners" element={<AdminBanners />} />
                        <Route path="/admin/reviews" element={<AdminReviews />} />
                        <Route path="/admin/contacts" element={<AdminContacts />} />
                        <Route path="/admin/profile" element={<AdminProfile />} />
                        <Route path="/admin/settings" element={<AdminSettings />} />
                        <Route path="/admin/audit-log" element={<AdminAuditLog />} />
                      </Route>
                    </Route>
                    <Route path="*" element={<NotFound />} />
                  </Routes>
                </Suspense>
              </BrowserRouter>
              <Toaster position="top-center" richColors closeButton />
            </WishlistProvider>
          </CartProvider>
        </SettingsProvider>
      </ThemeProvider>
      </HelmetProvider>
      </ErrorBoundary>
    </div>
  );
}

export default App;
