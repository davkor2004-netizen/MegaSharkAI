/**
 * Тонкие HTTP-хелперы поверх apiFetch (cookie-сессия).
 *
 * Не меняет глобальный auth flow: внутри используется тот же apiFetch
 * (credentials: 'include') и существующий handleUnauthorized.
 */
import { apiFetch } from '$lib/utils/api';
import { getAuthHeaders, handleUnauthorized } from '$lib/utils/auth';

/**
 * Машиночитаемая деталь ошибки доступа по тарифу (HTTP 402).
 *
 * Возвращается backend feature-guard сервисом для FEATURE_LOCKED / LIMIT_EXCEEDED.
 */
export interface LockDetail {
  code: 'FEATURE_LOCKED' | 'LIMIT_EXCEEDED' | 'NO_SUBSCRIPTION' | string;
  message: string;
  required_plan: string | null;
  current_plan: string | null;
  limit: number | null;
  used: number | null;
  reset_at: string | null;
  upgrade_url: string | null;
}

/** Достаёт читаемое сообщение об ошибке из ответа (detail) или возвращает fallback. */
export async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.clone().json();
    if (payload && typeof payload === 'object') {
      const detail = (payload as Record<string, unknown>).detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail.trim();
      }
      // Структурированная ошибка доступа (402): берём message из detail.
      if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
        const message = (detail as Record<string, unknown>).message;
        if (typeof message === 'string' && message.trim()) {
          return message.trim();
        }
      }
      // FastAPI может вернуть detail массивом (ошибки валидации).
      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0] as Record<string, unknown>;
        if (typeof first?.msg === 'string' && first.msg.trim()) {
          return first.msg.trim();
        }
      }
    }
  } catch {
    // Тело не JSON — оставляем fallback.
  }
  return fallback;
}

/** Достаёт структурированную деталь 402 (FEATURE_LOCKED/LIMIT_EXCEEDED), если есть. */
async function extractLockDetail(response: Response): Promise<LockDetail | undefined> {
  if (response.status !== 402) return undefined;
  try {
    const payload = await response.clone().json();
    const detail = (payload as Record<string, unknown>)?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const obj = detail as Record<string, unknown>;
      if (typeof obj.code === 'string') {
        return obj as unknown as LockDetail;
      }
    }
  } catch {
    // Тело не JSON — деталь недоступна.
  }
  return undefined;
}

/** Ошибка HTTP-запроса с сохранённым статусом и (опционально) деталью доступа. */
export class ApiError extends Error {
  status: number;
  detail?: LockDetail;
  constructor(message: string, status: number, detail?: LockDetail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/** Вернуть LockDetail, если ошибка — это 402 с тарифной блокировкой. */
export function getLockDetail(error: unknown): LockDetail | undefined {
  if (error instanceof ApiError && error.status === 402 && error.detail) {
    return error.detail;
  }
  return undefined;
}

/**
 * Выполнить запрос и вернуть распарсенный JSON.
 *
 * - прокидывает cookie-сессию через apiFetch;
 * - вызывает handleUnauthorized при 401 (как и остальные страницы);
 * - бросает ApiError с понятным сообщением при !ok.
 */
export async function apiJson<T = unknown>(
  input: RequestInfo | URL,
  init: RequestInit = {},
  fallbackError = 'Не удалось выполнить запрос'
): Promise<T> {
  const response = await apiFetch(input, {
    ...init,
    headers: getAuthHeaders((init.headers as Record<string, string>) ?? {})
  });

  handleUnauthorized(response);

  if (!response.ok) {
    throw new ApiError(
      await extractErrorMessage(response, fallbackError),
      response.status,
      await extractLockDetail(response)
    );
  }

  return (await response.json()) as T;
}

/**
 * Выполнить запрос и вернуть бинарный Blob (для скачивания файлов).
 *
 * Та же обработка ошибок/авторизации, что и в apiJson, но без парсинга JSON.
 */
export async function apiBlob(
  input: RequestInfo | URL,
  init: RequestInit = {},
  fallbackError = 'Не удалось получить файл'
): Promise<Blob> {
  const response = await apiFetch(input, {
    ...init,
    headers: getAuthHeaders((init.headers as Record<string, string>) ?? {})
  });

  handleUnauthorized(response);

  if (!response.ok) {
    throw new ApiError(
      await extractErrorMessage(response, fallbackError),
      response.status,
      await extractLockDetail(response)
    );
  }

  return await response.blob();
}

/**
 * Выполнить запрос без тела ответа (204 No Content и аналоги).
 *
 * Используется для DELETE и других операций без JSON в ответе.
 */
export async function apiNoContent(
  input: RequestInfo | URL,
  init: RequestInit = {},
  fallbackError = 'Не удалось выполнить запрос'
): Promise<void> {
  const response = await apiFetch(input, {
    ...init,
    headers: getAuthHeaders((init.headers as Record<string, string>) ?? {})
  });

  handleUnauthorized(response);

  if (!response.ok) {
    throw new ApiError(
      await extractErrorMessage(response, fallbackError),
      response.status,
      await extractLockDetail(response)
    );
  }
}
