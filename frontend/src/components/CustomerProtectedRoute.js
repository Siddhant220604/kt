import React, { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { api, isTokenExpired, logoutCustomer } from '../lib/api';

// Gates customer-only pages (checkout, account) behind sign-in. Per the site's requirement
// that checkout can only be reached once signed in, an unauthenticated visitor is sent to
// /signup (not /signin) - most visitors here are new, and the signup page itself links to
// sign in for existing customers. The attempted destination is preserved via location state
// so login/signup lands the customer back where they were headed, cart intact (cart lives in
// localStorage independent of auth, so it's untouched by this whole redirect round-trip).
const CustomerProtectedRoute = () => {
  const [status, setStatus] = useState('loading');
  const location = useLocation();

  useEffect(() => {
    const token = localStorage.getItem('kt_customer_token');
    if (!token || isTokenExpired(token)) {
      if (token) logoutCustomer();
      setStatus('fail');
      return;
    }

    api.get('/customer/auth/me')
      .then(() => setStatus('ok'))
      .catch(() => { logoutCustomer(); setStatus('fail'); });
  }, [location.pathname]);

  if (status === 'loading') {
    return (
      <div className="min-h-[60vh] grid place-items-center">
        <div className="h-10 w-10 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  if (status === 'fail') {
    return <Navigate to="/signup" replace state={{ from: location }} />;
  }

  return <Outlet />;
};

export default CustomerProtectedRoute;
