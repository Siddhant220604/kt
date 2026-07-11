import React, { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { api, isTokenExpired, logoutAdmin } from '../lib/api';

const ProtectedRoute = () => {
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    const token = localStorage.getItem('kt_admin_token');
    if (!token || isTokenExpired(token)) {
      if (token) logoutAdmin();
      setStatus('fail');
      return;
    }

    api.get('/auth/me')
      .then(() => setStatus('ok'))
      .catch(() => setStatus('fail'));
  }, []);

  if (status === 'loading') {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="h-10 w-10 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  if (status === 'fail') {
    return <Navigate to="/admin/login" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
