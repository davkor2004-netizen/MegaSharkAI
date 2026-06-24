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

export const ADMIN_NAV: AppNavItem[] = [
  { href: '/admin/chat', label: 'Чаты поддержки', match: 'prefix', audience: 'admin' },
  { href: '/settings', label: 'Настройки AI', match: 'prefix', audience: 'admin' }
];

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
