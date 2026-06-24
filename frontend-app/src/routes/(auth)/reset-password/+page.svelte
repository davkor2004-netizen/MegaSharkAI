<script lang="ts">
  import { apiFetch } from '$lib/utils/api';
  export let params: Record<string, string> = {};

  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { KeyRound } from 'lucide-svelte';
  import AuthFormCard from '../AuthFormCard.svelte';
  import { Alert, Button, FormField } from '$lib/components';

  let token = '';
  let new_password = '';
  let confirm_password = '';
  let error = '';
  let success = '';
  let loading = false;

  onMount(() => {
    if (browser) {
      const urlParams = new URLSearchParams(window.location.search);
      token = urlParams.get('token') || '';
    }
  });

  async function handleResetConfirm(e: Event) {
    e.preventDefault();
    error = '';
    success = '';
    loading = true;

    if (!token) {
      error = 'Токен не указан';
      loading = false;
      return;
    }

    if (new_password !== confirm_password) {
      error = 'Пароли не совпадают';
      loading = false;
      return;
    }

    if (new_password.length < 6) {
      error = 'Пароль должен быть не менее 6 символов';
      loading = false;
      return;
    }

    try {
      const response = await apiFetch('/api/v1/auth/reset-password-confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password }),
      });

      if (response.ok) {
        success = 'Пароль успешно изменён! Перенаправляем на вход...';
        setTimeout(() => goto('/login'), 2000);
      } else {
        const result = await response.json();
        error = result.detail || 'Ошибка сброса пароля';
      }
    } catch (err: any) {
      console.error('Ошибка:', err);
      error = 'Ошибка соединения с сервером';
    } finally {
      loading = false;
    }
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<AuthFormCard title="Новый пароль" subtitle="Придумайте надёжный пароль для входа" eyebrow="Reset">
  {#if success}
    <Alert variant="success" className="mb-5">{success}</Alert>
  {/if}

  {#if error}
    <Alert variant="error" className="mb-5">{error}</Alert>
  {/if}

  {#if !token}
    <Alert variant="warning" title="Токен не найден в URL" className="mb-5">
      Убедитесь, что перешли по ссылке из письма.
      <a href="/forgot-password" class="auth-link mt-2 inline-flex items-center gap-1 text-xs">
        Запросить ссылку заново →
      </a>
    </Alert>
  {/if}

  <form on:submit={handleResetConfirm} class="space-y-5" novalidate>
    <FormField label="Новый пароль" let:controlId>
      <input
        id={controlId}
        type="password"
        bind:value={new_password}
        required
        minlength="6"
        autocomplete="new-password"
        disabled={Boolean(success) || !token}
        class="page-input {error && new_password.length < 6 ? 'page-input-error' : ''}"
        placeholder="Минимум 6 символов"
      />
    </FormField>

    <FormField label="Подтверждение пароля" let:controlId>
      <input
        id={controlId}
        type="password"
        bind:value={confirm_password}
        required
        minlength="6"
        autocomplete="new-password"
        disabled={Boolean(success) || !token}
        class="page-input {error && new_password !== confirm_password ? 'page-input-error' : ''}"
        placeholder="Повторите пароль"
      />
    </FormField>

    <Button
      type="submit"
      variant="neural"
      fullWidth
      loading={loading}
      disabled={loading || !token || !new_password || !confirm_password || Boolean(success)}
    >
      <KeyRound class="h-4 w-4" aria-hidden="true" />
      {loading ? 'Сохранение...' : 'Изменить пароль'}
    </Button>
  </form>

  <svelte:fragment slot="footer">
    <p class="text-sm text-muted-foreground">
      Вспомнили пароль?
      <a href="/login" class="auth-link">Вернуться ко входу</a>
    </p>
  </svelte:fragment>
</AuthFormCard>
