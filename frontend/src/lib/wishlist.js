import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

const KEY = 'kt_wishlist_v1';
const Ctx = createContext(null);

export const WishlistProvider = ({ children }) => {
  const [ids, setIds] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
  });
  useEffect(() => { localStorage.setItem(KEY, JSON.stringify(ids)); }, [ids]);

  const toggle = useCallback((id) => {
    setIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }, []);
  const has = useCallback((id) => ids.includes(id), [ids]);
  const clear = useCallback(() => setIds([]), []);

  return <Ctx.Provider value={{ ids, toggle, has, clear }}>{children}</Ctx.Provider>;
};

export const useWishlist = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('useWishlist must be inside provider');
  return c;
};
