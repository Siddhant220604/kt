import { useNavigate } from "react-router-dom";
import { X, Trash, Minus, Plus } from "@phosphor-icons/react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Button } from "./ui/button";
import { useCart } from "../context/CartContext";
import { API_BASE } from "../lib/api";
import { money, resolveImage, tierPrice } from "../lib/product";

export default function CartDrawer() {
  const { items, updateQty, removeItem, totals, open, setOpen } = useCart();
  const navigate = useNavigate();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="right" className="w-full sm:max-w-md p-0 flex flex-col">
        <SheetHeader className="border-b border-border p-6">
          <SheetTitle className="text-lg font-bold" data-testid="cart-title">
            Your Cart · {totals.lines} item{totals.lines === 1 ? "" : "s"}
          </SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto" data-testid="cart-items-container">
          {items.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
              <div className="label-caps">Empty</div>
              <p className="text-sm text-muted-foreground">
                Browse the catalog and start adding wholesale items.
              </p>
              <Button
                variant="outline"
                className="mt-3 rounded-sm"
                onClick={() => {
                  setOpen(false);
                  navigate("/catalog");
                }}
                data-testid="cart-browse-catalog-button"
              >
                Browse Catalog
              </Button>
            </div>
          ) : (
            items.map((it) => {
              const unit = tierPrice(it.product, it.quantity);
              const img = resolveImage(it.product.images?.[0], API_BASE);
              return (
                <div
                  key={it.product.id}
                  className="flex gap-3 border-b border-border p-4"
                  data-testid={`cart-line-${it.product.sku}`}
                >
                  <div className="h-16 w-16 flex-shrink-0 overflow-hidden border border-border bg-muted">
                    {img && <img src={img} alt="" className="h-full w-full object-cover" />}
                  </div>
                  <div className="flex-1 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-sm font-semibold leading-tight">{it.product.name}</div>
                        <div className="font-mono text-xs text-muted-foreground">{it.product.sku}</div>
                      </div>
                      <button
                        onClick={() => removeItem(it.product.id)}
                        aria-label="Remove"
                        data-testid={`cart-remove-${it.product.sku}`}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center border border-border">
                        <button
                          className="p-1.5"
                          onClick={() => updateQty(it.product.id, it.quantity - 1)}
                          disabled={it.quantity <= it.product.moq}
                          data-testid={`cart-decrease-${it.product.sku}`}
                          aria-label="Decrease"
                        >
                          <Minus size={12} />
                        </button>
                        <input
                          type="number"
                          value={it.quantity}
                          min={it.product.moq}
                          onChange={(e) => updateQty(it.product.id, Number(e.target.value))}
                          className="w-14 border-x border-border py-1 text-center font-mono text-sm outline-none"
                          data-testid={`cart-qty-${it.product.sku}`}
                        />
                        <button
                          className="p-1.5"
                          onClick={() => updateQty(it.product.id, it.quantity + 1)}
                          data-testid={`cart-increase-${it.product.sku}`}
                          aria-label="Increase"
                        >
                          <Plus size={12} />
                        </button>
                      </div>
                      <div className="text-right">
                        <div className="font-mono text-sm font-semibold">
                          {money(unit * it.quantity)}
                        </div>
                        <div className="font-mono text-[10px] text-muted-foreground">{money(unit)} / {it.product.unit.split(" ")[0]}</div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {items.length > 0 && (
          <div className="border-t border-border p-6 space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="label-caps">Subtotal</span>
              <span className="font-mono text-lg font-bold" data-testid="cart-subtotal">
                {money(totals.subtotal)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">Shipping calculated at checkout.</p>
            <Button
              className="w-full rounded-sm btn-lift"
              onClick={() => {
                setOpen(false);
                navigate("/checkout");
              }}
              data-testid="cart-checkout-button"
            >
              Proceed to Checkout
            </Button>
            <Button
              variant="outline"
              className="w-full rounded-sm"
              onClick={() => setOpen(false)}
              data-testid="cart-continue-shopping-button"
            >
              Continue Shopping
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
