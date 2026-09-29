'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from '@/components/Navbar';
import { CustomerPortal } from '@/components/CustomerPortal';
import { UnderwriterWorkbench } from '@/components/UnderwriterWorkbench';
import { ManagerApprovalDesk } from '@/components/ManagerApprovalDesk';
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard';
import { LoginPage } from '@/components/LoginPage';
import { PendingApprovals } from '@/components/PendingApprovals';
import { RulesManager } from '@/components/RulesManager';
import {
  Role,
  ApplicationItem,
  LoanAccountItem,
  CollectionCaseItem,
  AuditLogItem,
  DocumentItem,
  RuleResultItem,
} from '@/types';
import {
  fetchApplications,
  createApplication as apiCreateApplication,
  transitionApplicationStage,
  uploadDocument as apiUploadDocument,
  verifyDocument as apiVerifyDocument,
  runEligibility as apiRunEligibility,
  calculateRiskScore as apiCalculateRisk,
  calculateLimit as apiCalculateLimit,
  disburseLoan as apiDisburseLoan,
  fetchLoanAccounts,
  payEmi as apiPayEmi,
  fetchCollectionCases,
  addCollectionFollowUp,
  loadSession,
  logout as apiLogout,
  SessionUser,
  fetchAuditLogs,
  fetchDocuments,
  fetchEligibilityResults,
} from '@/lib/api';

export default function Home() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [sessionChecked, setSessionChecked] = useState<boolean>(false);
  const currentRole: Role = user?.role ?? 'customer';
  const [activeTab, setActiveTab] = useState<'portal' | 'analytics' | 'rules'>('portal');

  // Core state
  const [applications, setApplications] = useState<ApplicationItem[]>([]);
  const [loanAccount, setLoanAccount] = useState<LoanAccountItem | undefined>(undefined);
  const [collectionCases, setCollectionCases] = useState<CollectionCaseItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ kind: 'error' | 'ok'; message: string } | null>(null);
  const notify = (kind: 'error' | 'ok', message: string) => setNotice({ kind, message });

  // Sync data from the real backend API
  const syncWithBackend = useCallback(async (role: Role) => {
    setIsLoading(true);
    try {
      const liveApps = await fetchApplications();

      // Customers need their own documents; officers load them per application on demand
      const docsByApp: Record<string, DocumentItem[]> = {};
      if (role === 'customer') {
        await Promise.all(
          liveApps.map(async (a) => {
            try {
              docsByApp[a.id] = await fetchDocuments(a.id);
            } catch {
              /* leave empty */
            }
          })
        );
      }
      setApplications((prev) =>
        liveApps.map((a) => {
          const old = prev.find((p) => p.id === a.id);
          return {
            ...a,
            documents: docsByApp[a.id] ?? old?.documents ?? [],
            rule_results: old?.rule_results ?? [],
          };
        })
      );

      const accounts = await fetchLoanAccounts();
      setLoanAccount(accounts && accounts.length > 0 ? accounts[0] : undefined);

      // Collection cases are visible to officers and managers only
      if (role !== 'customer') {
        setCollectionCases((await fetchCollectionCases()) || []);
      } else {
        setCollectionCases([]);
      }

      setIsLiveConnected(true);
      setStatusMessage('Connected to live backend (PostgreSQL + Gateway)');
    } catch (err: any) {
      if (/not authenticated|expired|invalid token|not signed in/i.test(err?.message || '')) {
        // Session is no longer valid: return to the login page
        await apiLogout();
        setUser(null);
        setIsLoading(false);
        return;
      }
      setIsLiveConnected(false);
      setStatusMessage(`Cannot reach the server: ${err?.message || 'unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Documents and stored rule results for one application (not part of the list response)
  const loadDetails = useCallback(async (appId: string) => {
    try {
      const [docs, elig] = await Promise.all([
        fetchDocuments(appId),
        fetchEligibilityResults(appId).catch(() => null),
      ]);
      setApplications((prev) =>
        prev.map((a) =>
          a.id === appId
            ? {
                ...a,
                documents: docs,
                ...(elig
                  ? { rule_results: elig.results, eligibility_passed: elig.passed, eligibility_total: elig.total }
                  : {}),
              }
            : a
        )
      );
    } catch {
      /* the file list stays as it was */
    }
  }, []);

  // Restore a saved session on first load
  useEffect(() => {
    const saved = loadSession();
    if (saved) {
      setUser(saved);
      syncWithBackend(saved.role);
    } else {
      setIsLoading(false);
    }
    setSessionChecked(true);
  }, [syncWithBackend]);

  const handleLoggedIn = async (loggedIn: SessionUser) => {
    setUser(loggedIn);
    setActiveTab('portal');
    setApplications([]);
    await syncWithBackend(loggedIn.role);
  };

  const handleLogout = async () => {
    await apiLogout();
    setUser(null);
    setApplications([]);
    setLoanAccount(undefined);
    setCollectionCases([]);
    setAuditLogs([]);
    setActiveTab('portal');
  };

  // Record audit log helper
  const logAudit = (
    entity_type: string,
    entity_id: string,
    action: string,
    new_value: string,
    old_value?: string,
    details?: Record<string, any>
  ) => {
    const performer = user ? `${user.username} (${user.full_name})` : 'unknown';

    const newLog: AuditLogItem = {
      id: `aud-${Date.now()}`,
      entity_type,
      entity_id,
      action,
      new_value,
      old_value,
      performed_by: performer,
      performed_by_role: currentRole,
      details,
      created_at: new Date().toISOString(),
    };
    setAuditLogs((prev) => [newLog, ...prev]);
  };

  // Stage names accepted by the backend state machine, in order
  const OFFICER_PIPELINE = ['Submitted', 'KYC', 'Docs', 'Verification', 'Risk', 'Prepared', 'With Manager'];

  // 1. Customer creates a new application and submits it for review
  const handleNewApplication = async (data: Partial<ApplicationItem>) => {
    try {
      const created = await apiCreateApplication({
        loan_type: data.loan_type || 'Home Loan',
        requested_amount: Number(data.requested_amount),
        annual_income: Number(data.annual_income),
        existing_emi: Number(data.existing_emi) || 0,
        employment_type: data.employment_type || 'Salaried',
        employer_name: data.employer_name || '',
        loan_tenure_months: Number(data.loan_tenure_months),
        customer_name: data.customer_name || user?.full_name || '',
      });
      await transitionApplicationStage(created.id, 'Submitted');
      logAudit('application', created.id, 'created', `Created ${created.app_number}: ₹${created.requested_amount.toLocaleString()}`);
      await syncWithBackend(currentRole);
      notify('ok', `Application ${created.app_number} submitted for review.`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not create the application');
    }
  };

  // 2. Upload a document (SHA-256 duplicate detection happens on the server too)
  const handleUploadDocument = async (
    appId: string,
    docType: string,
    fileName: string,
    fileHash: string,
    fileObj?: File
  ): Promise<boolean> => {
    const isDuplicate = applications.some((app) => app.documents?.some((d) => d.file_hash === fileHash));
    if (isDuplicate) {
      logAudit('document', 'hash-check', 'duplicate_rejected', `Duplicate file hash ${fileHash.substring(0, 16)} rejected`);
      return false;
    }
    if (!fileObj) return false;
    try {
      await apiUploadDocument(appId, docType, fileObj);
      await syncWithBackend(currentRole);
      return true;
    } catch (err: any) {
      if (err?.message && err.message.toLowerCase().includes('duplicate')) {
        logAudit('document', 'hash-check', 'duplicate_rejected', 'Backend rejected duplicate file hash');
        return false;
      }
      throw err;
    }
  };

  // 3. Officer verifies or rejects a document after reviewing it
  const handleVerifyDocument = async (docId: string, status: 'Verified' | 'Mismatch', remarks?: string) => {
    try {
      await apiVerifyDocument(docId, status, remarks);
      const owner = applications.find((a) => a.documents?.some((d) => d.id === docId));
      if (owner) await loadDetails(owner.id);
      logAudit('document', docId, 'verified', `Status set to ${status}${remarks ? ': ' + remarks : ''}`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not update the document');
    }
  };

  // 4. Run the manager-configured eligibility rules
  const handleRunRules = async (appId: string) => {
    try {
      const res = await apiRunEligibility(appId);
      setApplications((prev) =>
        prev.map((app) =>
          app.id === appId
            ? { ...app, rule_results: res.results, eligibility_passed: res.passed, eligibility_total: res.total }
            : app
        )
      );
      logAudit('application', appId, 'eligibility_checked', `Executed policy rules. Passed ${res.passed}/${res.total}`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not run the eligibility rules');
    }
  };

  // 5. Risk score
  const handleCalculateRisk = async (appId: string) => {
    try {
      const res = await apiCalculateRisk(appId);
      setApplications((prev) =>
        prev.map((app) => (app.id === appId ? { ...app, risk_score: res.score, risk_band: res.band } : app))
      );
      logAudit('application', appId, 'risk_scored', `Risk score: ${res.score}/100, Band: ${res.band}`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not calculate the risk score');
    }
  };

  // 6. Permissible limit (from the manager-configured limit rule)
  const handleCalculateLimit = async (appId: string) => {
    try {
      const res = await apiCalculateLimit(appId);
      setApplications((prev) =>
        prev.map((app) => (app.id === appId ? { ...app, max_permissible_limit: res.max_permissible_limit } : app))
      );
      logAudit('application', appId, 'limit_calculated', `Calculated limit: ₹${res.max_permissible_limit.toLocaleString()}`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not calculate the limit');
    }
  };

  // 7. Officer submits the prepared file to the manager (walks the state machine)
  const handleSubmitToManager = async (appId: string, remarks: string) => {
    const target = applications.find((a) => a.id === appId);
    if (!target) return;
    try {
      let stage = target.stage as string;
      if (stage === 'Draft') {
        throw new Error('This application is still a draft. The customer must submit it first.');
      }
      if (stage === 'Returned') {
        await transitionApplicationStage(appId, 'Submitted');
        stage = 'Submitted';
      }
      const from = OFFICER_PIPELINE.indexOf(stage);
      if (from === -1) throw new Error(`Cannot submit an application in stage "${stage}"`);
      for (let i = from + 1; i < OFFICER_PIPELINE.length; i++) {
        await transitionApplicationStage(appId, OFFICER_PIPELINE[i], i === OFFICER_PIPELINE.length - 1 ? remarks : undefined);
      }
      logAudit('application', appId, 'stage_changed', 'With Manager', stage, { remarks });
      await syncWithBackend(currentRole);
      notify('ok', `${target.app_number} submitted to the manager.`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not submit to the manager');
      await syncWithBackend(currentRole);
    }
  };

  // 8-10. Manager decisions (the server applies maker-checker and the active mandatory rules)
  const decide = async (appId: string, stage: 'Approved' | 'Returned' | 'Rejected', remarks: string) => {
    try {
      await transitionApplicationStage(appId, stage, remarks);
      logAudit('application', appId, 'stage_changed', stage, 'With Manager', { remarks });
      await syncWithBackend(currentRole);
      notify('ok', `Application ${stage.toLowerCase()}.`);
    } catch (err: any) {
      notify('error', err?.message || `Could not mark the application ${stage.toLowerCase()}`);
    }
  };
  const handleApprove = (appId: string, remarks: string) => decide(appId, 'Approved', remarks);
  const handleReturn = (appId: string, remarks: string) => decide(appId, 'Returned', remarks);
  const handleReject = (appId: string, remarks: string) => decide(appId, 'Rejected', remarks);

  // 11. Disburse loan
  const handleDisburse = async (appId: string, interestRate: number) => {
    try {
      const account = await apiDisburseLoan(appId, interestRate);
      setLoanAccount(account);
      await syncWithBackend(currentRole);
      logAudit(
        'loan_account',
        account.id,
        'disbursed',
        `Disbursed ₹${account.principal_amount.toLocaleString()} at ${interestRate}% for Account ${account.account_number}`
      );
      notify('ok', `Loan disbursed (${account.account_number}).`);
    } catch (err: any) {
      notify('error', err?.message || 'Could not disburse the loan');
    }
  };

  // 12. Repay EMI
  const handlePayEmi = async (accountId: string, amount: number) => {
    try {
      await apiPayEmi(accountId, amount);
      await syncWithBackend(currentRole);
      logAudit('payment', accountId, 'repayment_received', `Received EMI payment of ₹${amount.toLocaleString()}`);
    } catch (err: any) {
      notify('error', err?.message || 'Payment failed');
    }
  };

  // 13. Collection follow-up note
  const handleUpdateCollectionNote = async (caseId: string, note: string) => {
    try {
      await addCollectionFollowUp(caseId, note);
      await syncWithBackend(currentRole);
      logAudit('collection_case', caseId, 'follow_up_recorded', note);
    } catch (err: any) {
      notify('error', err?.message || 'Could not save the note');
    }
  };

  if (!sessionChecked) {
    return <div className="min-h-screen bg-[#F7F8F5]" />;
  }
  if (!user) {
    return <LoginPage onLoggedIn={handleLoggedIn} />;
  }

  return (
    <div className="min-h-screen bg-[#F7F8F5] flex flex-col font-sans">
      <Navbar
        currentRole={currentRole}
        userName={user.full_name}
        onLogout={handleLogout}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Backend Connection Indicator Banner */}
      <div className="bg-[#EBF3EF] border-b border-[#C3D9CE] py-1.5 px-4 text-xs">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className={`w-2 h-2 rounded-full ${isLiveConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <span className="font-medium text-[#0C3B2E]">
              {isLiveConnected ? 'Backend Status: Connected to Real PostgreSQL & Microservices Gateway' : 'Backend Status: Not connected'}
            </span>
          </div>
          {statusMessage && (
            <span className="text-[#3b5346] text-[11px] font-mono hidden md:inline">
              {statusMessage}
            </span>
          )}
        </div>
      </div>

      {notice && (
        <div
          className={`border-b py-2 px-4 text-xs ${
            notice.kind === 'error' ? 'bg-red-50 border-red-200 text-red-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'
          }`}
        >
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
            <span className="font-medium">{notice.message}</span>
            <button onClick={() => setNotice(null)} className="font-bold px-2" aria-label="Dismiss">
              ×
            </button>
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentRole !== 'customer' && activeTab === 'portal' && <PendingApprovals />}
        {isLoading && applications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-[#0C3B2E] border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-sm text-[#0C3B2E] font-medium">Syncing with LoanFlow backend...</p>
          </div>
        ) : activeTab === 'rules' && currentRole === 'manager' ? (
          <RulesManager />
        ) : activeTab === 'analytics' && currentRole !== 'customer' ? (
          <AnalyticsDashboard
            applications={applications}
            auditLogs={auditLogs}
            collectionCases={collectionCases}
            loanAccount={loanAccount}
          />
        ) : currentRole === 'customer' ? (
          <CustomerPortal
            customerName={user.full_name}
            applications={applications}
            loanAccount={loanAccount}
            onNewApplication={handleNewApplication}
            onUploadDocument={handleUploadDocument}
            onPayEmi={handlePayEmi}
          />
        ) : currentRole === 'employee' ? (
          <UnderwriterWorkbench
            applications={applications}
            collectionCases={collectionCases}
            onVerifyDocument={handleVerifyDocument}
            onRunRules={handleRunRules}
            onCalculateRisk={handleCalculateRisk}
            onCalculateLimit={handleCalculateLimit}
            onSubmitToManager={handleSubmitToManager}
            onUpdateCollectionNote={handleUpdateCollectionNote}
            onLoadDetails={loadDetails}
          />
        ) : (
          <ManagerApprovalDesk
            currentRole={currentRole}
            applications={applications}
            onApprove={handleApprove}
            onReturn={handleReturn}
            onReject={handleReject}
            onDisburse={handleDisburse}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-[#E5E9E1] py-6 text-center text-xs text-[#5e6d65]">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>© 2026 LoanFlow Technologies • Enterprise Digital Lending &amp; Servicing Platform</p>
          <div className="flex items-center space-x-4 text-[11px] font-medium text-[#0C3B2E]">
            <span>FastAPI Microservices</span>
            <span>•</span>
            <span>PostgreSQL Database</span>
            <span>•</span>
            <span>Upstash Redis</span>
            <span>•</span>
            <span>Maker-Checker Dual Control</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
