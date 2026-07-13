import axios from 'axios';
import { toast } from 'sonner';

export const BACKEND_URL =
  process.env.REACT_APP_BACKEND_URL || 'https://kt-3oe7.onrender.com';
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

const parseJwt = (token) => {
  try {
    const [, payload] = token.split('.');
    if (!payload) return null;
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decodeURIComponent(escape(decoded)));
  } catch {
    return null;
  }
};

export const isTokenExpired = (token) => {
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return true;
  const expires = typeof payload.exp === 'number' ? payload.exp * 1000 : Date.parse(payload.exp);
  return Number.isNaN(expires) ? true : Date.now() >= expires;
};

export const logoutAdmin = (message) => {
  localStorage.removeItem('kt_admin_token');
  if (message) {
    toast.error(message);
  }
  if (window.location.pathname !== '/admin/login') {
    window.location.href = '/admin/login';
  }
};

export const logoutCustomer = () => {
  localStorage.removeItem('kt_customer_token');
  localStorage.removeItem('kt_customer_mobile');
};

api.interceptors.request.use((config) => {
  // /customer/* endpoints are authenticated with the customer's own OTP-login token, never
  // the admin token - keeping the two entirely separate even if both happen to be present in
  // the same browser (e.g. the store owner testing the customer login while still admin-logged-in).
  const isCustomerPath = typeof config.url === 'string' && config.url.startsWith('/customer/');
  const token = localStorage.getItem(isCustomerPath ? 'kt_customer_token' : 'kt_admin_token');
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response && [401, 403].includes(err.response.status) && window.location.pathname.startsWith('/admin')) {
      const message = err.response.status === 401 ? 'Your session has expired. Please login again.' : 'Access denied. Please sign in again.';
      logoutAdmin(message);
    }
    return Promise.reject(err);
  }
);

export const formatINR = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n || 0);

// Downloads an authenticated endpoint's response as a file. Plain <a href> can't be
// used for admin exports since the browser won't attach the Bearer token to a direct
// navigation - this fetches via the authenticated axios client and saves the blob.
export const downloadFile = async (path, params, filename) => {
  const res = await api.get(path, { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};
