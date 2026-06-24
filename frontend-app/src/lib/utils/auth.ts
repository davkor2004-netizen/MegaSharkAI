/** Утилиты авторизации (HttpOnly cookie, без localStorage для JWT). */

import { apiFetch } from '$lib/utils/api';

const LEGACY_TOKEN_KEYS = ['access_token', 'refresh_token', 'token_type'] as const;

let logoutInProgress = false;

/** Удалить устаревшие JWT из localStorage (миграция с прошлой версии). */
function purgeLegacyTokenStorage(): void {
  if (typeof window === 'undefined') return;
  for (const key of LEGACY_TOKEN_KEYS) {
    localStorage.removeItem(key);
  }
}

/** Заголовки для API (Authorization не нужен — cookie). */
export function getAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return { ...extra };
}

/** Очистить сессию на сервере и локальные legacy-токены. */
export async function clearSession(): Promise<void> {
  if (typeof window === 'undefined') return;

  try {
    await apiFetch('/api/v1/auth/logout', { method: 'POST' });
  } catch {
    // Игнорируем сетевые ошибки при выходе
  }

  purgeLegacyTokenStorage();
}

/**
 * Пытается обновить короткоживущий access-токен по refresh cookie.
 *
 * Используется при старте приложения, когда access-токен истёк, но refresh-сессия
 * ещё жива (в т.ч. при включённом "Запомнить меня"). Возвращает true при успехе.
 * Никаких токенов в JS не хранится — всё в HttpOnly cookie.
 */
export async function attemptSessionRefresh(): Promise<boolean> {
  try {
    const response = await apiFetch('/api/v1/auth/refresh', { method: 'POST' });
    return response.ok;
  } catch {
    return false;
  }
}

/** @deprecated JWT в HttpOnly cookie, JS не читает токен. */
export function getAccessToken(): string | null {
  return null;
}

/** @deprecated Сессия определяется cookie + /auth/me. */
export function hasAccessToken(): boolean {
  return true;
}

/** Возвращает true, если сессия недействительна и выполнен logout. */
export function handleUnauthorized(response: Response): boolean {
  if (response.status !== 401) return false;
  if (logoutInProgress) return true;

  logoutInProgress = true;
  void clearSession();

  if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
    window.location.replace('/login');
  }

  return true;
}

export function resetLogoutGuard(): void {
  logoutInProgress = false;
}

/** Вызвать при старте приложения для миграции со старого localStorage. */
export function initAuthStorage(): void {
  purgeLegacyTokenStorage();
}
