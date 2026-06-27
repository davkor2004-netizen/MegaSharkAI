<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, MetricCard, PageHeader, StatusBadge, Alert, LoadingSkeleton, ErrorState } from '$lib/components';
  import {
    Users,
    CreditCard,
    Clock,
    Wallet,
    Activity,
    Database,
    Server,
    ListChecks
  } from 'lucide-svelte';
  import { AdminService, type AdminOverview } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminOverview | null = null;

  function healthVariant(status: string): 'success' | 'error' | 'warning' {
    if (status === 'ok') return 'success';
    if (status === 'unknown') return 'warning';
    return 'error';
  }

  function healthLabel(status: string): string {
    if (status === 'ok') return 'Работает';
    if (status === 'unknown') return 'Неизвестно';
    return 'Недоступно';
  }

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.overview();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки обзора';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Центр управления"
    title="Обзор"
    subtitle="Сводка по платформе MegaSharkAI: пользователи, подписки и состояние сервисов"
  >
    <svelte:fragment slot="meta">
      {#if data}
        <StatusBadge variant="success" label="Данные подключены" />
      {:else}
        <StatusBadge variant="info" label="Загрузка…" />
      {/if}
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {#each Array(8) as _}
        <LoadingSkeleton variant="metric" />
      {/each}
    </div>
  {:else if error}
    <ErrorState title="Не удалось загрузить обзор" description={error} on:click={load} />
  {:else if data}
    <section class="space-y-3">
      <h2 class="text-sm font-semibold uppercase tracking-[0.16em] text-muted-foreground">Бизнес-метрики</h2>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard title="Пользователи" value={data.users_total} subtitle="Всего зарегистрировано" icon={Users} />
        <MetricCard title="Новые за 24ч" value={data.new_users_24h} subtitle="+ за 7д: {data.new_users_7d} · 30д: {data.new_users_30d}" icon={Clock} />
        <MetricCard title="Активные подписки" value={data.active_subscriptions} subtitle="Платных: {data.paid_users} · Trial: {data.active_trials}" icon={CreditCard} />
        <MetricCard title="MRR (≈)" value="{data.approximate_mrr.toLocaleString('ru-RU')} ₽" subtitle="По активным платным подпискам" icon={Wallet} />
      </div>
    </section>

    <section class="space-y-3">
      <h2 class="text-sm font-semibold uppercase tracking-[0.16em] text-muted-foreground">Состояние сервисов</h2>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <GlassCard className="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <Activity class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            <span class="text-sm font-semibold text-foreground">API</span>
          </div>
          <StatusBadge variant={healthVariant(data.backend_status)} label={healthLabel(data.backend_status)} />
        </GlassCard>
        <GlassCard className="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <Database class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            <span class="text-sm font-semibold text-foreground">База данных</span>
          </div>
          <StatusBadge variant={healthVariant(data.db_status)} label={healthLabel(data.db_status)} />
        </GlassCard>
        <GlassCard className="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <Server class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            <span class="text-sm font-semibold text-foreground">Redis</span>
          </div>
          <StatusBadge variant={healthVariant(data.redis_status)} label={healthLabel(data.redis_status)} />
        </GlassCard>
        <GlassCard className="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <ListChecks class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            <span class="text-sm font-semibold text-foreground">Celery</span>
          </div>
          <StatusBadge variant={healthVariant(data.celery_status)} label={healthLabel(data.celery_status)} />
        </GlassCard>
      </div>
    </section>

    {#if data.parser_summary === null || data.ai_summary === null}
      <Alert variant="info" title="Часть метрик ещё не подключена">
        Сводка по парсеру и AI пока не собирается централизованно — появится в следующем спринте.
        Бизнес-метрики и состояние сервисов выше — реальные данные из backend.
      </Alert>
    {/if}
  {/if}
</div>
