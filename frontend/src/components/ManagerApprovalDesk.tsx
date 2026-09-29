'use client';

import React, { useState, useEffect } from 'react';
import { ApplicationItem, AssessmentReport, Role } from '@/types';
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  RotateCcw,
  AlertTriangle,
  Lock,
  FileCheck2,
  Cpu,
  TrendingUp,
  Calculator,
  IndianRupee,
  Layers,
  Sparkles,
} from 'lucide-react';

interface ManagerApprovalDeskProps {
  currentRole: Role;
  reviewerName: string;
  reviewerId: string;
  applications: ApplicationItem[];
  onLoadDetails: (appId: string) => void;
  onApprove: (appId: string, remarks: string) => void;
  onReturn: (appId: string, remarks: string) => void;
  onReject: (appId: string, remarks: string) => void;
  onDisburse: (appId: string, interestRate: number) => void;
}

export const ManagerApprovalDesk: React.FC<ManagerApprovalDeskProps> = ({
  currentRole,
  reviewerName,
  reviewerId,
  applications,
  onLoadDetails,
  onApprove,
  onReturn,
  onReject,
  onDisburse,
}) => {
  // Applications in With Manager or Approved
  const managerQueue = applications.filter(
    (a) => a.stage === 'With Manager' || a.stage === 'Approved'
  );

  const [selectedAppId, setSelectedAppId] = useState<string>('');
  const [managerRemarks, setManagerRemarks] = useState('Sanctioned as per bank retail credit policy.');
  const [sanctionRate, setSanctionRate] = useState(8.75);

  const activeApp = managerQueue.find((a) => a.id === selectedAppId) || managerQueue[0];

  // Documents and rule results are loaded per application
  const activeAppId = activeApp?.id;
  useEffect(() => {
    if (activeAppId) onLoadDetails(activeAppId);
  }, [activeAppId, onLoadDetails]);

  // Maker-checker simulation: if currentRole is 'employee', they prepared it and cannot approve!
  const isMaker = currentRole === 'employee' || (!!activeApp?.prepared_by && activeApp.prepared_by === reviewerId);
  const shortId = (id?: string | null) => (id ? id.slice(0, 8) : '');
  const segregated = !!activeApp?.prepared_by && activeApp.prepared_by !== reviewerId;
  const isManager = currentRole === 'manager';

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-[#0C3B2E] to-[#165443] rounded-2xl p-6 text-white shadow-xl border border-[#165443] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="p-1.5 rounded-lg bg-[#FFBA00]/20 text-[#FFBA00]">
              <ShieldCheck className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold tracking-tight">Branch Manager Approval Desk</h2>
          </div>
          <p className="text-xs text-[#8eb494] mt-1 max-w-xl">
            Dual-control approval hierarchy. Review automated assessment reports, audit logs, and enforce maker-checker segregation.
          </p>
        </div>

        {/* Segregation Badge */}
        <div className="p-3 rounded-xl bg-[#07261d]/80 border border-[#165443] text-xs">
          <span className="text-[10px] text-[#8eb494] uppercase tracking-wider font-semibold">Active Reviewer</span>
          <p className="font-bold text-white mt-0.5">
            {reviewerName} ({isManager ? 'Branch Manager - Checker' : 'Underwriter - Maker'})
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Manager Queue (4 cols) */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="font-bold text-[#0C3B2E] text-sm">Manager Approval Queue</h3>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#FFBA00]/20 text-[#0C3B2E]">
              {managerQueue.length} Files
            </span>
          </div>

          <div className="space-y-2.5">
            {managerQueue.map((app) => {
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
                          : 'bg-indigo-100 text-indigo-800'
                      }`}
                    >
                      {app.stage}
                    </span>
                  </div>

                  <div className="mt-3 pt-2 border-t border-[#F1F3EE] flex items-center justify-between text-[11px] text-[#5e6d65]">
                    <span>Prepared by: {app.prepared_by ? `officer ${shortId(app.prepared_by)}` : 'not recorded'}</span>
                    <span className="text-[#6D9773] font-semibold">Review Dossier →</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Assessment Report Dossier & Decision Bar (8 cols) */}
        {activeApp && (
          <div className="lg:col-span-8 space-y-6">
            {/* Dossier Header */}
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
                    {activeApp.loan_type} • Income: ₹{activeApp.annual_income.toLocaleString()}/yr
                  </p>
                </div>

                <div className="text-right">
                  <span className="text-xs text-[#5e6d65]">Sanction Amount</span>
                  <p className="text-xl font-bold text-[#0C3B2E]">₹{activeApp.requested_amount.toLocaleString()}</p>
                </div>
              </div>

              {/* MAKER-CHECKER SECURITY BANNER */}
              <div className="mt-4 p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-xl bg-[#0C3B2E]/10 flex items-center justify-center text-[#0C3B2E]">
                    <ShieldCheck className="w-5 h-5 text-[#6D9773]" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-[#0C3B2E]">Maker-Checker Dual Control</h4>
                    <p className="text-[11px] text-[#5e6d65]">
                      Prepared by: <span className="font-semibold text-[#0C3B2E]">{activeApp.prepared_by ? `officer ${shortId(activeApp.prepared_by)}` : 'not recorded'}</span> • Checker: <span className="font-semibold text-[#0C3B2E]">{reviewerName}</span>
                    </p>
                  </div>
                </div>

                <span
                  className={`px-3 py-1 rounded-full text-[11px] font-bold shrink-0 ${
                    segregated ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                  }`}
                >
                  {segregated ? 'Segregation Verified' : 'Maker and checker not separated'}
                </span>
              </div>
            </div>

            {/* Assessment Report Content */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1] space-y-6">
              <div className="flex items-center justify-between pb-3 border-b border-[#F1F3EE]">
                <h4 className="font-bold text-[#0C3B2E] text-base">Comprehensive Assessment Dossier</h4>
                <span className="text-xs text-[#5e6d65]">Auto-compiled for Credit Committee</span>
              </div>

              {/* 4-Box Grid: KYC, Rules, Risk, Limit */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* 1. KYC Check */}
                <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#0C3B2E] flex items-center space-x-1.5">
                      <Lock className="w-3.5 h-3.5 text-[#6D9773]" />
                      <span>KYC Verification</span>
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        activeApp.kyc_verified ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {activeApp.kyc_verified ? 'Verified' : 'Not verified'}
                    </span>
                  </div>
                  <p className="text-xs text-[#5e6d65]">
                    Aadhaar: <span className="font-mono text-[#0C3B2E] font-semibold">{activeApp.kyc_data?.aadhaar_number || 'Not available'}</span>
                  </p>
                  <p className="text-xs text-[#5e6d65]">
                    PAN: <span className="font-mono text-[#0C3B2E] font-semibold">{activeApp.kyc_data?.pan_number || 'Not available'}</span>
                  </p>
                </div>

                {/* 2. Rules Evaluation */}
                <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#0C3B2E] flex items-center space-x-1.5">
                      <Cpu className="w-3.5 h-3.5 text-[#BB8A52]" />
                      <span>Policy Rules Engine</span>
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        activeApp.eligibility_total > 0 && activeApp.eligibility_passed === activeApp.eligibility_total
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {activeApp.eligibility_total > 0
                        ? `Passed ${activeApp.eligibility_passed} / ${activeApp.eligibility_total}`
                        : 'Not run'}
                    </span>
                  </div>
                  {activeApp.rule_results && activeApp.rule_results.length > 0 ? (
                    <ul className="space-y-1">
                      {activeApp.rule_results.map((r) => (
                        <li key={r.id} className="text-[11px] text-[#5e6d65] flex gap-1.5">
                          <span className={r.passed ? 'text-emerald-700' : 'text-red-700'}>{r.passed ? '✓' : '✗'}</span>
                          <span>
                            <span className="font-semibold text-[#0C3B2E]">{r.rule_name}</span>: {r.reason}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-[#5e6d65]">The officer has not run the eligibility rules yet.</p>
                  )}
                </div>

                {/* 3. Risk Score */}
                <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#0C3B2E] flex items-center space-x-1.5">
                      <TrendingUp className="w-3.5 h-3.5 text-[#6D9773]" />
                      <span>Credit Risk Score</span>
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#FFBA00] text-[#0C3B2E]">
                      {activeApp.risk_band ? `${activeApp.risk_band} Risk` : 'Not scored'}
                    </span>
                  </div>
                  <p className="text-sm font-extrabold text-[#0C3B2E]">
                    {activeApp.risk_score != null ? `${activeApp.risk_score} / 100` : 'Not scored yet'}
                  </p>
                </div>

                {/* 4. Permissible Limit */}
                <div className="p-4 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#0C3B2E] flex items-center space-x-1.5">
                      <Calculator className="w-3.5 h-3.5 text-[#BB8A52]" />
                      <span>Max Permissible Limit</span>
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                        activeApp.max_permissible_limit == null
                          ? 'bg-amber-100 text-amber-800'
                          : activeApp.requested_amount <= activeApp.max_permissible_limit
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {activeApp.max_permissible_limit == null
                        ? 'Not calculated'
                        : activeApp.requested_amount <= activeApp.max_permissible_limit
                        ? 'Within limit'
                        : 'Exceeds limit'}
                    </span>
                  </div>
                  <p className="text-sm font-extrabold text-[#6D9773]">
                    {activeApp.max_permissible_limit != null ? `₹${activeApp.max_permissible_limit.toLocaleString()}` : 'Not calculated yet'}
                  </p>
                  <p className="text-xs text-[#5e6d65]">Requested ₹{activeApp.requested_amount.toLocaleString()}</p>
                </div>
              </div>

              {/* Verified Documents Checklist */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-[#0C3B2E]">Verified Documents & Digital Hashes</span>
                <div className="space-y-1.5">
                  {activeApp.documents?.map((doc) => (
                    <div
                      key={doc.id}
                      className="p-2.5 rounded-lg bg-[#F7F8F5] border border-[#E5E9E1] flex items-center justify-between text-xs"
                    >
                      <span className="font-semibold text-[#0C3B2E]">{doc.document_type}: {doc.file_name}</span>
                      <span className="font-mono text-[10px] text-[#5e6d65]">
                        {doc.status}
                        {doc.fraud_flag ? ` • fraud: ${doc.fraud_flag.toLowerCase().replace('_', ' ')}` : ''} • SHA: {doc.file_hash.substring(0, 12)}...
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Manager Decision Input & Maker-Checker Warning */}
              <div className="pt-4 border-t border-[#F1F3EE] space-y-3">
                <label className="block text-xs font-semibold text-[#0C3B2E]">
                  Branch Manager Sanction Remarks
                </label>
                <textarea
                  rows={2}
                  value={managerRemarks}
                  onChange={(e) => setManagerRemarks(e.target.value)}
                  className="w-full text-xs p-3 rounded-xl border border-[#E5E9E1] outline-none focus:ring-2 focus:ring-[#0C3B2E]"
                />

                {/* Maker-Checker Alert if unauthorized user attempts to approve */}
                {isMaker && (
                  <div className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
                    <span>
                      Maker-Checker Violation: You are logged in as Underwriter (Maker) and prepared this application. Only Manager (Priya Mehta) can sanction it.
                    </span>
                  </div>
                )}

                {/* Manager Decision Action Buttons */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
                  <div className="flex items-center space-x-2 w-full sm:w-auto">
                    <button
                      disabled={isMaker}
                      onClick={() => onReturn(activeApp.id, managerRemarks)}
                      className={`px-4 py-2 text-xs font-bold rounded-xl border border-[#BB8A52] text-[#BB8A52] hover:bg-[#F7F8F5] transition-all flex items-center space-x-1 ${
                        isMaker ? 'opacity-40 cursor-not-allowed' : ''
                      }`}
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Return for Re-check</span>
                    </button>
                    <button
                      disabled={isMaker}
                      onClick={() => onReject(activeApp.id, managerRemarks)}
                      className={`px-4 py-2 text-xs font-bold rounded-xl border border-red-300 text-red-700 hover:bg-red-50 transition-all flex items-center space-x-1 ${
                        isMaker ? 'opacity-40 cursor-not-allowed' : ''
                      }`}
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>
                  </div>

                  <button
                    disabled={isMaker || activeApp.stage === 'Approved'}
                    onClick={() => onApprove(activeApp.id, managerRemarks)}
                    className={`px-6 py-2.5 text-xs font-bold rounded-xl transition-all shadow-md flex items-center space-x-1.5 ${
                      isMaker || activeApp.stage === 'Approved'
                        ? 'bg-stone-300 text-stone-500 cursor-not-allowed'
                        : 'bg-emerald-700 hover:bg-emerald-800 text-white'
                    }`}
                  >
                    <CheckCircle2 className="w-4 h-4 text-[#FFBA00]" />
                    <span>
                      {activeApp.stage === 'Approved' ? 'Application Sanctioned' : 'Sanction & Approve Loan'}
                    </span>
                  </button>
                </div>
              </div>

              {/* Loan Disbursement Trigger (Available once Approved) */}
              {activeApp.stage === 'Approved' && (
                <div className="mt-4 p-5 rounded-xl bg-gradient-to-r from-[#0C3B2E] to-[#165443] text-white flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div>
                    <h5 className="font-bold text-sm text-[#FFBA00] flex items-center space-x-1.5">
                      <Sparkles className="w-4 h-4" />
                      <span>Application Sanctioned • Ready for Disbursement</span>
                    </h5>
                    <p className="text-xs text-[#8eb494] mt-1">
                      Trigger loan disbursement to credit customer account and activate the reducing-balance EMI schedule.
                    </p>
                  </div>

                  <button
                    onClick={() => onDisburse(activeApp.id, sanctionRate)}
                    className="px-5 py-2.5 rounded-xl bg-[#FFBA00] text-[#0C3B2E] text-xs font-bold shadow hover:brightness-105 active:scale-95 transition-all shrink-0"
                  >
                    Disburse ₹{activeApp.requested_amount.toLocaleString()}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
