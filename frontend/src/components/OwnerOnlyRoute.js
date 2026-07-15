import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { isAdminOwner } from '../lib/api';

// Gates pages a restricted 'staff' account shouldn't reach (catalog, coupons, settings, etc.)
// Backend already enforces this via require_admin vs require_staff - this just avoids staff
// landing on a page that silently fails to load its data.
const OwnerOnlyRoute = () => {
  if (!isAdminOwner()) return <Navigate to="/admin/orders" replace />;
  return <Outlet />;
};

export default OwnerOnlyRoute;
