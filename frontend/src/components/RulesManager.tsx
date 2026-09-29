'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Scale, Plus, Pencil, Trash2, X } from 'lucide-react';
import { RuleCatalog, RuleItem } from '@/types';
import {
  fetchRuleCatalog,
  fetchRules,
  createRule,
  updateRule,
  setRuleActive,
  deleteRule,
  RuleInput,
} from '@/lib/api';

const categoryLabel: Record<string, string> = {
  eligibility: 'Eligibility',
  limit: 'Loan limit',
  risk: 'Risk',
  fraud: 'Fraud',
};

interface FormState {
  id?: string;
  loan_type: string;
  rule_name: string;
  type: string;
  description: string;
  is_active: boolean;
  is_mandatory: boolean;
  params: Record<string, string>;
}

const toText = (v: any): string => (Array.isArray(v) ? v.join(', ') : v === undefined || v === null ? '' : String(v));

export const RulesManager: React.FC = () => {
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [catalog, setCatalog] = useState<RuleCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('ALL');
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, c] = await Promise.all([fetchRules(), fetchRuleCatalog()]);
      setRules(r);
      setCatalog(c);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Could not load rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const products = useMemo(() => {
    const set = new Set(rules.map((r) => r.loan_type));
    return Array.from(set).sort((a, b) => (a === '*' ? -1 : b === '*' ? 1 : a.localeCompare(b)));
  }, [rules]);

  const visible = rules.filter((r) => filter === 'ALL' || r.loan_type === filter);

  const openNew = () => {
    if (!catalog) return;
    const type = Object.keys(catalog.types)[0];
    setForm({
      loan_type: products.find((p) => p !== '*') || 'Home Loan',
      rule_name: '',
      type,
      description: '',
      is_active: true,
      is_mandatory: true,
      params: Object.fromEntries(catalog.types[type].params.map((p) => [p.name, toText(p.default)])),
    });
  };

  const openEdit = (r: RuleItem) => {
    if (!catalog) return;
    const spec = catalog.types[r.rule_config.type];
    setForm({
      id: r.id,
      loan_type: r.loan_type,
      rule_name: r.rule_name,
      type: r.rule_config.type,
      description: r.rule_config.description || '',
      is_active: r.is_active,
      is_mandatory: r.is_mandatory,
      params: Object.fromEntries((spec?.params || []).map((p) => [p.name, toText(r.rule_config[p.name])])),
    });
  };

  const changeType = (type: string) => {
    if (!catalog || !form) return;
    setForm({
      ...form,
      type,
      params: Object.fromEntries(catalog.types[type].params.map((p) => [p.name, toText(p.default)])),
    });
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form || !catalog) return;
    setSaving(true);
    setError(null);
    try {
      const spec = catalog.types[form.type];
      const cfg: Record<string, any> = { type: form.type, description: form.description || spec.label };
      for (const p of spec.params) {
        const raw = form.params[p.name];
        cfg[p.name] = p.type === 'boolean' ? raw === 'true' : raw;
      }
      const payload: RuleInput = {
        loan_type: form.loan_type,
        rule_name: form.rule_name,
        rule_config: cfg,
        is_active: form.is_active,
        is_mandatory: form.is_mandatory,
      };
      if (form.id) await updateRule(form.id, payload);
      else await createRule(payload);
      setForm(null);
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save the rule');
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (r: RuleItem) => {
    try {
      await setRuleActive(r.id, !r.is_active);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const remove = async (r: RuleItem) => {
    if (!window.confirm(`Delete rule "${r.rule_name}" for ${r.loan_type === '*' ? 'all products' : r.loan_type}?`)) return;
    try {
      await deleteRule(r.id);
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const summary = (r: RuleItem) => {
    const spec = catalog?.types[r.rule_config.type];
    if (!spec) return r.rule_config.description || '';
    return spec.params.map((p) => `${p.label}: ${toText(r.rule_config[p.name])}`).join(' • ');
  };

  const input =
    'w-full px-3 py-2 rounded-lg border border-[#C3D9CE] bg-white text-sm text-[#14241e] focus:outline-none focus:ring-2 focus:ring-[#6D9773]';

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl p-4 sm:p-5 shadow-sm border border-[#E5E9E1] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#EBF3EF] flex items-center justify-center text-[#0C3B2E]">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-[#0C3B2E]">Rules &amp; Regulations</h2>
            <p className="text-xs text-[#5e6d65]">
              Changes apply immediately to eligibility checks, limits, fraud checks and approvals.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select className={`${input} !w-auto`} value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="ALL">All products</option>
            {products.map((p) => (
              <option key={p} value={p}>
                {p === '*' ? 'Applies to all products' : p}
              </option>
            ))}
          </select>
          <button
            onClick={openNew}
            disabled={!catalog}
            className="flex items-center gap-1 px-3.5 py-2 rounded-lg bg-[#0C3B2E] text-white text-xs font-semibold hover:bg-[#165443] disabled:opacity-60"
          >
            <Plus className="w-3.5 h-3.5" /> New rule
          </button>
        </div>
      </div>

      {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>}

      <div className="bg-white rounded-2xl shadow-sm border border-[#E5E9E1] overflow-hidden">
        {loading ? (
          <p className="text-xs text-center py-10 text-[#5e6d65]">Loading rules...</p>
        ) : visible.length === 0 ? (
          <p className="text-xs text-center py-10 text-[#5e6d65]">No rules found.</p>
        ) : (
          <ul className="divide-y divide-[#F1F3EE]">
            {visible.map((r) => (
              <li key={r.id} className={`p-4 flex flex-col md:flex-row md:items-center gap-3 ${r.is_active ? '' : 'opacity-60'}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center flex-wrap gap-2">
                    <span className="text-sm font-bold text-[#14241e]">{r.rule_name}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EBF3EF] text-[#0C3B2E]">
                      {r.loan_type === '*' ? 'All products' : r.loan_type}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-800">
                      {categoryLabel[r.category || ''] || r.category}
                    </span>
                    {r.category === 'eligibility' && (
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          r.is_mandatory ? 'bg-red-50 text-red-800' : 'bg-amber-50 text-amber-800'
                        }`}
                      >
                        {r.is_mandatory ? 'Blocks approval' : 'Advisory'}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#5e6d65] mt-1">{r.rule_config.description}</p>
                  <p className="text-[11px] text-[#3b5346] mt-0.5 font-mono break-words">{summary(r)}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => toggle(r)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${
                      r.is_active
                        ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                        : 'border-[#C3D9CE] bg-white text-[#5e6d65]'
                    }`}
                  >
                    {r.is_active ? 'Active' : 'Inactive'}
                  </button>
                  <button onClick={() => openEdit(r)} title="Edit" className="p-2 rounded-lg border border-[#E5E9E1] hover:bg-[#F7F8F5]">
                    <Pencil className="w-3.5 h-3.5 text-[#0C3B2E]" />
                  </button>
                  <button onClick={() => remove(r)} title="Delete" className="p-2 rounded-lg border border-red-200 hover:bg-red-50">
                    <Trash2 className="w-3.5 h-3.5 text-red-700" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {form && catalog && (
        <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4 overflow-y-auto">
          <form onSubmit={save} className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-3 my-8">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-[#0C3B2E]">{form.id ? 'Edit rule' : 'New rule'}</h3>
              <button type="button" onClick={() => setForm(null)} className="p-1 rounded hover:bg-[#F7F8F5]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-[#3b5346] mb-1">Applies to</label>
                <input
                  list="loan-products"
                  className={input}
                  value={form.loan_type === '*' ? '*' : form.loan_type}
                  onChange={(e) => setForm({ ...form, loan_type: e.target.value })}
                  required
                />
                <datalist id="loan-products">
                  {products.map((p) => (
                    <option key={p} value={p} />
                  ))}
                </datalist>
                <p className="text-[10px] text-[#5e6d65] mt-1">Product name, or * for every product.</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-[#3b5346] mb-1">Rule name</label>
                <input className={input} value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} required />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[#3b5346] mb-1">Rule type</label>
              <select className={input} value={form.type} onChange={(e) => changeType(e.target.value)} disabled={!!form.id}>
                {Object.entries(catalog.types).map(([key, spec]) => (
                  <option key={key} value={key}>
                    {categoryLabel[spec.category]}: {spec.label}
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-[#5e6d65] mt-1">{catalog.types[form.type].description}</p>
            </div>

            {catalog.types[form.type].params.map((p) => (
              <div key={p.name}>
                <label className="block text-xs font-medium text-[#3b5346] mb-1">{p.label}</label>
                {p.type === 'boolean' ? (
                  <select
                    className={input}
                    value={form.params[p.name] === 'true' ? 'true' : 'false'}
                    onChange={(e) => setForm({ ...form, params: { ...form.params, [p.name]: e.target.value } })}
                  >
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                  </select>
                ) : (
                  <input
                    className={input}
                    value={form.params[p.name] ?? ''}
                    onChange={(e) => setForm({ ...form, params: { ...form.params, [p.name]: e.target.value } })}
                    required
                  />
                )}
              </div>
            ))}

            <div>
              <label className="block text-xs font-medium text-[#3b5346] mb-1">Description (shown to officers)</label>
              <input className={input} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>

            <div className="flex items-center gap-5 pt-1">
              <label className="flex items-center gap-2 text-xs text-[#3b5346]">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                Active
              </label>
              {catalog.types[form.type].category === 'eligibility' && (
                <label className="flex items-center gap-2 text-xs text-[#3b5346]">
                  <input type="checkbox" checked={form.is_mandatory} onChange={(e) => setForm({ ...form, is_mandatory: e.target.checked })} />
                  Blocks approval when not met
                </label>
              )}
            </div>

            {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setForm(null)} className="px-4 py-2 rounded-lg border border-[#E5E9E1] text-xs font-semibold">
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 rounded-lg bg-[#0C3B2E] text-white text-xs font-semibold hover:bg-[#165443] disabled:opacity-60"
              >
                {saving ? 'Saving...' : 'Save rule'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
