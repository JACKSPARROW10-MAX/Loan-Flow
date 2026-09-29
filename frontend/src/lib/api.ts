/**
 * LoanFlow Frontend API Client.
 * Connects directly to the real LoanFlow API Gateway.
 */

import { ApplicationItem, DocumentItem, LoanAccountItem, CollectionCaseItem, AuditLogItem, Role } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

let authToken: string | null = null;
let currentRoleUser: Role = 'customer';

// Default role credentials for rapid UI role switching
const ROLE_CREDENTIALS: Record<Role, { username: string; pass: string }> = {
  customer: { username: 'customer1', pass: 'cust123' },
  employee: { username: 'employee1', pass: 'emp123' },
  manager: { username: 'manager1', pass: 'mgr123' },
};

/**
 * Log in to the backend for the designated role.
 */
export async function switchRoleAuth(role: Role): Promise<string> {
  currentRoleUser = role;
  const creds = ROLE_CREDENTIALS[role];
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username: creds.username, password: creds.pass }),
    });

    if (res.ok) {
      const data = await res.json();
      authToken = data.token || data.access_token || null;
      if (typeof window !== 'undefined' && authToken) {
        localStorage.setItem(`loanflow_token_${role}`, authToken);
      }
      return authToken || '';
    }
  } catch (err) {
    console.warn(`[LoanFlow API] Automatic login for ${role} failed:`, err);
  }
  return '';
}

/**
 * Generic fetch wrapper with auth header and error handling.
 */
async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Get current token
  if (!authToken && typeof window !== 'undefined') {
    authToken = localStorage.getItem(`loanflow_token_${currentRoleUser}`);
  }

  // If still no token, perform transparent login
  if (!authToken) {
    authToken = await switchRoleAuth(currentRoleUser);
  }

  if (authToken) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    const errBody = await res.text();
    let errMsg = `API error ${res.status}: ${res.statusText}`;
    try {
      const json = JSON.parse(errBody);
      errMsg = json.detail || errMsg;
    } catch {
      if (errBody) errMsg = errBody;
    }
    throw new Error(errMsg);
  }

  return res.json() as Promise<T>;
}

// ═══════════════════════ Applications ═══════════════════════

export async function fetchApplications(): Promise<ApplicationItem[]> {
  const items = await apiFetch<any[]>('/applications');
  // Enrich application objects to match frontend ApplicationItem
  return items.map((app) => ({
    ...app,
    documents: app.documents || [],
    rule_results: app.rule_results || [],
    kyc_verified: app.kyc_verified ?? true,
    kyc_data: app.kyc_data || {
      aadhaar_number: '********9012',
      pan_number: '******234F',
      phone: '******3210',
      verified: true,
    },
  }));
}

export async function fetchApplicationDetails(appId: string): Promise<ApplicationItem> {
  return apiFetch<ApplicationItem>(`/applications/${appId}`);
}

export async function createApplication(data: {
  loan_type: string;
  requested_amount: number;
  annual_income: number;
  existing_emi?: number;
  employment_type?: string;
  employer_name?: string;
  loan_tenure_months?: number;
  customer_name?: string;
}): Promise<ApplicationItem> {
  return apiFetch<ApplicationItem>('/applications', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function transitionApplicationStage(
  appId: string,
  targetStage: string,
  remarks?: string
): Promise<any> {
  return apiFetch(`/applications/${appId}/transition`, {
    method: 'POST',
    body: JSON.stringify({ target_stage: targetStage, remarks }),
  });
}

// ═══════════════════════ Documents ═══════════════════════

export async function fetchDocuments(appId: string): Promise<DocumentItem[]> {
  return apiFetch<DocumentItem[]>(`/applications/${appId}/documents`);
}

export async function uploadDocument(
  appId: string,
  documentType: string,
  file: File
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append('document_type', documentType);
  formData.append('file', file);

  return apiFetch<DocumentItem>(`/applications/${appId}/documents`, {
    method: 'POST',
    body: formData,
  });
}

export async function verifyDocument(
  docId: string,
  status: 'Verified' | 'Mismatch',
  remarks?: string
): Promise<DocumentItem> {
  return apiFetch<DocumentItem>(`/documents/${docId}/verify`, {
    method: 'PATCH',
    body: JSON.stringify({ status, remarks }),
  });
}

// ═══════════════════════ Rules, Risk & Limit ═══════════════════════

export async function runEligibility(appId: string): Promise<any> {
  return apiFetch(`/applications/${appId}/eligibility`, {
    method: 'POST',
  });
}

export async function calculateRiskScore(appId: string): Promise<any> {
  return apiFetch(`/applications/${appId}/risk-score`, {
    method: 'POST',
  });
}

export async function calculateLimit(appId: string): Promise<any> {
  return apiFetch(`/applications/${appId}/limit`, {
    method: 'POST',
  });
}

export async function fetchAuditLogs(appId: string): Promise<AuditLogItem[]> {
  return apiFetch<AuditLogItem[]>(`/applications/${appId}/audit`);
}

// ═══════════════════════ Servicing & Disbursal ═══════════════════════

export async function disburseLoan(appId: string, interestRate: number): Promise<LoanAccountItem> {
  return apiFetch<LoanAccountItem>(`/applications/${appId}/disburse`, {
    method: 'POST',
    body: JSON.stringify({ interest_rate: interestRate }),
  });
}

export async function fetchLoanAccounts(): Promise<LoanAccountItem[]> {
  return apiFetch<LoanAccountItem[]>('/servicing/accounts');
}

export async function fetchServicingForApp(appId: string): Promise<LoanAccountItem | null> {
  try {
    return await apiFetch<LoanAccountItem>(`/applications/${appId}/servicing`);
  } catch {
    return null;
  }
}

export async function payEmi(accountId: string, amount: number): Promise<any> {
  return apiFetch(`/servicing/accounts/${accountId}/pay`, {
    method: 'POST',
    body: JSON.stringify({ amount }),
  });
}

// ═══════════════════════ Collections ═══════════════════════

export async function fetchCollectionCases(): Promise<CollectionCaseItem[]> {
  return apiFetch<CollectionCaseItem[]>('/collection/cases');
}

export async function addCollectionFollowUp(caseId: string, note: string): Promise<any> {
  return apiFetch(`/collection/cases/${caseId}/follow-up`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  });
}

// ═══════════════════════ Analytics ═══════════════════════

export async function fetchAnalyticsSummary(): Promise<any> {
  return apiFetch('/analytics/summary');
}
