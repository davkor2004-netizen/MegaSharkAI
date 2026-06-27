<script lang="ts">
  import { onMount } from 'svelte';
  import {
    CreditCard,
    Gift,
    Check,
    BarChart3,
    Wallet,
    Sparkles,
    LineChart,
    Headphones,
    Crown
  } from 'lucide-svelte';
  import type { ComponentType } from 'svelte';
  import { apiJson } from '$lib/utils/http';
  import {
    EmptyState,
    ErrorState,
    GlassCard,
    LoadingSkeleton,
    PageHeader,
    StatusBadge,
    Button,
    Alert
  } from '$lib/components';
  import { Lock, Gauge } from 'lucide-svelte';
  import { FEATURE_LABELS, USAGE_LABELS, type UsageSummary } from '$lib/utils/plans';

  interface TariffFeatures {
    monitoring?: string[];
    repricing?: string[];
    ai_generation?: string[];
    analytics?: string[];
    support?: string[];
  }

  interface Tariff {
    id: string;
    name: string;
    code: string;
    price_monthly: number;
    price_yearly: number;
    trial_days: number;
    features: TariffFeatures;
    limits?: Record<string, unknown>;
    sort_order?: number;
  }

  interface UserSubscription {
    tariff_code: string | null;
    tariff_name: string | null;
    status: string;
    is_trial: boolean;
    trial_ends_at?: string | null;
    expires_at?: string | null;
    billing_cycle?: string | null;
    days_remaining?: number | null;
  }

  interface SubscribeResponse {
    status: string;
    message: string;
    subscription: UserSubscription;
  }

  interface CancelResponse {
    status: string;
    message: string;
  }

  const featureGroups: { key: keyof TariffFeatures; label: string; icon: ComponentType }[] = [
    { key: 'monitoring', label: 'Мониторинг и парсинг', icon: BarChart3 },
    { key: 'repricing', label: 'Репрайсинг', icon: Wallet },
    { key: 'ai_generation', label: 'AI-генерация', icon: Sparkles },
    { key: 'analytics', label: 'Аналитика', icon: LineChart },
    { key: 'support', label: 'Поддержка', icon: Headphones }
  ];

  // Метрики, которые показываем прогресс-барами на странице биллинга.
  const usageMetricsOrder = ['ai_actions', 'parsing_requests', 'products', 'exports', 'tracked_competitors'];

  let tariffs: Tariff[] = [];
  let subscription: UserSubscription | null = null;
  let usageSummary: UsageSummary | null = null;
  let loading = true;
  let loadError = '';
  let actionError = '';
  let successMessage = '';
  let subscribingCode: string | null = null;
  let cancelling = false;

  $: hasActiveSubscription =
    Boolean(subscription) &&
    subscription!.status !== 'none' &&
    ['trial', 'active'].includes(subscription!.status);

  function formatPrice(price: number): string {
    return new Intl.NumberFormat('ru-RU').format(price);
  }

  function getSubscriptionBadgeVariant(status: string): 'success' | 'warning' | 'info' | 'neutral' {
    if (status === 'trial') return 'warning';
    if (status === 'active') return 'success';
    return 'neutral';
  }

  function getSubscriptionStatusLabel(status: string, isTrial: boolean): string {
    if (status === 'trial' || isTrial) return 'Пробный период';
    if (status === 'active') return 'Активна';
    if (status === 'none') return 'Нет подписки';
    return status;
  }

  function isRecommendedTariff(tariff: Tariff): boolean {
    return tariff.code === 'business';
  }

  function isCurrentTariff(tariff: Tariff): boolean {
    return Boolean(hasActiveSubscription && subscription?.tariff_code === tariff.code);
  }

  /** Процент использования лимита (0..100); безлимит → 0. */
  function usagePercent(used: number, limit: number | null, unlimited: boolean): number {
    if (unlimited || !limit || limit <= 0) return 0;
    return Math.min(100, Math.round((used / limit) * 100));
  }

  /** Цвет прогресс-бара по заполненности. */
  function usageBarClass(percent: number): string {
    if (percent >= 100) return 'bg-destructive';
    if (percent >= 80) return 'bg-warning';
    return 'bg-neural-cyan';
  }

  async function loadPageData(): Promise<void> {
    loading = true;
    loadError = '';

    try {
      const [tariffList, currentSub] = await Promise.all([
        apiJson<Tariff[]>('/api/v1/billing/list', {}, 'Не удалось загрузить тарифы'),
        apiJson<UserSubscription>('/api/v1/billing/current', {}, 'Не удалось загрузить подписку')
      ]);
      tariffs = tariffList;
      subscription = currentSub;
    } catch (err: unknown) {
      loadError = err instanceof Error ? err.message : 'Ошибка загрузки данных';
    } finally {
      loading = false;
    }

    // Сводка использования загружается отдельно: её сбой не должен ломать всю страницу.
    try {
      usageSummary = await apiJson<UsageSummary>(
        '/api/v1/billing/usage',
        {},
        'Не удалось загрузить использование'
      );
    } catch {
      usageSummary = null;
    }
  }

  async function subscribeToTariff(tariff: Tariff): Promise<void> {
    if (hasActiveSubscription) return;

    actionError = '';
    successMessage = '';
    subscribingCode = tariff.code;

    try {
      const result = await apiJson<SubscribeResponse>(
        '/api/v1/billing/subscribe',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tariff_code: tariff.code, billing_cycle: 'monthly' })
        },
        'Не удалось активировать тариф'
      );
      successMessage = result.message;
      subscription = result.subscription;
      await loadPageData();
    } catch (err: unknown) {
      actionError = err instanceof Error ? err.message : 'Ошибка активации тарифа';
    } finally {
      subscribingCode = null;
    }
  }

  async function cancelSubscription(): Promise<void> {
    if (!hasActiveSubscription) return;
    if (!confirm('Отменить подписку? Доступ сохранится до конца текущего периода.')) return;

    actionError = '';
    successMessage = '';
    cancelling = true;

    try {
      const result = await apiJson<CancelResponse>(
        '/api/v1/billing/cancel',
        { method: 'DELETE' },
        'Не удалось отменить подписку'
      );
      successMessage = result.message;
      await loadPageData();
    } catch (err: unknown) {
      actionError = err instanceof Error ? err.message : 'Ошибка отмены подписки';
    } finally {
      cancelling = false;
    }
  }

  onMount(loadPageData);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Shark Plans"
    title="Тарифы и подписка"
    subtitle="Выберите план для мониторинга, AI-инструментов и роста на маркетплейсах"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="7-дневный trial" dot={false} />
      {#if hasActiveSubscription && subscription}
        <StatusBadge
          variant={getSubscriptionBadgeVariant(subscription.status)}
          label="{subscription.tariff_name} · {getSubscriptionStatusLabel(subscription.status, subscription.is_trial)}"
          dot
        />
      {/if}
    </svelte:fragment>
  </PageHeader>

  <Alert variant="warning" title="Оплата через ЮKassa">
    Платёжный шлюз будет подключён перед открытым запуском. Сейчас доступна активация пробного периода без списания средств.
  </Alert>

  {#if successMessage}
    <Alert variant="success" title="Готово">{successMessage}</Alert>
  {/if}
  {#if actionError}
    <Alert variant="error" title="Ошибка">{actionError}</Alert>
  {/if}

  {#if loading}
    <div class="grid gap-6 md:grid-cols-2">
      <LoadingSkeleton variant="card" />
      <LoadingSkeleton variant="card" />
    </div>

  {:else if loadError && tariffs.length === 0}
    <ErrorState title="Не удалось загрузить тарифы" description={loadError} on:click={loadPageData} />

  {:else if tariffs.length === 0}
    <EmptyState
      title="Тарифы недоступны"
      description="Список тарифов пуст. Попробуйте обновить страницу позже."
      icon={CreditCard}
    >
      <Button slot="action" variant="ghost" size="sm" on:click={loadPageData}>
        Обновить
      </Button>
    </EmptyState>

  {:else}
    {#if hasActiveSubscription && subscription}
      <GlassCard glow padding="lg" className="space-y-4">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-1">
            <p class="text-xs font-semibold uppercase tracking-wider text-neural-cyan">Текущий план</p>
            <h2 class="text-xl font-bold text-foreground">{subscription.tariff_name ?? '—'}</h2>
            <div class="flex flex-wrap gap-2 pt-1">
              <StatusBadge
                variant={getSubscriptionBadgeVariant(subscription.status)}
                label={getSubscriptionStatusLabel(subscription.status, subscription.is_trial)}
                dot
              />
              {#if subscription.days_remaining !== null && subscription.days_remaining !== undefined}
                <StatusBadge variant="neutral" label="Осталось {subscription.days_remaining} дн." dot={false} />
              {/if}
              {#if subscription.billing_cycle}
                <StatusBadge variant="info" label={subscription.billing_cycle === 'yearly' ? 'Годовой' : 'Месячный'} dot={false} />
              {/if}
            </div>
          </div>
          <Button variant="ghost" size="sm" loading={cancelling} disabled={cancelling} on:click={cancelSubscription}>
            Отменить подписку
          </Button>
        </div>
      </GlassCard>
    {/if}

    {#if usageSummary}
      <GlassCard padding="lg" className="space-y-5">
        <div class="flex items-center gap-2">
          <Gauge class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
          <h2 class="text-lg font-semibold text-foreground">Использование тарифа</h2>
          <StatusBadge variant="info" label={usageSummary.plan_name} dot={false} />
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          {#each usageMetricsOrder as metric}
            {@const entry = usageSummary.usage[metric]}
            {#if entry}
              {@const percent = usagePercent(entry.used, entry.limit, entry.unlimited)}
              <div class="space-y-1.5">
                <div class="flex items-center justify-between text-sm">
                  <span class="text-foreground">{USAGE_LABELS[metric] ?? entry.label}</span>
                  <span class="text-muted-foreground">
                    {entry.used} / {entry.unlimited ? '∞' : entry.limit}
                  </span>
                </div>
                <div class="h-2 w-full overflow-hidden rounded-full bg-muted/40">
                  <div
                    class="h-full rounded-full transition-all {usageBarClass(percent)}"
                    style="width: {entry.unlimited ? 4 : percent}%"
                  ></div>
                </div>
              </div>
            {/if}
          {/each}
        </div>

        <div class="space-y-2 border-t border-border pt-4">
          <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Возможности тарифа</p>
          <div class="flex flex-wrap gap-2">
            {#each Object.entries(usageSummary.features) as [feature, enabled]}
              <span
                class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium {enabled
                  ? 'border-success/30 bg-success/10 text-success'
                  : 'border-border bg-muted/40 text-muted-foreground'}"
              >
                {#if enabled}
                  <Check class="h-3 w-3" aria-hidden="true" />
                {:else}
                  <Lock class="h-3 w-3" aria-hidden="true" />
                {/if}
                {FEATURE_LABELS[feature] ?? feature}
              </span>
            {/each}
          </div>
        </div>
      </GlassCard>
    {/if}

    <div class="grid gap-6 md:grid-cols-2">
      {#each tariffs as tariff (tariff.id)}
        {@const recommended = isRecommendedTariff(tariff)}
        {@const current = isCurrentTariff(tariff)}
        <GlassCard
          glow={recommended}
          padding="lg"
          hoverable
          className="relative overflow-hidden {recommended ? 'border-neural-purple/30' : ''}"
        >
          {#if recommended}
            <div class="absolute right-4 top-4">
              <StatusBadge variant="ai" label="Рекомендуем" dot={false} />
            </div>
          {/if}
          {#if current}
            <div class="absolute left-4 top-4">
              <StatusBadge variant="success" label="Ваш тариф" dot />
            </div>
          {/if}

          <div class="mb-6 {recommended || current ? 'pt-6' : ''}">
            <div class="flex items-center gap-2">
              {#if recommended}
                <Crown class="h-5 w-5 text-neural-purple" aria-hidden="true" />
              {/if}
              <h3 class="text-2xl font-bold text-foreground">{tariff.name}</h3>
            </div>
            <p class="mt-1 text-sm text-muted-foreground">
              {tariff.trial_days}-дневный пробный период
            </p>
          </div>

          <div class="surface mb-6 p-4">
            <div class="flex flex-wrap items-baseline gap-2">
              <span class="text-4xl font-bold text-gradient">{formatPrice(tariff.price_monthly)} ₽</span>
              <span class="text-muted-foreground">/мес</span>
            </div>
            <p class="mt-2 text-sm text-muted-foreground">
              или {formatPrice(tariff.price_yearly)} ₽ в год
              {#if tariff.price_monthly * 12 > tariff.price_yearly}
                <span class="text-neural-cyan">
                  (экономия {formatPrice(tariff.price_monthly * 12 - tariff.price_yearly)} ₽)
                </span>
              {/if}
            </p>
          </div>

          {#if current}
            <Button variant="subtle" fullWidth disabled>
              Это ваш текущий тариф
            </Button>
          {:else if hasActiveSubscription}
            <Button variant="subtle" fullWidth disabled>
              Уже есть активная подписка
            </Button>
          {:else}
            <Button
              variant={recommended ? 'neural' : 'ghost'}
              fullWidth
              loading={subscribingCode === tariff.code}
              disabled={subscribingCode !== null}
              on:click={() => subscribeToTariff(tariff)}
            >
              <Gift class="h-5 w-5" aria-hidden="true" />
              {subscribingCode === tariff.code
                ? 'Активация...'
                : `Активировать trial ${tariff.trial_days} дней`}
            </Button>
          {/if}

          <div class="mt-8 space-y-5">
            {#each featureGroups as group}
              {@const items = tariff.features[group.key]}
              {#if items && items.length > 0}
                <div>
                  <h4 class="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                    <svelte:component this={group.icon} class="h-4 w-4 text-neural-cyan" aria-hidden="true" />
                    {group.label}
                  </h4>
                  <ul class="space-y-1.5">
                    {#each items as feature}
                      <li class="flex items-start gap-2 text-sm text-muted-foreground">
                        <Check class="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                        <span>{feature}</span>
                      </li>
                    {/each}
                  </ul>
                </div>
              {/if}
            {/each}
          </div>
        </GlassCard>
      {/each}
    </div>

    <GlassCard padding="lg" className="mx-auto max-w-3xl text-center">
      <div class="mx-auto flex max-w-xl flex-col items-center gap-3">
        <div class="flex h-12 w-12 items-center justify-center rounded-xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
          <Gift class="h-6 w-6" aria-hidden="true" />
        </div>
        <h3 class="text-lg font-semibold text-foreground">Пробный период без оплаты</h3>
        <p class="text-sm text-muted-foreground">
          Активация trial даёт полный доступ к функциям выбранного тарифа на {tariffs[0]?.trial_days ?? 7} дней.
          Списание через ЮKassa будет доступно после подключения платёжного шлюза.
        </p>
      </div>
    </GlassCard>
  {/if}
</div>
