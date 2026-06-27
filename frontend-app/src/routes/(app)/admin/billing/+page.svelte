<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, EmptyState, LoadingSkeleton, ErrorState, Button, Alert } from '$lib/components';
  import { CreditCard } from 'lucide-svelte';
  import { AdminService, type AdminSubscriptionRow } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let rows: AdminSubscriptionRow[] = [];
  let total = 0;
  let statusFilter = '';
  let planFilter = '';

  // Доступные коды тарифов для ручной смены (совпадает с backend ALLOWED_PLAN_CODES).
  const planOptions = [
    { value: 'trial', label: 'Trial' },
    { value: 'pro', label: 'PRO' },
    { value: 'business', label: 'BUSINESS' },
    { value: 'agency', label: 'AGENCY' },
    { value: 'enterprise', label: 'ENTERPRISE' },
    { value: 'manual', label: 'Manual' }
  ];

  // Модалка действий
  let modalSub: AdminSubscriptionRow | null = null;
  let modalMode: 'change' | 'extend' | 'cancel' = 'change';
  let formReason = '';
  let formPlan = 'pro';
  let formPeriodEnd = '';
  let formTrialEnd = '';
  let formDays = 30;
  let actionLoading = false;
  let actionError = '';
  let feedback: { variant: 'success' | 'error'; message: string } | null = null;

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

  function openModal(sub: AdminSubscriptionRow, mode: 'change' | 'extend' | 'cancel') {
    modalSub = sub;
    modalMode = mode;
    formReason = '';
    formPlan = sub.plan || 'pro';
    formPeriodEnd = '';
    formTrialEnd = '';
    formDays = 30;
    actionError = '';
  }

  function closeModal() {
    modalSub = null;
    actionLoading = false;
    actionError = '';
  }

  function isoOrUndefined(value: string): string | undefined {
    if (!value) return undefined;
    // input type=date → 'YYYY-MM-DD'; backend принимает ISO datetime.
    return new Date(value).toISOString();
  }

  async function confirmAction() {
    if (!modalSub) return;
    actionLoading = true;
    actionError = '';
    try {
      if (modalMode === 'change') {
        await AdminService.changePlan(modalSub.user_id, {
          tariff_code: formPlan,
          reason: formReason.trim(),
          period_end: isoOrUndefined(formPeriodEnd),
          trial_end: isoOrUndefined(formTrialEnd)
        });
        feedback = { variant: 'success', message: `Тариф для ${modalSub.user_email} изменён вручную на ${formPlan}` };
      } else if (modalMode === 'extend') {
        await AdminService.extendSubscription(modalSub.user_id, {
          days: formDays,
          reason: formReason.trim()
        });
        feedback = { variant: 'success', message: `Подписка ${modalSub.user_email} продлена на ${formDays} дн.` };
      } else {
        await AdminService.cancelSubscription(modalSub.user_id, formReason.trim());
        feedback = { variant: 'success', message: `Подписка ${modalSub.user_email} отменена вручную` };
      }
      closeModal();
      await load();
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'Не удалось выполнить действие';
    } finally {
      actionLoading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Центр управления"
    title="Подписки и платежи"
    subtitle="Контроль биллинга и ручное управление подписками (без реальных платежей)"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="Всего: {total}" dot={false} />
    </svelte:fragment>
  </PageHeader>

  {#if feedback}
    <Alert variant={feedback.variant} title={feedback.variant === 'success' ? 'Готово' : 'Ошибка'}>
      {feedback.message}
    </Alert>
  {/if}

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
      {#each planOptions as opt}
        <option value={opt.value}>{opt.label}</option>
      {/each}
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
              <th class="px-4 py-3 font-semibold">Источник</th>
              <th class="px-4 py-3 font-semibold text-right">Действия</th>
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
                <td class="px-4 py-3 text-muted-foreground">{sub.source ?? '—'}</td>
                <td class="px-4 py-3">
                  <div class="flex justify-end gap-1.5">
                    <Button variant="ghost" size="sm" on:click={() => openModal(sub, 'change')}>Тариф</Button>
                    <Button variant="ghost" size="sm" on:click={() => openModal(sub, 'extend')}>Продлить</Button>
                    <Button variant="ghost" size="sm" on:click={() => openModal(sub, 'cancel')}>Отменить</Button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </GlassCard>
  {/if}
</div>

{#if modalSub}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
    <GlassCard className="w-full max-w-md space-y-4">
      <h2 class="text-lg font-semibold text-foreground">
        {#if modalMode === 'change'}Ручная смена тарифа
        {:else if modalMode === 'extend'}Продлить подписку
        {:else}Отменить подписку{/if}
      </h2>
      <p class="text-sm text-muted-foreground">
        Пользователь: <span class="font-medium text-foreground">{modalSub.user_email}</span>
      </p>

      <Alert variant="warning" title="Это ручное изменение">
        Платёж не проводится (YooKassa не вызывается). Изменение помечается как manual/admin override и записывается в журнал.
      </Alert>

      {#if modalMode === 'change'}
        <label class="block space-y-1">
          <span class="text-xs font-medium text-muted-foreground">Новый тариф</span>
          <select bind:value={formPlan} class="w-full rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40">
            {#each planOptions as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
        </label>
        <label class="block space-y-1">
          <span class="text-xs font-medium text-muted-foreground">Окончание периода (необязательно)</span>
          <input type="date" bind:value={formPeriodEnd} class="w-full rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" />
        </label>
        <label class="block space-y-1">
          <span class="text-xs font-medium text-muted-foreground">Окончание триала (переведёт в trial, необязательно)</span>
          <input type="date" bind:value={formTrialEnd} class="w-full rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" />
        </label>
      {:else if modalMode === 'extend'}
        <label class="block space-y-1">
          <span class="text-xs font-medium text-muted-foreground">Продлить на (дней, 1..365)</span>
          <input type="number" min="1" max="365" bind:value={formDays} class="w-full rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" />
        </label>
      {/if}

      <label class="block space-y-1">
        <span class="text-xs font-medium text-muted-foreground">Причина (необязательно)</span>
        <input type="text" bind:value={formReason} maxlength="500" placeholder="Например: компенсация, договорённость…" class="w-full rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" />
      </label>

      {#if actionError}
        <Alert variant="error" title="Ошибка">{actionError}</Alert>
      {/if}

      <div class="flex justify-end gap-2">
        <Button variant="ghost" on:click={closeModal} disabled={actionLoading}>Отмена</Button>
        <Button
          variant={modalMode === 'cancel' ? 'danger' : 'neural'}
          on:click={confirmAction}
          disabled={actionLoading}
        >
          {#if actionLoading}Выполняется…
          {:else if modalMode === 'change'}Сменить тариф
          {:else if modalMode === 'extend'}Продлить
          {:else}Отменить подписку{/if}
        </Button>
      </div>
    </GlassCard>
  </div>
{/if}
