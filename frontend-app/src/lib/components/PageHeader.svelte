<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /** Заголовок страницы Command Center. */
  export let title: string;
  export let subtitle = '';
  export let eyebrow = '';
  export let className = '';
</script>

<header class={cn('mb-8 space-y-3 animate-fade-in', className)}>
  {#if eyebrow}
    <p class="text-xs font-semibold uppercase tracking-[0.2em] text-neural-cyan">{eyebrow}</p>
  {/if}
  <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
    <div class="space-y-1">
      <h1 class="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">{title}</h1>
      {#if subtitle}
        <p class="max-w-2xl text-sm text-muted-foreground sm:text-base">{subtitle}</p>
      {/if}
    </div>
    {#if $$slots.actions}
      <div class="flex shrink-0 flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    {/if}
  </div>
  {#if $$slots.meta}
    <div class="flex flex-wrap items-center gap-2 pt-1">
      <slot name="meta" />
    </div>
  {/if}
</header>
