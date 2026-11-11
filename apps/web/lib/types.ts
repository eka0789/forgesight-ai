// ForgeSight AI — API contract types (mirrors services/api/app/schemas)

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: "owner" | "admin" | "engineer" | "operator" | "viewer";
  org_id: number;
  is_active: boolean;
  created_at?: string;
}

export interface Organization {
  id: number;
  name: string;
  slug: string;
  is_demo: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: User;
  organization: Organization;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Machine {
  id: number;
  code: string;
  name: string;
  machine_type: string;
  location: string | null;
  status: "healthy" | "warning" | "critical" | "offline";
  is_active: boolean;
  created_at?: string;
}

export interface MachineHealth {
  machine_id: number;
  machine_code: string;
  status: string;
  health_score: number;
  failure_probability: number;
  risk_level: "low" | "medium" | "high" | "critical";
  rul_hours: number | null;
  predicted_modes: Record<string, number> | null;
  recommendations: string[] | null;
  model_version: string | null;
  latest_reading: Record<string, number | string> | null;
  is_prediction_available: boolean;
  note: string | null;
}

export interface Defect {
  id?: number;
  label: string;
  confidence: number;
  bbox_x1?: number | null;
  bbox_y1?: number | null;
  bbox_x2?: number | null;
  bbox_y2?: number | null;
  severity?: string | null;
  method?: string | null;
  frame_index?: number;
}

export interface Inspection {
  id: number;
  machine_id: number | null;
  kind: "image" | "video";
  filename: string;
  status: "pending" | "processing" | "completed" | "failed";
  result: "ok" | "defect_detected" | null;
  defect_count: number;
  avg_confidence: number | null;
  method_used: string | null;
  processing_ms: number | null;
  model_version: string | null;
  error: string | null;
  is_demo: boolean | null;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface InspectionDetail extends Inspection {
  defects: Defect[];
  images: { file_key: string; annotated?: boolean; frame_index?: number | null }[];
  anomaly?: {
    score: number;
    threshold?: number | null;
    is_anomalous?: boolean;
    method: string;
  } | null;
  ocr?: { text: string; method: string; available?: boolean; note?: string } | null;
}

export interface Prediction {
  id: number;
  machine_id: number;
  model_version: string;
  failure_probability: number;
  risk_level: string;
  health_score: number;
  rul_hours: number | null;
  predicted_modes: Record<string, number> | null;
  recommendations: string[] | null;
  is_demo: boolean | null;
  created_at?: string | null;
}

export interface MaintenanceRequest {
  id: number;
  machine_id: number;
  title: string;
  description: string | null;
  priority: "low" | "medium" | "high" | "urgent";
  status: "open" | "approved" | "in_progress" | "done" | "rejected";
  source: string;
  created_at?: string | null;
}

export interface DocumentOut {
  id: number;
  title: string;
  filename: string;
  status: "pending" | "processing" | "indexed" | "failed";
  error: string | null;
  chunk_count: number;
  page_count: number | null;
  size_bytes: number | null;
  is_demo: boolean | null;
  created_at?: string | null;
}

export interface Citation {
  index: number;
  document_id: number;
  document_title: string;
  page_number: number | null;
  chunk_index: number;
  quote: string | null;
}

export interface ChatResponse {
  conversation_id: number;
  answer: string;
  citations: Citation[];
  llm_provider: string;
  has_context: boolean;
  disclaimer: string | null;
}

export interface AgentTool {
  name: string;
  description: string;
  requires_approval: boolean;
  args_schema: string[];
}

export interface ToolLog {
  id: number;
  tool_name: string;
  args: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  status: string;
  duration_ms: number | null;
}

export interface AgentChatResult {
  execution_id: number;
  conversation_id: number;
  status: string;
  planner: string;
  iterations: number;
  answer?: string;
  tool_results: { tool: string; status: string; result: unknown }[];
  approval_required?: { tool: string; args: Record<string, unknown> };
  message?: string;
}

export interface AgentExecution {
  id: number;
  input: string;
  status: string;
  iterations: number;
  planner: string;
  result: Record<string, unknown> | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ModelVersion {
  id: number;
  version: string;
  framework: string;
  status: string;
  artifact_path: string | null;
  metrics: Record<string, unknown> | null;
  params: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface MLModel {
  id: number;
  name: string;
  task: string;
  description: string | null;
  versions: ModelVersion[];
}

export interface Experiment {
  id: number;
  name: string;
  kind: string;
  params: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface Kpis {
  total_inspections: number;
  total_defects: number;
  defect_detection_rate: number;
  avg_machine_health: number;
  predicted_maintenance_events: number;
  avg_inference_ms: number | null;
  open_maintenance_requests: number;
}

export interface DashboardSummary {
  kpis: Kpis;
  production_trend: { date: string; inspections: number; defects: number }[];
  defect_distribution: { label: string; count: number }[];
  machine_status: { status: string; count: number }[];
  model_metrics: { model_name: string; task: string; metrics: Record<string, unknown> }[];
  recent_activity: { ts: string; kind: string; title: string; detail: string | null }[];
  ai_system_health: {
    llm_provider: string;
    llm_mode: string;
    embedding_provider: string;
    artifacts_status: string;
    status: string;
  };
  is_demo_data: boolean;
}

export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
  storage: string;
  artifacts: string;
  llm_provider: string;
  embedding_provider: string;
  version: string;
}

export interface DriftReport {
  available: boolean;
  window_days?: number;
  n_readings?: number;
  psi_per_feature?: Record<string, number>;
  max_psi?: number;
  verdict?: string;
  note?: string;
}
