'use client';

import React, { useState } from 'react';
import { ApplicationItem, LoanAccountItem, DocumentItem } from '@/types';
import {
  FileText,
  Upload,
  CheckCircle2,
  Clock,
  AlertTriangle,
  CreditCard,
  Calendar,
  IndianRupee,
  ShieldCheck,
  ChevronRight,
  PlusCircle,
  X,
  FileCheck2,
  Lock,
} from 'lucide-react';

interface CustomerPortalProps {
  applications: ApplicationItem[];
  loanAccount?: LoanAccountItem;
  onNewApplication: (data: Partial<ApplicationItem>) => void;
  onUploadDocument: (appId: string, docType: string, fileName: string, fileHash: string) => boolean;
  onPayEmi: (accountId: string, amount: number) => void;
}

export const CustomerPortal: React.FC<CustomerPortalProps> = ({
  applications,
  loanAccount,
  onNewApplication,
  onUploadDocument,
  onPayEmi,
}) => {
  const [selectedAppId, setSelectedAppId] = useState<string>(applications[0]?.id || '');
  const [isApplyModalOpen, setIsApplyModalOpen] = useState(false);
  const [isPayModalOpen, setIsPayModalOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [docUploadError, setDocUploadError] = useState<string | null>(null);

  // Apply form state
  const [loanType, setLoanType] = useState('Home Loan');
  const [amount, setAmount] = useState(2500000);
  const [tenure, setTenure] = useState(120);
  const [income, setIncome] = useState(1200000);
  const [existingEmi, setExistingEmi] = useState(8000);
  const [employer, setEmployer] = useState('Tata Consultancy Services');
  const [employmentType, setEmploymentType] = useState('Salaried');

  // Selected application
  const activeApp = applications.find((a) => a.id === selectedAppId) || applications[0];

  // Estimated EMI
  const calculateEstimatedEmi = (p: number, n: number, rate = 8.75) => {
    const r = rate / 12 / 100;
    const emi = (p * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
    return Math.round(emi);
  };

  const stages = [
    'Draft',
    'Submitted',
    'KYC',
    'Docs',
    'Verification',
    'Risk',
    'Prepared',
    'With Manager',
    'Approved',
  ];

  const getStageIndex = (stage: string) => {
    const idx = stages.indexOf(stage);
    return idx === -1 ? 0 : idx;
  };

  // Mock document upload with duplicate check demo
  const handleFileUpload = (docType: string, e: React.ChangeEvent<HTMLInputElement>) => {
    setDocUploadError(null);
    const file = e.target.files?.[0];
    if (!file || !activeApp) return;

    // Simulate simple hash check
    const mockHash = `hash_${file.name.replace(/\s+/g, '_')}_${file.size}`;
    const success = onUploadDocument(activeApp.id, docType, file.name, mockHash);
    if (!success) {
      setDocUploadError(`Duplicate detected! The file "${file.name}" has already been uploaded previously.`);
    }
  };

  const handleApplySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onNewApplication({
      loan_type: loanType,
      requested_amount: Number(amount),
      loan_tenure_months: Number(tenure),
      annual_income: Number(income),
      existing_emi: Number(existingEmi),
      employer_name: employer,
      employment_type: employmentType,
      customer_name: 'Amit Sharma',
    });
    setIsApplyModalOpen(false);
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Hero / Quick Stats */}
      <div className="bg-gradient-to-r from-[#0C3B2E] via-[#165443] to-[#0C3B2E] rounded-2xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden border border-[#165443]">
        <div className="absolute right-0 top-0 bottom-0 w-96 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-[#FFBA00]/20 via-transparent to-transparent pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-[#FFBA00]/15 text-[#FFBA00] text-xs font-semibold mb-3 border border-[#FFBA00]/30">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>KYC Verified Borrower</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Welcome, Amit Sharma</h1>
            <p className="text-sm text-[#8eb494] mt-1 max-w-xl">
              Track live approval stages, view explainable rule decisions, and manage your active loan repayments seamlessly.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setIsApplyModalOpen(true)}
              className="flex items-center space-x-2 px-5 py-3 rounded-xl bg-gradient-to-r from-[#FFBA00] to-[#BB8A52] text-[#0C3B2E] font-bold text-sm shadow-lg hover:brightness-105 active:scale-95 transition-all"
            >
              <PlusCircle className="w-4 h-4 stroke-[2.5]" />
              <span>Apply for New Loan</span>
            </button>
          </div>
        </div>

        {/* Quick Numbers Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-[#165443]/80">
          <div className="bg-[#07261d]/60 backdrop-blur p-4 rounded-xl border border-[#165443]">
            <p className="text-xs text-[#8eb494]">Active Disbursed Loan</p>
            <p className="text-xl font-bold text-white mt-1">₹50,00,000</p>
            <p className="text-[11px] text-[#FFBA00] mt-0.5">Account: LN-1042 (Home Loan)</p>
          </div>
          <div className="bg-[#07261d]/60 backdrop-blur p-4 rounded-xl border border-[#165443]">
            <p className="text-xs text-[#8eb494]">Next Upcoming EMI</p>
            <p className="text-xl font-bold text-white mt-1">₹44,186</p>
            <p className="text-[11px] text-[#6D9773] mt-0.5">Due on 5th Oct 2026</p>
          </div>
          <div className="bg-[#07261d]/60 backdrop-blur p-4 rounded-xl border border-[#165443]">
            <p className="text-xs text-[#8eb494]">Pre-Approved Credit Limit</p>
            <p className="text-xl font-bold text-white mt-1">₹85,00,000</p>
            <p className="text-[11px] text-[#8eb494] mt-0.5">Based on Tier-1 salary policy</p>
          </div>
        </div>
      </div>

      {/* Active Loan Servicing & Repayment Card */}
      {loanAccount && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 border-b border-[#F1F3EE] gap-4">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-xl bg-[#0C3B2E] text-white flex items-center justify-center font-bold text-lg">
                <CreditCard className="w-6 h-6 text-[#FFBA00]" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-lg font-bold text-[#0C3B2E]">Loan Servicing & Repayment</h2>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
                    Active Account
                  </span>
                </div>
                <p className="text-xs text-[#5e6d65]">Account No: {loanAccount.account_number} • Tenure: {loanAccount.tenure_months} Months</p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-[#F7F8F5] text-[#0C3B2E] border border-[#E5E9E1] hover:bg-[#F1F3EE] transition-all"
              >
                View Amortization Schedule
              </button>
              <button
                onClick={() => setIsPayModalOpen(true)}
                className="px-5 py-2 text-xs font-bold rounded-xl bg-[#0C3B2E] text-white hover:bg-[#165443] shadow-md transition-all flex items-center space-x-1.5"
              >
                <IndianRupee className="w-3.5 h-3.5 text-[#FFBA00]" />
                <span>Pay Next EMI</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
            <div className="p-3.5 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
              <span className="text-xs text-[#5e6d65]">Principal Amount</span>
              <p className="text-base font-bold text-[#0C3B2E] mt-1">₹{loanAccount.principal_amount.toLocaleString()}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
              <span className="text-xs text-[#5e6d65]">Outstanding Balance</span>
              <p className="text-base font-bold text-[#BB8A52] mt-1">₹{loanAccount.outstanding_balance.toLocaleString()}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
              <span className="text-xs text-[#5e6d65]">Monthly EMI</span>
              <p className="text-base font-bold text-[#0C3B2E] mt-1">₹{loanAccount.emi_amount.toLocaleString()}</p>
            </div>
            <div className="p-3.5 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
              <span className="text-xs text-[#5e6d65]">Annual Interest Rate</span>
              <p className="text-base font-bold text-[#6D9773] mt-1">{loanAccount.interest_rate}% p.a.</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid: Application Selector & Stage Tracker */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Applications List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-[#0C3B2E] text-base">Your Applications</h3>
            <span className="text-xs text-[#5e6d65]">{applications.length} Found</span>
          </div>

          <div className="space-y-3">
            {applications.map((app) => {
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
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold text-[#0C3B2E]">{app.app_number}</span>
                        <span className="text-xs text-[#5e6d65]">• {app.loan_type}</span>
                      </div>
                      <p className="text-base font-bold text-[#0C3B2E] mt-1">₹{app.requested_amount.toLocaleString()}</p>
                    </div>

                    <span
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold ${
                        app.stage === 'Approved'
                          ? 'bg-emerald-100 text-emerald-800'
                          : app.stage === 'With Manager'
                          ? 'bg-indigo-100 text-indigo-800'
                          : app.stage === 'Verification'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-stone-100 text-stone-800'
                      }`}
                    >
                      {app.stage}
                    </span>
                  </div>

                  <div className="flex items-center justify-between mt-3 pt-3 border-t border-[#F1F3EE] text-[11px] text-[#5e6d65]">
                    <span>Tenure: {app.loan_tenure_months}m</span>
                    <span className="flex items-center text-[#6D9773] font-medium">
                      View tracker <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Live Tracker, KYC & Documents */}
        {activeApp && (
          <div className="lg:col-span-2 space-y-6">
            {/* Live State Machine Stepper */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1]">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="font-bold text-[#0C3B2E] text-base">Live Application Journey</h3>
                  <p className="text-xs text-[#5e6d65]">Tracking File {activeApp.app_number} ({activeApp.loan_type})</p>
                </div>
                <div className="flex items-center space-x-1.5 text-xs text-[#0C3B2E] bg-[#F7F8F5] px-3 py-1.5 rounded-lg border border-[#E5E9E1]">
                  <Clock className="w-3.5 h-3.5 text-[#BB8A52]" />
                  <span>SLA: {activeApp.sla_days} Days</span>
                </div>
              </div>

              {/* Horizontal Stepper */}
              <div className="relative">
                <div className="overflow-x-auto pb-4">
                  <div className="flex items-center min-w-[620px] justify-between relative">
                    {/* Connecting line */}
                    <div className="absolute top-4 left-6 right-6 h-0.5 bg-[#E5E9E1] -z-0" />
                    <div
                      className="absolute top-4 left-6 h-0.5 bg-[#0C3B2E] transition-all duration-500 -z-0"
                      style={{
                        width: `${(getStageIndex(activeApp.stage) / (stages.length - 1)) * 90}%`,
                      }}
                    />

                    {stages.map((st, idx) => {
                      const currentIdx = getStageIndex(activeApp.stage);
                      const isCompleted = idx < currentIdx;
                      const isCurrent = idx === currentIdx;

                      return (
                        <div key={st} className="flex flex-col items-center relative z-10 flex-1">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs transition-all ${
                              isCompleted
                                ? 'bg-[#0C3B2E] text-white'
                                : isCurrent
                                ? 'bg-[#FFBA00] text-[#0C3B2E] ring-4 ring-[#FFBA00]/30 animate-pulse-subtle'
                                : 'bg-white border-2 border-[#E5E9E1] text-[#5e6d65]'
                            }`}
                          >
                            {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : idx + 1}
                          </div>
                          <span
                            className={`text-[10px] mt-2 font-medium text-center ${
                              isCurrent ? 'text-[#0C3B2E] font-bold' : isCompleted ? 'text-[#6D9773]' : 'text-[#5e6d65]'
                            }`}
                          >
                            {st}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* KYC Profile & Masking Card */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1]">
              <div className="flex items-center justify-between pb-4 border-b border-[#F1F3EE]">
                <div className="flex items-center space-x-2.5">
                  <div className="w-8 h-8 rounded-lg bg-[#0C3B2E]/10 flex items-center justify-center text-[#0C3B2E]">
                    <Lock className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="font-bold text-[#0C3B2E] text-sm">KYC Verification & Data Privacy</h4>
                    <p className="text-[11px] text-[#5e6d65]">Sensitive identifiers securely masked (Only last 4 digits stored)</p>
                  </div>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 flex items-center space-x-1">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>UIDAI Verified</span>
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                  <span className="text-[11px] text-[#5e6d65]">Aadhaar Number</span>
                  <p className="text-sm font-semibold font-mono text-[#0C3B2E] mt-0.5">
                    {activeApp.kyc_data?.aadhaar_number || '•••• •••• 9012'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                  <span className="text-[11px] text-[#5e6d65]">PAN Card</span>
                  <p className="text-sm font-semibold font-mono text-[#0C3B2E] mt-0.5">
                    {activeApp.kyc_data?.pan_number || '••••••234F'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]">
                  <span className="text-[11px] text-[#5e6d65]">Registered Phone</span>
                  <p className="text-sm font-semibold font-mono text-[#0C3B2E] mt-0.5">
                    {activeApp.kyc_data?.phone || '••••••3210'}
                  </p>
                </div>
              </div>
            </div>

            {/* Document Upload & Duplicate Detection */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-[#E5E9E1]">
              <div className="flex items-center justify-between pb-4 border-b border-[#F1F3EE]">
                <div>
                  <h4 className="font-bold text-[#0C3B2E] text-sm">Application Documents</h4>
                  <p className="text-[11px] text-[#5e6d65]">Duplicate-checked via SHA-256 hash & virus scanned</p>
                </div>
                <span className="text-xs text-[#6D9773] font-medium">
                  {activeApp.documents?.length || 0} Documents Uploaded
                </span>
              </div>

              {docUploadError && (
                <div className="mt-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
                  <span>{docUploadError}</span>
                </div>
              )}

              {/* Upload Dropzones */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                {['Salary Slip', 'Bank Statement', 'Property Deed', 'ITR V'].map((type) => (
                  <label
                    key={type}
                    className="flex items-center justify-between p-3.5 rounded-xl border border-dashed border-[#BB8A52] bg-[#F7F8F5]/80 hover:bg-[#F1F3EE] cursor-pointer transition-all"
                  >
                    <div className="flex items-center space-x-2.5">
                      <Upload className="w-4 h-4 text-[#BB8A52]" />
                      <div>
                        <p className="text-xs font-semibold text-[#0C3B2E]">Upload {type}</p>
                        <p className="text-[10px] text-[#5e6d65]">PDF or JPG up to 5MB</p>
                      </div>
                    </div>
                    <input
                      type="file"
                      className="hidden"
                      onChange={(e) => handleFileUpload(type, e)}
                    />
                    <span className="text-[10px] font-bold px-2 py-1 rounded bg-[#0C3B2E] text-white">Select</span>
                  </label>
                ))}
              </div>

              {/* Uploaded Documents List */}
              <div className="space-y-2 mt-5">
                {activeApp.documents && activeApp.documents.length > 0 ? (
                  activeApp.documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-3 rounded-xl bg-[#F7F8F5] border border-[#E5E9E1]"
                    >
                      <div className="flex items-center space-x-3 overflow-hidden">
                        <FileCheck2 className="w-5 h-5 text-[#6D9773] shrink-0" />
                        <div className="truncate">
                          <p className="text-xs font-bold text-[#0C3B2E] truncate">{doc.file_name}</p>
                          <p className="text-[10px] text-[#5e6d65] font-mono truncate">SHA: {doc.file_hash.substring(0, 16)}...</p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3 shrink-0">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            doc.status === 'Verified'
                              ? 'bg-emerald-100 text-emerald-800'
                              : doc.status === 'Mismatch'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {doc.status}
                        </span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-center py-4 text-[#5e6d65]">No documents uploaded yet.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Apply Loan Modal */}
      {isApplyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-[#E5E9E1] max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-4 border-b border-[#F1F3EE]">
              <div>
                <h3 className="text-lg font-bold text-[#0C3B2E]">Apply for Loan</h3>
                <p className="text-xs text-[#5e6d65]">Fill in your application details for instant policy evaluation</p>
              </div>
              <button
                onClick={() => setIsApplyModalOpen(false)}
                className="p-1 rounded-lg text-[#5e6d65] hover:text-[#0C3B2E] hover:bg-[#F1F3EE]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleApplySubmit} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-semibold text-[#0C3B2E] mb-1">Loan Type</label>
                <select
                  value={loanType}
                  onChange={(e) => setLoanType(e.target.value)}
                  className="w-full text-xs p-2.5 rounded-xl border border-[#E5E9E1] bg-white focus:outline-none focus:ring-2 focus:ring-[#0C3B2E]"
                >
                  <option value="Home Loan">Home Loan (Rate: ~8.75%)</option>
                  <option value="Personal Loan">Personal Loan (Rate: ~11.5%)</option>
                  <option value="Vehicle Loan">Vehicle Loan (Rate: ~9.25%)</option>
                </select>
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold text-[#0C3B2E] mb-1">
                  <span>Loan Amount</span>
                  <span className="text-[#BB8A52] font-bold">₹{amount.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min={100000}
                  max={10000000}
                  step={50000}
                  value={amount}
                  onChange={(e) => setAmount(Number(e.target.value))}
                  className="w-full accent-[#0C3B2E]"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs font-semibold text-[#0C3B2E] mb-1">
                  <span>Tenure (Months)</span>
                  <span className="text-[#BB8A52] font-bold">{tenure} Months ({(tenure / 12).toFixed(1)} yrs)</span>
                </div>
                <input
                  type="range"
                  min={12}
                  max={360}
                  step={12}
                  value={tenure}
                  onChange={(e) => setTenure(Number(e.target.value))}
                  className="w-full accent-[#0C3B2E]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#0C3B2E] mb-1">Annual Income (₹)</label>
                  <input
                    type="number"
                    value={income}
                    onChange={(e) => setIncome(Number(e.target.value))}
                    className="w-full text-xs p-2.5 rounded-xl border border-[#E5E9E1] focus:ring-2 focus:ring-[#0C3B2E] outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#0C3B2E] mb-1">Existing Monthly EMIs (₹)</label>
                  <input
                    type="number"
                    value={existingEmi}
                    onChange={(e) => setExistingEmi(Number(e.target.value))}
                    className="w-full text-xs p-2.5 rounded-xl border border-[#E5E9E1] focus:ring-2 focus:ring-[#0C3B2E] outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#0C3B2E] mb-1">Employment Type</label>
                  <select
                    value={employmentType}
                    onChange={(e) => setEmploymentType(e.target.value)}
                    className="w-full text-xs p-2.5 rounded-xl border border-[#E5E9E1] bg-white outline-none"
                  >
                    <option value="Salaried">Salaried</option>
                    <option value="Self-Employed">Self-Employed</option>
                    <option value="Business">Business</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#0C3B2E] mb-1">Employer / Org</label>
                  <input
                    type="text"
                    value={employer}
                    onChange={(e) => setEmployer(e.target.value)}
                    className="w-full text-xs p-2.5 rounded-xl border border-[#E5E9E1] outline-none"
                    required
                  />
                </div>
              </div>

              {/* Live EMI calculation badge */}
              <div className="p-3.5 rounded-xl bg-[#F7F8F5] border border-[#BB8A52]/40 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-[#5e6d65]">Estimated Monthly EMI</span>
                  <p className="text-base font-bold text-[#0C3B2E]">₹{calculateEstimatedEmi(amount, tenure).toLocaleString()}/mo</p>
                </div>
                <span className="text-[11px] font-semibold text-[#6D9773]">No hidden charges</span>
              </div>

              <div className="pt-3 border-t border-[#F1F3EE] flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setIsApplyModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold text-[#5e6d65] hover:bg-[#F1F3EE] rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 text-xs font-bold text-[#0C3B2E] bg-[#FFBA00] hover:brightness-105 rounded-xl shadow"
                >
                  Submit Application
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Pay EMI Modal */}
      {isPayModalOpen && loanAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-[#E5E9E1]">
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F3EE]">
              <h3 className="font-bold text-[#0C3B2E] text-base">Make Loan Repayment</h3>
              <button onClick={() => setIsPayModalOpen(false)}>
                <X className="w-4 h-4 text-[#5e6d65]" />
              </button>
            </div>

            <div className="my-4 space-y-3">
              <div className="p-4 rounded-xl bg-[#0C3B2E] text-white">
                <span className="text-xs text-[#8eb494]">Installment Amount</span>
                <p className="text-2xl font-bold text-[#FFBA00] mt-1">₹{loanAccount.emi_amount.toLocaleString()}</p>
                <p className="text-[11px] text-[#8eb494] mt-1">Account: {loanAccount.account_number}</p>
              </div>

              <div className="space-y-2">
                <span className="text-xs font-semibold text-[#0C3B2E]">Select Payment Mode</span>
                <label className="flex items-center justify-between p-3 rounded-xl border border-[#0C3B2E] bg-[#F7F8F5] cursor-pointer">
                  <span className="text-xs font-bold text-[#0C3B2E]">Instant UPI (GPay / PhonePe)</span>
                  <input type="radio" name="pay_mode" defaultChecked className="accent-[#0C3B2E]" />
                </label>
                <label className="flex items-center justify-between p-3 rounded-xl border border-[#E5E9E1] hover:bg-[#F7F8F5] cursor-pointer">
                  <span className="text-xs text-[#5e6d65]">NetBanking / Auto-Debit NACH</span>
                  <input type="radio" name="pay_mode" className="accent-[#0C3B2E]" />
                </label>
              </div>
            </div>

            <button
              onClick={() => {
                onPayEmi(loanAccount.id, loanAccount.emi_amount);
                setIsPayModalOpen(false);
              }}
              className="w-full py-3 rounded-xl bg-[#0C3B2E] text-white text-xs font-bold hover:bg-[#165443] shadow-md transition-all"
            >
              Confirm & Pay ₹{loanAccount.emi_amount.toLocaleString()}
            </button>
          </div>
        </div>
      )}

      {/* Amortization Schedule Modal */}
      {isScheduleModalOpen && loanAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-[#E5E9E1] max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-4 border-b border-[#F1F3EE]">
              <div>
                <h3 className="font-bold text-[#0C3B2E] text-base">Amortization Schedule</h3>
                <p className="text-xs text-[#5e6d65]">Account {loanAccount.account_number} • Reducing Balance Method</p>
              </div>
              <button onClick={() => setIsScheduleModalOpen(false)}>
                <X className="w-5 h-5 text-[#5e6d65]" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 my-4 divide-y divide-[#F1F3EE]">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-[#F7F8F5] text-[#0C3B2E] font-bold border-b border-[#E5E9E1]">
                  <tr>
                    <th className="py-2.5 px-3">#</th>
                    <th className="py-2.5 px-3">Due Date</th>
                    <th className="py-2.5 px-3">EMI (₹)</th>
                    <th className="py-2.5 px-3">Principal (₹)</th>
                    <th className="py-2.5 px-3">Interest (₹)</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F1F3EE]">
                  {loanAccount.schedules?.map((item) => (
                    <tr key={item.id} className="hover:bg-[#F7F8F5]/60">
                      <td className="py-2.5 px-3 font-semibold text-[#0C3B2E]">{item.installment_number}</td>
                      <td className="py-2.5 px-3 text-[#5e6d65]">
                        {new Date(item.due_date).toLocaleDateString()}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-[#0C3B2E]">₹{item.emi_amount.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-[#6D9773]">₹{item.principal_component.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-[#BB8A52]">₹{item.interest_component.toLocaleString()}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            item.status === 'PAID'
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-amber-100 text-amber-800'
                          }`}
                        >
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
