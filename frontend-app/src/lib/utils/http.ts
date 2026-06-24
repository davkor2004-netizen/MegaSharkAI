/**
 * Тонкие HTTP-хелперы поверх apiFetch (cookie-сессия).
 *
 * Не меняет глобальный auth flow: внутри используется тот же apiFetch
 * (credentials: 'include') и существующий handleUnauthorized.
 */
import { apiFetch } from '$lib/utils/api';
import { getAuthHeaders, handleUnauthorized } from '$lib/utils/auth';

/** Достаёт читаемое сообщение об ошибке из ответа (detail) или возвращает fallback. */
export async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.clone().json();
    if (payload && typeof payload === 'object') {
      const detail = (payload as Record<string, unknown>).detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail.trim();
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

/** Ошибка HTTP-запроса с сохранённым статусом. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
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
    throw new ApiError(await extractErrorMessage(response, fallbackError), response.status);
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
    throw new ApiError(await extractErrorMessage(response, fallbackError), response.status);
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
    throw new ApiError(await extractErrorMessage(response, fallbackError), response.status);
  }
}
