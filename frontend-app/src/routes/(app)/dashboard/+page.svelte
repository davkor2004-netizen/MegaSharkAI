<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ArrowRight,
    Package,
    Radar,
    RefreshCw,
    Sparkles,
    Tag,
    TrendingUp,
    Wallet,
    Zap
  } from 'lucide-svelte';
  import { apiJson } from '$lib/utils/http';
  import {
    AIInsightCard,
    Button,
    EmptyState,
    ErrorState,
    GlassCard,
    LoadingSkeleton,
    MetricCard,
    PageHeader,
    StatusBadge
  } from '$lib/components';
  import CompetitorRadar from '$lib/components/dashboard/CompetitorRadar.svelte';
  import TrendChart from '$lib/components/dashboard/TrendChart.svelte';

  type DashboardPeriod = 'today' | '7d' | '30d';

  interface DashboardStats {
    period: DashboardPeriod;
    period_start: string;
    period_end: string;
    total_products: number;
    own_products: number;
    competitor_products: number;
    average_price: number;
    average_competitor_price: number;
    products_with_discount: number;
    marketplace_distribution: Record<string, number>;
    previous_period: {
      total_products: number;
      average_price: number;
    };
    delta: {
      total_products_percent: number | null;
      average_price_percent: number | null;
    };
  }

  interface DashboardProduct {
    id: number;
    name: string;
    price: number | null;
    marketplace: string | null;
    is_own: boolean;
    created_at: string | null;
  }

  interface ProductListResponse {
    items?: DashboardProduct[];
  }

  interface TrendMetric {
    period: DashboardPeriod;
    label: string;
    total_products: number;
    average_price: number;
    total_products_delta: number | null;
    average_price_delta: number | null;
  }

  interface DailyInsight {
    title: string;
    insight: string;
    confidence: number;
    highlight?: boolean;
  }

  const DEFAULT_STATS: DashboardStats = {
    period: '30d',
    period_start: '',
    period_end: '',
    total_products: 0,
    own_products: 0,
    competitor_products: 0,
    average_price: 0,
    average_competitor_price: 0,
    products_with_discount: 0,
    marketplace_distribution: {},
    previous_period: {
      total_products: 0,
      average_price: 0
    },
    delta: {
      total_products_percent: null,
      average_price_percent: null
    }
  };

  const PERIOD_OPTIONS: { value: DashboardPeriod; label: string }[] = [
    { value: 'today', label: 'Сегодня' },
    { value: '7d', label: '7 дней' },
    { value: '30d', label: '30 дней' }
  ];

  const TREND_PERIODS: DashboardPeriod[] = ['today', '7d', '30d'];

  let selectedPeriod: DashboardPeriod = '30d';
  let stats: DashboardStats = { ...DEFAULT_STATS };
  let trendMetrics: TrendMetric[] = [];
  let products: DashboardProduct[] = [];
  let loading = true;
  let isPeriodSwitching = false;
  let errorMessage = '';
  let statusMessage = '';

  const numberFormatter = new Intl.NumberFormat('ru-RU');
  const currencyFormatter = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0
  });

  $: dailyInsights = buildDailyInsights(stats);
  $: marketplaceRows = getSortedMarketplaceDistribution();

  onMount(() => {
    loadDashboardData();
  });

  function showError(message: string): void {
    errorMessage = message;
    statusMessage = '';
  }

  function showStatus(message: string): void {
    statusMessage = message;
    errorMessage = '';
  }

  async function loadDashboardData(
    period: DashboardPeriod = selectedPeriod,
    fullScreenLoading: boolean = true
  ): Promise<void> {
    if (fullScreenLoading) {
      loading = true;
    }

    isPeriodSwitching = !fullScreenLoading;
    showStatus('');
    selectedPeriod = period;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    try {
      const [productsData, ...trendData] = await Promise.all([
        apiJson<ProductListResponse>(
          '/api/v1/products/list?limit=5',
          { signal: controller.signal },
          'Не удалось загрузить последние товары'
        ),
        ...TREND_PERIODS.map((trendPeriod) =>
          apiJson<DashboardStats>(
            `/api/v1/products/stats/summary?period=${trendPeriod}`,
            { signal: controller.signal },
            'Не удалось загрузить тренды'
          )
        )
      ]);

      const selectedStats = trendData.find((item) => item.period === selectedPeriod);
      if (!selectedStats) {
        throw new Error('Не удалось получить статистику выбранного периода');
      }

      stats = {
        ...DEFAULT_STATS,
        ...selectedStats
      };
      products = Array.isArray(productsData?.items) ? productsData.items : [];

      trendMetrics = trendData.map((item) => ({
        period: item.period,
        label: PERIOD_OPTIONS.find((option) => option.value === item.period)?.label || item.period,
        total_products: item.total_products ?? 0,
        average_price: item.average_price ?? 0,
        total_products_delta: item.delta?.total_products_percent ?? null,
        average_price_delta: item.delta?.average_price_percent ?? null
      }));

      showStatus(`Данные обновлены за период: ${getSelectedPeriodLabel()}`);
    } catch (err) {
      console.error('Ошибка загрузки дашборда:', err);
      stats = { ...DEFAULT_STATS };
      trendMetrics = [];
      products = [];

      if (err instanceof DOMException && err.name === 'AbortError') {
        showError('Сервер долго отвечает. Попробуйте обновить данные.');
      } else {
        showError(err instanceof Error ? err.message : 'Ошибка загрузки данных дашборда');
      }
    } finally {
      clearTimeout(timeoutId);
      loading = false;
      isPeriodSwitching = false;
    }
  }

  function buildDailyInsights(data: DashboardStats): DailyInsight[] {
    const insights: DailyInsight[] = [];

    if (data.total_products === 0) {
      insights.push({
        title: 'Быстрый старт',
        insight:
          'Каталог пуст. Запустите парсинг конкурентов или импорт Excel — командный центр начнёт строить аналитику автоматически.',
        confidence: 96,
        highlight: true
      });
      return insights;
    }

    if (data.competitor_products > data.own_products) {
      insights.push({
        title: 'Доля конкурентов выше',
        insight: `В базе ${numberFormatter.format(data.competitor_products)} конкурентных SKU против ${numberFormatter.format(data.own_products)} своих. Рекомендуем усилить мониторинг цен и repricing.`,
        confidence: 88
      });
    }

    if (data.average_competitor_price > 0 && data.average_price > 0) {
      const gap = ((data.average_price - data.average_competitor_price) / data.average_competitor_price) * 100;
      if (gap < -5) {
        insights.push({
          title: 'Ценовое давление',
          insight: `Средняя цена на ${Math.abs(gap).toFixed(1)}% выше конкурентов. Проверьте карточки со скидкой и правила repricing.`,
          confidence: 84,
          highlight: true
        });
      } else if (gap > 5) {
        insights.push({
          title: 'Потенциал маржи',
          insight: `Вы ниже рынка на ${gap.toFixed(1)}%. Есть пространство для аккуратного повышения цены без потери конверсии.`,
          confidence: 81
        });
      }
    }

    if (data.products_with_discount > 0) {
      insights.push({
        title: 'Скидки в портфеле',
        insight: `${numberFormatter.format(data.products_with_discount)} товаров со скидкой. Сверьте промо-акции с маржинальностью в разделе Repricing.`,
        confidence: 79
      });
    }

    if (insights.length === 0) {
      insights.push({
        title: 'Стабильный режим',
        insight:
          'Ключевые метрики в норме. Продолжайте мониторинг конкурентов и обновляйте парсинг раз в 7 дней.',
        confidence: 77
      });
    }

    return insights.slice(0, 2);
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit'
    });
  }

  function formatNumber(value: number | null | undefined): string {
    return numberFormatter.format(value ?? 0);
  }

  function formatCurrency(value: number | null | undefined): string {
    return currencyFormatter.format(value ?? 0);
  }

  function formatOptionalPrice(value: number | null | undefined): string {
    if (value === null || value === undefined || value <= 0) return 'Не указана';
    return formatCurrency(value);
  }

  function getDeltaTrend(value: number | null | undefined): 'up' | 'down' | 'neutral' {
    if (value === null || value === undefined || value === 0) return 'neutral';
    return value > 0 ? 'up' : 'down';
  }

  function getMarketplaceLabel(marketplace: string): string {
    const labels: Record<string, string> = {
      wildberries: 'Wildberries',
      ozon: 'Ozon',
      yandex_market: 'Яндекс Маркет',
      avito: 'Avito',
      kazanexpress: 'KazanExpress',
      other: 'Другое'
    };

    return labels[marketplace] || marketplace || 'Не указан';
  }

  function getMarketplacePercent(count: number): number {
    if (!stats.total_products || count <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((count / stats.total_products) * 100)));
  }

  function getSelectedPeriodLabel(): string {
    return PERIOD_OPTIONS.find((item) => item.value === selectedPeriod)?.label || selectedPeriod;
  }

  function getSortedMarketplaceDistribution(): Array<{ marketplace: string; count: number }> {
    return Object.entries(stats.marketplace_distribution || {})
      .filter(([, count]) => Number(count) > 0)
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .map(([marketplace, count]) => ({ marketplace, count: Number(count) }));
  }

  async function handleTrendSelect(period: string): Promise<void> {
    await handleTrendCardClick(period as DashboardPeriod);
  }

  async function handleTrendCardClick(period: DashboardPeriod): Promise<void> {
    if (loading || isPeriodSwitching || period === selectedPeriod) {
      return;
    }

    await loadDashboardData(period, false);
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<div class="mx-auto max-w-[1400px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр MegaShark"
    title="Обзор портфеля"
    subtitle="KPI, AI-инсайты и radar конкурентов за период {getSelectedPeriodLabel()}"
  >
    <svelte:fragment slot="meta">
      <div class="flex flex-wrap items-center gap-1.5">
        {#each PERIOD_OPTIONS as option}
          <Button
            variant={selectedPeriod === option.value ? 'neural' : 'ghost'}
            size="sm"
            disabled={loading || isPeriodSwitching}
            on:click={() => loadDashboardData(option.value, true)}
          >
            {option.label}
          </Button>
        {/each}
      </div>
      {#if statusMessage && !errorMessage}
        <StatusBadge variant="success" label="Synced" dot={false} />
      {/if}
    </svelte:fragment>

    <svelte:fragment slot="actions">
      <Button
        variant="ghost"
        size="sm"
        className="hidden sm:inline-flex"
        disabled={loading || isPeriodSwitching}
        on:click={() => loadDashboardData(selectedPeriod, true)}
      >
        <RefreshCw class="h-4 w-4 {loading || isPeriodSwitching ? 'animate-spin' : ''}" aria-hidden="true" />
        Обновить
      </Button>
      <Button variant="neural" size="sm" className="hidden sm:inline-flex" on:click={() => goto('/parsing')}>
        <Radar class="h-4 w-4" aria-hidden="true" />
        Парсинг
      </Button>
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {#each Array(4) as _}
        <LoadingSkeleton variant="metric" />
      {/each}
    </div>
    <div class="grid gap-4 lg:grid-cols-2">
      <LoadingSkeleton variant="card" />
      <LoadingSkeleton variant="card" />
    </div>
    <LoadingSkeleton variant="card" />
  {:else if errorMessage}
    <ErrorState title="Не удалось загрузить командный центр" description={errorMessage}>
      <svelte:fragment slot="action">
        <Button variant="neural" on:click={() => loadDashboardData()}>
          <RefreshCw class="h-4 w-4" aria-hidden="true" />
          Повторить
        </Button>
      </svelte:fragment>
    </ErrorState>
  {:else}
    <!-- KPI -->
    <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        title="Всего SKU"
        value={formatNumber(stats.total_products)}
        change={stats.delta.total_products_percent}
        changeLabel="к пред. периоду"
        trend={getDeltaTrend(stats.delta.total_products_percent)}
        icon={Package}
        glow
      />
      <MetricCard
        title="Свои товары"
        value={formatNumber(stats.own_products)}
        subtitle="{stats.total_products > 0 ? Math.round((stats.own_products / stats.total_products) * 100) : 0}% портфеля"
        trend="neutral"
        icon={TrendingUp}
      />
      <MetricCard
        title="Конкуренты"
        value={formatNumber(stats.competitor_products)}
        subtitle="объектов radar"
        trend={stats.competitor_products > stats.own_products ? 'down' : 'up'}
        icon={Zap}
      />
      <MetricCard
        title="Средняя цена"
        value={formatCurrency(stats.average_price)}
        change={stats.delta.average_price_percent}
        changeLabel="Δ цены"
        trend={getDeltaTrend(stats.delta.average_price_percent)}
        subtitle="Со скидкой: {formatNumber(stats.products_with_discount)}"
        icon={Wallet}
      />
    </section>

    <!-- AI + Radar -->
    <section class="grid gap-4 lg:grid-cols-5">
      <div class="space-y-4 lg:col-span-3">
        <div class="flex items-center gap-2">
          <Sparkles class="h-5 w-5 text-neural-purple" aria-hidden="true" />
          <h2 class="text-lg font-semibold text-foreground">AI-рекомендации дня</h2>
        </div>
        <div class="grid gap-4 md:grid-cols-2">
          {#each dailyInsights as insight, index}
            <AIInsightCard
              title={insight.title}
              insight={insight.insight}
              confidence={insight.confidence}
              variant={insight.highlight || index === 0 ? 'highlight' : 'default'}
            />
          {/each}
        </div>
      </div>

      <div class="lg:col-span-2">
        <CompetitorRadar
          ownProducts={stats.own_products}
          competitorProducts={stats.competitor_products}
          averagePrice={stats.average_price}
          averageCompetitorPrice={stats.average_competitor_price}
        />
      </div>
    </section>

    <!-- Charts -->
    <section class="grid gap-4 xl:grid-cols-3">
      <div class="xl:col-span-2">
        <TrendChart
          trends={trendMetrics}
          selectedPeriod={selectedPeriod}
          {isPeriodSwitching}
          disabled={loading}
          onSelect={handleTrendSelect}
        />
      </div>

      <GlassCard padding="md">
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Marketplaces</p>
        <h2 class="mt-1 text-lg font-semibold text-foreground">Распределение</h2>

        {#if marketplaceRows.length > 0}
          <div class="mt-4 space-y-3">
            {#each marketplaceRows as item}
              <div>
                <div class="mb-1.5 flex items-center justify-between text-sm">
                  <span class="font-medium text-foreground">{getMarketplaceLabel(item.marketplace)}</span>
                  <span class="text-muted-foreground">
                    {formatNumber(item.count)} · {getMarketplacePercent(item.count)}%
                  </span>
                </div>
                <div class="h-2 overflow-hidden rounded-full bg-background/60">
                  <div
                    class="h-full rounded-full gradient-neural"
                    style="width: {getMarketplacePercent(item.count)}%"
                  ></div>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <EmptyState
            className="mt-4 !p-4"
            title="Нет данных"
            description="Добавьте товары через парсинг или импорт."
            icon={Tag}
          />
        {/if}
      </GlassCard>
    </section>

    <!-- Recent products -->
    <section>
      <GlassCard padding="md">
        <div class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Inventory</p>
            <h2 class="text-lg font-semibold text-foreground">Последние товары</h2>
          </div>
          <Button variant="ghost" size="sm" className="w-fit" on:click={() => goto('/products')}>
            Все товары
            <ArrowRight class="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>

        {#if products.length > 0}
          <!-- Desktop: таблица -->
          <div class="hidden overflow-x-auto md:block">
            <table class="w-full min-w-[640px] text-sm">
              <thead>
                <tr class="border-b border-border/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th class="pb-3 pr-4 font-medium">Товар</th>
                  <th class="pb-3 pr-4 font-medium">Площадка</th>
                  <th class="pb-3 pr-4 font-medium">Цена</th>
                  <th class="pb-3 pr-4 font-medium">Тип</th>
                  <th class="pb-3 font-medium">Добавлен</th>
                </tr>
              </thead>
              <tbody>
                {#each products as product}
                  <tr class="border-b border-border/40 transition-neural hover:bg-background/30">
                    <td class="py-3 pr-4 font-medium text-foreground">{product.name}</td>
                    <td class="py-3 pr-4 text-muted-foreground">
                      {getMarketplaceLabel(product.marketplace || '')}
                    </td>
                    <td class="py-3 pr-4 font-semibold text-neural-cyan">
                      {formatOptionalPrice(product.price)}
                    </td>
                    <td class="py-3 pr-4">
                      <StatusBadge
                        variant={product.is_own ? 'info' : 'warning'}
                        label={product.is_own ? 'Свой' : 'Конкурент'}
                      />
                    </td>
                    <td class="py-3 text-muted-foreground">{formatDate(product.created_at)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <!-- Mobile: карточки (без горизонтального overflow) -->
          <div class="space-y-3 md:hidden">
            {#each products as product}
              <div class="rounded-xl border border-border/50 bg-background/30 p-3">
                <div class="flex items-start justify-between gap-3">
                  <p class="min-w-0 break-words font-medium text-foreground">{product.name}</p>
                  <StatusBadge
                    variant={product.is_own ? 'info' : 'warning'}
                    label={product.is_own ? 'Свой' : 'Конкурент'}
                  />
                </div>
                <div class="mt-2 flex items-end justify-between gap-3">
                  <div>
                    <p class="font-semibold text-neural-cyan">{formatOptionalPrice(product.price)}</p>
                    <p class="text-xs text-muted-foreground">{getMarketplaceLabel(product.marketplace || '')}</p>
                  </div>
                  <p class="text-xs text-muted-foreground">{formatDate(product.created_at)}</p>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <EmptyState title="Каталог пуст" description="Спарсите первый товар или импортируйте Excel.">
            <svelte:fragment slot="action">
              <Button variant="neural" on:click={() => goto('/parsing')}>
                <Radar class="h-4 w-4" aria-hidden="true" />
                Спарсить товар
              </Button>
            </svelte:fragment>
          </EmptyState>
        {/if}
      </GlassCard>
    </section>

    <!-- Quick actions -->
    <section class="grid gap-3 sm:grid-cols-3">
      <a href="/parsing" class="glass-card rounded-xl p-4 transition-neural hover:border-glow-cyan hover:shadow-glow-sm">
        <Radar class="mb-2 h-5 w-5 text-neural-cyan" />
        <p class="font-semibold text-foreground">Парсинг</p>
        <p class="text-xs text-muted-foreground">Конкуренты по URL</p>
      </a>
      <a href="/repricing" class="glass-card rounded-xl p-4 transition-neural hover:border-glow-cyan hover:shadow-glow-sm">
        <Wallet class="mb-2 h-5 w-5 text-neural-purple" />
        <p class="font-semibold text-foreground">Repricing</p>
        <p class="text-xs text-muted-foreground">Правила цен</p>
      </a>
      <a href="/ai" class="glass-card rounded-xl p-4 transition-neural hover:border-glow-cyan hover:shadow-glow-sm">
        <Sparkles class="mb-2 h-5 w-5 text-neural-purple" />
        <p class="font-semibold text-foreground">AI Generator</p>
        <p class="text-xs text-muted-foreground">SEO и описания</p>
      </a>
    </section>
  {/if}
</div>

<style>
  .transition-neural {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
</style>
