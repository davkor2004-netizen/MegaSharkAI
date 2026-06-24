<script lang="ts">
  import { apiFetch } from '$lib/utils/api';
  export let params: Record<string, string> = {};

  import { Mail } from 'lucide-svelte';
  import AuthFormCard from '../AuthFormCard.svelte';
  import { Alert, Button, FormField } from '$lib/components';

  let email = '';
  let error = '';
  let success = '';
  let loading = false;
  let touched = false;

  $: emailError = touched && !email ? 'Укажите email, указанный при регистрации' : '';

  async function handleResetRequest(e: Event) {
    e.preventDefault();
    error = '';
    success = '';
    loading = true;
    touched = true;

    if (!email) {
      loading = false;
      return;
    }

    try {
      const response = await apiFetch('/api/v1/auth/reset-password-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (response.ok) {
        await response.json();
        success = 'Ссылка для сброса пароля отправлена на ваш email';
      } else {
        const result = await response.json();
        error = result.detail || 'Ошибка запроса';
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

<AuthFormCard
  title="Восстановление пароля"
  subtitle="Отправим ссылку для сброса на ваш email"
  eyebrow="Security"
>
  {#if success}
    <Alert variant="success" title={success} className="mb-5">
      Проверьте почту и перейдите по ссылке. Ссылка действительна в течение 1 часа.
    </Alert>
  {/if}

  {#if error}
    <Alert variant="error" className="mb-5">{error}</Alert>
  {/if}

  <form on:submit={handleResetRequest} class="space-y-5" novalidate>
    <FormField label="Email" error={emailError} let:controlId let:invalid let:describedById>
      <input
        id={controlId}
        type="email"
        bind:value={email}
        required
        autocomplete="email"
        disabled={Boolean(success)}
        class="page-input {invalid || error ? 'page-input-error' : ''}"
        placeholder="seller@example.com"
        on:blur={() => (touched = true)}
        aria-invalid={Boolean(invalid || error)}
        aria-describedby={describedById}
      />
    </FormField>

    <Button type="submit" variant="neural" fullWidth loading={loading} disabled={loading || !email || Boolean(success)}>
      <Mail class="h-4 w-4" aria-hidden="true" />
      {loading ? 'Отправка...' : 'Отправить ссылку'}
    </Button>
  </form>

  <svelte:fragment slot="footer">
    <p class="text-sm text-muted-foreground">
      Вспомнили пароль?
      <a href="/login" class="auth-link">Вернуться ко входу</a>
    </p>
  </svelte:fragment>
</AuthFormCard>
