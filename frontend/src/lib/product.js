// Utility helpers for products and pricing
export function tierPrice(product, qty) {
  if (!product) return 0;
  const tiers = product.price_tiers || [];
  if (!tiers.length) return product.base_price;
  const sorted = [...tiers].sort((a, b) => b.min_qty - a.min_qty);
  for (const t of sorted) {
    if (qty >= t.min_qty) return t.price;
  }
  return product.base_price;
}

export function resolveImage(src, apiBase) {
  if (!src) return "";
  if (src.startsWith("http")) return src;
  return `${apiBase}/files/${src}`;
}

export function money(n) {
  const v = Number(n || 0);
  return v.toLocaleString("en-US", { style: "currency", currency: "USD" });
}
