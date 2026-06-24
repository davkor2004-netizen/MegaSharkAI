<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiFetch } from '$lib/utils/api';
  import { KeyRound, ShieldAlert } from 'lucide-svelte';
  import AuthFormCard from '../AuthFormCard.svelte';
  import { Alert, Button, FormField } from '$lib/components';

  // Ключ для опционального запоминания только email (без пароля и токенов).
  const REMEMBER_EMAIL_KEY = 'megashark_remember_email';

  let email = '';
  let password = '';
  let rememberMe = false;
  let error = '';
  let loading = false;
  let touched = { email: false, password: false };

  $: emailError = touched.email && !email ? 'Укажите email' : '';
  $: passwordError = touched.password && !password ? 'Укажите пароль' : '';

  onMount(() => {
    // Подставляем ранее сохранённый email (если пользователь включал "Запомнить меня").
    const savedEmail = localStorage.getItem(REMEMBER_EMAIL_KEY);
    if (savedEmail) {
      email = savedEmail;
      rememberMe = true;
    }
  });

  async function handleLogin(e: Event) {
    e.preventDefault();
    error = '';
    loading = true;
    touched = { email: true, password: true };

    if (!email || !password) {
      loading = false;
      return;
    }

    try {
      error = '';
      loading = true;

      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);
      formData.append('remember_me', String(rememberMe));

      const response = await apiFetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
      });

      if (!response.ok) {
        let errorMessage = 'Ошибка входа';
        try {
          const data = await response.json();
          errorMessage = data.detail || `Ошибка ${response.status}`;
        } catch {
          if (response.status === 401) errorMessage = 'Неверный email или пароль';
          else if (response.status === 403) errorMessage = 'Аккаунт заблокирован';
          else if (response.status === 422) errorMessage = 'Неверные данные формы';
          else errorMessage = `Ошибка сервера (${response.status})`;
        }
        throw new Error(errorMessage);
      }

      await response.json();

      // Запоминаем только email (никогда пароль/токены).
      if (rememberMe) {
        localStorage.setItem(REMEMBER_EMAIL_KEY, email);
      } else {
        localStorage.removeItem(REMEMBER_EMAIL_KEY);
      }

      await goto('/dashboard', { replaceState: true });
    } catch (err: any) {
      error = err.message || 'Не удалось войти';
    } finally {
      loading = false;
    }
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<AuthFormCard title="Вход в кабинет" subtitle="Акула среди AI-помощников для селлеров">
  <form on:submit={handleLogin} class="space-y-5" novalidate>
    <FormField label="Email" error={emailError} let:controlId let:invalid let:describedById>
      <input
        id={controlId}
        type="email"
        bind:value={email}
        required
        autocomplete="email"
        class="page-input {invalid || error ? 'page-input-error' : ''}"
        placeholder="seller@example.com"
        on:blur={() => (touched = { ...touched, email: true })}
        aria-invalid={Boolean(invalid || error)}
        aria-describedby={describedById}
      />
    </FormField>

    <div class="space-y-1.5">
      <FormField label="Пароль" error={passwordError} let:controlId let:invalid let:describedById>
        <input
          id={controlId}
          type="password"
          bind:value={password}
          required
          autocomplete="current-password"
          class="page-input {invalid || error ? 'page-input-error' : ''}"
          placeholder="••••••••"
          on:blur={() => (touched = { ...touched, password: true })}
          aria-invalid={Boolean(invalid || error)}
          aria-describedby={describedById}
        />
      </FormField>
      <div class="flex justify-end">
        <a href="/forgot-password" class="text-xs auth-link">Забыли пароль?</a>
      </div>
    </div>

    <div
      class="rounded-xl border border-border/80 bg-background/30 p-3 transition-neural {rememberMe
        ? 'border-neural-cyan/50 bg-neural-cyan/10 shadow-glow-sm'
        : 'hover:border-neural-cyan/30'}"
    >
      <label class="flex cursor-pointer items-center gap-3 text-sm text-foreground">
        <input
          type="checkbox"
          bind:checked={rememberMe}
          class="h-5 w-5 shrink-0 cursor-pointer rounded border-2 border-neural-cyan/60 bg-background/60 accent-neural-cyan focus:outline-none focus:ring-2 focus:ring-neural-cyan/40"
        />
        <span class="font-semibold">Запомнить меня</span>
      </label>
      <p class="mt-2 flex items-start gap-2 text-xs text-muted-foreground">
        <ShieldAlert class="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden="true" />
        <span>Не включайте на чужом или общем устройстве — сессия будет дольше активна.</span>
      </p>
    </div>

    {#if error}
      <Alert variant="error">{error}</Alert>
    {/if}

    <Button type="submit" variant="neural" fullWidth loading={loading} disabled={loading || !email || !password}>
      <KeyRound class="h-4 w-4" aria-hidden="true" />
      {loading ? 'Вход...' : 'Войти'}
    </Button>
  </form>

  <svelte:fragment slot="footer">
    <p class="text-sm text-muted-foreground">
      Нет аккаунта?
      <a href="/register" class="auth-link">Зарегистрироваться</a>
    </p>
  </svelte:fragment>
</AuthFormCard>
