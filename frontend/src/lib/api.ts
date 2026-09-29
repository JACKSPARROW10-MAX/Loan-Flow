/**
 * LoanFlow Frontend API Client.
 * Connects directly to the real LoanFlow API Gateway.
 */

import {
  ApplicationItem, DocumentItem, LoanAccountItem, CollectionCaseItem, AuditLogItem, Role,
  RuleCatalog, RuleItem, RuleResultItem,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

let authToken: string | null = null;

export interface SessionUser {
  id: string;
  username: string;
  full_name: string;
  role: Role;
}

export interface PendingUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: Role;
  status: string;
  created_at: string;
}

const SESSION_KEY = 'loanflow_session';

/** Restore a previously saved login (token + user) from this browser. */
export function loadSession(): SessionUser | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const { token, user } = JSON.parse(raw);
    if (!token || !user) return null;
    authToken = token;
    return user as SessionUser;
  } catch {
    return null;
  }
}

/** Log in with real credentials. Throws with the server's message on failure. */
export async function login(username: string, password: string): Promise<SessionUser> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Login failed');
  }
  authToken = data.token || data.access_token;
  const user: SessionUser = data.user;
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify({ token: authToken, user }));
  } catch {}
  return user;
}

export async function logout(): Promise<void> {
  authToken = null;
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {}
  try {
    await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
  } catch {}
}

/** Register a new account. It stays pending until an officer/manager approves it. */
export async function registerUser(data: {
  username: string;
  email: string;
  password: string;
  full_name: string;
  role: 'customer' | 'employee';
}): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === 'string' ? detail : Array.isArray(detail) ? 'Please check the entered details' : 'Registration failed'
    );
  }
}

/**
 * Generic fetch wrapper with auth header and error handling.
 */
async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (!authToken) {
    throw new Error('Not signed in');
  }
  headers.set('Authorization', `Bearer ${authToken}`);

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

// ═══════════════════════ Account approvals ═══════════════════════

export async function fetchPendingUsers(): Promise<PendingUser[]> {
  return apiFetch<PendingUser[]>('/auth/pending');
}

export async function reviewUser(userId: string, action: 'approve' | 'reject'): Promise<PendingUser> {
  return apiFetch<PendingUser>(`/auth/users/${userId}/${action}`, { method: 'POST' });
}

// ═══════════════════════ Applications ═══════════════════════

export async function fetchApplications(): Promise<ApplicationItem[]> {
  const items = await apiFetch<any[]>('/applications');
  // Enrich application objects to match frontend ApplicationItem
  return items.map((app) => ({
    ...app,
    documents: app.documents || [],
    rule_results: app.rule_results || [],
    kyc_verified: app.kyc_verified ?? false,
    kyc_data: app.kyc_data || undefined,
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

const STAGE_NAMES: Record<string, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  kyc: 'KYC',
  docs: 'Docs',
  verification: 'Verification',
  risk: 'Risk',
  prepared: 'Prepared',
  with_manager: 'With Manager',
  approved: 'Approved',
  returned: 'Returned',
  rejected: 'Rejected',
};

export async function transitionApplicationStage(
  appId: string,
  targetStage: string,
  remarks?: string
): Promise<any> {
  // Accept either the display name ("With Manager") or a slug ("with_manager")
  const stage = STAGE_NAMES[targetStage.toLowerCase().replace(/\s+/g, '_')] || targetStage;
  return apiFetch(`/applications/${appId}/transition`, {
    method: 'POST',
    body: JSON.stringify({ target_stage: stage, remarks }),
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

export async function fetchEligibilityResults(
  appId: string
): Promise<{ passed: number; total: number; results: RuleResultItem[] }> {
  return apiFetch(`/applications/${appId}/eligibility`);
}

/** Download an uploaded file (with the session token) so it can be previewed in the browser. */
export async function fetchDocumentBlob(docId: string): Promise<Blob> {
  if (!authToken) throw new Error('Not signed in');
  const res = await fetch(`${API_BASE}/documents/${docId}/file`, {
    headers: { Authorization: `Bearer ${authToken}` },
    credentials: 'include',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'File is not available');
  }
  return res.blob();
}

// ═══════════════════════ Rules & Regulations (manager module) ═══════════════════════

export async function fetchRuleCatalog(): Promise<RuleCatalog> {
  return apiFetch<RuleCatalog>('/rules/catalog');
}

export async function fetchRules(): Promise<RuleItem[]> {
  return apiFetch<RuleItem[]>('/rules');
}

export interface RuleInput {
  loan_type: string;
  rule_name: string;
  rule_config: Record<string, any>;
  is_active: boolean;
  is_mandatory: boolean;
}

function ruleError(err: any): never {
  throw err;
}

export async function createRule(rule: RuleInput): Promise<RuleItem> {
  return apiFetch<RuleItem>('/rules', { method: 'POST', body: JSON.stringify(rule) }).catch(ruleError);
}

export async function updateRule(id: string, rule: RuleInput): Promise<RuleItem> {
  return apiFetch<RuleItem>(`/rules/${id}`, { method: 'PUT', body: JSON.stringify(rule) }).catch(ruleError);
}

export async function setRuleActive(id: string, isActive: boolean): Promise<RuleItem> {
  return apiFetch<RuleItem>(`/rules/${id}/active`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active: isActive }),
  });
}

export async function deleteRule(id: string): Promise<void> {
  await apiFetch(`/rules/${id}`, { method: 'DELETE' });
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
