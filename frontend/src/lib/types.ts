export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  avatar_url?: string | null;
  auth_provider?: string;
  plan: "free" | "pro" | "team";
  is_admin: boolean;
  created_at: string;
}

export interface AnalysisSummary {
  id: string;
  dataset_name: string;
  status: "pending" | "processing" | "completed" | "failed";
  row_count?: number | null;
  column_count?: number | null;
  file_size_bytes: number;
  quality_score?: number | null;
  ml_readiness_score?: number | null;
  issue_count?: number | null;
  created_at: string;
  completed_at?: string | null;
}

export interface QualityIssue {
  type: string;
  column: string | null;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  detail: string;
  recommendation: string;
}

export interface AnalysisDetail extends AnalysisSummary {
  profile_result?: any;
  quality_result?: { total_issues: number; issues: QualityIssue[]; exact_duplicate_rows: number; duplicate_row_percentage: number };
  correlation_result?: any;
  target_result?: any;
  ml_readiness_result?: {
    overall_score: number;
    breakdown: Record<string, number>;
    methodology: string;
    disclaimer: string;
  };
  ai_insights?: {
    executive_summary: string;
    top_issues: { title: string; explanation: string }[];
    critical_issues: { title: string; explanation: string }[];
    recommended_cleaning_steps: string[];
    feature_engineering_suggestions: string[];
    potential_modeling_concerns: string[];
    leakage_warnings: string[];
    recommended_next_steps: string[];
    _meta?: { source: string };
  };
  charts?: any;
  error_message?: string | null;
}

export interface UsageOut {
  plan: string;
  analyses_used_this_month: number;
  analyses_limit: number;
  max_upload_mb: number;
}

// --- Teams ---
export interface Team {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  plan: string;
  member_count?: number;
  created_at: string;
}

export interface TeamMember {
  id: string;
  user_id: string;
  email?: string;
  full_name?: string;
  role: string;
  joined_at: string;
}

// --- Database Connectors ---
export interface DatabaseConnection {
  id: string;
  name: string;
  connector_type: string;
  host?: string;
  port?: number;
  database_name: string;
  username?: string;
  is_active: boolean;
  last_tested_at?: string;
  created_at: string;
}

// --- Scheduled Analysis ---
export interface ScheduledAnalysis {
  id: string;
  name: string;
  source_type: string;
  connection_id?: string;
  frequency: string;
  is_active: boolean;
  last_run_at?: string;
  next_run_at?: string;
  alert_on_quality_drop?: number;
  alert_on_row_count_change?: number;
  alert_severity: string;
  alert_channels?: string[];
  created_at: string;
}

export interface ScheduleRun {
  id: string;
  schedule_id: string;
  analysis_id?: string;
  status: string;
  alerts_triggered?: any;
  error_message?: string;
  started_at: string;
  completed_at?: string;
}

// --- Custom Rules ---
export interface CustomRule {
  id: string;
  name: string;
  description?: string;
  column_name?: string;
  operator: string;
  value?: any;
  severity: string;
  is_active: boolean;
  created_at: string;
}

export interface RuleEvaluation {
  rule_id: string;
  rule_name: string;
  passed: boolean;
  violation_count: number;
  violation_sample?: any[];
  message: string;
}

// --- Shareable Reports ---
export interface ShareableReport {
  id: string;
  analysis_id: string;
  share_token: string;
  title?: string;
  is_public: boolean;
  has_password: boolean;
  expires_at?: string;
  view_count: number;
  created_at: string;
  share_url?: string;
}

// --- Webhooks ---
export interface WebhookConfig {
  id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
  last_triggered_at?: string;
  failure_count: number;
  created_at: string;
}

// --- Audit ---
export interface AuditLogEntry {
  id: string;
  user_id?: string;
  user_email?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  details?: any;
  ip_address?: string;
  created_at: string;
}
