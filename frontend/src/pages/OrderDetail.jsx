import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, formatApiError } from "../lib/api";
import { money } from "../lib/product";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../components/ui/dialog";
import { ArrowLeft, CheckCircle, Circle, Star } from "@phosphor-icons/react";
import { toast } from "sonner";

const STEPS = ["pending", "confirmed", "shipped", "delivered"];

export default function OrderDetail() {
  const { id } = useParams();
  const [order, setOrder] = useState(null);
  const [existingReviews, setExistingReviews] = useState({}); // pid -> true

  const load = async () => {
    const { data } = await api.get(`/orders/${id}`);
    setOrder(data);
    if (data.status === "delivered") {
      // Fetch my reviews for these products (we don't have a "my reviews" endpoint, we can check by trying to create — skip)
    }
  };

  useEffect(() => { load(); }, [id]);

  if (!order) return <div className="p-12 text-center text-sm text-muted-foreground">Loading…</div>;

  const stepIdx = STEPS.indexOf(order.status);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <Link to="/orders" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft size={14} /> Back to orders
      </Link>

      <div className="mt-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="label-caps mb-1">{order.order_number}</div>
          <h1 className="text-3xl font-black tracking-tighter">Order summary</h1>
          <div className="mt-1 text-sm text-muted-foreground">Placed {new Date(order.created_at).toLocaleString()}</div>
        </div>
        <Badge className="rounded-sm text-sm px-3 py-1" data-testid="order-status-badge">{order.status.toUpperCase()}</Badge>
      </div>

      {/* Status timeline */}
      {order.status !== "cancelled" && (
        <div className="mt-8 border border-border bg-card p-6">
          <div className="grid grid-cols-4 gap-4">
            {STEPS.map((s, i) => {
              const active = i <= stepIdx;
              return (
                <div key={s} className="flex flex-col items-start gap-2" data-testid={`order-step-${s}`}>
                  <div className={`flex items-center gap-2 ${active ? "text-primary" : "text-muted-foreground"}`}>
                    {active ? <CheckCircle size={18} weight="fill" /> : <Circle size={18} />}
                    <span className="label-caps text-[10px]">Step {i + 1}</span>
                  </div>
                  <div className={`text-sm font-semibold ${active ? "" : "text-muted-foreground"}`}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </div>
                  <div className={`h-0.5 w-full ${active ? "bg-primary" : "bg-border"}`} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div className="border border-border bg-card">
          <div className="border-b border-border p-4"><div className="label-caps">Items</div></div>
          <div className="divide-y divide-border">
            {order.items.map((it) => (
              <div key={it.product_id} className="flex items-center justify-between p-4">
                <div>
                  <div className="font-medium">{it.product_name}</div>
                  <div className="font-mono text-xs text-muted-foreground">{it.sku} · {it.quantity} × {money(it.unit_price)}</div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="font-mono font-semibold">{money(it.subtotal)}</div>
                  {order.status === "delivered" && (
                    <ReviewDialog
                      orderId={order.id}
                      productId={it.product_id}
                      productName={it.product_name}
                      submitted={!!existingReviews[it.product_id]}
                      onSubmitted={() => setExistingReviews({ ...existingReviews, [it.product_id]: true })}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-border p-4 space-y-1 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span className="font-mono">{money(order.subtotal)}</span></div>
            <div className="flex justify-between text-base font-bold border-t border-border pt-2 mt-2"><span>Total</span><span className="font-mono">{money(order.total)}</span></div>
          </div>
        </div>

        <div className="border border-border bg-card p-5 h-fit">
          <div className="label-caps mb-3">Shipping to</div>
          <div className="text-sm space-y-1">
            <div className="font-semibold">{order.shipping_address.full_name}</div>
            {order.shipping_address.company && <div>{order.shipping_address.company}</div>}
            <div>{order.shipping_address.line1}</div>
            {order.shipping_address.line2 && <div>{order.shipping_address.line2}</div>}
            <div>{order.shipping_address.city}, {order.shipping_address.state} {order.shipping_address.postal_code}</div>
            <div>{order.shipping_address.country}</div>
            <div className="font-mono text-xs text-muted-foreground pt-2">{order.shipping_address.phone}</div>
          </div>
          {order.notes && (
            <>
              <div className="label-caps mt-4 mb-2">Notes</div>
              <div className="text-sm text-muted-foreground">{order.notes}</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ReviewDialog({ orderId, productId, productName, submitted, onSubmitted }) {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/reviews", { order_id: orderId, product_id: productId, rating, title, comment });
      toast.success("Review submitted — pending approval");
      setOpen(false);
      onSubmitted?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline" className="rounded-sm" disabled={submitted} data-testid={`review-button-${productId}`}>
          {submitted ? "Reviewed" : "Review"}
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-sm">
        <DialogHeader>
          <DialogTitle>Review · {productName}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label className="label-caps">Rating</Label>
            <div className="mt-2 flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setRating(n)}
                  data-testid={`review-star-${n}`}
                  className="p-1"
                >
                  <Star size={22} weight={n <= rating ? "fill" : "regular"} className="text-primary" />
                </button>
              ))}
            </div>
          </div>
          <div>
            <Label className="label-caps">Title</Label>
            <Input required value={title} onChange={(e) => setTitle(e.target.value)} className="mt-2 rounded-sm" data-testid="review-title-input" />
          </div>
          <div>
            <Label className="label-caps">Comment</Label>
            <Textarea required rows={4} value={comment} onChange={(e) => setComment(e.target.value)} className="mt-2 rounded-sm" data-testid="review-comment-input" />
          </div>
          <DialogFooter>
            <Button type="submit" className="rounded-sm" disabled={loading} data-testid="review-submit-button">
              {loading ? "Submitting…" : "Submit review"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
