<script lang="ts">
  import type { ComponentType } from 'svelte';
  import { Inbox } from 'lucide-svelte';
  import GlassCard from './GlassCard.svelte';
  import { cn } from '$lib/utils/cn';

  /** Пустое состояние с иконкой и опциональным действием. */
  export let title = 'Нет данных';
  export let description = 'Здесь пока ничего нет. Добавьте первую запись или измените фильтры.';
  export let icon: ComponentType = Inbox;
  export let className = '';
</script>

<GlassCard className={cn('text-center', className)} padding="lg">
  <div class="mx-auto flex max-w-sm flex-col items-center gap-4">
    <div
      class="flex h-14 w-14 items-center justify-center rounded-2xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan"
      aria-hidden="true"
    >
      <svelte:component this={icon} class="h-7 w-7" />
    </div>
    <div class="space-y-2">
      <h3 class="text-lg font-semibold text-foreground">{title}</h3>
      <p class="text-sm text-muted-foreground">{description}</p>
    </div>
    {#if $$slots.action}
      <div class="pt-2">
        <slot name="action" />
      </div>
    {/if}
  </div>
</GlassCard>
