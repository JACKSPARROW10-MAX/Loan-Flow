'use client';

import React, { useState } from 'react';
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
  INITIAL_APPLICATIONS,
  INITIAL_LOAN_ACCOUNT,
  INITIAL_COLLECTION_CASES,
  INITIAL_AUDIT_LOGS,
} from '@/lib/mockData';

export default function Home() {
  const [currentRole, setCurrentRole] = useState<Role>('customer');
  const [activeTab, setActiveTab] = useState<'portal' | 'analytics'>('portal');

  // Core state
  const [applications, setApplications] = useState<ApplicationItem[]>(INITIAL_APPLICATIONS);
  const [loanAccount, setLoanAccount] = useState<LoanAccountItem | undefined>(INITIAL_LOAN_ACCOUNT);
  const [collectionCases, setCollectionCases] = useState<CollectionCaseItem[]>(INITIAL_COLLECTION_CASES);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>(INITIAL_AUDIT_LOGS);

  // Helper to record audit log
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

  // 1. Customer creates new application
  const handleNewApplication = (data: Partial<ApplicationItem>) => {
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
      kyc_data: {
        aadhaar_number: '********9012',
        pan_number: '******234F',
        phone: '******3210',
        verified: true,
      },
      sla_days: 7,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      documents: [],
      rule_results: [],
    };

    setApplications((prev) => [newApp, ...prev]);
    logAudit('application', newApp.id, 'created', `Created ${newApp.app_number}: ₹${newApp.requested_amount.toLocaleString()}`);
  };

  // 2. Upload Document with duplicate detection via hash
  const handleUploadDocument = (
    appId: string,
    docType: string,
    fileName: string,
    fileHash: string
  ): boolean => {
    // Check all existing documents across app for hash collision
    const isDuplicate = applications.some((app) =>
      app.documents?.some((d) => d.file_hash === fileHash)
    );

    if (isDuplicate) {
      logAudit('document', 'hash-check', 'duplicate_rejected', `Duplicate file hash ${fileHash.substring(0, 16)} rejected`);
      return false;
    }

    const newDoc: DocumentItem = {
      id: `doc-${Date.now()}`,
      application_id: appId,
      document_type: docType,
      file_name: fileName,
      file_hash: fileHash,
      file_size: 1024 * 750,
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
  const handleVerifyDocument = (docId: string, status: 'Verified' | 'Mismatch', remarks?: string) => {
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
    logAudit('document', docId, 'verified', `Status set to ${status}${remarks ? ': ' + remarks : ''}`);
  };

  // 4. Run Policy & Eligibility Rules
  const handleRunRules = (appId: string) => {
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

  // 5. Calculate Risk Score
  const handleCalculateRisk = (appId: string) => {
    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          const score = 84.0;
          return { ...app, risk_score: score, risk_band: 'Low' };
        }
        return app;
      })
    );
    logAudit('application', appId, 'risk_scored', 'Credit risk score: 84.0/100, Band: Low');
  };

  // 6. Calculate Permissible Limit
  const handleCalculateLimit = (appId: string) => {
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

  // 7. Submit to Manager (Lock Maker Stage)
  const handleSubmitToManager = (appId: string, remarks: string) => {
    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          return {
            ...app,
            stage: 'With Manager',
            prepared_by: 'emp-201',
            updated_at: new Date().toISOString(),
          };
        }
        return app;
      })
    );
    logAudit('application', appId, 'stage_changed', 'With Manager', 'Verification', { remarks });
  };

  // 8. Manager Decision: Approve
  const handleApprove = (appId: string, remarks: string) => {
    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          return {
            ...app,
            stage: 'Approved',
            approved_by: 'mgr-301',
            updated_at: new Date().toISOString(),
          };
        }
        return app;
      })
    );
    logAudit('application', appId, 'stage_changed', 'Approved', 'With Manager', { remarks });
  };

  // 9. Manager Decision: Return
  const handleReturn = (appId: string, remarks: string) => {
    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          return {
            ...app,
            stage: 'Submitted',
            updated_at: new Date().toISOString(),
          };
        }
        return app;
      })
    );
    logAudit('application', appId, 'stage_changed', 'Returned to Maker', 'With Manager', { remarks });
  };

  // 10. Manager Decision: Reject
  const handleReject = (appId: string, remarks: string) => {
    setApplications((prev) =>
      prev.map((app) => {
        if (app.id === appId) {
          return {
            ...app,
            stage: 'Rejected',
            updated_at: new Date().toISOString(),
          };
        }
        return app;
      })
    );
    logAudit('application', appId, 'stage_changed', 'Rejected', 'With Manager', { remarks });
  };

  // 11. Disburse Loan
  const handleDisburse = (appId: string, interestRate: number) => {
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

  // 12. Repay EMI
  const handlePayEmi = (accountId: string, amount: number) => {
    if (!loanAccount) return;

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

    logAudit('payment', accountId, 'repayment_received', `Received EMI payment of ₹${amount.toLocaleString()}`);
  };

  // 13. Update Collection Note
  const handleUpdateCollectionNote = (caseId: string, note: string) => {
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
    logAudit('collection_case', caseId, 'follow_up_recorded', note);
  };

  return (
    <div className="min-h-screen bg-[#F7F8F5] flex flex-col font-sans">
      <Navbar
        currentRole={currentRole}
        onRoleChange={setCurrentRole}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'analytics' ? (
          <AnalyticsDashboard
            applications={applications}
            auditLogs={auditLogs}
            collectionCases={collectionCases}
            loanAccount={loanAccount}
          />
        ) : currentRole === 'customer' ? (
          <CustomerPortal
            applications={applications.filter((a) => a.customer_id === 'cust-101')}
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
            <span>Supabase PostgreSQL</span>
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
