<script lang="ts">
  import { apiJson } from '$lib/utils/http';
  import {
    GlassCard,
    PageHeader,
    StatusBadge,
    Button,
    Alert,
    FormField,
    LoadingSkeleton,
    EmptyState,
    ErrorState
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';
  import { Calculator, Layers, TrendingUp, Package } from 'lucide-svelte';

  type Tab = 'unit' | 'abc' | 'competitor';

  interface UnitEconomicsPayload {
    price: number;
    cost_price: number;
    commission_percent: number;
    logistics: number;
    storage: number;
    other_costs: number;
    tax_percent: number;
    buyout_percent: number;
  }

  interface UnitEconomicsResult {
    price: number;
    total_costs: number;
    breakdown: Record<string, number>;
    profit_per_unit: number;
    margin_percent: number;
    markup_percent: number | null;
    is_profitable: boolean;
  }

  interface AbcItem {
    id?: number;
    name: string;
    revenue?: number;
  }

  interface AbcResult {
    total_products: number;
    total_revenue: number;
    note?: string;
    groups: Record<'A' | 'B' | 'C', AbcItem[] | string[]>;
  }

  interface CompetitorSalesResult {
    product_id: number;
    product_name: string;
    reviews_count: number;
    estimated_total_sales: { min: number; max: number };
    estimated_monthly_sales: { min: number | null; max: number | null };
    price_history_points: number;
    method: string;
    disclaimer: string;
  }

  let activeTab: Tab = 'unit';
  let loading = false;
  let error = '';

  // --- Юнит-экономика ---
  let ue: UnitEconomicsPayload = {
    price: 1990,
    cost_price: 700,
    commission_percent: 17,
    logistics: 90,
    storage: 10,
    other_costs: 0,
    tax_percent: 6,
    buyout_percent: 92
  };
  let ueResult: UnitEconomicsResult | null = null;

  // --- ABC ---
  let abcResult: AbcResult | null = null;
  let abcAttempted = false;

  // --- Продажи конкурента ---
  let competitorProductId: number | null = null;
  let competitorResult: CompetitorSalesResult | null = null;

  const abcGroups = ['A', 'B', 'C'] as const;

  function switchTab(tab: Tab): void {
    activeTab = tab;
    error = '';
  }

  function money(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return new Intl.NumberFormat('ru-RU').format(Math.round(n)) + ' ₽';
  }

  function isAbcItem(item: AbcItem | string): item is AbcItem {
    return typeof item === 'object' && item !== null && 'name' in item;
  }

  function isAbcEmpty(result: AbcResult): boolean {
    if (result.total_products === 0) return true;
    const allGroupsEmpty = abcGroups.every((g) => (result.groups[g]?.length ?? 0) === 0);
    return allGroupsEmpty;
  }

  async function calcUnitEconomics(e: Event): Promise<void> {
    e.preventDefault();
    error = '';
    ueResult = null;
    loading = true;

    try {
      ueResult = await apiJson<UnitEconomicsResult>(
        '/api/v1/analytics/unit-economics',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(ue)
        },
        'Ошибка расчёта'
      );
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка расчёта';
    } finally {
      loading = false;
    }
  }

  async function loadAbc(): Promise<void> {
    error = '';
    abcResult = null;
    abcAttempted = true;
    loading = true;

    try {
      abcResult = await apiJson<AbcResult>('/api/v1/analytics/abc', {}, 'Ошибка загрузки ABC-анализа');
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка ABC-анализа';
    } finally {
      loading = false;
    }
  }

  async function loadCompetitorSales(e: Event): Promise<void> {
    e.preventDefault();
    error = '';
    competitorResult = null;

    if (!competitorProductId) {
      error = 'Укажите ID товара-конкурента';
      return;
    }

    loading = true;

    try {
      competitorResult = await apiJson<CompetitorSalesResult>(
        `/api/v1/analytics/competitor-sales/${competitorProductId}`,
        {},
        'Ошибка оценки продаж'
      );
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка оценки продаж';
    } finally {
      loading = false;
    }
  }
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр"
    title="Аналитика"
    subtitle="Юнит-экономика, ABC-анализ и оценка продаж конкурентов"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="ai" label="Финансы и ассортимент" dot={false} />
    </svelte:fragment>
  </PageHeader>

  {#if error && activeTab !== 'abc'}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}

  <GlassCard glow padding="lg" className="space-y-6">
    <!-- Табы -->
    <div class="flex flex-wrap gap-2">
      <Button
        variant={activeTab === 'unit' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('unit')}
      >
        <Calculator class="h-4 w-4" aria-hidden="true" />
        Юнит-экономика
      </Button>
      <Button
        variant={activeTab === 'abc' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('abc')}
      >
        <Layers class="h-4 w-4" aria-hidden="true" />
        ABC-анализ
      </Button>
      <Button
        variant={activeTab === 'competitor' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('competitor')}
      >
        <TrendingUp class="h-4 w-4" aria-hidden="true" />
        Продажи конкурента
      </Button>
    </div>

    {#if activeTab === 'unit'}
      <form on:submit={calcUnitEconomics} class="space-y-6">
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <FormField label="Цена продажи, ₽" let:controlId>
            <input id={controlId} class="page-input" type="number" min="1" bind:value={ue.price} />
          </FormField>
          <FormField label="Себестоимость, ₽" let:controlId>
            <input id={controlId} class="page-input" type="number" min="0" bind:value={ue.cost_price} />
          </FormField>
          <FormField label="Комиссия, %" let:controlId>
            <input id={controlId} class="page-input" type="number" min="0" max="100" bind:value={ue.commission_percent} />
          </FormField>
          <FormField label="Логистика, ₽" let:controlId>
            <input id={controlId} class="page-input" type="number" min="0" bind:value={ue.logistics} />
          </FormField>
          <FormField label="Хранение, ₽" let:controlId>
            <input id={controlId} class="page-input" type="number" min="0" bind:value={ue.storage} />
          </FormField>
          <FormField label="Прочие, ₽" let:controlId>
            <input id={controlId} class="page-input" type="number" min="0" bind:value={ue.other_costs} />
          </FormField>
          <FormField label="Налог, %" let:controlId>
            <input id={controlId} class="page-input" type="number" min="0" max="100" bind:value={ue.tax_percent} />
          </FormField>
          <FormField label="Выкуп, %" hint="Доля выкупленных заказов" let:controlId>
            <input id={controlId} class="page-input" type="number" min="1" max="100" bind:value={ue.buyout_percent} />
          </FormField>
        </div>

        <Button type="submit" variant="neural" loading={loading} disabled={loading}>
          <Calculator class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Расчёт...' : 'Рассчитать прибыль'}
        </Button>
      </form>

      {#if loading && !ueResult}
        <LoadingSkeleton variant="card" />
      {:else if ueResult}
        <div class="space-y-4">
          <div class="grid gap-4 sm:grid-cols-3">
            <div class="surface p-4">
              <p class="text-sm text-muted-foreground">Прибыль с единицы</p>
              <p class="metric-value mt-1 {ueResult.is_profitable ? 'text-neural-cyan' : 'text-destructive'}">
                {money(ueResult.profit_per_unit)}
              </p>
            </div>
            <div class="surface p-4">
              <p class="text-sm text-muted-foreground">Маржа</p>
              <p class="metric-value mt-1 text-foreground">{ueResult.margin_percent}%</p>
            </div>
            <div class="surface p-4">
              <p class="text-sm text-muted-foreground">Сумма расходов</p>
              <p class="metric-value mt-1 text-foreground">{money(ueResult.total_costs)}</p>
            </div>
          </div>

          <details class="surface p-4">
            <summary class="cursor-pointer text-sm font-medium text-foreground">Детализация расходов</summary>
            <div class="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
              {#each Object.entries(ueResult.breakdown) as [key, value]}
                <div class="flex justify-between gap-3">
                  <span>{key}</span>
                  <span class="text-foreground">{money(Number(value))}</span>
                </div>
              {/each}
            </div>
          </details>
        </div>
      {/if}

    {:else if activeTab === 'abc'}
      <div class="space-y-6">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-foreground">ABC-анализ ассортимента</h2>
          <p class="text-sm text-muted-foreground">
            Разбивка ваших товаров на группы A/B/C по доле в выручке (цена × продажи).
          </p>
        </div>

        <Button variant="neural" loading={loading} disabled={loading} on:click={loadAbc}>
          <Layers class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Загрузка...' : 'Построить ABC-анализ'}
        </Button>

        {#if loading}
          <LoadingSkeleton variant="card" />
          <div class="grid gap-4 sm:grid-cols-3">
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
            <LoadingSkeleton variant="metric" />
          </div>
        {:else if error && abcAttempted}
          <ErrorState title="Не удалось построить ABC-анализ" description={error} on:click={loadAbc} />
        {:else if abcResult}
          {#if abcResult.note}
            <Alert variant="warning" title="Недостаточно данных">{abcResult.note}</Alert>
          {/if}

          {#if isAbcEmpty(abcResult)}
            <EmptyState
              icon={Package}
              title="Нет данных для ABC-анализа"
              description="Добавьте товары с продажами (sales_count) в раздел «Товары», затем повторите анализ."
            />
          {:else}
            <div class="flex flex-wrap gap-2">
              <StatusBadge variant="info" label={`Товаров: ${abcResult.total_products}`} dot={false} />
              <StatusBadge variant="neutral" label={`Выручка: ${money(abcResult.total_revenue)}`} dot={false} />
            </div>

            <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {#each abcGroups as group}
                {@const items = abcResult.groups[group] ?? []}
                <div class="surface p-4">
                  <p class="mb-3 text-sm font-semibold text-foreground">
                    Группа {group}
                    <span class="text-muted-foreground">({items.length})</span>
                  </p>
                  {#if items.length === 0}
                    <p class="text-xs text-muted-foreground">Нет товаров в группе</p>
                  {:else}
                    <ul class="space-y-1.5 text-xs text-muted-foreground">
                      {#each items.slice(0, 12) as item}
                        <li class="flex justify-between gap-2">
                          <span class="truncate">{isAbcItem(item) ? item.name : item}</span>
                          {#if isAbcItem(item) && item.revenue !== undefined}
                            <span class="shrink-0 text-foreground">{money(item.revenue)}</span>
                          {/if}
                        </li>
                      {/each}
                    </ul>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </div>

    {:else}
      <form on:submit={loadCompetitorSales} class="space-y-6">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-foreground">Оценка продаж конкурента</h2>
          <p class="text-sm text-muted-foreground">
            Эвристическая оценка по отзывам и истории цен. Точные продажи маркетплейсы не раскрывают.
          </p>
        </div>

        <FormField
          label="ID товара-конкурента"
          hint="ID берётся из раздела «Товары» (карточка конкурента)."
          let:controlId
        >
          <input
            id={controlId}
            class="page-input max-w-xs"
            type="number"
            min="1"
            bind:value={competitorProductId}
            placeholder="например, 42"
          />
        </FormField>

        <Button type="submit" variant="neural" loading={loading} disabled={loading}>
          <TrendingUp class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Оценка...' : 'Оценить продажи'}
        </Button>
      </form>

      {#if loading && !competitorResult}
        <LoadingSkeleton variant="card" />
        <div class="grid gap-4 sm:grid-cols-2">
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
        </div>
      {:else if competitorResult}
        <div class="space-y-4">
          <p class="text-sm text-muted-foreground">
            Товар:
            <span class="font-medium text-foreground">{competitorResult.product_name}</span>
          </p>

          <div class="grid gap-4 sm:grid-cols-2">
            <div class="surface p-4">
              <p class="text-sm text-muted-foreground">Оценка всего продаж</p>
              <p class="metric-value mt-1 text-foreground">
                {competitorResult.estimated_total_sales.min} – {competitorResult.estimated_total_sales.max}
              </p>
            </div>
            <div class="surface p-4">
              <p class="text-sm text-muted-foreground">Оценка в месяц</p>
              <p class="metric-value mt-1 text-foreground">
                {competitorResult.estimated_monthly_sales.min ?? '—'} – {competitorResult.estimated_monthly_sales.max ?? '—'}
              </p>
            </div>
          </div>

          <Alert variant="info" title="Метод оценки">
            {competitorResult.disclaimer}
          </Alert>
        </div>
      {/if}
    {/if}
  </GlassCard>
</div>

<AppPageStyles />
