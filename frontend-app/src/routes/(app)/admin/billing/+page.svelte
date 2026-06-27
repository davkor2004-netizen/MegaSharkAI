<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, EmptyState, LoadingSkeleton, ErrorState } from '$lib/components';
  import { CreditCard } from 'lucide-svelte';
  import { AdminService, type AdminSubscriptionRow } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let rows: AdminSubscriptionRow[] = [];
  let total = 0;
  let statusFilter = '';
  let planFilter = '';

  function statusVariant(status: string): 'success' | 'warning' | 'neutral' | 'error' {
    if (status === 'active') return 'success';
    if (status === 'trial') return 'warning';
    if (status === 'blocked' || status === 'expired') return 'error';
    return 'neutral';
  }

  function formatDate(value: string | null): string {
    if (!value) return '—';
    return new Date(value).toLocaleDateString('ru-RU');
  }

  function formatPrice(value: number | null): string {
    if (value == null) return '—';
    return `${value.toLocaleString('ru-RU')} ₽`;
  }

  async function load() {
    loading = true;
    error = '';
    try {
      const data = await AdminService.subscriptions({
        status: statusFilter,
        plan: planFilter,
        limit: 100
      });
      rows = data.items;
      total = data.total;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки подписок';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Центр управления"
    title="Подписки и платежи"
    subtitle="Контроль биллинга: подписки, статусы и тарифы (только чтение)"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="Всего: {total}" dot={false} />
    </svelte:fragment>
  </PageHeader>

  <div class="flex flex-wrap items-center gap-2">
    <select
      bind:value={statusFilter}
      on:change={load}
      class="rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40"
      aria-label="Фильтр по статусу"
    >
      <option value="">Все статусы</option>
      <option value="active">Активные</option>
      <option value="trial">Trial</option>
      <option value="expired">Истёкшие</option>
      <option value="cancelled">Отменённые</option>
      <option value="blocked">Заблокированные</option>
    </select>
    <select
      bind:value={planFilter}
      on:change={load}
      class="rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40"
      aria-label="Фильтр по тарифу"
    >
      <option value="">Все тарифы</option>
      <option value="pro">PRO</option>
      <option value="business">BUSINESS</option>
    </select>
  </div>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={5} />
  {:else if error}
    <ErrorState title="Не удалось загрузить подписки" description={error} on:click={load} />
  {:else if rows.length === 0}
    <EmptyState icon={CreditCard} title="Подписок нет" description="С выбранными фильтрами подписок не найдено." />
  {:else}
    <GlassCard padding="none">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border/60 text-left text-muted-foreground">
            <tr>
              <th class="px-4 py-3 font-semibold">Пользователь</th>
              <th class="px-4 py-3 font-semibold">Тариф</th>
              <th class="px-4 py-3 font-semibold">Статус</th>
              <th class="px-4 py-3 font-semibold">Начало</th>
              <th class="px-4 py-3 font-semibold">Окончание</th>
              <th class="px-4 py-3 font-semibold">Цена</th>
              <th class="px-4 py-3 font-semibold">Цикл</th>
              <th class="px-4 py-3 font-semibold">Источник</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as sub}
              <tr class="border-b border-border/40 last:border-0">
                <td class="px-4 py-3 text-foreground">{sub.user_email}</td>
                <td class="px-4 py-3 text-muted-foreground">{sub.plan_name}</td>
                <td class="px-4 py-3">
                  <StatusBadge variant={statusVariant(sub.status)} label={sub.status} dot={false} />
                </td>
                <td class="px-4 py-3 text-muted-foreground">{formatDate(sub.started_at)}</td>
                <td class="px-4 py-3 text-muted-foreground">{formatDate(sub.is_trial ? sub.trial_ends_at : sub.current_period_end)}</td>
                <td class="px-4 py-3 text-muted-foreground">{formatPrice(sub.price)}</td>
                <td class="px-4 py-3 text-muted-foreground">{sub.billing_cycle ?? '—'}</td>
                <td class="px-4 py-3 text-muted-foreground">{sub.source ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </GlassCard>
  {/if}
</div>
