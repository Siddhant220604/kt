import React, { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { api } from '../lib/api';

const RequireAdmin = () => {
  const [state, setState] = useState('loading'); // loading | ok | fail
  useEffect(() => {
    const token = localStorage.getItem('kt_admin_token');
    if (!token) { setState('fail'); return; }
    api.get('/auth/me').then(() => setState('ok')).catch(() => setState('fail'));
  }, []);
  if (state === 'loading') return (
    <div className="min-h-screen grid place-items-center">
      <div className="h-10 w-10 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
    </div>
  );
  if (state === 'fail') return <Navigate to="/admin/login" replace />;
  return <Outlet />;
};

export default RequireAdmin;
