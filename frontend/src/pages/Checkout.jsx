import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { api, formatApiError } from "../lib/api";
import { money, tierPrice } from "../lib/product";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";

export default function Checkout() {
  const { items, totals, clear } = useCart();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [addr, setAddr] = useState({
    full_name: user?.name || "",
    company: user?.company || "",
    line1: "",
    line2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "United States",
    phone: "",
  });
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <div className="label-caps mb-2">Checkout</div>
        <h1 className="text-2xl font-bold">Your cart is empty</h1>
        <Button onClick={() => navigate("/catalog")} className="mt-4 rounded-sm" data-testid="checkout-browse-button">
          Browse Catalog
        </Button>
      </div>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        items: items.map((it) => ({ product_id: it.product.id, quantity: it.quantity })),
        shipping_address: addr,
        notes,
      };
      const { data } = await api.post("/orders", payload);
      clear();
      toast.success(`Order ${data.order_number} placed`);
      navigate(`/orders/${data.id}`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="label-caps mb-2">Checkout</div>
      <h1 className="text-3xl sm:text-4xl font-black tracking-tighter">Confirm your wholesale order</h1>

      <form onSubmit={submit} className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-[1fr_380px]" data-testid="checkout-form">
        <div className="space-y-8">
          <section className="border border-border bg-card p-6">
            <div className="label-caps mb-4">Shipping Address</div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label className="label-caps">Full name</Label>
                <Input required value={addr.full_name} onChange={(e) => setAddr({ ...addr, full_name: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-fullname" />
              </div>
              <div className="sm:col-span-2">
                <Label className="label-caps">Company</Label>
                <Input value={addr.company} onChange={(e) => setAddr({ ...addr, company: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-company" />
              </div>
              <div className="sm:col-span-2">
                <Label className="label-caps">Address line 1</Label>
                <Input required value={addr.line1} onChange={(e) => setAddr({ ...addr, line1: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-line1" />
              </div>
              <div className="sm:col-span-2">
                <Label className="label-caps">Address line 2</Label>
                <Input value={addr.line2} onChange={(e) => setAddr({ ...addr, line2: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-line2" />
              </div>
              <div>
                <Label className="label-caps">City</Label>
                <Input required value={addr.city} onChange={(e) => setAddr({ ...addr, city: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-city" />
              </div>
              <div>
                <Label className="label-caps">State</Label>
                <Input required value={addr.state} onChange={(e) => setAddr({ ...addr, state: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-state" />
              </div>
              <div>
                <Label className="label-caps">Postal code</Label>
                <Input required value={addr.postal_code} onChange={(e) => setAddr({ ...addr, postal_code: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-postal" />
              </div>
              <div>
                <Label className="label-caps">Country</Label>
                <Input required value={addr.country} onChange={(e) => setAddr({ ...addr, country: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-country" />
              </div>
              <div className="sm:col-span-2">
                <Label className="label-caps">Phone</Label>
                <Input required value={addr.phone} onChange={(e) => setAddr({ ...addr, phone: e.target.value })} className="mt-2 rounded-sm" data-testid="checkout-phone" />
              </div>
            </div>
          </section>

          <section className="border border-border bg-card p-6">
            <div className="label-caps mb-4">Order Notes</div>
            <Textarea
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Delivery preferences, PO reference, etc."
              className="rounded-sm"
              data-testid="checkout-notes"
            />
          </section>
        </div>

        {/* Summary */}
        <aside className="lg:sticky lg:top-20 h-fit border border-border bg-card">
          <div className="border-b border-border p-5">
            <div className="label-caps">Order Summary</div>
          </div>
          <div className="divide-y divide-border">
            {items.map((it) => {
              const unit = tierPrice(it.product, it.quantity);
              return (
                <div key={it.product.id} className="flex items-center justify-between p-4 text-sm">
                  <div className="flex-1 pr-2">
                    <div className="font-medium leading-tight">{it.product.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">{it.quantity} × {money(unit)}</div>
                  </div>
                  <div className="font-mono font-semibold">{money(unit * it.quantity)}</div>
                </div>
              );
            })}
          </div>
          <div className="border-t border-border p-5 space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span className="font-mono">{money(totals.subtotal)}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Shipping</span><span className="font-mono">TBD</span></div>
            <div className="flex justify-between border-t border-border pt-2 text-base font-bold"><span>Total</span><span className="font-mono">{money(totals.subtotal)}</span></div>
          </div>
          <div className="p-5 border-t border-border">
            <Button type="submit" className="w-full rounded-sm btn-lift" size="lg" disabled={loading} data-testid="checkout-submit-button">
              {loading ? "Placing order…" : "Place Order"}
            </Button>
            <p className="mt-3 text-[11px] text-muted-foreground">
              Payments are handled offline — you'll receive an invoice from our team after confirmation.
            </p>
          </div>
        </aside>
      </form>
    </div>
  );
}
