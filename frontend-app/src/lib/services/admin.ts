/**
 * Клиент Admin Control Center.
 *
 * Тонкая типизированная обёртка над apiJson для read-only admin-эндпоинтов.
 * Не меняет глобальный auth flow (используется тот же apiFetch + handleUnauthorized).
 */
import { apiJson } from '$lib/utils/http';

export interface AdminOverview {
  users_total: number;
  new_users_24h: number;
  new_users_7d: number;
  new_users_30d: number;
  active_trials: number;
  paid_users: number;
  active_subscriptions: number;
  approximate_mrr: number;
  currency: string;
  backend_status: string;
  db_status: string;
  redis_status: string;
  celery_status: string;
  parser_summary: unknown | null;
  ai_summary: unknown | null;
}

export interface AdminUserRow {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  is_marketplace_seller: boolean;
  created_at: string;
  current_tariff: string | null;
  subscription_status: string;
  trial_until: string | null;
  products_count: number;
  marketplace_keys_count: number;
  last_activity: string | null;
}

export interface AdminUsersResponse {
  items: AdminUserRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminSubscriptionRow {
  user_email: string;
  plan: string;
  plan_name: string;
  status: string;
  started_at: string | null;
  current_period_end: string | null;
  trial_ends_at: string | null;
  is_trial: boolean;
  is_active: boolean;
  price: number | null;
  billing_cycle: string | null;
  source: string | null;
}

export interface AdminSubscriptionsResponse {
  items: AdminSubscriptionRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminTariff {
  code: string;
  name: string;
  price: number | null;
  currency: string;
  billing_period: string;
  is_public: boolean;
  is_manual_only: boolean;
  limits: Record<string, number>;
  feature_flags: Record<string, boolean>;
}

export interface AdminSystemStatus {
  environment: string;
  debug: boolean;
  is_production: boolean;
  version: string;
  commit: string | null;
  uptime_seconds: number;
  db_status: string;
  redis_status: string;
  celery_status: string;
  celery_workers: string[];
  alembic_current: string | null;
  alembic_head: string | null;
  parser_debug_dumps_enabled: boolean;
  warnings: string[];
}

export interface AdminParserStatus {
  parser_debug_dumps_enabled: boolean;
  parser_debug_dir: string | null;
  supported_marketplaces: string[];
  proxy_pool: { enabled: boolean; total: number; available: number; blocked: number };
  recent_stats: unknown | null;
}

export interface AdminAiProvider {
  configured: boolean;
  key_masked: string | null;
}

export interface AdminAiStatus {
  active_provider: string;
  providers: Record<string, AdminAiProvider>;
  test_connection_status: unknown | null;
  usage_counters: unknown | null;
  last_errors: unknown | null;
}

export interface AdminUserRef {
  id: string;
  email: string;
  full_name: string | null;
}

export interface AdminSecurityEventRow {
  id: number;
  event_type: string;
  severity: 'info' | 'warning' | 'high' | 'critical';
  user: AdminUserRef | null;
  ip: string | null;
  user_agent: string | null;
  path: string | null;
  method: string | null;
  status_code: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

export interface AdminSecurityRecentFailedLogin {
  id: number;
  ip: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
}

export interface AdminSecurityEvents {
  available: boolean;
  note?: string;
  items: AdminSecurityEventRow[];
  total: number;
  summary: { info: number; warning: number; high: number; critical: number };
  recent_failed_logins: AdminSecurityRecentFailedLogin[];
  limit: number;
  offset: number;
  filters?: Record<string, string | null>;
}

export interface AdminAuditRow {
  id: number;
  action: string;
  actor: AdminUserRef | null;
  target: AdminUserRef | null;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown> | null;
  ip: string | null;
  user_agent: string | null;
  created_at: string | null;
}

export interface AdminAuditResponse {
  available: boolean;
  note?: string;
  items: AdminAuditRow[];
  total: number;
  limit: number;
  offset: number;
  filters?: Record<string, string | null>;
}

const BASE = '/api/v1/admin';

export const AdminService = {
  overview: () => apiJson<AdminOverview>(`${BASE}/overview`, {}, 'Не удалось загрузить обзор'),

  users: (params: { search?: string; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.search) qs.set('search', params.search);
    if (params.limit != null) qs.set('limit', String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return apiJson<AdminUsersResponse>(`${BASE}/users${suffix}`, {}, 'Не удалось загрузить пользователей');
  },

  subscriptions: (params: { status?: string; plan?: string; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set('status', params.status);
    if (params.plan) qs.set('plan', params.plan);
    if (params.limit != null) qs.set('limit', String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return apiJson<AdminSubscriptionsResponse>(
      `${BASE}/billing/subscriptions${suffix}`,
      {},
      'Не удалось загрузить подписки'
    );
  },

  tariffs: () =>
    apiJson<{ items: AdminTariff[] }>(`${BASE}/tariffs`, {}, 'Не удалось загрузить тарифы'),

  systemStatus: () =>
    apiJson<AdminSystemStatus>(`${BASE}/system/status`, {}, 'Не удалось загрузить статус системы'),

  parserStatus: () =>
    apiJson<AdminParserStatus>(`${BASE}/parser/status`, {}, 'Не удалось загрузить статус парсера'),

  aiStatus: () => apiJson<AdminAiStatus>(`${BASE}/ai/status`, {}, 'Не удалось загрузить статус AI'),

  securityEvents: (
    params: { severity?: string; event_type?: string; user_id?: string; limit?: number; offset?: number } = {}
  ) => {
    const qs = new URLSearchParams();
    if (params.severity) qs.set('severity', params.severity);
    if (params.event_type) qs.set('event_type', params.event_type);
    if (params.user_id) qs.set('user_id', params.user_id);
    if (params.limit != null) qs.set('limit', String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return apiJson<AdminSecurityEvents>(
      `${BASE}/security/events${suffix}`,
      {},
      'Не удалось загрузить события'
    );
  },

  audit: (
    params: { action?: string; entity_type?: string; actor?: string; target?: string; limit?: number; offset?: number } = {}
  ) => {
    const qs = new URLSearchParams();
    if (params.action) qs.set('action', params.action);
    if (params.entity_type) qs.set('entity_type', params.entity_type);
    if (params.actor) qs.set('actor', params.actor);
    if (params.target) qs.set('target', params.target);
    if (params.limit != null) qs.set('limit', String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return apiJson<AdminAuditResponse>(`${BASE}/audit${suffix}`, {}, 'Не удалось загрузить журнал');
  }
};
