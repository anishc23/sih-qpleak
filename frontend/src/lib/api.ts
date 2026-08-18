/**
 * Typed client for the SecureLock API.
 *
 * One rule enforced here: the frontend never decides whether something is
 * allowed. It asks, and renders whatever the server says -- including the
 * denials, which are part of the story rather than errors to hide.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
const TOKEN_KEY = "securelock.token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** 423 = the smart contract refused. Rendered as a lock, not a failure. */
  get isTimeLocked() {
    return this.status === 423;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isChainDown() {
    return this.status === 503;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const { params, ...init } = options;
  const url = new URL(`${BASE}${path}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    }
  }

  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(url.toString(), { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(
      "Cannot reach the SecureLock API. Is the backend running on port 8000?",
      0,
    );
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }

  if (!res.ok) {
    const detail =
      (body as { detail?: unknown })?.detail ??
      (typeof body === "string" ? body : null) ??
      res.statusText;
    throw new ApiError(
      typeof detail === "string" ? detail : JSON.stringify(detail),
      res.status,
    );
  }
  return body as T;
}

const get = <T,>(p: string, params?: Record<string, string | number | boolean | undefined>) =>
  request<T>(p, { method: "GET", params });
const post = <T,>(p: string, body?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
  request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined, params });
const put = <T,>(p: string, body?: unknown) =>
  request<T>(p, { method: "PUT", body: body ? JSON.stringify(body) : undefined });

// ---------------------------------------------------------------- types

export type Role =
  | "SUPER_ADMIN"
  | "QUESTION_SETTER"
  | "REVIEWER"
  | "EXAM_AUTHORITY"
  | "AUDITOR";

export type Difficulty = "EASY" | "MEDIUM" | "HARD";

export type QuestionStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "AVAILABLE_FOR_SYNTHESIS"
  | "SELECTED"
  | "USED_IN_PAPER"
  | "RETIRED";

export type PaperStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "ENCRYPTED"
  | "BLOCKCHAIN_REGISTERED"
  | "LOCKED"
  | "RELEASED";

export interface User {
  user_uid: string;
  name: string;
  email: string;
  role: Role;
  department: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Permissions {
  read: boolean;
  write: boolean;
  approve: boolean;
}

export interface Question {
  question_uid: string;
  subject: string;
  topic: string;
  difficulty: Difficulty;
  question_type: string;
  marks: number;
  learning_objective: string | null;
  content_hash: string;
  version: number;
  status: QuestionStatus;
  creator_uid: string;
  creator_name: string;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  permissions: Permissions;
}

export interface ChainReceipt {
  submitted: boolean;
  confirmed: boolean;
  tx_hash: string | null;
  block_number: number | null;
  status: string | null;
  error: string | null;
  message: string | null;
}

export interface Paper {
  paper_uid: string;
  exam_uid: string;
  exam_title: string;
  status: PaperStatus;
  paper_hash: string | null;
  release_time: string | null;
  released_at: string | null;
  contract_address: string | null;
  registration_tx: string | null;
  release_tx: string | null;
  question_count: number;
  blueprint_compliance: BlueprintCompliance | null;
  synthesis_report: SynthesisReport | null;
  created_at: string;
  questions?: PaperQuestion[];
}

export interface PaperQuestion {
  sequence: number;
  question_uid: string;
  topic: string;
  difficulty: Difficulty;
  marks: number;
  selection_score: number;
  selection_reason: string | null;
  used_variation: boolean;
}

export interface BlueprintCompliance {
  difficulty_compliance: number;
  topic_compliance: number;
  marks_compliance: number;
  duplicate_risk: string;
  worst_pair_similarity: number;
  difficulty_targets: Record<string, number>;
  difficulty_actual: Record<string, number>;
  topic_targets: Record<string, number>;
  topic_actual: Record<string, number>;
  marks_target: number;
  marks_actual: number;
}

export interface SynthesisReport {
  seed: number;
  pool_size: number;
  selected_count: number;
  distinct_contributors: number;
  duplicate_pairs_detected: number;
  high_risk_duplicates: number;
  duplicate_threshold: number;
  method: string;
  duplicates?: DuplicatePair[];
}

export interface DuplicatePair {
  left: string;
  right: string;
  similarity: number;
  risk: "HIGH" | "MEDIUM" | "LOW" | "NEGLIGIBLE";
}

export interface TimeLockState {
  registered: boolean;
  blockchain_available?: boolean;
  status: string;
  paper_uid?: string;
  paper_hash?: string;
  release_time?: number;
  blockchain_time?: number;
  server_time?: number;
  release_time_reached?: boolean;
  seconds_remaining?: number;
  released?: boolean;
  authority?: string;
  note?: string;
  message?: string;
  error?: string;
}

export interface AuditEvent {
  event_uid: string;
  event_type: string;
  actor_uid: string | null;
  actor_role: string | null;
  resource_type: string;
  resource_id: string;
  resource_hash: string | null;
  success: boolean;
  detail: Record<string, unknown> | null;
  blockchain_tx: string | null;
  event_hash: string;
  prev_hash: string;
  created_at: string;
}

export interface ChainVerification {
  total_events: number;
  intact: boolean;
  broken_count: number;
  first_broken_at: string | null;
  broken_events: Array<Record<string, unknown>>;
  chain_head: string;
}

export interface DashboardStats {
  total_questions: number;
  approved_questions: number;
  pending_review: number;
  rejected_questions: number;
  active_exams: number;
  papers_locked: number;
  papers_released: number;
  blockchain_transactions: number;
  security_events: number;
  audit_events: number;
}

export interface BlockchainStatus {
  connected: boolean;
  rpc_url: string;
  chain_id?: number;
  network_label: string;
  latest_block?: number;
  blockchain_time?: number;
  sender?: string;
  contracts?: Record<string, string>;
  error?: string;
}

export interface SecurityCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface Exam {
  exam_uid: string;
  title: string;
  subject: string;
  total_marks: number;
  question_count: number;
  scheduled_at: string | null;
  blueprint: {
    difficulty_distribution: Record<string, number>;
    topic_distribution: Record<string, number>;
  } | null;
  paper_count: number;
  created_at: string;
}

export interface Variation {
  id: number;
  question_uid: string;
  original: string;
  variation: string;
  similarity_score: number;
  generation_method: string;
  review_status: string;
  original_hash: string;
  generated_hash: string;
  topic: string;
  difficulty: Difficulty;
}

// ---------------------------------------------------------------- endpoints

export const api = {
  login: (email: string, password: string) =>
    post<{ access_token: string; expires_in: number; user: User }>("/auth/login", {
      email,
      password,
    }),
  me: () => get<User>("/auth/me"),
  users: () => get<User[]>("/auth/users"),

  questions: (params?: Record<string, string | number | undefined>) =>
    get<Question[]>("/questions", params),
  question: (uid: string) => get<Question>(`/questions/${uid}`),
  createQuestion: (body: Record<string, unknown>) =>
    post<{
      question: Question;
      encryption: Record<string, unknown>;
      blockchain: ChainReceipt;
    }>("/questions", body),
  readQuestion: (uid: string) =>
    post<{ question_uid: string; content: string; content_hash: string; version: number }>(
      `/questions/${uid}/read`,
    ),
  updateQuestion: (uid: string, body: Record<string, unknown>) =>
    put<Question>(`/questions/${uid}`, body),
  submitQuestion: (uid: string) => post<Question>(`/questions/${uid}/submit`),
  reviewQuestion: (uid: string, approve: boolean, comment?: string) =>
    post<Question>(`/questions/${uid}/review`, { approve, comment }),
  questionVersions: (uid: string) =>
    get<Array<{ version: number; content_hash: string; change_note: string | null; created_at: string }>>(
      `/questions/${uid}/versions`,
    ),
  questionAccessLog: (uid: string) =>
    get<
      Array<{
        access_type: string;
        granted: boolean;
        reason: string | null;
        user_uid: string;
        user_name: string;
        role: string;
        created_at: string;
      }>
    >(`/questions/${uid}/access-log`),
  verifyQuestion: (uid: string) => get<Record<string, unknown>>(`/questions/${uid}/verify`),
  questionAudit: (uid: string) => get<AuditEvent[]>(`/audit/questions/${uid}`),

  exams: () => get<Exam[]>("/exams"),
  generatePaper: (examUid: string, applyVariations: boolean) =>
    post<Paper>(`/exams/${examUid}/generate-paper`, { apply_variations: applyVariations }),

  duplicates: (subject?: string) =>
    get<{
      pool_size: number;
      threshold: number;
      method: string;
      pairs: DuplicatePair[];
      high_risk: number;
    }>("/synthesis/duplicates", { subject }),
  variations: () => get<Variation[]>("/synthesis/variations"),
  reviewVariation: (id: number, approve: boolean) =>
    post<{ id: number; review_status: string }>(
      `/synthesis/variations/${id}/review`,
      undefined,
      { approve },
    ),

  papers: () => get<Paper[]>("/papers"),
  paper: (uid: string) => get<Paper>(`/papers/${uid}`),
  encryptPaper: (uid: string) => post<Paper>(`/papers/${uid}/encrypt`),
  registerPaper: (uid: string, releaseInSeconds: number) =>
    post<{
      tx_hash: string;
      block_number: number;
      contract_address: string;
      release_time: string;
    }>(`/papers/${uid}/register-blockchain`, { release_in_seconds: releaseInSeconds }),
  timeLock: (uid: string) => get<TimeLockState>(`/papers/${uid}/time-lock`),
  releasePaper: (uid: string) =>
    post<{ released: boolean; tx_hash: string | null; already_released: boolean }>(
      `/papers/${uid}/release`,
    ),
  decryptPaper: (uid: string) =>
    post<{
      paper_uid: string;
      content: string;
      paper_hash: string;
      released_at: string | null;
      blockchain_verified: boolean;
    }>(`/papers/${uid}/decrypt`),
  verifyPaper: (uid: string) => get<Record<string, unknown>>(`/papers/${uid}/verify`),
  paperAudit: (uid: string) => get<AuditEvent[]>(`/audit/papers/${uid}`),

  audit: (params?: Record<string, string | number | boolean | undefined>) =>
    get<AuditEvent[]>("/audit", params),
  verifyAudit: () => get<ChainVerification>("/audit/verify"),
  tamperAudit: (eventUid: string) =>
    post<Record<string, unknown>>("/demo/tamper-audit", undefined, {
      event_uid: eventUid,
      new_event_type: "QUESTION_APPROVED",
    }),
  resetTamper: () => post<Record<string, unknown>>("/demo/reset-tamper"),
  clockComparison: (paperUid: string) =>
    get<Record<string, unknown>>("/demo/clock-comparison", { paper_uid: paperUid }),

  blockchainStatus: () => get<BlockchainStatus>("/blockchain/status"),
  blockchainTransactions: () =>
    get<
      Array<{
        tx_hash: string | null;
        contract: string;
        contract_address: string | null;
        method: string;
        resource_type: string;
        resource_id: string;
        status: string;
        block_number: number | null;
        gas_used: number | null;
        error: string | null;
        created_at: string;
      }>
    >("/blockchain/transactions"),
  blockchainEvents: () =>
    get<
      Array<{
        contract: string;
        event: string;
        block_number: number;
        tx_hash: string;
        args: Record<string, unknown>;
      }>
    >("/blockchain/events"),

  dashboardStats: () => get<DashboardStats>("/dashboard/stats"),
  securityStatus: () =>
    get<{
      checks: SecurityCheck[];
      audit_chain: { intact: boolean; head: string };
      blockchain: BlockchainStatus;
    }>("/security/status"),
};
