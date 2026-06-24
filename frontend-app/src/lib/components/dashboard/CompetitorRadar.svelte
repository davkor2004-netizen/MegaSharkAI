<script lang="ts">
  import GlassCard from '$lib/components/GlassCard.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import { cn } from '$lib/utils/cn';

  /** Визуализация «радара конкурентов» на данных дашборда. */
  export let ownProducts = 0;
  export let competitorProducts = 0;
  export let averagePrice = 0;
  export let averageCompetitorPrice = 0;
  export let className = '';

  $: totalTracked = ownProducts + competitorProducts;
  $: ownShare = totalTracked > 0 ? Math.round((ownProducts / totalTracked) * 100) : 0;
  $: competitorShare = totalTracked > 0 ? Math.round((competitorProducts / totalTracked) * 100) : 0;

  $: priceGap =
    averagePrice > 0 && averageCompetitorPrice > 0
      ? Math.round(((averagePrice - averageCompetitorPrice) / averageCompetitorPrice) * 100)
      : null;

  $: radarIntensity = Math.min(100, competitorProducts * 12 + (priceGap !== null && priceGap < 0 ? 20 : 0));

  const numberFormatter = new Intl.NumberFormat('ru-RU');
  const currencyFormatter = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0
  });
</script>

<GlassCard className={cn('relative overflow-hidden', className)} glow padding="md">
  <div
    class="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-neural-purple/15 blur-3xl"
    aria-hidden="true"
  ></div>

  <div class="relative space-y-5">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-neural-cyan">Live Scan</p>
        <h2 class="text-lg font-semibold text-foreground">Competitor Radar</h2>
        <p class="mt-1 text-sm text-muted-foreground">Соотношение своих SKU и конкурентов в базе</p>
      </div>
      <StatusBadge
        variant={competitorProducts > ownProducts ? 'warning' : 'success'}
        label={competitorProducts > ownProducts ? 'Давление' : 'Контроль'}
      />
    </div>

    <!-- Radar visualization -->
    <div class="relative mx-auto flex h-44 w-44 items-center justify-center" aria-hidden="true">
      <div class="absolute inset-0 rounded-full border border-neural-cyan/15"></div>
      <div class="absolute inset-[15%] rounded-full border border-neural-cyan/10"></div>
      <div class="absolute inset-[30%] rounded-full border border-neural-cyan/10"></div>
      <div
        class="absolute inset-0 rounded-full opacity-40"
        style="background: conic-gradient(from 0deg, transparent, hsl(var(--neural-cyan) / 0.25) 40deg, transparent 80deg); animation: radarSpin 6s linear infinite;"
      ></div>
      <div class="relative z-10 text-center">
        <p class="text-2xl font-bold text-gradient">{numberFormatter.format(totalTracked)}</p>
        <p class="text-[10px] uppercase tracking-wider text-muted-foreground">объектов</p>
      </div>
      {#if competitorProducts > 0}
        <div
          class="absolute h-3 w-3 rounded-full bg-warning shadow-glow-sm"
          style="top: 18%; right: 22%; opacity: {0.4 + radarIntensity / 200};"
        ></div>
      {/if}
      {#if ownProducts > 0}
        <div
          class="absolute h-3 w-3 rounded-full bg-neural-cyan shadow-glow-sm"
          style="bottom: 20%; left: 24%;"
        ></div>
      {/if}
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="rounded-xl border border-neural-cyan/20 bg-neural-cyan/5 p-3">
        <p class="text-xs text-muted-foreground">Свои</p>
        <p class="text-lg font-bold text-neural-cyan">{numberFormatter.format(ownProducts)}</p>
        <p class="text-xs text-muted-foreground">{ownShare}% портфеля</p>
      </div>
      <div class="rounded-xl border border-warning/20 bg-warning/5 p-3">
        <p class="text-xs text-muted-foreground">Конкуренты</p>
        <p class="text-lg font-bold text-warning">{numberFormatter.format(competitorProducts)}</p>
        <p class="text-xs text-muted-foreground">{competitorShare}% портфеля</p>
      </div>
    </div>

    <div class="rounded-xl border border-border/60 bg-background/30 p-3 text-sm">
      <div class="flex items-center justify-between gap-2">
        <span class="text-muted-foreground">Средняя цена (вы)</span>
        <span class="font-medium text-foreground">{currencyFormatter.format(averagePrice)}</span>
      </div>
      <div class="mt-2 flex items-center justify-between gap-2">
        <span class="text-muted-foreground">Средняя цена (конкуренты)</span>
        <span class="font-medium text-foreground">
          {averageCompetitorPrice > 0 ? currencyFormatter.format(averageCompetitorPrice) : '—'}
        </span>
      </div>
      {#if priceGap !== null}
        <p class="mt-2 text-xs {priceGap >= 0 ? 'text-success' : 'text-warning'}">
          {priceGap >= 0 ? '↑' : '↓'} {Math.abs(priceGap)}% относительно конкурентов
        </p>
      {/if}
    </div>

    <a href="/parsing" class="btn-ghost-neural w-full text-center text-sm">Открыть парсинг →</a>
  </div>
</GlassCard>

<style>
  @keyframes radarSpin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    div[style*='radarSpin'] {
      animation: none !important;
    }
  }
</style>
