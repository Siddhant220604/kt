import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { tierPrice } from "../lib/product";

const CartContext = createContext(null);
const KEY = "bulkhaus_cart_v1";

export function CartProvider({ children }) {
  const [items, setItems] = useState([]); // [{product, quantity}]
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setItems(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(items));
  }, [items]);

  const addItem = useCallback((product, quantity) => {
    const qty = Math.max(Number(quantity) || product.moq || 1, product.moq || 1);
    setItems((prev) => {
      const idx = prev.findIndex((it) => it.product.id === product.id);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = { ...copy[idx], quantity: copy[idx].quantity + qty };
        return copy;
      }
      return [...prev, { product, quantity: qty }];
    });
    toast.success(`Added ${qty} × ${product.name} to cart`);
  }, []);

  const updateQty = useCallback((productId, quantity) => {
    setItems((prev) =>
      prev.map((it) =>
        it.product.id === productId ? { ...it, quantity: Math.max(quantity, it.product.moq || 1) } : it,
      ),
    );
  }, []);

  const removeItem = useCallback((productId) => {
    setItems((prev) => prev.filter((it) => it.product.id !== productId));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const totals = items.reduce(
    (acc, it) => {
      const unit = tierPrice(it.product, it.quantity);
      const line = unit * it.quantity;
      acc.count += it.quantity;
      acc.lines += 1;
      acc.subtotal += line;
      return acc;
    },
    { count: 0, lines: 0, subtotal: 0 },
  );

  return (
    <CartContext.Provider
      value={{ items, addItem, updateQty, removeItem, clear, totals, open, setOpen }}
    >
      {children}
    </CartContext.Provider>
  );
}

export const useCart = () => useContext(CartContext);
