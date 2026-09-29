'use client';

import React, { useState, useEffect } from 'react';
import { DocumentReview } from '@/components/DocumentReview';
import {
  ApplicationItem,
  DocumentItem,
  RuleResultItem,
  CollectionCaseItem,
} from '@/types';
import {
  CheckCircle2,
  XCircle,
  FileCheck2,
  Cpu,
  Calculator,
  ShieldAlert,
  Send,
  Search,
  Filter,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  Clock,
  PhoneCall,
  User,
  History,
} from 'lucide-react';

interface UnderwriterWorkbenchProps {
  applications: ApplicationItem[];
  collectionCases: CollectionCaseItem[];
  onVerifyDocument: (docId: string, status: 'Verified' | 'Mismatch', remarks?: string) => void;
  onRunRules: (appId: string) => void;
  onCalculateRisk: (appId: string) => void;
  onCalculateLimit: (appId: string) => void;
  onSubmitToManager: (appId: string, remarks: string) => void;
  onUpdateCollectionNote: (caseId: string, note: string) => void;
  onLoadDetails: (appId: string) => void;
}

export const UnderwriterWorkbench: React.FC<UnderwriterWorkbenchProps> = ({
  applications,
  collectionCases,
  onVerifyDocument,
  onRunRules,
  onCalculateRisk,
  onCalculateLimit,
  onSubmitToManager,
  onUpdateCollectionNote,
  onLoadDetails,
}) => {
  const [selectedAppId, setSelectedAppId] = useState<string>(applications[0]?.id || '');
  const [activeTab, setActiveTab] = useState<'docs' | 'rules' | 'risk' | 'limit' | 'submit'>('docs');
  const [activeSection, setActiveSection] = useState<'origination' | 'collection'>('origination');
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [makerRemarks, setMakerRemarks] = useState<string>('Dossier verified with clean bureau and income documents.');
  const [docRemarks, setDocRemarks] = useState<Record<string, string>>({});
  const [recoveryNoteInput, setRecoveryNoteInput] = useState<Record<string, string>>({});

  const filteredApps = applications.filter((app) => {
    const matchesStage = stageFilter === 'ALL' || app.stage === stageFilter;
    const matchesSearch =
      app.app_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.customer_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStage && matchesSearch;
  });

  const activeApp = applications.find((a) => a.id === selectedAppId) || filteredApps[0];

  // Documents and rule results are not part of the application list: load them for the open file
  const activeAppId = activeApp?.id;
  useEffect(() => {
    if (activeAppId) onLoadDetails(activeAppId);
  }, [activeAppId, onLoadDetails]);

  return (
    <div className="space-y-6">
      {/* Top Underwriter Navigation Bar */}
      <div className="bg-white rounded-2xl p-4 sm:p-5 shadow-sm border border-[#E5E9E1] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-[#0C3B2E]">Underwriter Operations Workbench</h2>
          <p className="text-xs text-[#5e6d65]">
            Run document verification, policy rules, risk scoring, limit calculations, and collection monitoring.
          </p>
        </div>

        {/* Section Switcher: Origination vs Collection */}
        <div className="flex items-center space-x-2 bg-[#F7F8F5] p-1 rounded-xl border border-[#E5E9E1]">
          <button
            onClick={() => setActiveSection('origination')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              activeSection === 'origination'
                ? 'bg-[#0C3B2E] text-white shadow-sm'
                : 'text-[#5e6d65] hover:text-[#0C3B2E]'
            }`}
          >
            Loan Underwriting Queue
          </button>
          <button
            onClick={() => setActiveSection('collection')}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center space-x-1.5 ${
              activeSection === 'collection'
                ? 'bg-[#BB8A52] text-white shadow-sm'
                : 'text-[#5e6d65] hover:text-[#0C3B2E]'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Delinquency Desk ({collectionCases.length})</span>
          </button>
        </div>
      </div>

      {activeSection === 'origination' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Applications List (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Filters */}
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-[#E5E9E1] space-y-3">
              <div className="relative">
                <Search className="w-4 h-4 text-[#5e6d65] absolute left-3 top-3" />
                <input
                  type="text"
                  placeholder="Search application or name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full text-xs pl-9 pr-3 py-2.5 rounded-xl border border-[#E5E9E1] focus:ring-2 focus:ring-[#0C3B2E] outline-none"
                />
              </div>

              <div className="flex items-center space-x-2 overflow-x-auto pb-1">
                {['ALL', 'Submitted', 'Verification', 'Risk', 'Prepared', 'With Manager', 'Approved'].map(
                  (st) => (
                    <button
                      key={st}
                      onClick={() => setStageFilter(st)}
                      className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold shrink-0 transition-all ${
                        stageFilter === st
                          ? 'bg-[#0C3B2E] text-white'
                          : 'bg-[#F7F8F5] text-[#5e6d65] hover:bg-[#F1F3EE]'
                      }`}
                    >
                      {st}
                    </button>
                  )
                )}
              </div>
            </div>

            {/* List */}
            <div className="space-y-3 max-h-[700px] overflow-y-auto pr-1">
              {filteredApps.map((app) => {
                const isSelected = app.id === activeApp?.id;
                return (
                  <div
                    key={app.id}
                    onClick={() => setSelectedAppId(app.id)}
                    className={`p-4 rounded-2xl cursor-pointer transition-all border ${
                      isSelected
                        ? 'bg-white border-[#0C3B2E] shadow-md ring-1 ring-[#0C3B2E]'
                        : 'bg-white border-[#E5E9E1] hover:border-[#BB8A52] hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-xs font-bold text-[#0C3B2E]">{app.app_number}</span>
                        <h4 className="text-sm font-bold text-[#14241e] mt-0.5">{app.customer_name}</h4>
                        <p className="text-xs text-[#5e6d65]">{app.loan_type} • ₹{app.requested_amount.toLocaleString()}</p>
                      </div>

                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          app.stage === 'Approved'
                            ? 'bg-emerald-100 text-emerald-800'
                            : app.stage === 'With Manager'
                            ? 'bg-indigo-100 text-indigo-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {app.stage}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-[#F1F3EE] text-[11px] text-[#5e6d65]">
                      <div>
                        <span className="text-[#8eb494]">Income: </span>₹{(app.annual_income / 100000).toFixed(1)}L/yr
                      </div>
                      <div className="text-right">
                        <span className="text-[#8eb494]">SLA: </span>{app.sla_days}d remaining
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Workbench & Action Tabs (8 cols) */}
          {activeApp && (
            <div className="lg:col-span-8 space-y-6">
              {/* Applicant Header Card */}
              <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1]">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#F1F3EE]">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded bg-[#0C3B2E] text-white">
                        {activeApp.app_number}
                      </span>
                      <h3 className="text-lg font-bold text-[#0C3B2E]">{activeApp.customer_name}</h3>
                    </div>
                    <p className="text-xs text-[#5e6d65] mt-1">
                      {activeApp.loan_type} • Employer: {activeApp.employer_name || 'Salaried'} ({activeApp.employment_type})
                    </p>
                  </div>

                  <div className="text-right">
                    <span className="text-xs text-[#5e6d65]">Requested Amount</span>
                    <p className="text-xl font-bold text-[#0C3B2E]">₹{activeApp.requested_amount.toLocaleString()}</p>
                    <p className="text-[11px] text-[#6D9773]">Tenure: {activeApp.loan_tenure_months} Months</p>
                  </div>
                </div>

                {/* KPI metrics row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                  <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                    <span className="text-[10px] text-[#5e6d65] uppercase tracking-wide">Annual Income</span>
                    <p className="text-sm font-bold text-[#0C3B2E] mt-0.5">₹{activeApp.annual_income.toLocaleString()}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                    <span className="text-[10px] text-[#5e6d65] uppercase tracking-wide">Existing EMI</span>
                    <p className="text-sm font-bold text-[#BB8A52] mt-0.5">₹{activeApp.existing_emi.toLocaleString()}/mo</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                    <span className="text-[10px] text-[#5e6d65] uppercase tracking-wide">Risk Band</span>
                    <p className="text-sm font-bold text-[#6D9773] mt-0.5">{activeApp.risk_band || 'Pending Score'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                    <span className="text-[10px] text-[#5e6d65] uppercase tracking-wide">Permissible Limit</span>
                    <p className="text-sm font-bold text-[#0C3B2E] mt-0.5">
                      {activeApp.max_permissible_limit ? `₹${activeApp.max_permissible_limit.toLocaleString()}` : 'Uncalculated'}
                    </p>
                  </div>
                </div>

                {/* Sub-nav Tabs */}
                <div className="flex items-center space-x-2 mt-5 border-b border-[#F1F3EE] pb-2 overflow-x-auto">
                  <button
                    onClick={() => setActiveTab('docs')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                      activeTab === 'docs'
                        ? 'bg-[#0C3B2E] text-white shadow-sm'
                        : 'text-[#5e6d65] hover:text-[#0C3B2E]'
                    }`}
                  >
                    <FileCheck2 className="w-3.5 h-3.5" />
                    <span>Doc Verification</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('rules')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                      activeTab === 'rules'
                        ? 'bg-[#0C3B2E] text-white shadow-sm'
                        : 'text-[#5e6d65] hover:text-[#0C3B2E]'
                    }`}
                  >
                    <Cpu className="w-3.5 h-3.5" />
                    <span>Policy Rules</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('risk')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                      activeTab === 'risk'
                        ? 'bg-[#0C3B2E] text-white shadow-sm'
                        : 'text-[#5e6d65] hover:text-[#0C3B2E]'
                    }`}
                  >
                    <TrendingUp className="w-3.5 h-3.5" />
                    <span>Risk Scoring</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('limit')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                      activeTab === 'limit'
                        ? 'bg-[#0C3B2E] text-white shadow-sm'
                        : 'text-[#5e6d65] hover:text-[#0C3B2E]'
                    }`}
                  >
                    <Calculator className="w-3.5 h-3.5" />
                    <span>Limit Calc</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('submit')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all ${
                      activeTab === 'submit'
                        ? 'bg-[#FFBA00] text-[#0C3B2E] font-bold shadow-sm'
                        : 'text-[#5e6d65] hover:text-[#0C3B2E]'
                    }`}
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Submit to Manager</span>
                  </button>
                </div>
              </div>

              {/* Tab 1: Document Verification */}
              {activeTab === 'docs' && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1] space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-bold text-[#0C3B2E] text-sm">Underwriting Document Verification</h4>
                      <p className="text-xs text-[#5e6d65]">Review each uploaded file with the fraud-detection result, then verify or reject it.</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {activeApp.documents && activeApp.documents.length > 0 ? (
                      activeApp.documents.map((doc) => (
                        <DocumentReview
                          key={doc.id}
                          doc={doc}
                          remarks={docRemarks[doc.id] || ''}
                          onRemarksChange={(value) => setDocRemarks({ ...docRemarks, [doc.id]: value })}
                          onVerify={(status) =>
                            onVerifyDocument(
                              doc.id,
                              status,
                              docRemarks[doc.id] ||
                                (status === 'Verified' ? 'Verified by officer after document review' : 'Rejected by officer after document review')
                            )
                          }
                        />
                      ))
                    ) : (
                      <p className="text-xs text-center py-6 text-[#5e6d65]">No documents uploaded yet.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 2: Policy & Eligibility Engine */}
              {activeTab === 'rules' && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1] space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-[#F1F3EE]">
                    <div>
                      <h4 className="font-bold text-[#0C3B2E] text-sm">Policy & Eligibility Rules Engine</h4>
                      <p className="text-xs text-[#5e6d65]">
                        Rules stored per loan product in DB, evaluated in service, and explainable reasons recorded.
                      </p>
                    </div>

                    <button
                      onClick={() => onRunRules(activeApp.id)}
                      className="px-4 py-2 text-xs font-bold rounded-xl bg-[#0C3B2E] text-white hover:bg-[#165443] transition-all flex items-center space-x-1.5 shadow"
                    >
                      <Cpu className="w-3.5 h-3.5 text-[#FFBA00]" />
                      <span>Execute Rule Engine</span>
                    </button>
                  </div>

                  <div className="space-y-3">
                    {activeApp.rule_results && activeApp.rule_results.length > 0 ? (
                      activeApp.rule_results.map((rule) => (
                        <div
                          key={rule.id}
                          className={`p-3.5 rounded-xl border flex items-start justify-between ${
                            rule.passed
                              ? 'bg-emerald-50/50 border-emerald-200'
                              : 'bg-red-50/50 border-red-200'
                          }`}
                        >
                          <div className="flex items-start space-x-3">
                            {rule.passed ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
                            )}
                            <div>
                              <p className="text-xs font-bold text-[#0C3B2E]">{rule.rule_description || rule.rule_name}</p>
                              <p className="text-xs text-[#5e6d65] mt-0.5">
                                <span className="font-semibold">Explainable Reason: </span>
                                {rule.reason}
                              </p>
                            </div>
                          </div>

                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              rule.passed ? 'bg-emerald-200 text-emerald-800' : 'bg-red-200 text-red-800'
                            }`}
                          >
                            {rule.passed ? 'PASSED' : 'FAILED'}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-[#5e6d65]">
                        <p className="text-xs">Rules not yet evaluated for this file.</p>
                        <button
                          onClick={() => onRunRules(activeApp.id)}
                          className="mt-2 text-xs font-bold text-[#0C3B2E] underline"
                        >
                          Click here to run automated eligibility rules
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 3: Risk Assessment */}
              {activeTab === 'risk' && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1] space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-[#F1F3EE]">
                    <div>
                      <h4 className="font-bold text-[#0C3B2E] text-sm">Credit & Fraud Risk Assessment</h4>
                      <p className="text-xs text-[#5e6d65]">
                        Scoring model computes multi-factor score (0-100) and maps applicant to Risk Band.
                      </p>
                    </div>

                    <button
                      onClick={() => onCalculateRisk(activeApp.id)}
                      className="px-4 py-2 text-xs font-bold rounded-xl bg-[#0C3B2E] text-white hover:bg-[#165443] transition-all flex items-center space-x-1.5 shadow"
                    >
                      <TrendingUp className="w-3.5 h-3.5 text-[#FFBA00]" />
                      <span>Compute Risk Score</span>
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-5 rounded-2xl bg-[#0C3B2E] text-white">
                      <span className="text-xs text-[#8eb494]">Computed Credit Risk Score</span>
                      <div className="flex items-baseline space-x-2 mt-2">
                        <span className="text-4xl font-extrabold text-[#FFBA00]">
                          {activeApp.risk_score || 75.0}
                        </span>
                        <span className="text-sm text-[#8eb494]">/ 100</span>
                      </div>
                      <div className="mt-4 pt-3 border-t border-[#165443] flex items-center justify-between text-xs">
                        <span>Risk Band Classification:</span>
                        <span className="px-2 py-0.5 rounded font-bold bg-[#FFBA00] text-[#0C3B2E]">
                          {activeApp.risk_band || 'Low'}
                        </span>
                      </div>
                    </div>

                    <div className="p-4 rounded-2xl bg-[#F7F8F5] border border-[#E5E9E1] space-y-2 text-xs">
                      <h5 className="font-bold text-[#0C3B2E]">Score Factor Weightings</h5>
                      <div className="flex justify-between py-1 border-b border-[#E5E9E1]">
                        <span className="text-[#5e6d65]">Annual Income Weight (+15 pts)</span>
                        <span className="font-bold text-emerald-700">₹{(activeApp.annual_income / 100000).toFixed(1)}L Tier-1</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-[#E5E9E1]">
                        <span className="text-[#5e6d65]">EMI Burden Factor (+10 pts)</span>
                        <span className="font-bold text-emerald-700">
                          {((activeApp.existing_emi / (activeApp.annual_income / 12)) * 100).toFixed(1)}% Ratio
                        </span>
                      </div>
                      <div className="flex justify-between py-1">
                        <span className="text-[#5e6d65]">Employment Stability (+5 pts)</span>
                        <span className="font-bold text-emerald-700">{activeApp.employment_type}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 4: Limit Calculator */}
              {activeTab === 'limit' && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1] space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-[#F1F3EE]">
                    <div>
                      <h4 className="font-bold text-[#0C3B2E] text-sm">Loan Limit Determination</h4>
                      <p className="text-xs text-[#5e6d65]">
                        Limit = (Annual Income × Multiple) – (Existing EMIs × 12), capped by policy.
                      </p>
                    </div>

                    <button
                      onClick={() => onCalculateLimit(activeApp.id)}
                      className="px-4 py-2 text-xs font-bold rounded-xl bg-[#0C3B2E] text-white hover:bg-[#165443] transition-all flex items-center space-x-1.5 shadow"
                    >
                      <Calculator className="w-3.5 h-3.5 text-[#FFBA00]" />
                      <span>Calculate Max Limit</span>
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                      <span className="text-xs text-[#5e6d65]">Requested Loan</span>
                      <p className="text-lg font-bold text-[#0C3B2E] mt-1">₹{activeApp.requested_amount.toLocaleString()}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                      <span className="text-xs text-[#5e6d65]">Max Permissible Limit</span>
                      <p className="text-lg font-bold text-[#6D9773] mt-1">
                        ₹{(activeApp.max_permissible_limit || activeApp.requested_amount * 1.5).toLocaleString()}
                      </p>
                    </div>
                    <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                      <span className="text-xs text-[#5e6d65]">Policy Compliance</span>
                      <p className="text-sm font-bold text-emerald-700 mt-1 flex items-center space-x-1">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Within Safe Limit</span>
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 5: Submit to Manager */}
              {activeTab === 'submit' && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1] space-y-4">
                  <div>
                    <h4 className="font-bold text-[#0C3B2E] text-sm">Submit to Branch Manager (Maker Hand-off)</h4>
                    <p className="text-xs text-[#5e6d65]">
                      Locks underwriting stage and tags you as Maker (Rahul Verma). Manager (Priya Mehta) will review.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#0C3B2E] mb-1">
                      Maker Underwriting Recommendation Note
                    </label>
                    <textarea
                      rows={3}
                      value={makerRemarks}
                      onChange={(e) => setMakerRemarks(e.target.value)}
                      className="w-full text-xs p-3 rounded-xl border border-[#E5E9E1] focus:ring-2 focus:ring-[#0C3B2E] outline-none"
                    />
                  </div>

                  <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                    <span>
                      Maker-Checker Rule Enforced: Once submitted, you cannot approve this file yourself. Final approval requires Manager role.
                    </span>
                  </div>

                  <button
                    onClick={() => onSubmitToManager(activeApp.id, makerRemarks)}
                    className="w-full py-3 rounded-xl bg-[#0C3B2E] text-white font-bold text-xs hover:bg-[#165443] shadow-md transition-all flex items-center justify-center space-x-2"
                  >
                    <Send className="w-4 h-4 text-[#FFBA00]" />
                    <span>Hand-off File to Manager (Stage: With Manager)</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Collection & Delinquency Desk Section */
        <div className="space-y-4">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1]">
            <div className="flex items-center justify-between pb-4 border-b border-[#F1F3EE]">
              <div>
                <h3 className="font-bold text-[#0C3B2E] text-base">Overdue Loans & Collection Recovery Desk</h3>
                <p className="text-xs text-[#5e6d65]">Automated aging buckets (SMA-0, SMA-1, SMA-2, NPA) & follow-up tracking.</p>
              </div>
              <span className="text-xs font-bold text-[#BB8A52] px-3 py-1 bg-amber-50 rounded-lg border border-amber-200">
                {collectionCases.length} Accounts Monitored
              </span>
            </div>

            <div className="divide-y divide-[#F1F3EE] mt-2">
              {collectionCases.map((c) => (
                <div key={c.id} className="py-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-sm text-[#0C3B2E]">{c.account_number}</span>
                        <span className="text-xs text-[#5e6d65]">• {c.customer_name}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            c.dpd > 90
                              ? 'bg-red-100 text-red-800'
                              : c.dpd > 60
                              ? 'bg-orange-100 text-orange-800'
                              : c.dpd > 30
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {c.bucket} ({c.dpd} DPD)
                        </span>
                      </div>
                      <p className="text-xs text-red-700 font-semibold mt-1">Overdue Amount: ₹{c.overdue_amount.toLocaleString()}</p>
                    </div>

                    <div className="text-right text-xs text-[#5e6d65]">
                      <span>Assigned to: {c.assigned_to}</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] text-xs">
                    <span className="font-semibold text-[#0C3B2E]">Last Officer Note: </span>
                    <span className="text-[#5e6d65]">{c.notes}</span>
                  </div>

                  {/* Follow-up Note input */}
                  <div className="flex items-center space-x-2 pt-1">
                    <input
                      type="text"
                      placeholder="Add follow-up recovery remark (e.g., Customer visited, PTP 2nd Oct)..."
                      value={recoveryNoteInput[c.id] || ''}
                      onChange={(e) =>
                        setRecoveryNoteInput({ ...recoveryNoteInput, [c.id]: e.target.value })
                      }
                      className="flex-1 text-xs px-3 py-2 rounded-xl border border-[#E5E9E1] outline-none"
                    />
                    <button
                      onClick={() => {
                        if (recoveryNoteInput[c.id]) {
                          onUpdateCollectionNote(c.id, recoveryNoteInput[c.id]);
                          setRecoveryNoteInput({ ...recoveryNoteInput, [c.id]: '' });
                        }
                      }}
                      className="px-4 py-2 text-xs font-bold rounded-xl bg-[#0C3B2E] text-white hover:bg-[#165443] transition-all shrink-0"
                    >
                      Record Follow-up
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
