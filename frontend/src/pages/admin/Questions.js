import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Trash2, Send } from 'lucide-react';
import { toast } from 'sonner';

export default function AdminQuestions() {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [drafts, setDrafts] = useState({});
  const load = useCallback(() => api.get('/questions', { params: { answered: filter === 'pending' ? false : true } }).then(r => setRows(r.data)), [filter]);
  useEffect(() => { load(); }, [load]);

  const answer = async (id) => {
    const text = (drafts[id] || '').trim();
    if (!text) return toast.error('Write an answer first');
    try {
      await api.put(`/questions/${id}/answer`, { answer: text });
      toast.success('Answer posted');
      setDrafts(d => ({ ...d, [id]: '' }));
      load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to answer'); }
  };

  const del = async (id) => { if (!window.confirm('Delete this question?')) return; await api.delete(`/questions/${id}`); load(); };

  return (
    <div className="space-y-4">
      <div><h1 className="text-2xl font-display font-bold">Questions</h1><p className="text-sm text-muted-foreground">Answer customer product questions</p></div>
      <Tabs value={filter} onValueChange={setFilter}>
        <TabsList><TabsTrigger value="pending">Pending</TabsTrigger><TabsTrigger value="answered">Answered</TabsTrigger></TabsList>
      </Tabs>
      <div className="space-y-3">
        {rows.map(q => (
          <div key={q.id} className="bg-card border border-border rounded-2xl p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{q.question}</p>
                <div className="text-xs text-muted-foreground mt-1">By {q.name} • Product: {q.product_id}</div>
                {q.answer && <div className="mt-2 text-sm border-l-2 border-primary/30 pl-3">{q.answer}</div>}
              </div>
              <Button size="sm" variant="outline" onClick={() => del(q.id)} className="text-destructive shrink-0"><Trash2 className="h-3.5 w-3.5" /></Button>
            </div>
            {filter === 'pending' && (
              <div className="mt-3 flex gap-2 items-start">
                <Textarea rows={2} placeholder="Write an answer..." value={drafts[q.id] || ''} onChange={(e) => setDrafts(d => ({ ...d, [q.id]: e.target.value }))} className="flex-1" />
                <Button size="sm" onClick={() => answer(q.id)} className="gap-1 shrink-0"><Send className="h-3.5 w-3.5" />Answer</Button>
              </div>
            )}
          </div>
        ))}
        {rows.length === 0 && <div className="text-sm text-muted-foreground text-center py-8">No questions</div>}
      </div>
    </div>
  );
}
