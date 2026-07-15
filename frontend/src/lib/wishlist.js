import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, isCustomerLoggedIn } from './api';

const KEY = 'kt_wishlist_v1';
const Ctx = createContext(null);

const readLocal = () => {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
};

export const WishlistProvider = ({ children }) => {
  const [ids, setIds] = useState(readLocal);
  // Once a signed-in customer's wishlist has been fetched, the server is the source of
  // truth and toggles stop writing to the guest localStorage key.
  const syncedRef = useRef(false);

  // Folds any product IDs saved as a guest (localStorage) into the signed-in account -
  // the server list is always the union, never a replace - so a wishlist built before
  // logging in survives, then switches `ids` over to the account's copy so it carries
  // across devices/browsers from here on.
  const syncAfterLogin = useCallback(async () => {
    const local = readLocal();
    try {
      const { data } = local.length
        ? await api.post('/customer/wishlist/merge', { product_ids: local })
        : await api.get('/customer/wishlist');
      setIds(data.product_ids || []);
      localStorage.removeItem(KEY);
      syncedRef.current = true;
    } catch { /* leave local state as-is; a later page load will retry */ }
  }, []);

  useEffect(() => {
    if (isCustomerLoggedIn()) syncAfterLogin();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!syncedRef.current && !isCustomerLoggedIn()) localStorage.setItem(KEY, JSON.stringify(ids));
  }, [ids]);

  const toggle = useCallback((id) => {
    setIds(prev => {
      const already = prev.includes(id);
      const next = already ? prev.filter(x => x !== id) : [...prev, id];
      if (isCustomerLoggedIn()) {
        (already ? api.delete(`/customer/wishlist/${id}`) : api.post(`/customer/wishlist/${id}`)).catch(() => {});
      }
      return next;
    });
  }, []);

  const has = useCallback((id) => ids.includes(id), [ids]);
  const clear = useCallback(() => setIds([]), []);

  // Called on customer sign-out so the account's wishlist stops showing once logged out,
  // and a fresh guest session starts saving to localStorage again instead of the API.
  const resetOnLogout = useCallback(() => {
    syncedRef.current = false;
    setIds(readLocal());
  }, []);

  return <Ctx.Provider value={{ ids, toggle, has, clear, syncAfterLogin, resetOnLogout }}>{children}</Ctx.Provider>;
};

export const useWishlist = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('useWishlist must be inside provider');
  return c;
};
