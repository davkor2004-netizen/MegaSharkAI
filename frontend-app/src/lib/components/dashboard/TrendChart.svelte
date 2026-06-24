<script lang="ts">
  import GlassCard from '$lib/components/GlassCard.svelte';
  import { cn } from '$lib/utils/cn';

  interface TrendItem {
    period: string;
    label: string;
    total_products: number;
    average_price: number;
    total_products_delta: number | null;
    average_price_delta: number | null;
  }

  /** CSS-bar chart трендов по периодам в стиле Command Center. */
  export let trends: TrendItem[] = [];
  export let selectedPeriod = '';
  export let isPeriodSwitching = false;
  export let disabled = false;
  export let className = '';
  export let onSelect: (period: string) => void = () => {};

  const currencyFormatter = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0
  });

  function maxProducts(): number {
    if (!trends.length) return 0;
    return Math.max(...trends.map((t) => t.total_products));
  }

  function barWidth(value: number): number {
    const max = maxProducts();
    if (!max || value <= 0) return 0;
    return Math.max(8, Math.round((value / max) * 100));
  }

  function deltaClass(value: number | null): string {
    if (value === null || value === undefined) return 'text-muted-foreground';
    if (value > 0) return 'text-success';
    if (value < 0) return 'text-destructive';
    return 'text-muted-foreground';
  }

  function deltaText(value: number | null): string {
    if (value === null || value === undefined) return 'н/д';
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  }
</script>

<GlassCard className={className} padding="md">
  <div class="mb-4">
    <p class="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Analytics</p>
    <h2 class="text-lg font-semibold text-foreground">Динамика по периодам</h2>
  </div>

  {#if trends.length > 0}
    <div class="grid gap-3 md:grid-cols-3">
      {#each trends as trend}
        <button
          type="button"
          class={cn(
            'rounded-xl border p-4 text-left transition-neural',
            selectedPeriod === trend.period
              ? 'border-neural-cyan/40 bg-neural-cyan/10 shadow-glow-sm'
              : 'border-border/60 bg-background/30 hover:border-neural-cyan/25',
            (disabled || isPeriodSwitching) && 'opacity-70'
          )}
          disabled={disabled || isPeriodSwitching || selectedPeriod === trend.period}
          on:click={() => onSelect(trend.period)}
        >
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-semibold text-foreground">{trend.label}</span>
            {#if selectedPeriod === trend.period}
              <span class="rounded-full bg-neural-cyan/20 px-2 py-0.5 text-[10px] font-semibold uppercase text-neural-cyan">
                {isPeriodSwitching ? '…' : 'Active'}
              </span>
            {/if}
          </div>

          <p class="mt-3 text-2xl font-bold text-gradient">{trend.total_products}</p>
          <p class="text-xs text-muted-foreground">товаров</p>

          <div class="mt-3 h-2 overflow-hidden rounded-full bg-background/60">
            <div
              class="h-full rounded-full gradient-neural transition-all duration-500"
              style="width: {barWidth(trend.total_products)}%"
            ></div>
          </div>

          <div class="mt-3 flex items-center justify-between text-xs">
            <span class={deltaClass(trend.total_products_delta)}>Δ {deltaText(trend.total_products_delta)}</span>
            <span class="text-muted-foreground">{currencyFormatter.format(trend.average_price)}</span>
          </div>
        </button>
      {/each}
    </div>
  {:else}
    <p class="text-sm text-muted-foreground">Нет данных для графика.</p>
  {/if}
</GlassCard>

<style>
  .transition-neural {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
</style>
