/** Mirrors backend/app/schemas.py one-to-one. */

export type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";
export type ApplicationStatus =
  | "PENDING"
  | "SCORED"
  | "APPROVED"
  | "REJECTED"
  | "NEEDS_INFO";
export type DecisionType =
  | "APPROVE"
  | "APPROVE_MODIFIED"
  | "REQUEST_INFO"
  | "REJECT";

export interface MonthlyPoint {
  month: string;
  inflow_pkr: number;
  outflow_pkr: number;
  utility_paid_on_time: boolean;
}

export interface QistBreakdown {
  disposable_income_pkr: number;
  dsr_cap: number;
  volatility_haircut: number;
  depth_confidence: number;
  consistency_bonus: number;
}

export interface QistLimit {
  eligible: boolean;
  reason: string | null;
  safe_installment_pkr: number;
  principal_pkr: number;
  tenor_months: number;
  flat_markup_monthly: number;
  total_repayable_pkr: number;
  breakdown: QistBreakdown;
}

export interface ReasonCode {
  feature: string;
  impact_points: number;
  impact_points_exact?: number;
  direction: "positive" | "negative";
  label_en: string;
  label_ur: string;
  category: string;
}

export interface BehavioralMetrics {
  payment_discipline: number;
  cashflow_stability: number;
  transaction_activity: number;
  savings_behavior: number;
  business_maturity: number;
  network_trust: number;
}

export interface DataGap {
  block: string;
  detail: string;
}

export interface ScoreResponse {
  application_id: string | null;
  score: number;
  probability_of_default: number;
  risk_band: RiskBand;
  band_label: string;
  confidence: number;
  qist_limit: QistLimit;
  reason_codes: ReasonCode[];
  ledger_lines: ReasonCode[];
  base_contribution: number;
  adverse_action_codes: string[];
  behavioral_metrics: BehavioralMetrics;
  portfolio_median_metrics: BehavioralMetrics;
  monthly_series: MonthlyPoint[];
  data_gaps: DataGap[];
  model_version: string;
  scored_at: string;
  disclaimer: string;
}

export interface ExtractedField {
  name: string;
  value: string | number | null;
  confidence: number;
}

export interface ParseBillResponse {
  filename: string;
  doc_type: "UTILITY_BILL";
  extraction_method: "pdf_text" | "tesseract" | "simulated";
  confidence: number;
  fields: ExtractedField[];
  derived_features: Record<string, number>;
  disclaimer: string;
}

export interface NormalisedTxn {
  date: string;
  amount: number;
  direction: "credit" | "debit";
  counterparty: string;
  balance: number | null;
  channel: string | null;
  category: string;
}

export interface ParseTransactionsResponse {
  filename: string;
  doc_type: "TRANSACTION_LOG";
  row_count: number;
  months_observed: number;
  transactions: NormalisedTxn[];
  derived_features: Record<string, number>;
  monthly_series: MonthlyPoint[];
  disclaimer: string;
}

export interface ApplicantIn {
  full_name: string;
  cnic: string;
  phone: string;
  city: string;
  archetype: string;
  business_type: string;
  dependents_count: number;
  has_fixed_premises: boolean;
}

export interface ApplicantOut {
  id: string;
  full_name: string;
  cnic_masked: string;
  phone_masked: string;
  city: string;
  archetype: string;
  business_type: string;
  dependents_count: number;
  has_fixed_premises: boolean;
  created_at: string;
}

export interface DocumentOut {
  id: string;
  doc_type: string;
  filename: string;
  extraction_method: string;
  confidence: number;
  extracted_json: Record<string, unknown>;
  uploaded_at: string;
}

export interface DecisionOut {
  id: string;
  decision: string;
  approved_amount_pkr: number | null;
  approved_installment_pkr: number | null;
  tenor_months: number | null;
  officer_note: string;
  override_flag: boolean;
  created_at: string;
}

export interface ApplicationSummary {
  id: string;
  applicant_name: string;
  city: string;
  archetype: string;
  status: ApplicationStatus;
  requested_amount_pkr: number;
  score: number | null;
  risk_band: RiskBand | null;
  safe_installment_pkr: number | null;
  principal_pkr: number | null;
  submitted_at: string;
  decided_at: string | null;
  override_flag: boolean;
}

export interface ApplicationDetail {
  id: string;
  status: ApplicationStatus;
  requested_amount_pkr: number;
  purpose: string;
  submitted_at: string;
  decided_at: string | null;
  decided_by: string | null;
  applicant: ApplicantOut;
  documents: DocumentOut[];
  score_result: ScoreResponse | null;
  decision: DecisionOut | null;
}

export interface PaginatedApplications {
  items: ApplicationSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface DecisionCreate {
  decision: DecisionType;
  approved_amount_pkr?: number | null;
  approved_installment_pkr?: number | null;
  tenor_months?: number | null;
  officer_note?: string;
  decided_by?: string;
  justification?: string | null;
}

export interface MetricsResponse {
  applications_total: number;
  applications_today: number;
  approval_rate: number;
  mean_score: number;
  portfolio_expected_loss_pkr: number;
  override_rate: number;
  band_distribution: Record<string, number>;
  score_histogram: { range: string; count: number; band: RiskBand }[];
  approval_rate_by_band: Record<string, number>;
  city_breakdown: {
    city: string;
    applications: number;
    mean_score: number;
    approval_rate: number;
  }[];
  override_trend: {
    date: string;
    decisions: number;
    overrides: number;
    rate: number;
  }[];
  disclaimer: string;
}

export interface ModelInfoResponse {
  version: string;
  trained_at: string | null;
  feature_order: string[];
  n_features: number;
  base_rate: number;
  metrics: Record<string, number>;
  decile_lift: { decile: number; n: number; default_rate: number; lift: number }[];
  hyperparameters: Record<string, unknown>;
  fairness_summary: { source: string; headlines: string[] } | null;
}

export interface MockProfile {
  id: string;
  display_name: string;
  headline: string;
  city: string;
  archetype: string;
  business_type: string;
  requested_amount_pkr: number;
  purpose: string;
  applicant: ApplicantIn;
  features: Record<string, number>;
  bill_fields: Record<string, unknown>;
  monthly_series: MonthlyPoint[];
  expected_band: RiskBand;
}

export const DISCLAIMER =
  "Demonstration model trained on synthetic data. Not a regulated credit decision.";
