<script lang="ts">
  import { goto } from '$app/navigation';
  import { Lock, ArrowUpCircle } from 'lucide-svelte';
  import GlassCard from '$lib/components/GlassCard.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import type { LockDetail } from '$lib/utils/http';
  import { planLabel } from '$lib/utils/plans';

  /** Деталь блокировки (из ApiError.detail при 402). */
  export let detail: LockDetail | null = null;
  /** Заголовок карточки (можно переопределить под конкретную страницу). */
  export let title = 'Функция недоступна на вашем тарифе';
  /** Дополнительный текст под заголовком (необязательно). */
  export let description = '';

  $: isLimit = detail?.code === 'LIMIT_EXCEEDED';
  $: message = detail?.message ?? 'Эта возможность доступна на более высоком тарифе.';
  $: currentPlan = detail?.current_plan ? planLabel(detail.current_plan) : null;
  $: requiredPlan = detail?.required_plan ? planLabel(detail.required_plan) : null;
  $: resetAt = detail?.reset_at ? new Date(detail.reset_at) : null;

  function goToBilling() {
    goto('/billing');
  }
</script>

<GlassCard className="max-w-2xl mx-auto text-center" padding="lg" glow>
  <div class="flex flex-col items-center gap-4">
    <div class="flex h-14 w-14 items-center justify-center rounded-full bg-warning/10 text-warning">
      <Lock class="h-7 w-7" aria-hidden="true" />
    </div>

    <h2 class="text-xl font-semibold text-foreground">{title}</h2>

    {#if description}
      <p class="text-sm text-muted-foreground">{description}</p>
    {/if}

    <p class="text-sm text-muted-foreground">{message}</p>

    <div class="flex flex-wrap items-center justify-center gap-2">
      {#if currentPlan}
        <StatusBadge label={`Текущий тариф: ${currentPlan}`} variant="neutral" />
      {/if}
      {#if requiredPlan}
        <StatusBadge label={`Нужен тариф: ${requiredPlan}`} variant="info" />
      {/if}
    </div>

    {#if isLimit && detail}
      <p class="text-xs text-muted-foreground">
        Использовано {detail.used ?? 0} из {detail.limit ?? '∞'}
        {#if resetAt}
          · сброс {resetAt.toLocaleDateString('ru-RU')}
        {/if}
      </p>
    {/if}

    <Button variant="neural" on:click={goToBilling}>
      <ArrowUpCircle class="h-4 w-4" aria-hidden="true" />
      Улучшить тариф
    </Button>
  </div>
</GlassCard>
