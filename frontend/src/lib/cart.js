import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';

const CartContext = createContext(null);
const KEY = 'kt_cart_v1';

export const CartProvider = ({ children }) => {
  const [items, setItems] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
  });

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(items));
  }, [items]);

  const addItem = useCallback((product, qty = 1) => {
    setItems(prev => {
      const idx = prev.findIndex(i => i.product_id === product.id);
      const minQ = Math.max(qty, product.moq || 1);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], quantity: next[idx].quantity + qty };
        return next;
      }
      return [...prev, {
        product_id: product.id,
        name: product.name,
        price: product.price,
        image: (product.images || [])[0] || '',
        size: product.size || '',
        unit: product.unit || 'piece',
        moq: product.moq || 1,
        quantity: minQ,
      }];
    });
  }, []);

  const updateQty = useCallback((product_id, qty) => {
    setItems(prev => prev.map(i => i.product_id === product_id ? { ...i, quantity: Math.max(i.moq || 1, qty) } : i));
  }, []);

  const removeItem = useCallback((product_id) => setItems(prev => prev.filter(i => i.product_id !== product_id)), []);
  const clear = useCallback(() => setItems([]), []);

  const subtotal = useMemo(() => items.reduce((s, i) => s + i.price * i.quantity, 0), [items]);
  const count = useMemo(() => items.reduce((s, i) => s + i.quantity, 0), [items]);

  return (
    <CartContext.Provider value={{ items, addItem, updateQty, removeItem, clear, subtotal, count }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used within CartProvider');
  return ctx;
};
