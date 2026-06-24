<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /** Скелетон загрузки с shimmer-эффектом. */
  export let lines = 3;
  export let variant: 'text' | 'card' | 'avatar' | 'metric' = 'text';
  export let className = '';
</script>

{#if variant === 'card'}
  <div
    class={cn('glass-card animate-pulse rounded-xl p-6', className)}
    role="status"
    aria-label="Загрузка"
  >
    <div class="skeleton-shimmer mb-4 h-4 w-1/3 animate-shimmer rounded-md"></div>
    <div class="skeleton-shimmer mb-2 h-8 w-1/2 animate-shimmer rounded-md"></div>
    <div class="skeleton-shimmer h-3 w-2/3 animate-shimmer rounded-md"></div>
  </div>
{:else if variant === 'avatar'}
  <div class={cn('flex items-center gap-3', className)} role="status" aria-label="Загрузка">
    <div class="skeleton-shimmer h-10 w-10 animate-shimmer rounded-full"></div>
    <div class="flex-1 space-y-2">
      <div class="skeleton-shimmer h-3 w-24 animate-shimmer rounded-md"></div>
      <div class="skeleton-shimmer h-2 w-32 animate-shimmer rounded-md"></div>
    </div>
  </div>
{:else if variant === 'metric'}
  <div class={cn('glass-card rounded-xl p-6', className)} role="status" aria-label="Загрузка">
    <div class="skeleton-shimmer mb-3 h-3 w-20 animate-shimmer rounded-md"></div>
    <div class="skeleton-shimmer mb-2 h-9 w-28 animate-shimmer rounded-md"></div>
    <div class="skeleton-shimmer h-2 w-16 animate-shimmer rounded-md"></div>
  </div>
{:else}
  <div class={cn('space-y-2', className)} role="status" aria-label="Загрузка">
    {#each Array(lines) as _, i}
      <div
        class={cn(
          'skeleton-shimmer h-3 animate-shimmer rounded-md',
          i === lines - 1 ? 'w-2/3' : 'w-full'
        )}
      ></div>
    {/each}
  </div>
{/if}
