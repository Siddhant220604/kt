import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Trash2, MailCheck, Phone } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminContacts() {
  const [rows, setRows] = useState([]);
  const load = () => api.get('/contact').then(r => setRows(r.data));
  useEffect(() => { load(); }, []);
  const markRead = async (id) => { await api.put(`/contact/${id}/read`); load(); };
  const del = async (id) => { if (!window.confirm('Delete message?')) return; await api.delete(`/contact/${id}`); load(); };

  return (
    <div className="space-y-4">
      <div><h1 className="text-2xl font-display font-bold">Contact Messages</h1><p className="text-sm text-muted-foreground">{rows.length} messages</p></div>
      <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
        {rows.map(m => (
          <div key={m.id} className={`bg-card border rounded-2xl p-4 ${m.read ? 'border-border' : 'border-primary/40'}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2"><div className="font-medium">{m.name}</div>{!m.read && <Badge className="bg-[hsl(var(--brand-marigold))] text-black text-[10px]">NEW</Badge>}</div>
                <div className="text-xs text-muted-foreground">{m.mobile} {m.email && `• ${m.email}`}</div>
                {m.subject && <div className="text-sm mt-1 font-semibold">{m.subject}</div>}
                <p className="text-sm text-muted-foreground mt-1">{m.message}</p>
                <div className="text-[10px] text-muted-foreground mt-1">{m.created_at?.slice(0, 16).replace('T', ' ')}</div>
              </div>
              <div className="flex gap-1">
                <a href={`tel:${m.mobile}`}><Button size="icon" variant="outline"><Phone className="h-3.5 w-3.5" /></Button></a>
                {!m.read && <Button size="icon" variant="outline" onClick={() => markRead(m.id)}><MailCheck className="h-3.5 w-3.5" /></Button>}
                <Button size="icon" variant="outline" onClick={() => del(m.id)} className="text-destructive"><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-muted-foreground text-center py-8">No messages</div>}
      </div>
    </div>
  );
}
