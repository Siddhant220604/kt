import { Link } from "react-router-dom";
import { API_BASE } from "../lib/api";
import { money, resolveImage } from "../lib/product";
import { Star, ArrowUpRight } from "@phosphor-icons/react";
import { Badge } from "./ui/badge";

export default function ProductCard({ product, testId }) {
  const startingPrice = product.price_tiers?.length
    ? Math.min(...product.price_tiers.map((t) => t.price))
    : product.base_price;
  const img = resolveImage(product.images?.[0], API_BASE);

  return (
    <Link
      to={`/product/${product.id}`}
      data-testid={testId || `product-card-${product.sku}`}
      className="group relative flex flex-col bg-card border border-border hover-lift rounded-sm"
    >
      <div className="aspect-[4/3] overflow-hidden border-b border-border bg-muted">
        {img ? (
          <img
            src={img}
            alt={product.name}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">No image</div>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center justify-between">
          <span className="label-caps text-[10px]">{product.unit}</span>
          <Badge variant="outline" className="rounded-sm font-mono text-[10px]" data-testid="product-moq-badge">
            MOQ {product.moq}
          </Badge>
        </div>
        <div className="text-sm font-semibold leading-snug text-foreground line-clamp-2">{product.name}</div>
        <div className="mt-1 flex items-end justify-between">
          <div>
            <div className="label-caps text-[9px]">From</div>
            <div className="font-mono text-lg font-bold text-foreground">{money(startingPrice)}</div>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            {product.rating_count > 0 && (
              <>
                <Star size={12} weight="fill" className="text-primary" />
                <span className="font-mono">{product.rating_avg.toFixed(1)}</span>
                <span>({product.rating_count})</span>
              </>
            )}
          </div>
        </div>
        <div className="mt-2 flex items-center justify-between border-t border-border pt-3 text-xs">
          <span className="font-mono text-muted-foreground">{product.sku}</span>
          <span className="flex items-center gap-1 font-medium text-primary">
            View <ArrowUpRight size={12} weight="bold" />
          </span>
        </div>
      </div>
    </Link>
  );
}
