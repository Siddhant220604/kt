import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';

const CartContext = createContext(null);
const KEY = 'kt_cart_v1';

// Bulk/wholesale pricing: picks the highest tier whose min_qty <= qty, falling back to the
// product's base price. Mirrors backend's effective_unit_price() so the cart preview matches
// what /orders will actually charge.
export const computeUnitPrice = (basePrice, tiers, qty) => {
  let price = basePrice;
  for (const t of [...(tiers || [])].sort((a, b) => a.min_qty - b.min_qty)) {
    if (qty >= t.min_qty) price = t.price; else break;
  }
  return price;
};

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
      const maxQ = product.stock > 0 ? product.stock : Infinity;
      const minQ = Math.max(qty, product.moq || 1);
      if (idx >= 0) {
        const next = [...prev];
        const merged = Math.min(next[idx].quantity + qty, maxQ);
        next[idx] = {
          ...next[idx],
          stock: product.stock,
          basePrice: product.price,
          price_tiers: product.price_tiers || [],
          price: computeUnitPrice(product.price, product.price_tiers, merged),
          quantity: merged,
        };
        return next;
      }
      const q = Math.min(minQ, maxQ);
      return [...prev, {
        product_id: product.id,
        name: product.name,
        basePrice: product.price,
        price: computeUnitPrice(product.price, product.price_tiers, q),
        price_tiers: product.price_tiers || [],
        image: (product.images || [])[0] || '',
        size: product.size || '',
        unit: product.unit || 'piece',
        moq: product.moq || 1,
        stock: product.stock,
        quantity: q,
      }];
    });
  }, []);

  const updateQty = useCallback((product_id, qty) => {
    setItems(prev => prev.map(i => {
      if (i.product_id !== product_id) return i;
      const maxQ = i.stock > 0 ? i.stock : Infinity;
      const q = Math.min(Math.max(i.moq || 1, qty), maxQ);
      return { ...i, quantity: q, price: computeUnitPrice(i.basePrice ?? i.price, i.price_tiers, q) };
    }));
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
