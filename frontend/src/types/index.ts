export type Role = 'customer' | 'employee' | 'manager';

export type ApplicationStage =
  | 'Draft'
  | 'Submitted'
  | 'KYC'
  | 'Docs'
  | 'Verification'
  | 'Risk'
  | 'Prepared'
  | 'With Manager'
  | 'Approved'
  | 'Returned'
  | 'Rejected';

export type DocumentStatus = 'Pending' | 'Verified' | 'Mismatch';

export type RiskBand = 'Low' | 'Medium' | 'High' | 'Very High';

export interface DocumentItem {
  id: string;
  application_id: string;
  document_type: string;
  file_name: string;
  file_hash: string;
  file_size: number;
  mime_type?: string;
  status: DocumentStatus;
  fraud_score?: number | null;
  fraud_flag?: 'CLEAN' | 'SUSPICIOUS' | 'HIGH_RISK' | null;
  fraud_findings?: string[] | null;
  malware_scanned: boolean;
  verified_by?: string;
  verified_at?: string;
  remarks?: string;
  created_at: string;
}

export interface RuleResultItem {
  id: string;
  rule_name: string;
  rule_description?: string;
  passed: boolean;
  reason: string;
  evaluated_at: string;
}

export interface ApplicationItem {
  id: string;
  app_number: string;
  customer_id: string;
  customer_name: string;
  loan_type: string;
  requested_amount: number;
  annual_income: number;
  existing_emi: number;
  employment_type: string;
  employer_name: string;
  loan_tenure_months: number;
  max_permissible_limit?: number;
  risk_score?: number;
  risk_band?: string;
  eligibility_passed: number;
  eligibility_total: number;
  stage: ApplicationStage;
  prepared_by?: string;
  approved_by?: string;
  kyc_verified: boolean;
  kyc_data?: {
    aadhaar_number?: string;
    pan_number?: string;
    phone?: string;
    dob?: string;
    address?: string;
    verified?: boolean;
  };
  sla_days: number;
  sla_deadline?: string;
  created_at: string;
  updated_at: string;
  documents?: DocumentItem[];
  rule_results?: RuleResultItem[];
}

export interface EMIScheduleItem {
  id: string;
  installment_number: number;
  due_date: string;
  emi_amount: number;
  principal_component: number;
  interest_component: number;
  outstanding_principal: number;
  status: 'PENDING' | 'PAID' | 'OVERDUE';
  paid_at?: string;
  paid_amount: number;
}

export interface LoanAccountItem {
  id: string;
  account_number: string;
  application_id: string;
  customer_id: string;
  principal_amount: number;
  interest_rate: number;
  tenure_months: number;
  emi_amount: number;
  outstanding_balance: number;
  total_paid: number;
  status: 'ACTIVE' | 'CLOSED' | 'DELINQUENT';
  disbursed_at: string;
  next_due_date?: string;
  schedules?: EMIScheduleItem[];
}

export interface CollectionCaseItem {
  id: string;
  loan_account_id: string;
  account_number: string;
  customer_name: string;
  dpd: number;
  bucket: string;
  overdue_amount: number;
  assigned_to?: string;
  last_contact_date?: string;
  next_action_date?: string;
  notes?: string;
  status: string;
}

export interface AuditLogItem {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  old_value?: string;
  new_value?: string;
  performed_by: string;
  performed_by_role?: string;
  details?: Record<string, any>;
  created_at: string;
}

export interface AssessmentReport {
  application: ApplicationItem;
  kyc?: Record<string, any>;
  documents: DocumentItem[];
  rules: RuleResultItem[];
  risk: {
    score: number;
    band: string;
    model_version: string;
    explainability: Record<string, string>;
  };
  limit: {
    max_permissible_limit: number;
    requested_amount: number;
    policy_compliant: boolean;
  };
  maker_checker: {
    prepared_by: string;
    approved_by: string;
    maker_checker_compliant: boolean;
    stage: string;
  };
  audit_history: AuditLogItem[];
}

export interface AnalyticsSummary {
  total_applications: number;
  approval_rate_pct: number;
  stage_counts: Record<string, number>;
  risk_distribution: Record<string, number>;
  total_disbursed_volume: number;
  active_loans_count: number;
  delinquency_metrics: {
    current_portfolio: number;
    par_30: number;
    par_60: number;
    par_90_npa: number;
  };
}

// ═══════════════════════ Rules & Regulations ═══════════════════════

export interface RuleParamSpec {
  name: string;
  label: string;
  type: 'number' | 'integer' | 'text' | 'list' | 'boolean';
  default: any;
}

export interface RuleTypeSpec {
  label: string;
  category: 'eligibility' | 'limit' | 'risk' | 'fraud';
  description: string;
  params: RuleParamSpec[];
}

export interface RuleCatalog {
  all_products: string;
  types: Record<string, RuleTypeSpec>;
}

export interface RuleItem {
  id: string;
  loan_type: string;
  rule_name: string;
  rule_config: Record<string, any> & { type: string; description?: string };
  category: string | null;
  is_active: boolean;
  is_mandatory: boolean;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string;
  updated_at?: string;
}
