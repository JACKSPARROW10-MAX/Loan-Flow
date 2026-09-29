'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { UserPlus, Check, X } from 'lucide-react';
import { fetchPendingUsers, reviewUser, PendingUser } from '@/lib/api';

const roleLabel: Record<string, string> = {
  customer: 'Customer',
  employee: 'Loan officer',
  manager: 'Manager',
};

export const PendingApprovals: React.FC = () => {
  const [items, setItems] = useState<PendingUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await fetchPendingUsers());
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (id: string, action: 'approve' | 'reject') => {
    setBusyId(id);
    try {
      await reviewUser(id, action);
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  if (items.length === 0 && !error) return null;

  return (
    <section className="mb-6 bg-white border border-[#E5E9E1] rounded-2xl shadow-sm">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#E5E9E1]">
        <UserPlus className="w-4 h-4 text-[#0C3B2E]" />
        <h2 className="text-sm font-bold text-[#0C3B2E]">Pending registrations ({items.length})</h2>
      </div>
      {error && <div className="px-4 py-2 text-xs text-red-700">{error}</div>}
      <ul className="divide-y divide-[#E5E9E1]">
        {items.map((u) => (
          <li key={u.id} className="flex items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-[#14241e] truncate">{u.full_name}</div>
              <div className="text-xs text-[#5e6d65] truncate">
                {roleLabel[u.role] || u.role} • {u.username} • {u.email}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                disabled={busyId === u.id}
                onClick={() => act(u.id, 'approve')}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#0C3B2E] text-white text-xs font-semibold hover:bg-[#165443] disabled:opacity-60"
              >
                <Check className="w-3.5 h-3.5" /> Approve
              </button>
              <button
                disabled={busyId === u.id}
                onClick={() => act(u.id, 'reject')}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-300 text-red-700 text-xs font-semibold hover:bg-red-50 disabled:opacity-60"
              >
                <X className="w-3.5 h-3.5" /> Reject
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};
