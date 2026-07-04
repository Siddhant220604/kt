import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../../components/ui/select";
import { Star, Check, X } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function AdminReviews() {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("pending");

  const load = () => {
    const q = filter === "all" ? "" : `?status=${filter}`;
    api.get(`/admin/reviews${q}`).then((r) => setItems(r.data || []));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [filter]);

  const moderate = async (id, approve) => {
    await api.put(`/admin/reviews/${id}/moderate?approve=${approve}`);
    toast.success(approve ? "Approved" : "Rejected");
    load();
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="label-caps mb-1">Moderation</div>
          <h1 className="text-3xl font-black tracking-tighter">Reviews</h1>
        </div>
        <Select value={filter} onValueChange={setFilter}>
          <SelectTrigger className="w-40 rounded-sm" data-testid="admin-review-filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="all">All</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {items.length === 0 && (
          <div className="border border-border bg-card p-8 text-center text-sm text-muted-foreground md:col-span-2">
            No reviews to show.
          </div>
        )}
        {items.map((r) => (
          <div key={r.id} className="border border-border bg-card p-5" data-testid={`admin-review-${r.id}`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-sm">{r.title}</div>
                <div className="text-xs text-muted-foreground">by {r.user_name}</div>
              </div>
              <div className="flex items-center gap-0.5">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star key={s} size={12} weight={s <= r.rating ? "fill" : "regular"} className="text-primary" />
                ))}
              </div>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">{r.comment}</p>
            <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
              <Badge variant="outline" className="rounded-sm">
                {r.approved ? "approved" : "pending"}
              </Badge>
              <div className="flex gap-2">
                {!r.approved && (
                  <Button size="sm" className="rounded-sm" onClick={() => moderate(r.id, true)} data-testid={`review-approve-${r.id}`}>
                    <Check size={14} className="mr-1" /> Approve
                  </Button>
                )}
                <Button size="sm" variant="outline" className="rounded-sm" onClick={() => moderate(r.id, false)} data-testid={`review-reject-${r.id}`}>
                  <X size={14} className="mr-1" /> {r.approved ? "Remove" : "Reject"}
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
