import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, API_BASE } from "../lib/api";
import { money, resolveImage, tierPrice } from "../lib/product";
import { useCart } from "../context/CartContext";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { CheckCircle, ArrowLeft, Minus, Plus, Star } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function ProductDetail() {
  const { id } = useParams();
  const { addItem } = useCart();
  const [product, setProduct] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [qty, setQty] = useState(1);
  const [selectedImg, setSelectedImg] = useState(0);

  useEffect(() => {
    api.get(`/products/${id}`).then((r) => {
      setProduct(r.data);
      setQty(r.data.moq || 1);
    });
    api.get(`/reviews?product_id=${id}`).then((r) => setReviews(r.data || []));
  }, [id]);

  if (!product) return <div className="p-12 text-center text-sm text-muted-foreground">Loading…</div>;

  const unit = tierPrice(product, qty);
  const total = unit * qty;
  const belowMoq = qty < (product.moq || 1);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <Link
        to="/catalog"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        data-testid="pd-back-link"
      >
        <ArrowLeft size={14} /> Back to catalog
      </Link>

      <div className="mt-6 grid grid-cols-1 gap-10 lg:grid-cols-2">
        {/* Images */}
        <div>
          <div className="aspect-square overflow-hidden border border-border bg-card">
            {product.images?.[selectedImg] ? (
              <img
                src={resolveImage(product.images[selectedImg], API_BASE)}
                alt={product.name}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full items-center justify-center text-muted-foreground">No image</div>
            )}
          </div>
          {product.images?.length > 1 && (
            <div className="mt-3 grid grid-cols-4 gap-2">
              {product.images.map((im, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedImg(i)}
                  className={`aspect-square overflow-hidden border ${selectedImg === i ? "border-primary" : "border-border"}`}
                >
                  <img src={resolveImage(im, API_BASE)} alt="" className="h-full w-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div>
          <div className="flex items-center gap-3">
            <span className="label-caps">{product.unit}</span>
            <Badge variant="outline" className="rounded-sm font-mono">SKU · {product.sku}</Badge>
          </div>
          <h1 className="mt-3 text-3xl sm:text-4xl font-black tracking-tighter">{product.name}</h1>
          {product.rating_count > 0 && (
            <div className="mt-2 flex items-center gap-1 text-sm text-muted-foreground">
              <Star size={14} weight="fill" className="text-primary" />
              <span className="font-mono">{product.rating_avg.toFixed(1)}</span>
              <span>· {product.rating_count} reviews</span>
            </div>
          )}
          <p className="mt-4 text-base leading-relaxed text-muted-foreground">{product.description}</p>

          {/* Bulk pricing table */}
          <div className="mt-6 border border-border bg-card" data-testid="bulk-pricing-table">
            <div className="flex items-center justify-between border-b border-border p-4">
              <div>
                <div className="label-caps">Bulk Pricing</div>
                <div className="text-xs text-muted-foreground">Volume discounts apply automatically</div>
              </div>
              <Badge className="rounded-sm bg-primary text-primary-foreground">MOQ {product.moq}</Badge>
            </div>
            <div className="grid grid-cols-[1fr_1fr_1fr]">
              {(product.price_tiers || []).map((t, i, arr) => {
                const isBest = i === arr.length - 1;
                const savings = arr[0] ? Math.round(((arr[0].price - t.price) / arr[0].price) * 100) : 0;
                return (
                  <div
                    key={i}
                    className={`grid-cell p-4 last:border-r-0 ${isBest ? "bg-primary/5" : ""}`}
                  >
                    <div className="label-caps text-[10px]">{i === 0 ? "Starter" : i === arr.length - 1 ? "Best Value" : "Volume"}</div>
                    <div className="mt-2 font-mono text-2xl font-bold">{money(t.price)}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">/ {product.unit.split(" ")[0]}</div>
                    <div className="mt-3 flex items-center gap-1 text-xs">
                      <CheckCircle size={12} weight="bold" className="text-primary" />
                      <span>Buy {t.min_qty}+</span>
                    </div>
                    {i > 0 && savings > 0 && (
                      <div className="mt-1 font-mono text-[10px] text-primary">Save {savings}%</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quantity + Add to cart */}
          <div className="mt-6 flex items-center gap-4">
            <div className="flex items-center border border-border">
              <button
                onClick={() => setQty(Math.max(qty - 1, product.moq))}
                className="p-2"
                data-testid="pd-qty-decrease"
                aria-label="Decrease"
              >
                <Minus size={14} />
              </button>
              <input
                type="number"
                value={qty}
                min={product.moq}
                onChange={(e) => setQty(Math.max(Number(e.target.value) || product.moq, product.moq))}
                className="w-20 border-x border-border py-2 text-center font-mono outline-none"
                data-testid="pd-qty-input"
              />
              <button
                onClick={() => setQty(qty + 1)}
                className="p-2"
                data-testid="pd-qty-increase"
                aria-label="Increase"
              >
                <Plus size={14} />
              </button>
            </div>
            <div>
              <div className="label-caps">Order Total</div>
              <div className="font-mono text-2xl font-bold" data-testid="pd-order-total">{money(total)}</div>
            </div>
          </div>

          <div className="mt-6 flex gap-3">
            <Button
              size="lg"
              className="flex-1 rounded-sm btn-lift"
              onClick={() => {
                if (product.stock < qty) {
                  toast.error(`Only ${product.stock} in stock`);
                  return;
                }
                addItem(product, qty);
              }}
              disabled={belowMoq || product.stock < qty}
              data-testid="pd-add-to-cart-button"
            >
              Add to Cart · {money(total)}
            </Button>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-6 text-xs">
            <div>
              <div className="label-caps">Stock</div>
              <div className="font-mono text-sm">{product.stock} {product.unit.split(" ")[0]}(s)</div>
            </div>
            <div>
              <div className="label-caps">Unit</div>
              <div className="font-mono text-sm">{product.unit}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Reviews */}
      <div className="mt-16 border-t border-border pt-10">
        <div className="mb-6 flex items-end justify-between">
          <div>
            <div className="label-caps mb-2">Reviews</div>
            <h2 className="text-2xl font-bold">Verified buyer reviews</h2>
          </div>
          <div className="text-sm text-muted-foreground">{reviews.length} approved review{reviews.length === 1 ? "" : "s"}</div>
        </div>
        {reviews.length === 0 ? (
          <div className="border border-border bg-card p-8 text-center text-sm text-muted-foreground">
            No reviews yet. Buyers can leave a review after their order is delivered.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {reviews.map((r) => (
              <div key={r.id} className="border border-border bg-card p-5">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold">{r.title}</div>
                  <div className="flex items-center gap-0.5">
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Star key={s} size={12} weight={s <= r.rating ? "fill" : "regular"} className="text-primary" />
                    ))}
                  </div>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{r.comment}</p>
                <div className="mt-3 label-caps text-[9px]">— {r.user_name}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
