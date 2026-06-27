/** Идентификаторы смысловых групп навигации (Seller workspace). */
export type NavSection = 'overview' | 'catalog' | 'ai' | 'account';

/** Конфигурация навигации AppShell MegaSharkAI. */
export interface AppNavItem {
  href: string;
  label: string;
  /** exact — только точное совпадение; prefix — вложенные маршруты тоже активны */
  match?: 'exact' | 'prefix';
  /** admin — только для superuser */
  audience?: 'all' | 'admin';
  /** Смысловая группа в боковом меню. */
  section?: NavSection;
}

export const MAIN_NAV: AppNavItem[] = [
  { href: '/dashboard', label: 'Дашборд', match: 'exact', section: 'overview' },
  { href: '/parsing', label: 'Парсинг', match: 'prefix', section: 'catalog' },
  { href: '/products', label: 'Товары', match: 'prefix', section: 'catalog' },
  { href: '/import', label: 'Импорт', match: 'prefix', section: 'catalog' },
  { href: '/repricing', label: 'Репрайсинг', match: 'prefix', section: 'catalog' },
  { href: '/calendar', label: 'Календарь', match: 'prefix', section: 'catalog' },
  { href: '/ai', label: 'AI Генератор', match: 'prefix', section: 'ai' },
  { href: '/ai-studio', label: 'AI Студия', match: 'prefix', section: 'ai' },
  { href: '/analytics', label: 'Аналитика', match: 'prefix', section: 'ai' },
  { href: '/reports', label: 'Отчёты', match: 'prefix', section: 'ai' },
  { href: '/widget', label: 'Виджет', match: 'prefix', section: 'account' },
  { href: '/notifications', label: 'Уведомления', match: 'prefix', section: 'account' },
  { href: '/billing', label: 'Тарифы', match: 'prefix', section: 'account' },
  { href: '/partners', label: 'Партнёрство', match: 'prefix', section: 'account' },
  { href: '/profile', label: 'Профиль', match: 'prefix', section: 'account' }
];

/** Порядок и заголовки смысловых групп Seller workspace. */
export const NAV_SECTIONS: { id: NavSection; label: string }[] = [
  { id: 'overview', label: 'Обзор' },
  { id: 'catalog', label: 'Товары и цены' },
  { id: 'ai', label: 'AI и аналитика' },
  { id: 'account', label: 'Кабинет' }
];

/** Сгруппировать пункты MAIN_NAV по секциям с сохранением порядка. */
export function getNavGroups(): { id: NavSection; label: string; items: AppNavItem[] }[] {
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: MAIN_NAV.filter((item) => (item.section ?? 'overview') === section.id)
  })).filter((group) => group.items.length > 0);
}

/** Идентификаторы групп админского меню (Admin Control Center). */
export type AdminNavSection = 'control' | 'monitoring' | 'security' | 'support';

/** Группа админского меню с заголовком и пунктами. */
export interface AdminNavGroup {
  id: AdminNavSection;
  label: string;
  items: AppNavItem[];
}

/**
 * Навигация Admin Control Center (только для superuser).
 *
 * Полностью отделена от Seller workspace: обычный селлер этих пунктов не видит,
 * а админ видит только это меню вместо инструментов кабинета.
 */
export const ADMIN_NAV_GROUPS: AdminNavGroup[] = [
  {
    id: 'control',
    label: 'Центр управления',
    items: [
      { href: '/admin', label: 'Обзор', match: 'exact', audience: 'admin' },
      { href: '/admin/users', label: 'Пользователи', match: 'prefix', audience: 'admin' },
      { href: '/admin/billing', label: 'Подписки и платежи', match: 'prefix', audience: 'admin' },
      { href: '/admin/tariffs', label: 'Тарифы и лимиты', match: 'prefix', audience: 'admin' }
    ]
  },
  {
    id: 'monitoring',
    label: 'Мониторинг',
    items: [
      { href: '/admin/system', label: 'Система', match: 'prefix', audience: 'admin' },
      { href: '/admin/parser', label: 'Парсер', match: 'prefix', audience: 'admin' },
      { href: '/admin/ai', label: 'AI-провайдеры', match: 'prefix', audience: 'admin' }
    ]
  },
  {
    id: 'security',
    label: 'Безопасность',
    items: [
      { href: '/admin/security', label: 'Безопасность', match: 'prefix', audience: 'admin' },
      { href: '/admin/audit', label: 'Журнал действий', match: 'prefix', audience: 'admin' }
    ]
  },
  {
    id: 'support',
    label: 'Поддержка',
    items: [{ href: '/admin/chat', label: 'Чаты поддержки', match: 'prefix', audience: 'admin' }]
  }
];

/** Группы админского меню (для Sidebar при isSuperuser). */
export function getAdminNavGroups(): AdminNavGroup[] {
  return ADMIN_NAV_GROUPS;
}

export const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Дашборд',
  '/parsing': 'Парсинг',
  '/products': 'Товары',
  '/import': 'Импорт',
  '/repricing': 'Репрайсинг',
  '/calendar': 'Календарь',
  '/ai': 'AI Генератор',
  '/ai-studio': 'AI Студия',
  '/analytics': 'Аналитика',
  '/reports': 'Отчёты',
  '/widget': 'Виджет',
  '/notifications': 'Уведомления',
  '/billing': 'Тарифы',
  '/profile': 'Профиль',
  '/settings': 'Настройки',
  '/partners': 'Партнёрство',
  // Admin Control Center
  '/admin': 'Центр управления',
  '/admin/users': 'Пользователи',
  '/admin/billing': 'Подписки и платежи',
  '/admin/tariffs': 'Тарифы и лимиты',
  '/admin/system': 'Система',
  '/admin/parser': 'Мониторинг парсера',
  '/admin/ai': 'AI-провайдеры',
  '/admin/security': 'Безопасность',
  '/admin/audit': 'Журнал действий',
  '/admin/chat': 'Чаты поддержки'
};

/** Заголовок страницы по pathname. */
export function getPageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];

  const prefixMatch = Object.entries(PAGE_TITLES)
    .filter(([path]) => path !== '/dashboard')
    .sort((a, b) => b[0].length - a[0].length)
    .find(([path]) => pathname.startsWith(path));

  return prefixMatch?.[1] ?? 'MegaSharkAI';
}

/** Активен ли пункт меню для текущего URL. */
export function isNavItemActive(pathname: string, item: AppNavItem): boolean {
  if (item.match === 'exact') return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
