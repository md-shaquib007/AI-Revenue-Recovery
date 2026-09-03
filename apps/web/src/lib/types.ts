export type Metrics = {
  total_revenue_at_risk_rupees: number;
  total_revenue_recovered_rupees: number;
  recovery_rate_pct: number;
  active_cases_count: number;
  escalated_human_count: number;
  predicted_ev_rupees?: number;
  realized_recovered_rupees?: number;
  ev_calibration_ratio?: number;
};

export type RecoveryCase = {
  id: string;
  payment_id: string;
  customer: {
    id: string;
    name: string;
    email: string;
    tier: string;
    tokens_remaining: number;
    opted_out?: boolean;
  };
  state: string;
  risk_tier: string;
  amount_in_rupees: number;
  traces_count: number;
  failure_code?: string | null;
  method?: string | null;
  bank_key?: string | null;
  next_action_at?: string | null;
  grace_expires_at?: string | null;
};

export type OpsItem = {
  case_id: string;
  payment_id: string;
  customer_name: string;
  customer_email: string;
  amount_in_rupees: number;
  failure_code: string;
  risk_tier: string;
  escalated_reason: string;
};

export type BankEntity = {
  entity_key: string;
  health_score: number;
  health_pct: number;
  status: string;
  downtime_until: string | null;
};

export type SystemStatus = {
  app_env: string;
  auth_required: boolean;
  chaos_enabled: boolean;
  worker_enabled: boolean;
  llm_configured: boolean;
  llm_outage_simulated: boolean;
  version: string;
};

export type PolicyCheck = { rule_name: string; passed: boolean; detail: string };

export type DecisionTrace = {
  id: string;
  step_number: number;
  agent_mode: string;
  raw_event_type: string;
  diagnosis: Record<string, unknown>;
  proposed_action?: string;
  approved_action?: string;
  policy_checks: PolicyCheck[];
  final_action: string;
  execution_result?: Record<string, unknown>;
  prev_hash?: string | null;
  record_hash?: string | null;
  latency_ms: number;
};

export type CaseDetail = RecoveryCase & {
  amount_in_rupees: number;
  version?: number;
  audit_chain_verified?: boolean;
  payment: Record<string, unknown>;
  decision_traces: DecisionTrace[];
};

export type BenchmarkResult = {
  baseline: {
    total_recovered_amount_paise: number;
    recovery_rate_pct: number;
    unnecessary_nudges_count: number;
    policy_violations_count: number;
  };
  revive: {
    total_recovered_amount_paise: number;
    recovery_rate_pct: number;
    unnecessary_nudges_count: number;
    policy_violations_count: number;
  };
  comparison: {
    net_incremental_recovered_rupees: number;
    recovery_rate_lift_pct: number;
    unnecessary_nudges_reduced_count: number;
  };
};

export type PulseFunnelRow = { state: string; count: number; amount_rupees: number };

export type PulseCase = RecoveryCase & {
  p_recover?: number | null;
  recommended_action?: string | null;
  ev_rupees?: number | null;
  churn_risk?: number | null;
};

export type CircadianPoint = { hour: number; label: string; conversion_index: number };

export type LiveEvent = {
  type?: string;
  ts?: string;
  case_id?: string;
  payment_id?: string;
  state?: string;
  action?: string;
  count?: number;
  reason?: string;
};

export type Pulse = {
  generated_at: string;
  ist_now: string;
  ist_hour: number;
  quiet_hours: boolean;
  circadian_multiplier: number;
  seconds_until_send_window: number;
  funnel: PulseFunnelRow[];
  failure_mix: { code: string; count: number }[];
  at_risk: PulseCase[];
  active_cases: number;
  active_rupees: number;
  predicted_recover_rupees: number;
  recovered_rupees: number;
  circadian_curve: CircadianPoint[];
  live_feed: LiveEvent[];
};

export type TwinStrategy = {
  action: string;
  approved_action: string;
  policy_allowed: boolean;
  requires_human: boolean;
  p_recover: number;
  expected_value_rupees: number;
  delay_seconds: number;
  channel: string;
  override_reason?: string | null;
  preferred_rail?: string | null;
};

export type DigitalTwin = {
  ist_now: string;
  ist_hour: number;
  quiet_hours: boolean;
  circadian_multiplier: number;
  salary_cycle_boost: number;
  seconds_until_send_window: number;
  churn_risk: number;
  bank_health: number;
  base_p_recover: number;
  preferred_rail: string;
  winner: TwinStrategy;
  lift_vs_wait_rupees: number;
  strategies: TwinStrategy[];
  narrative: string;
  current_state?: string;
  case?: PulseCase;
};

export type CopilotResponse = {
  intent: string;
  answer: string;
  matches: PulseCase[];
  focus_case_id?: string;
};
