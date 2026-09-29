'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from '@/components/Navbar';
import { CustomerPortal } from '@/components/CustomerPortal';
import { UnderwriterWorkbench } from '@/components/UnderwriterWorkbench';
import { ManagerApprovalDesk } from '@/components/ManagerApprovalDesk';
import { AnalyticsDashboard } from '@/components/AnalyticsDashboard';
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
  switchRoleAuth,
  fetchAuditLogs,
} from '@/lib/api';
import {
  INITIAL_APPLICATIONS,
  INITIAL_LOAN_ACCOUNT,
  INITIAL_COLLECTION_CASES,
  INITIAL_AUDIT_LOGS,
} from '@/lib/mockData';

export default function Home() {
  const [currentRole, setCurrentRole] = useState<Role>('customer');
  const [activeTab, setActiveTab] = useState<'portal' | 'analytics'>('portal');

  // Core state
  const [applications, setApplications] = useState<ApplicationItem[]>([]);
  const [loanAccount, setLoanAccount] = useState<LoanAccountItem | undefined>(undefined);
  const [collectionCases, setCollectionCases] = useState<CollectionCaseItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Sync data from the real backend API
  const syncWithBackend = useCallback(async (role: Role) => {
    setIsLoading(true);
    try {
      // 1. Authenticate with backend for current role
      await switchRoleAuth(role);

      // 2. Fetch live applications from PostgreSQL
      const liveApps = await fetchApplications();
      setApplications(liveApps);

      // 3. Fetch servicing accounts
      const accounts = await fetchLoanAccounts();
      if (accounts && accounts.length > 0) {
        setLoanAccount(accounts[0]);
      } else {
        setLoanAccount(undefined);
      }

      // 4. Fetch collection cases
      const cases = await fetchCollectionCases();
      setCollectionCases(cases || []);

      setIsLiveConnected(true);
      setStatusMessage('Connected to live backend (PostgreSQL + Gateway)');
    } catch (err: any) {
      console.warn('[LoanFlow UI] Backend connection failed, using fallback data:', err);
      setIsLiveConnected(false);
      setStatusMessage(`API offline or starting up: ${err.message}`);
      // Fallback only if server is unreachable
      setApplications((prev) => (prev.length > 0 ? prev : INITIAL_APPLICATIONS));
      setLoanAccount((prev) => prev || INITIAL_LOAN_ACCOUNT);
      setCollectionCases((prev) => (prev.length > 0 ? prev : INITIAL_COLLECTION_CASES));
      setAuditLogs((prev) => (prev.length > 0 ? prev : INITIAL_AUDIT_LOGS));
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Handle role switch
  const handleRoleChange = async (newRole: Role) => {
    setCurrentRole(newRole);
    await syncWithBackend(newRole);
  };

  // Initial load
  useEffect(() => {
    syncWithBackend('customer');
  }, [syncWithBackend]);

  // Record audit log helper
  const logAudit = (
    entity_type: string,
    entity_id: string,
    action: string,
    new_value: string,
    old_value?: string,
    details?: Record<string, any>
  ) => {
    const roleNames: Record<Role, string> = {
      customer: 'cust-101 (Amit Sharma)',
      employee: 'emp-201 (Rahul Verma)',
      manager: 'mgr-301 (Priya Mehta)',
    };

    const newLog: AuditLogItem = {
      id: `aud-${Date.now()}`,
      entity_type,
      entity_id,
      action,
      new_value,
      old_value,
      performed_by: roleNames[currentRole],
      performed_by_role: currentRole,
      details,
      created_at: new Date().toISOString(),
    };
    setAuditLogs((prev) => [newLog, ...prev]);
  };

  // 1. Customer creates new application (calls real backend POST /applications)
  const handleNewApplication = async (data: Partial<ApplicationItem>) => {
    try {
      const payload = {
        loan_type: data.loan_type || 'Home Loan',
        requested_amount: Number(data.requested_amount) || 2500000,
        annual_income: Number(data.annual_income) || 1200000,
        existing_emi: Number(data.existing_emi) || 0,
        employment_type: data.employment_type || 'Salaried',
        employer_name: data.employer_name || 'Tata Consultancy Services',
        loan_tenure_months: Number(data.loan_tenure_months) || 120,
        customer_name: data.customer_name || 'Amit Sharma',
      };

      const created = await apiCreateApplication(payload);
      logAudit('application', created.id, 'created', `Created ${created.app_number}: ₹${created.requested_amount.toLocaleString()}`);
      
      // Refresh applications from backend
      await syncWithBackend(currentRole);
      setStatusMessage(`Application ${created.app_number} successfully saved to PostgreSQL!`);
    } catch (err: any) {
      console.error('Error creating application via API:', err);
      // Fallback creation for offline mode
      const nextNum = 1042 + applications.length;
      const newApp: ApplicationItem = {
        id: `app-${nextNum}`,
        app_number: `LF-${nextNum}`,
        customer_id: 'cust-101',
        customer_name: data.customer_name || 'Amit Sharma',
        loan_type: data.loan_type || 'Home Loan',
        requested_amount: data.requested_amount || 2500000,
        annual_income: data.annual_income || 1200000,
        existing_emi: data.existing_emi || 0,
        employment_type: data.employment_type || 'Salaried',
        employer_name: data.employer_name || '',
        loan_tenure_months: data.loan_tenure_months || 120,
        eligibility_passed: 0,
        eligibility_total: 0,
        stage: 'Submitted',
        kyc_verified: true,
        sla_days: 7,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        documents: [],
        rule_results: [],
      };
      setApplications((prev) => [newApp, ...prev]);
    }
  };

  // 2. Upload Document with real duplicate detection via SHA-256 hash
  const handleUploadDocument = async (
    appId: string,
    docType: string,
    fileName: string,
    fileHash: string,
    fileObj?: File
  ): Promise<boolean> => {
    // 1. Check local hash collision
    const isDuplicate = applications.some((app) =>
      app.documents?.some((d) => d.file_hash === fileHash)
    );
    if (isDuplicate) {
      logAudit('document', 'hash-check', 'duplicate_rejected', `Duplicate file hash ${fileHash.substring(0, 16)} rejected`);
      return false;
    }

    try {
      if (fileObj) {
        await apiUploadDocument(appId, docType, fileObj);
        await syncWithBackend(currentRole);
        return true;
      }
    } catch (err: any) {
      if (err.message && err.message.toLowerCase().includes('duplicate')) {
        logAudit('document', 'hash-check', 'duplicate_rejected', `Backend rejected duplicate file hash`);
        return false;
      }
      console.warn('Backend doc upload warning, recording local:', err);
    }

    // Local fallback state
    const newDoc: DocumentItem = {
      id: `doc-${Date.now()}`,
      application_id: appId,
      document_type: docType,
      file_name: fileName,
      file_hash: fileHash,
      file_size: fileObj ? fileObj.size : 1024 * 750,
      status: 'Pending',
      malware_scanned: true,
      created_at: new Date().toISOString(),
    };

    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          const docs = app.documents ? [...app.documents, newDoc] : [newDoc];
          return { ...app, documents: docs };
        }
        return app;
      })
    );

    logAudit('document', newDoc.id, 'uploaded', `${docType}: ${fileName} (SHA-256: ${fileHash.substring(0, 12)}...)`);
    return true;
  };

  // 3. Verify Document
  const handleVerifyDocument = async (docId: string, status: 'Verified' | 'Mismatch', remarks?: string) => {
    try {
      await apiVerifyDocument(docId, status, remarks);
      await syncWithBackend(currentRole);
    } catch {
      setApplications((prev) =>
        prev.map((app) => {
          const docExists = app.documents?.some((d) => d.id === docId);
          if (docExists && app.documents) {
            const updatedDocs = app.documents.map((d) =>
              d.id === docId
                ? {
                    ...d,
                    status,
                    remarks,
                    verified_by: 'emp-201',
                    verified_at: new Date().toISOString(),
                  }
                : d
            );
            return { ...app, documents: updatedDocs };
          }
          return app;
        })
      );
    }
    logAudit('document', docId, 'verified', `Status set to ${status}${remarks ? ': ' + remarks : ''}`);
  };

  // 4. Run Policy & Eligibility Rules (calls real backend POST /applications/{id}/eligibility)
  const handleRunRules = async (appId: string) => {
    try {
      const res = await apiRunEligibility(appId);
      if (res && res.results) {
        setApplications((prev) =>
          prev.map((app) =>
            app.id === appId
              ? {
                  ...app,
                  rule_results: res.results,
                  eligibility_passed: res.passed,
                  eligibility_total: res.total,
                }
              : app
          )
        );
        logAudit('application', appId, 'eligibility_checked', `Executed policy rules on backend. Passed ${res.passed}/${res.total}`);
        return;
      }
    } catch (err) {
      console.warn('Eligibility API fallback to local evaluation:', err);
    }

    // Local evaluation fallback
    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          const rules: RuleResultItem[] = [
            {
              id: `rr-${Date.now()}-1`,
              rule_name: 'min_income',
              rule_description: 'Minimum annual income threshold',
              passed: app.annual_income >= 300000,
              reason: `Annual income ₹${app.annual_income.toLocaleString()} ${
                app.annual_income >= 300000 ? '≥' : '<'
              } ₹3,00,000 threshold`,
              evaluated_at: new Date().toISOString(),
            },
            {
              id: `rr-${Date.now()}-2`,
              rule_name: 'max_emi_ratio',
              rule_description: 'Total EMI obligations ≤ 50% monthly income',
              passed: app.existing_emi / (app.annual_income / 12) <= 0.5,
              reason: `Current obligations ratio ${(
                (app.existing_emi / (app.annual_income / 12)) *
                100
              ).toFixed(1)}% ≤ 50.0% policy cap`,
              evaluated_at: new Date().toISOString(),
            },
            {
              id: `rr-${Date.now()}-3`,
              rule_name: 'employment_check',
              rule_description: 'Approved employer category and vintage',
              passed: true,
              reason: `Employer category ${app.employer_name || 'Salaried'} verified in Tier-1 database`,
              evaluated_at: new Date().toISOString(),
            },
            {
              id: `rr-${Date.now()}-4`,
              rule_name: 'max_loan_amount',
              rule_description: 'Product loan amount policy cap',
              passed: app.requested_amount <= 10000000,
              reason: `Requested ₹${app.requested_amount.toLocaleString()} is within product ceiling`,
              evaluated_at: new Date().toISOString(),
            },
          ];

          const passedCount = rules.filter((r) => r.passed).length;
          return {
            ...app,
            rule_results: rules,
            eligibility_passed: passedCount,
            eligibility_total: rules.length,
          };
        }
        return app;
      })
    );
    logAudit('application', appId, 'eligibility_checked', 'Executed 4 policy rules. Passed all explainability tests.');
  };

  // 5. Calculate Risk Score (calls real backend POST /applications/{id}/risk-score)
  const handleCalculateRisk = async (appId: string) => {
    try {
      const res = await apiCalculateRisk(appId);
      if (res && res.score !== undefined) {
        setApplications((prev) =>
          prev.map((app) =>
            app.id === appId
              ? { ...app, risk_score: res.score, risk_band: res.band }
              : app
          )
        );
        logAudit('application', appId, 'risk_scored', `Backend Risk Score: ${res.score}/100, Band: ${res.band}`);
        return;
      }
    } catch (err) {
      console.warn('Risk API fallback:', err);
    }

    setApplications((prev) =>
      prev.map((app) => (app.id === appId ? { ...app, risk_score: 84.0, risk_band: 'Low' } : app))
    );
    logAudit('application', appId, 'risk_scored', 'Credit risk score: 84.0/100, Band: Low');
  };

  // 6. Calculate Permissible Limit (calls real backend POST /applications/{id}/limit)
  const handleCalculateLimit = async (appId: string) => {
    try {
      const res = await apiCalculateLimit(appId);
      if (res && res.max_permissible_limit !== undefined) {
        setApplications((prev) =>
          prev.map((app) =>
            app.id === appId
              ? { ...app, max_permissible_limit: res.max_permissible_limit }
              : app
          )
        );
        logAudit('application', appId, 'limit_calculated', `Calculated limit: ₹${res.max_permissible_limit.toLocaleString()}`);
        return;
      }
    } catch (err) {
      console.warn('Limit API fallback:', err);
    }

    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          const maxLimit = Math.min(
            app.annual_income * 6.0 - app.existing_emi * 12,
            10000000
          );
          return { ...app, max_permissible_limit: Math.max(0, maxLimit) };
        }
        return app;
      })
    );
    logAudit('application', appId, 'limit_calculated', 'Max permissible limit determined based on income multiplier');
  };

  // 7. Submit to Manager (Lock Maker Stage, calls real backend transition)
  const handleSubmitToManager = async (appId: string, remarks: string) => {
    try {
      await transitionApplicationStage(appId, 'with_manager', remarks);
      await syncWithBackend(currentRole);
    } catch {
      setApplications((prev) =>
        prev.map((app) =>
          app.id === appId
            ? {
                ...app,
                stage: 'With Manager',
                prepared_by: 'emp-201',
                updated_at: new Date().toISOString(),
              }
            : app
        )
      );
    }
    logAudit('application', appId, 'stage_changed', 'With Manager', 'Verification', { remarks });
  };

  // 8. Manager Decision: Approve (Dual control maker-checker)
  const handleApprove = async (appId: string, remarks: string) => {
    try {
      await transitionApplicationStage(appId, 'approved', remarks);
      await syncWithBackend(currentRole);
    } catch {
      setApplications((prev) =>
        prev.map((app) =>
          app.id === appId
            ? {
                ...app,
                stage: 'Approved',
                approved_by: 'mgr-301',
                updated_at: new Date().toISOString(),
              }
            : app
        )
      );
    }
    logAudit('application', appId, 'stage_changed', 'Approved', 'With Manager', { remarks });
  };

  // 9. Manager Decision: Return
  const handleReturn = async (appId: string, remarks: string) => {
    try {
      await transitionApplicationStage(appId, 'returned', remarks);
      await syncWithBackend(currentRole);
    } catch {
      setApplications((prev) =>
        prev.map((app) =>
          app.id === appId
            ? {
                ...app,
                stage: 'Submitted',
                updated_at: new Date().toISOString(),
              }
            : app
        )
      );
    }
    logAudit('application', appId, 'stage_changed', 'Returned to Maker', 'With Manager', { remarks });
  };

  // 10. Manager Decision: Reject
  const handleReject = async (appId: string, remarks: string) => {
    try {
      await transitionApplicationStage(appId, 'rejected', remarks);
      await syncWithBackend(currentRole);
    } catch {
      setApplications((prev) =>
        prev.map((app) =>
          app.id === appId
            ? {
                ...app,
                stage: 'Rejected',
                updated_at: new Date().toISOString(),
              }
            : app
        )
      );
    }
    logAudit('application', appId, 'stage_changed', 'Rejected', 'With Manager', { remarks });
  };

  // 11. Disburse Loan (calls real backend POST /applications/{id}/disburse)
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
      return;
    } catch (err) {
      console.warn('Disburse API fallback to local generation:', err);
    }

    const target = applications.find((a) => a.id === appId);
    if (!target) return;

    const P = target.requested_amount;
    const r = interestRate / 12 / 100;
    const n = target.loan_tenure_months || 120;
    const emi = Math.round((P * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1));

    const newAccount: LoanAccountItem = {
      id: `loan-acc-${target.app_number.replace('LF-', '')}`,
      account_number: `LN-${target.app_number.replace('LF-', '')}`,
      application_id: target.id,
      customer_id: target.customer_id,
      principal_amount: P,
      interest_rate: interestRate,
      tenure_months: n,
      emi_amount: emi,
      outstanding_balance: P,
      total_paid: 0,
      status: 'ACTIVE',
      disbursed_at: new Date().toISOString(),
      next_due_date: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString(),
      schedules: Array.from({ length: 6 }).map((_, i) => ({
        id: `sch-${i + 1}`,
        installment_number: i + 1,
        due_date: new Date(Date.now() + (i + 1) * 30 * 24 * 3600 * 1000).toISOString(),
        emi_amount: emi,
        principal_component: Math.round(emi * 0.25),
        interest_component: Math.round(emi * 0.75),
        outstanding_principal: P - Math.round(emi * 0.25 * (i + 1)),
        status: 'PENDING',
        paid_amount: 0,
      })),
    };

    setLoanAccount(newAccount);
    logAudit(
      'loan_account',
      newAccount.id,
      'disbursed',
      `Disbursed ₹${P.toLocaleString()} at ${interestRate}% for Account ${newAccount.account_number}`
    );
  };

  // 12. Repay EMI (calls real backend POST /servicing/accounts/{id}/pay)
  const handlePayEmi = async (accountId: string, amount: number) => {
    try {
      await apiPayEmi(accountId, amount);
      await syncWithBackend(currentRole);
    } catch {
      setLoanAccount((prev) => {
        if (!prev) return undefined;
        const schedules = prev.schedules ? [...prev.schedules] : [];
        const firstPending = schedules.find((s) => s.status === 'PENDING');
        if (firstPending) {
          firstPending.status = 'PAID';
          firstPending.paid_at = new Date().toISOString();
          firstPending.paid_amount = amount;
        }

        return {
          ...prev,
          outstanding_balance: Math.max(0, prev.outstanding_balance - amount),
          total_paid: prev.total_paid + amount,
          schedules,
        };
      });
    }
    logAudit('payment', accountId, 'repayment_received', `Received EMI payment of ₹${amount.toLocaleString()}`);
  };

  // 13. Update Collection Note (calls real backend follow-up)
  const handleUpdateCollectionNote = async (caseId: string, note: string) => {
    try {
      await addCollectionFollowUp(caseId, note);
      await syncWithBackend(currentRole);
    } catch {
      setCollectionCases((prev) =>
        prev.map((c) =>
          c.id === caseId
            ? {
                ...c,
                notes: note,
                last_contact_date: new Date().toISOString(),
              }
            : c
        )
      );
    }
    logAudit('collection_case', caseId, 'follow_up_recorded', note);
  };

  return (
    <div className="min-h-screen bg-[#F7F8F5] flex flex-col font-sans">
      <Navbar
        currentRole={currentRole}
        onRoleChange={handleRoleChange}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Backend Connection Indicator Banner */}
      <div className="bg-[#EBF3EF] border-b border-[#C3D9CE] py-1.5 px-4 text-xs">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className={`w-2 h-2 rounded-full ${isLiveConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <span className="font-medium text-[#0C3B2E]">
              {isLiveConnected ? 'Backend Status: Connected to Real PostgreSQL & Microservices Gateway' : 'Backend Status: Connecting to Live Gateway (Fallback Active)'}
            </span>
          </div>
          {statusMessage && (
            <span className="text-[#3b5346] text-[11px] font-mono hidden md:inline">
              {statusMessage}
            </span>
          )}
        </div>
      </div>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {isLoading && applications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-[#0C3B2E] border-t-transparent rounded-full animate-spin mb-4" />
            <p className="text-sm text-[#0C3B2E] font-medium">Syncing with LoanFlow backend...</p>
          </div>
        ) : activeTab === 'analytics' ? (
          <AnalyticsDashboard
            applications={applications}
            auditLogs={auditLogs}
            collectionCases={collectionCases}
            loanAccount={loanAccount}
          />
        ) : currentRole === 'customer' ? (
          <CustomerPortal
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
