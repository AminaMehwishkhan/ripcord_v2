export type EntityStatus = "UNKNOWN" | "UNCERTAIN" | "CLARIFYING" | "VERIFIED" | "INVALIDATED";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface Word {
  text: string;
  confidence: number;
  start: number;
  end: number;
  word_is_final: boolean;
}

export interface CriticalEntity {
  type: string;
  value: string;
  raw_words: Word[];
  confidence: number;
  expected_pattern: string;
  format_valid: boolean;
  status: EntityStatus;
  turn_order: number;
  end_of_turn_confidence: number | null;
  digit_confidences: number[];
  style: "digits" | "pairs" | "cardinal" | "numeral";
  min_confidence: number;
  low_conf_fraction: number;
  context_confidence: number | null;
  teen_ten_words: number;
  homophone_digits: number;
  carrier_found: boolean;
  competing_spans: number;
  speech_rate: number | null;
}

export interface RiskAssessment {
  risk_score: number;
  risk_level: RiskLevel;
  signals: string[];
  should_clarify: boolean;
  breakdown: Record<string, number>;
  reasons: string[];
  weak_positions: number[];
  threshold: number;
  engine: string;
}

export interface ClarificationQuestion {
  question: string;
  kind: "confirm" | "disambiguate" | "repeat_digit_by_digit" | "read_back";
  candidate_value: string | null;
  alternative_value: string | null;
  uncertain_positions: number[];
}

export interface TimelineEvent {
  ts_ms: number;
  label: string;
  detail: string | null;
  kind: "speech" | "capture" | "risk" | "pause" | "clarify" | "verify" | "resume" | "action" | "system";
}

export interface ConversationTurn {
  role: "caller" | "agent" | "system";
  text: string;
  words: Word[];
  ts_ms: number;
  note: string | null;
}

export type ConnectionStatus = "idle" | "connecting" | "live" | "reconnecting" | "disconnected";

export interface ResolvedEntry {
  entity_type: string;
  value: string;
  status: EntityStatus;
  required_clarification: boolean;
  risk_score: number | null;
  ts_ms: number;
}

export interface SessionState {
  session_id: string;
  ripcord_enabled: boolean;
  mock_mode: boolean;
  connection_status: ConnectionStatus;
  transcript: string;
  live_partial: string;
  entity: CriticalEntity | null;
  risk: RiskAssessment | null;
  clarification: ClarificationQuestion | null;
  verified_value: string | null;
  action_result: string | null;
  workflow_paused: boolean;
  escalated: boolean;
  attempts: number;
  timeline: TimelineEvent[];
  conversation: ConversationTurn[];
  last_decision_latency_ms: number | null;
  history: ResolvedEntry[];
}

export interface CompareState {
  truth: string | null;
  scenario_id: number;
  a: SessionState;
  b: SessionState;
}

export interface Scenario {
  id: number;
  title: string;
  spoken: string;
  source: "recorded" | "scripted";
  condition: string | null;
  has_replies: boolean;
  truth: string | null;
  category: string | null;
}

export interface Health {
  status: string;
  mock_mode: boolean;
  assemblyai_key_configured: boolean;
  risk_engine: string;
  clarify_threshold: number;
  model_meta: Record<string, unknown> | null;
}

export interface EvaluationReport {
  scenario_count: number;
  entity_errors_without_ripcord: string;
  entity_errors_with_ripcord: string;
  recovered_correctly: string;
  false_clarifications: string;
  verified_entity_rate: string;
  avg_extra_turns_from_ripcord: number;
  per_scenario: Array<{
    id: number;
    title: string;
    mode_a_value: string | null;
    mode_b_value: string | null;
    ground_truth: string | null;
    mode_a_wrong: boolean;
    mode_b_wrong: boolean;
    clarified: boolean;
  }>;
}

export interface Rate {
  value: number;
  ci: [number, number];
  n: number;
}

export interface PolicyResult {
  label: string;
  n: number;
  wrong_action: Rate;
  correct_action: Rate;
  unresolved: Rate;
  questions_per_call: Rate;
  error_catch_rate: Rate | null;
  false_alarm_rate: Rate | null;
  misheard_calls: number;
  clean_capture_calls: number;
  silent_catch_rate?: Rate | null;
  misheard_valid_format_calls?: number;
}

export interface CurvePoint {
  threshold: number;
  catch: number;
  false_alarm: number;
}

export interface HardCase {
  n: number;
  n_misheard: number;
  auroc: Record<string, number | null>;
  curves: Record<string, Array<{ false_alarm: number; catch: number }>>;
}

export interface BenchmarkResults {
  split: string;
  n_calls: number;
  capture_error_rate: number | null;
  no_entity_rate: number | null;
  generated: string;
  policies: Record<string, PolicyResult>;
  auroc: Record<string, number | null>;
  auroc_valid_format?: Record<string, number | null>;
  format_valid_rate?: number | null;
  hard_case?: HardCase | null;
  curves: Record<string, CurvePoint[]>;
  reliability: { ece: number; bins: Array<{ bin: string; predicted: number; observed: number; n: number }> } | null;
  by_condition: Record<
    string,
    {
      label: string;
      n: number;
      no_check?: { wrong_action: number; asked: number };
      ripcord_v2?: { wrong_action: number; asked: number };
    }
  >;
  silent_failures: Array<{
    id: string;
    condition: string;
    truth: string;
    heard: string | null;
    transcript: string;
    min_conf: number | null;
    mean_conf: number | null;
  }>;
  model: {
    features: string[];
    weights: number[];
    mean: number[];
    std: number[];
    bias: number;
    threshold: number;
    invalid_format_p?: number;
    meta: Record<string, unknown>;
  };
  dataset: {
    total: number;
    per_split: Record<string, number>;
    speakers: number;
    asr: string;
    tts: string;
  };
}

export interface AssessResponse {
  entity: CriticalEntity | null;
  risk: RiskAssessment | null;
  question: ClarificationQuestion | null;
}
