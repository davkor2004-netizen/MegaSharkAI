/** Утилиты отображения тарифов на фронтенде (соответствуют backend plans.py). */

/** Человекочитаемые названия тарифов по коду. */
const PLAN_LABELS: Record<string, string> = {
  trial: 'Trial',
  pro: 'PRO',
  business: 'BUSINESS',
  agency: 'AGENCY',
  enterprise: 'ENTERPRISE'
};

/** Вернуть отображаемое имя тарифа по коду (или сам код, если неизвестен). */
export function planLabel(code: string | null | undefined): string {
  if (!code) return '—';
  return PLAN_LABELS[code.toLowerCase()] ?? code;
}

/** Человекочитаемые подписи метрик использования. */
export const USAGE_LABELS: Record<string, string> = {
  ai_actions: 'AI-действия',
  ai_audits: 'AI-аудиты',
  seo_generations: 'SEO-генерации',
  review_replies: 'Ответы на отзывы',
  parsing_requests: 'Запросы парсинга',
  exports: 'Экспорты',
  products: 'Товары',
  tracked_competitors: 'Конкуренты',
  marketplace_keys: 'Ключи маркетплейсов'
};

/** Человекочитаемые подписи feature-флагов. */
export const FEATURE_LABELS: Record<string, string> = {
  ai_audit_access: 'AI-аудит карточек',
  competitor_analysis_access: 'Анализ конкурентов',
  analytics_access: 'Аналитика',
  reports_access: 'Отчёты',
  repricing_access: 'Репрайсинг',
  auto_repricing_access: 'Авторепрайсинг',
  widget_access: 'Виджет для сайта',
  telegram_notifications_access: 'Telegram-уведомления',
  bulk_import_access: 'Массовый импорт',
  advanced_reports_access: 'Расширенные отчёты',
  white_label_reports_access: 'White-label отчёты',
  team_access: 'Командный доступ',
  priority_queue_access: 'Приоритетная очередь',
  agency_projects_access: 'Агентские проекты'
};

/** Тип сводки использования (ответ GET /api/v1/billing/usage). */
export interface UsageEntry {
  used: number;
  limit: number | null;
  unlimited: boolean;
  kind: 'monthly' | 'volume';
  label: string;
}

export interface UsageSummary {
  current_plan: string;
  plan_name: string;
  is_subscribed: boolean;
  reset_at: string;
  limits: Record<string, number>;
  features: Record<string, boolean>;
  usage: Record<string, UsageEntry>;
  upgrade_url?: string;
  plan_order?: string[];
}
