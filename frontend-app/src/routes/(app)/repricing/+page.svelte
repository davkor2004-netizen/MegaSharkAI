<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Calculator, Package, RefreshCw, TrendingDown, TrendingUp, Wallet } from 'lucide-svelte';
  import { apiJson, apiNoContent } from '$lib/utils/http';
  import {
    AIInsightCard,
    Alert,
    Button,
    EmptyState,
    ErrorState,
    FormField,
    GlassCard,
    LoadingSkeleton,
    MetricCard,
    PageHeader,
    StatusBadge
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';

  type StrategyCode = 'aggressive' | 'margin_protection' | 'night' | 'balanced';

  interface StrategyItem {
    value: StrategyCode;
    label: string;
    desc: string;
    icon: string;
  }

  interface ProductListItem {
    id: number;
    name: string;
    price: number | null;
    marketplace: string | null;
    is_own: boolean;
  }

  interface ProductListResponse {
    items: ProductListItem[];
  }

  interface RepricingResult {
    product_id: number;
    product_name: string;
    current_price: number;
    recommended_price: number;
    strategy: string;
    strategy_code: StrategyCode;
    target_margin: number;
    competitor_count: number;
    min_competitor_price: number | null;
    avg_competitor_price: number | null;
    change_percent: number;
    data_source: string;
    reasoning: string;
    competitor_prices_source: 'manual' | 'auto' | 'none';
  }

  interface StrategySettingsResponse {
    strategy: StrategyCode;
    target_margin: number;
    night_repricing_enabled: boolean;
    auto_update_enabled: boolean;
  }

  let productId = '';
  let productSearch = '';
  let competitorPricesText = '';

  let strategy: StrategyCode = 'margin_protection';
  let targetMargin = 30;
  let nightRepricingEnabled = false;
  let autoUpdateEnabled = true;

  let products: ProductListItem[] = [];
  let result: RepricingResult | null = null;

  let loading = false;
  let loadingProducts = false;
  let savingSettings = false;

  let error = '';
  let statusMessage = '';
  // Отдельная ошибка загрузки списка товаров (критичный для страницы ресурс).
  let productsError = '';
  
  const strategies: StrategyItem[] = [
    { value: 'aggressive', label: 'Агрессивный рост', desc: 'Цена ниже всех конкурентов', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
    { value: 'margin_protection', label: 'Защита маржи', desc: 'Цена с учётом целевой маржи', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
    { value: 'night', label: 'Ночной', desc: 'Снижение на 10% от текущей цены', icon: 'M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z' },
    { value: 'balanced', label: 'Сбалансированная', desc: 'Между средним и минимальным', icon: 'M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3' }
  ];
  
  $: normalizedSearch = productSearch.trim().toLowerCase();
  $: filteredProducts = normalizedSearch
    ? products.filter((p) => `${p.id} ${p.name}`.toLowerCase().includes(normalizedSearch))
    : products;

  function showError(message: string): void {
    error = message;
    statusMessage = '';
  }

  function showStatus(message: string): void {
    statusMessage = message;
    error = '';
  }

  function getCompetitorSourceLabel(source: 'manual' | 'auto' | 'none'): string {
    if (source === 'manual') {
      return 'Введены вручную';
    }
    if (source === 'auto') {
      return 'Подобраны автоматически из базы';
    }
    return 'Не использовались';
  }

  function getStrategyLabel(code: StrategyCode): string {
    return strategies.find((item) => item.value === code)?.label || code;
  }

  function parseCompetitorPrices(): number[] | undefined {
    const normalized = competitorPricesText.trim();
    if (!normalized) {
      return undefined;
    }

    const parts = normalized
      .split(/[\n,;]+/)
      .map((value) => value.trim())
      .filter(Boolean);

    if (parts.length === 0) {
      return undefined;
    }

    const parsed = parts.map((value) => Number(value.replace(',', '.')));
    if (parsed.some((price) => !Number.isFinite(price) || price <= 0)) {
      throw new Error('Цены конкурентов должны быть положительными числами.');
    }

    return parsed;
  }

  async function loadProducts(): Promise<void> {
    loadingProducts = true;

    try {
      const data = await apiJson<ProductListResponse>(
        '/api/v1/products/list?is_own=true&limit=500',
        {},
        'Не удалось загрузить список товаров'
      );
      products = data.items || [];
      productsError = '';
    } catch (err: unknown) {
      productsError = err instanceof Error ? err.message : 'Не удалось загрузить список товаров';
    } finally {
      loadingProducts = false;
    }
  }

  async function loadStrategySettings(): Promise<void> {
    try {
      const data = await apiJson<StrategySettingsResponse>(
        '/api/v1/repricing/strategies',
        {},
        'Не удалось загрузить настройки репрайсинга'
      );
      strategy = data.strategy;
      targetMargin = data.target_margin;
      nightRepricingEnabled = data.night_repricing_enabled;
      autoUpdateEnabled = data.auto_update_enabled;
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Не удалось загрузить настройки репрайсинга');
    }
  }

  async function saveStrategySettings(): Promise<void> {
    savingSettings = true;

    try {
      // apiNoContent не парсит тело ответа — сохраняем прежнее поведение (тело не использовалось).
      await apiNoContent(
        '/api/v1/repricing/strategies',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            strategy,
            target_margin: targetMargin,
            night_repricing_enabled: nightRepricingEnabled,
            auto_update_enabled: autoUpdateEnabled
          })
        },
        'Не удалось сохранить настройки репрайсинга'
      );

      showStatus('Настройки репрайсинга сохранены');
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Не удалось сохранить настройки репрайсинга');
    } finally {
      savingSettings = false;
    }
  }

  async function calculatePrice(): Promise<void> {
    if (!productId) {
      showError('Выберите товар из списка');
      return;
    }

    loading = true;
    error = '';
    statusMessage = '';
    result = null;

    try {
      const competitorPrices = parseCompetitorPrices();

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      try {
        const calculatedResult = await apiJson<RepricingResult>(
          '/api/v1/repricing/calculate',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            signal: controller.signal,
            body: JSON.stringify({
              product_id: parseInt(productId, 10),
              strategy,
              target_margin: targetMargin,
              competitor_prices: competitorPrices
            })
          },
          'Ошибка расчёта'
        );

        result = calculatedResult;
        showStatus(`Расчёт выполнен успешно. Источник цен конкурентов: ${getCompetitorSourceLabel(calculatedResult.competitor_prices_source)}.`);
      } finally {
        clearTimeout(timeoutId);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        showError('Сервер долго отвечает. Попробуйте ещё раз.');
      } else {
        showError(err instanceof Error ? err.message : 'Ошибка расчёта');
      }
    } finally {
      loading = false;
    }
  }

  async function refreshAll(): Promise<void> {
    await loadStrategySettings();
    await loadProducts();
  }

  onMount(async () => {
    await loadStrategySettings();
    await loadProducts();
  });
</script>

{#if false}{JSON.stringify(params)}{/if}

<div class="mx-auto max-w-[1400px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр · Repricing"
    title="Репрайсинг"
    subtitle="Profit Autopilot — автоматический расчёт оптимальной цены"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="ai" label={getStrategyLabel(strategy)} dot={false} />
      <StatusBadge
        variant={autoUpdateEnabled ? 'success' : 'neutral'}
        label={autoUpdateEnabled ? 'Автообновление вкл.' : 'Автообновление выкл.'}
        dot={autoUpdateEnabled}
      />
      {#if nightRepricingEnabled}
        <StatusBadge variant="info" label="Ночной режим" dot={false} />
      {/if}
    </svelte:fragment>

    <svelte:fragment slot="actions">
      <Button variant="ghost" size="sm" disabled={loadingProducts || loading} on:click={refreshAll}>
        <RefreshCw class="h-4 w-4 {loadingProducts ? 'animate-spin' : ''}" aria-hidden="true" />
        Обновить
      </Button>
    </svelte:fragment>
  </PageHeader>

  {#if statusMessage}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}
  {#if error}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}

  <div class="grid gap-6 xl:grid-cols-12">
    <!-- Настройки и расчёт -->
    <GlassCard glow padding="lg" className="xl:col-span-7">
      {#if productsError && products.length === 0 && !loadingProducts}
        <ErrorState title="Не удалось загрузить товары" description={productsError}>
          <svelte:fragment slot="action">
            <Button variant="neural" on:click={loadProducts}>
              <RefreshCw class="h-4 w-4" aria-hidden="true" />
              Повторить
            </Button>
          </svelte:fragment>
        </ErrorState>
      {:else if !loadingProducts && products.length === 0}
        <EmptyState
          title="Нет своих товаров"
          description="Для расчёта репрайсинга нужны ваши товары. Добавьте их через парсинг или каталог."
          icon={Package}
        >
          <svelte:fragment slot="action">
            <Button variant="neural" on:click={() => goto('/products')}>Перейти к товарам</Button>
          </svelte:fragment>
        </EmptyState>
      {:else}
        <div class="space-y-6">
          {#if productsError}
            <Alert variant="warning" title="Обновление товаров">{productsError}</Alert>
          {/if}

          <FormField label="Поиск товара" let:controlId>
            <input
              id={controlId}
              type="text"
              bind:value={productSearch}
              class="page-input"
              placeholder="Начните вводить ID или название товара"
            />
          </FormField>

          <FormField label="Товар для расчёта" let:controlId>
            <select
              id={controlId}
              bind:value={productId}
              class="page-select"
              disabled={loadingProducts}
            >
              <option value="">{loadingProducts ? 'Загрузка товаров...' : 'Выберите товар'}</option>
              {#each filteredProducts as product}
                <option value={String(product.id)}>
                  #{product.id} — {product.name} ({product.price ?? 0} ₽)
                </option>
              {/each}
            </select>
          </FormField>

          <FormField label="Стратегия">
            <div class="grid gap-3 md:grid-cols-2">
              {#each strategies as s}
                <label class="glass-card flex cursor-pointer items-center gap-3 p-4 transition-neural hover:border-neural-cyan/40 has-[:checked]:border-neural-cyan has-[:checked]:bg-neural-cyan/10">
                  <input
                    type="radio"
                    name="strategy"
                    checked={strategy === s.value}
                    on:change={() => strategy = s.value}
                    class="h-4 w-4 text-primary"
                  />
                  <svg class="w-5 h-5 text-neural-cyan flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={s.icon}></path></svg>
                  <div class="min-w-0">
                    <div class="font-medium text-foreground">{s.label}</div>
                    <div class="text-xs text-muted-foreground">{s.desc}</div>
                  </div>
                </label>
              {/each}
            </div>
          </FormField>

          <FormField label={`Целевая маржа: ${targetMargin}%`} let:controlId>
            <input
              id={controlId}
              type="range"
              min="0"
              max="100"
              step="1"
              bind:value={targetMargin}
              class="w-full"
            />
            <div class="mt-1 flex justify-between text-xs text-muted-foreground">
              <span>0%</span>
              <span>100%</span>
            </div>
          </FormField>

          <FormField
            label="Цены конкурентов (необязательно)"
            hint="Разделители: запятая, точка с запятой или перенос строки. Если поле пустое, система попробует подобрать цены конкурентов автоматически."
            let:controlId
          >
            <textarea
              id={controlId}
              bind:value={competitorPricesText}
              rows="3"
              class="page-textarea"
              placeholder="Например: 1990, 2050, 2100"
            ></textarea>
          </FormField>

          <div class="grid gap-3 md:grid-cols-2">
            <label class="glass-card flex items-center gap-2 px-4 py-3 text-sm text-foreground">
              <input type="checkbox" bind:checked={nightRepricingEnabled} class="h-4 w-4" />
              Ночной репрайсинг включён
            </label>

            <label class="glass-card flex items-center gap-2 px-4 py-3 text-sm text-foreground">
              <input type="checkbox" bind:checked={autoUpdateEnabled} class="h-4 w-4" />
              Автообновление цен включено
            </label>
          </div>

          <div class="grid gap-3 md:grid-cols-2">
            <Button variant="ghost" loading={savingSettings} on:click={saveStrategySettings}>
              {savingSettings ? 'Сохранение…' : 'Сохранить настройки'}
            </Button>

            <Button variant="neural" loading={loading} disabled={!productId} on:click={calculatePrice}>
              {#if !loading}
                <Calculator class="h-5 w-5" aria-hidden="true" />
              {/if}
              {loading ? 'Расчёт…' : 'Рассчитать цену'}
            </Button>
          </div>
        </div>
      {/if}
    </GlassCard>

    <!-- Результат расчёта -->
    <div class="xl:col-span-5">
      {#if loading}
        <GlassCard glow padding="lg">
          <div class="space-y-4">
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="card" />
          </div>
        </GlassCard>
      {:else if result}
        <GlassCard glow padding="lg">
          <h2 class="mb-6 text-xl font-semibold text-foreground">Результат расчёта</h2>

          <div class="grid gap-4 sm:grid-cols-3 xl:grid-cols-1">
            <MetricCard
              title="Текущая цена"
              value={`${result.current_price} ₽`}
              trend="neutral"
              icon={Wallet}
            />
            <MetricCard
              title="Рекомендуемая"
              value={`${result.recommended_price} ₽`}
              trend="up"
              glow
              icon={TrendingUp}
            />
            <MetricCard
              title="Изменение"
              value={`${result.change_percent > 0 ? '+' : ''}${result.change_percent}%`}
              trend={result.change_percent > 0 ? 'up' : result.change_percent < 0 ? 'down' : 'neutral'}
              icon={result.change_percent >= 0 ? TrendingUp : TrendingDown}
            />
          </div>

          <div class="mt-6 flex flex-wrap items-center gap-2">
            <StatusBadge variant="ai" label={result.strategy} dot={false} />
            <StatusBadge
              variant={result.change_percent > 0 ? 'success' : result.change_percent < 0 ? 'warning' : 'neutral'}
              label={`Маржа: ${result.target_margin}%`}
              dot={false}
            />
            <StatusBadge
              variant="info"
              label={getCompetitorSourceLabel(result.competitor_prices_source)}
              dot={false}
            />
          </div>

          {#if result.reasoning}
            <div class="mt-6">
              <AIInsightCard title="Почему такая цена" insight={result.reasoning} />
            </div>
          {/if}

          <div class="mt-6 glass-card rounded-xl p-5">
            <div class="grid gap-4 sm:grid-cols-2">
              <div>
                <p class="text-sm text-muted-foreground">Источник данных расчёта</p>
                <p class="mt-1 break-words font-medium text-foreground">{result.data_source}</p>
              </div>

              <div>
                <p class="text-sm text-muted-foreground">Конкурентов</p>
                <p class="mt-1 font-medium text-foreground">{result.competitor_count}</p>
              </div>

              {#if result.min_competitor_price}
                <div>
                  <p class="text-sm text-muted-foreground">Мин. цена конкурента</p>
                  <p class="mt-1 font-medium text-foreground">{result.min_competitor_price} ₽</p>
                </div>
              {/if}

              {#if result.avg_competitor_price}
                <div>
                  <p class="text-sm text-muted-foreground">Средняя цена конкурентов</p>
                  <p class="mt-1 font-medium text-foreground">{result.avg_competitor_price} ₽</p>
                </div>
              {/if}
            </div>
          </div>
        </GlassCard>
      {:else}
        <GlassCard padding="lg">
          <EmptyState
            title="Результат появится здесь"
            description="Выберите товар и нажмите «Рассчитать цену», чтобы получить рекомендацию Profit Autopilot."
            icon={Calculator}
          />
        </GlassCard>
      {/if}
    </div>
  </div>
</div>

<AppPageStyles />
