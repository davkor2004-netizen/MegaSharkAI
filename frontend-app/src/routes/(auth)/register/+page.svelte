<script lang="ts">
  import { apiFetch } from '$lib/utils/api';
  export let params: Record<string, string> = {};

  import { goto } from '$app/navigation';
  import {
    ArrowLeft,
    ArrowRight,
    Check,
    KeyRound,
    Rocket,
    ShieldCheck
  } from 'lucide-svelte';
  import AuthFormCard from '../AuthFormCard.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import { Alert, Button, FormField } from '$lib/components';

  let step = 1;

  let email = '';
  let password = '';
  let confirmPassword = '';
  let fullName = '';

  let selectedMarketplaces: string[] = [];

  let apiKeys: Record<string, string> = {
    wildberries: '',
    ozon: '',
    yandex_market: '',
    avito: ''
  };

  let ozonClientId = '';

  let error = '';
  let loading = false;

  const marketplaceOptions = [
    { id: 'wildberries', name: 'Wildberries', icon: '🔵', color: 'from-blue-500 to-purple-600' },
    { id: 'ozon', name: 'Ozon', icon: '🔷', color: 'from-blue-400 to-blue-600' },
    { id: 'yandex_market', name: 'Яндекс Маркет', icon: '🟡', color: 'from-yellow-400 to-red-500' },
    { id: 'avito', name: 'Avito', icon: '🟢', color: 'from-green-400 to-blue-500' }
  ];

  const stepLabels = ['Аккаунт', 'Маркетплейсы', 'API ключи'];

  function toggleMarketplace(id: string) {
    if (selectedMarketplaces.includes(id)) {
      selectedMarketplaces = selectedMarketplaces.filter((m) => m !== id);
    } else {
      selectedMarketplaces = [...selectedMarketplaces, id];
    }
  }

  function isPasswordStrong(value: string): boolean {
    if (value.length < 8) return false;
    if (!/[A-Za-zА-Яа-я]/.test(value)) return false;
    if (!/\d/.test(value)) return false;
    return true;
  }

  function nextStep() {
    if (step === 1 && (!email || !password || !confirmPassword)) {
      error = 'Заполните все обязательные поля';
      return;
    }

    if (password !== confirmPassword) {
      error = 'Пароли не совпадают';
      return;
    }

    if (!isPasswordStrong(password)) {
      error = 'Пароль: минимум 8 символов, буква и цифра';
      return;
    }

    error = '';
    step++;
  }

  function prevStep() {
    step--;
    error = '';
  }

  async function handleRegister(e: Event) {
    e.preventDefault();
    error = '';
    loading = true;

    try {
      const registerResponse = await apiFetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName || undefined,
          is_marketplace_seller: selectedMarketplaces.length > 0
        })
      });

      if (!registerResponse.ok) {
        const data = await registerResponse.json();
        throw new Error(data.detail || 'Ошибка регистрации');
      }

      if (selectedMarketplaces.length > 0) {
        for (const marketplace of selectedMarketplaces) {
          const apiKey = apiKeys[marketplace];
          if (apiKey && apiKey.trim().length > 0) {
            try {
              const keyResponse = await apiFetch('/api/v1/marketplace-keys', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  marketplace,
                  api_key: apiKey,
                  client_id: marketplace === 'ozon' ? ozonClientId : undefined,
                  is_active: true
                })
              });
              if (!keyResponse.ok) {
                const keyData = await keyResponse.json();
                throw new Error(keyData.detail || 'Не удалось сохранить ключ маркетплейса');
              }
            } catch (keyError) {
              // Не прерываем регистрацию: пользователь сможет добавить ключ в профиле.
            }
          }
        }
      }

      goto('/');
    } catch (err: any) {
      error = err.message || 'Не удалось зарегистрироваться';
    } finally {
      loading = false;
    }
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<AuthFormCard
  title="Регистрация"
  subtitle="Создайте аккаунт продавца за 3 шага"
  maxWidth="2xl"
  eyebrow="Onboarding"
>
  <!-- Stepper -->
  <div class="mb-6">
    <div class="flex items-center justify-center gap-2 sm:gap-4">
      {#each [1, 2, 3] as s}
        <div class="flex items-center gap-2">
          <div
            class="flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold transition-neural sm:h-10 sm:w-10 {step >= s
              ? 'gradient-neural text-primary-foreground shadow-glow-sm'
              : 'border border-border bg-background/40 text-muted-foreground'}"
            aria-current={step === s ? 'step' : undefined}
          >
            {#if step > s}
              <Check class="h-4 w-4" aria-hidden="true" />
            {:else}
              {s}
            {/if}
          </div>
          {#if s < 3}
            <div class="hidden h-0.5 w-8 sm:block sm:w-12 {step > s ? 'bg-neural-cyan/60' : 'bg-border'}"></div>
          {/if}
        </div>
      {/each}
    </div>
    <div class="mt-3 flex justify-between px-1 text-[11px] text-muted-foreground sm:text-xs">
      {#each stepLabels as label, i}
        <span class={step === i + 1 ? 'font-medium text-neural-cyan' : ''}>{label}</span>
      {/each}
    </div>
  </div>

  <form on:submit={handleRegister} class="space-y-5">
    {#if step === 1}
      <div class="space-y-4">
        <FormField label="Email" required let:controlId>
          <input
            id={controlId}
            type="email"
            bind:value={email}
            required
            autocomplete="email"
            class="page-input {error && !email ? 'page-input-error' : ''}"
            placeholder="seller@example.com"
          />
        </FormField>

        <FormField label="Полное имя" let:controlId>
          <input
            id={controlId}
            type="text"
            bind:value={fullName}
            autocomplete="name"
            class="page-input"
            placeholder="Иван Петров"
          />
        </FormField>

        <div class="grid gap-4 sm:grid-cols-2">
          <FormField label="Пароль" required hint="Минимум 8 символов, буква и цифра" let:controlId>
            <input
              id={controlId}
              type="password"
              bind:value={password}
              required
              minlength="8"
              autocomplete="new-password"
              class="page-input {error && !isPasswordStrong(password) ? 'page-input-error' : ''}"
              placeholder="••••••••"
            />
          </FormField>
          <FormField label="Подтверждение" required let:controlId>
            <input
              id={controlId}
              type="password"
              bind:value={confirmPassword}
              required
              minlength="8"
              autocomplete="new-password"
              class="page-input {error && password !== confirmPassword ? 'page-input-error' : ''}"
              placeholder="••••••••"
            />
          </FormField>
        </div>

        {#if error}
          <Alert variant="error">{error}</Alert>
        {/if}

        <Button type="button" variant="neural" fullWidth on:click={nextStep}>
          Далее
          <ArrowRight class="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    {/if}

    {#if step === 2}
      <div class="space-y-4">
        <div class="text-center">
          <h3 class="text-lg font-semibold text-foreground">На каких площадках вы продаёте?</h3>
          <p class="mt-1 text-sm text-muted-foreground">Выберите один или несколько маркетплейсов</p>
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {#each marketplaceOptions as mp}
            <button
              type="button"
              on:click={() => toggleMarketplace(mp.id)}
              class="relative rounded-xl border-2 p-4 text-left transition-neural {selectedMarketplaces.includes(mp.id)
                ? 'border-neural-cyan/50 bg-neural-cyan/10 shadow-glow-sm'
                : 'border-border/80 bg-background/30 hover:border-neural-cyan/30'}"
              aria-pressed={selectedMarketplaces.includes(mp.id)}
            >
              <div class="flex items-center gap-3">
                <span class="text-2xl" aria-hidden="true">{mp.icon}</span>
                <p class="font-semibold text-foreground">{mp.name}</p>
              </div>
              {#if selectedMarketplaces.includes(mp.id)}
                <div
                  class="absolute right-3 top-3 flex h-6 w-6 items-center justify-center rounded-full gradient-neural"
                  aria-hidden="true"
                >
                  <Check class="h-3.5 w-3.5 text-primary-foreground" />
                </div>
              {/if}
            </button>
          {/each}
        </div>

        {#if selectedMarketplaces.length > 0}
          <div class="flex flex-wrap gap-2">
            {#each selectedMarketplaces as mpId}
              {@const mp = marketplaceOptions.find((m) => m.id === mpId)}
              <StatusBadge variant="info" label={mp?.name ?? mpId} />
            {/each}
          </div>
        {/if}

        {#if error}
          <Alert variant="error">{error}</Alert>
        {/if}

        <div class="flex gap-3">
          <Button type="button" variant="subtle" className="flex-1" on:click={prevStep}>
            <ArrowLeft class="h-4 w-4" aria-hidden="true" />
            Назад
          </Button>
          <Button
            type="button"
            variant="neural"
            className="flex-1"
            disabled={selectedMarketplaces.length === 0}
            on:click={nextStep}
          >
            Далее
            <ArrowRight class="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    {/if}

    {#if step === 3}
      <div class="space-y-4">
        <div class="text-center">
          <h3 class="flex items-center justify-center gap-2 text-lg font-semibold text-foreground">
            <KeyRound class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            API ключи для подключения
          </h3>
          <p class="mt-1 text-sm text-muted-foreground">
            Можно пропустить и добавить позже в профиле.
          </p>
        </div>

        <Alert variant="info" icon={false}>
          <span class="flex items-center gap-2">
            <ShieldCheck class="h-4 w-4 shrink-0" aria-hidden="true" />
            Ключи шифруются на сервере и доступны только вашему аккаунту.
          </span>
        </Alert>

        {#each selectedMarketplaces as mpId}
          {@const mp = marketplaceOptions.find((m) => m.id === mpId)}
          <div class="glass-card rounded-xl border-glow-cyan p-4 space-y-3">
            <div class="flex items-center gap-3">
              <span class="text-2xl" aria-hidden="true">{mp?.icon}</span>
              <p class="font-semibold text-foreground">{mp?.name}</p>
            </div>

            <FormField label="API ключ" let:controlId>
              <input
                id={controlId}
                type="text"
                bind:value={apiKeys[mpId]}
                class="page-input"
                placeholder="Введите API ключ"
                autocomplete="off"
              />
            </FormField>

            {#if mpId === 'ozon'}
              <FormField
                label="Ozon Client-Id"
                hint="Для Ozon Seller API нужны оба значения: API key и Client-Id"
                let:controlId
              >
                <input
                  id={controlId}
                  type="text"
                  bind:value={ozonClientId}
                  class="page-input"
                  placeholder="Client-Id из кабинета Ozon Seller"
                  autocomplete="off"
                />
              </FormField>
            {/if}
          </div>
        {/each}

        {#if error}
          <Alert variant="error">{error}</Alert>
        {/if}

        <div class="flex gap-3">
          <Button type="button" variant="subtle" className="flex-1" on:click={prevStep}>
            <ArrowLeft class="h-4 w-4" aria-hidden="true" />
            Назад
          </Button>
          <Button type="submit" variant="neural" className="flex-1" loading={loading} disabled={loading}>
            <Rocket class="h-4 w-4" aria-hidden="true" />
            {loading ? 'Регистрация...' : 'Создать аккаунт'}
          </Button>
        </div>
      </div>
    {/if}
  </form>

  <svelte:fragment slot="footer">
    <p class="text-sm text-muted-foreground">
      Уже есть аккаунт?
      <a href="/login" class="auth-link">Войти</a>
    </p>
  </svelte:fragment>
</AuthFormCard>
