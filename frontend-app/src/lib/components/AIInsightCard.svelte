<script lang="ts">
  import { Sparkles } from 'lucide-svelte';
  import GlassCard from './GlassCard.svelte';
  import StatusBadge from './StatusBadge.svelte';
  import { cn } from '$lib/utils/cn';

  /** Карточка AI-инсайта с уровнем уверенности. */
  export let title: string;
  export let insight: string;
  export let confidence: number | null = null;
  export let variant: 'default' | 'highlight' = 'default';
  export let className = '';
</script>

<GlassCard
  className={cn(
    'relative overflow-hidden border-glow-purple',
    variant === 'highlight' && 'glass-card-glow',
    className
  )}
  glow={variant === 'highlight'}
  padding="md"
>
  <div
    class="pointer-events-none absolute inset-0 bg-gradient-to-br from-neural-purple/10 via-transparent to-neural-cyan/5"
    aria-hidden="true"
  ></div>

  <div class="relative space-y-4">
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-center gap-2">
        <div
          class="flex h-9 w-9 items-center justify-center rounded-lg gradient-ai text-white shadow-glow-sm"
          aria-hidden="true"
        >
          <Sparkles class="h-4 w-4" />
        </div>
        <div>
          <p class="text-xs font-semibold uppercase tracking-wider text-neural-purple">AI Insight</p>
          <h3 class="text-sm font-semibold text-foreground">{title}</h3>
        </div>
      </div>
      {#if confidence !== null}
        <StatusBadge variant="ai" label="{confidence}%" />
      {/if}
    </div>

    <p class="text-sm leading-relaxed text-muted-foreground">{insight}</p>

    {#if $$slots.actions}
      <div class="flex flex-wrap items-center gap-2 border-t border-border/60 pt-4">
        <slot name="actions" />
      </div>
    {/if}
  </div>
</GlassCard>
