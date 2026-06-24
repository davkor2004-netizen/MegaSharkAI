<script lang="ts">
  import { AlertTriangle, RefreshCw } from 'lucide-svelte';
  import GlassCard from './GlassCard.svelte';
  import { cn } from '$lib/utils/cn';

  /** Состояние ошибки с кнопкой повтора. */
  export let title = 'Что-то пошло не так';
  export let description = 'Не удалось загрузить данные. Попробуйте ещё раз.';
  export let className = '';
</script>

<GlassCard
  className={cn('border-destructive/25', className)}
  padding="lg"
  role="alert"
>
  <div class="mx-auto flex max-w-md flex-col items-center gap-4 text-center">
    <div
      class="flex h-14 w-14 items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10 text-destructive"
      aria-hidden="true"
    >
      <AlertTriangle class="h-7 w-7" />
    </div>
    <div class="space-y-2">
      <h3 class="text-lg font-semibold text-foreground">{title}</h3>
      <p class="text-sm text-muted-foreground">{description}</p>
    </div>
    {#if $$slots.action}
      <slot name="action" />
    {:else}
      <button type="button" class="btn-ghost-neural" on:click>
        <RefreshCw class="h-4 w-4" aria-hidden="true" />
        Повторить
      </button>
    {/if}
  </div>
</GlassCard>
