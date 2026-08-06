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

// A cart line is identified by product *and* chosen colour, not by product alone: the same
// ribbon in Red and in Black are two separate lines a customer can order together, with their
// own quantities. Colourless products keep a stable key of `<id>::`, so nothing else changes.
export const lineKey = (product_id, color = '') => `${product_id}::${(color || '').trim().toLowerCase()}`;

export const CartProvider = ({ children }) => {
  const [items, setItems] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || '[]');
      // Carts saved before colours existed have no key/colour - stamp them so a returning
      // customer's cart keeps working instead of quietly failing to update or remove.
      return saved.map(i => ({ color: '', ...i, key: i.key || lineKey(i.product_id, i.color) }));
    } catch { return []; }
  });

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(items));
  }, [items]);

  const addItem = useCallback((product, qty = 1, color = '') => {
    setItems(prev => {
      const key = lineKey(product.id, color);
      const idx = prev.findIndex(i => i.key === key);
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
        key,
        product_id: product.id,
        color,
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

  const updateQty = useCallback((key, qty) => {
    setItems(prev => prev.map(i => {
      if (i.key !== key) return i;
      const maxQ = i.stock > 0 ? i.stock : Infinity;
      const q = Math.min(Math.max(i.moq || 1, qty), maxQ);
      return { ...i, quantity: q, price: computeUnitPrice(i.basePrice ?? i.price, i.price_tiers, q) };
    }));
  }, []);

  const removeItem = useCallback((key) => setItems(prev => prev.filter(i => i.key !== key)), []);
  const clear = useCallback(() => setItems([]), []);

  const subtotal = useMemo(() => items.reduce((s, i) => s + i.price * i.quantity, 0), [items]);
  const count = useMemo(() => items.reduce((s, i) => s + i.quantity, 0), [items]);

  return (
    <CartContext.Provider value={{ items, addItem, updateQty, removeItem, clear, subtotal, count, lineKey }}>
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used within CartProvider');
  return ctx;
};
