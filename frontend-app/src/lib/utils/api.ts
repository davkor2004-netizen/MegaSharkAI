/** HTTP-клиент с cookie-сессией (HttpOnly JWT). */

/** Все API-запросы отправляют cookies сессии. */
export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, {
    ...init,
    credentials: 'include',
  });
}
