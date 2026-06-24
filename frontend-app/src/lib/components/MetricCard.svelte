<script lang="ts">
  import type { ComponentType } from 'svelte';
  import { TrendingUp, TrendingDown, Minus } from 'lucide-svelte';
  import GlassCard from './GlassCard.svelte';
  import { cn } from '$lib/utils/cn';

  /** Карточка метрики с трендом и иконкой. */
  export let title: string;
  export let value: string | number;
  export let subtitle = '';
  export let change: number | null = null;
  export let changeLabel = '';
  export let trend: 'up' | 'down' | 'neutral' = 'neutral';
  export let icon: ComponentType | null = null;
  export let className = '';
  export let glow = false;

  $: TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  $: trendColor =
    trend === 'up'
      ? 'text-success'
      : trend === 'down'
        ? 'text-destructive'
        : 'text-muted-foreground';
</script>

<GlassCard className={cn('relative overflow-hidden', className)} {glow} padding="md">
  <div class="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-neural-cyan/10 blur-2xl" aria-hidden="true"></div>

  <div class="relative flex items-start justify-between gap-4">
    <div class="min-w-0 flex-1 space-y-2">
      <p class="text-sm font-medium text-muted-foreground">{title}</p>
      <p class="metric-value text-gradient">{value}</p>
      {#if subtitle}
        <p class="text-xs text-muted-foreground">{subtitle}</p>
      {/if}
      {#if change !== null || changeLabel}
        <div class={cn('flex items-center gap-1.5 text-xs font-medium', trendColor)}>
          <svelte:component this={TrendIcon} class="h-3.5 w-3.5" aria-hidden="true" />
          {#if change !== null}
            <span>{change > 0 ? '+' : ''}{change}%</span>
          {/if}
          {#if changeLabel}
            <span class="text-muted-foreground">{changeLabel}</span>
          {/if}
        </div>
      {/if}
    </div>

    {#if icon}
      <div
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan shadow-glow-sm"
        aria-hidden="true"
      >
        <svelte:component this={icon} class="h-5 w-5" />
      </div>
    {/if}
  </div>
</GlassCard>
