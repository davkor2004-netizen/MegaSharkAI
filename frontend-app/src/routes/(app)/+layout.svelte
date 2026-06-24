<script lang="ts">
  export let params: Record<string, string> = {};

  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { LoadingSkeleton } from '$lib/components';
  import {
    clearSession,
    handleUnauthorized,
    resetLogoutGuard,
    initAuthStorage,
    attemptSessionRefresh
  } from '$lib/utils/auth';
  import { apiFetch } from '$lib/utils/api';

  let isCheckingAuth = true;
  let authError = '';
  let isSuperuser = false;
  let isAuthenticated = false;

  async function clearSessionAndRedirect(): Promise<void> {
    await clearSession();
    goto('/login', { replaceState: true });
  }

  $: if (isAuthenticated && !isSuperuser && $page.url.pathname.startsWith('/admin')) {
    goto('/dashboard', { replaceState: true });
  }

  onMount(async () => {
    initAuthStorage();
    resetLogoutGuard();

    try {
      let response = await apiFetch('/api/v1/auth/me');

      // Access-токен мог истечь, пока refresh-сессия ещё жива
      // (особенно при "Запомнить меня"). Пробуем тихо обновить токен один раз.
      if (response.status === 401) {
        const refreshed = await attemptSessionRefresh();
        if (refreshed) {
          response = await apiFetch('/api/v1/auth/me');
        }
      }

      if (handleUnauthorized(response)) {
        return;
      }

      if (!response.ok) {
        if (response.status === 401) {
          await clearSessionAndRedirect();
          return;
        }
        authError = 'Не удалось проверить сессию. Попробуйте обновить страницу.';
        return;
      }

      const user = await response.json();
      isSuperuser = Boolean(user.is_superuser);
      isAuthenticated = true;

      if ($page.url.pathname.startsWith('/admin') && !isSuperuser) {
        goto('/dashboard', { replaceState: true });
        return;
      }
    } catch {
      authError = 'Backend недоступен. Проверьте, что API запущен.';
    } finally {
      isCheckingAuth = false;
    }
  });
</script>

{#if false}{JSON.stringify(params)}{/if}

{#if isCheckingAuth}
  <div class="mx-auto max-w-3xl space-y-4 py-8 animate-fade-in">
    <LoadingSkeleton variant="metric" />
    <LoadingSkeleton variant="card" />
  </div>
{:else if authError}
  <div class="mx-auto max-w-xl glass-card rounded-xl border border-destructive/30 p-6 text-sm text-destructive">
    {authError}
  </div>
{:else}
  <slot />
{/if}
