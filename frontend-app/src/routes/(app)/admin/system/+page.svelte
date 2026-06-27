<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, Alert, LoadingSkeleton, ErrorState } from '$lib/components';
  import { AdminService, type AdminSystemStatus } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminSystemStatus | null = null;

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

  function formatUptime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h} ч ${m} мин`;
    return `${m} мин`;
  }

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.systemStatus();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки статуса';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Мониторинг"
    title="Система"
    subtitle="Состояние инфраструктуры: окружение, сервисы, миграции и health"
  >
    <svelte:fragment slot="meta">
      {#if data}
        <StatusBadge variant={data.is_production ? 'success' : 'warning'} label={data.environment} />
      {/if}
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={6} />
  {:else if error}
    <ErrorState title="Не удалось загрузить статус" description={error} on:click={load} />
  {:else if data}
    {#if data.warnings.length > 0}
      <Alert variant="warning" title="Предупреждения конфигурации">
        <ul class="space-y-1">
          {#each data.warnings as warning}
            <li>• {warning}</li>
          {/each}
        </ul>
      </Alert>
    {:else}
      <Alert variant="success" title="Опасных конфигураций не обнаружено">
        Все ключевые параметры в норме.
      </Alert>
    {/if}

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <GlassCard className="flex items-center justify-between gap-3">
        <span class="text-sm font-semibold text-foreground">Backend (API)</span>
        <StatusBadge variant="success" label="Работает" />
      </GlassCard>
      <GlassCard className="flex items-center justify-between gap-3">
        <span class="text-sm font-semibold text-foreground">База данных</span>
        <StatusBadge variant={healthVariant(data.db_status)} label={healthLabel(data.db_status)} />
      </GlassCard>
      <GlassCard className="flex items-center justify-between gap-3">
        <span class="text-sm font-semibold text-foreground">Redis</span>
        <StatusBadge variant={healthVariant(data.redis_status)} label={healthLabel(data.redis_status)} />
      </GlassCard>
      <GlassCard className="flex items-center justify-between gap-3">
        <span class="text-sm font-semibold text-foreground">Celery worker</span>
        <StatusBadge variant={healthVariant(data.celery_status)} label={healthLabel(data.celery_status)} />
      </GlassCard>
    </div>

    <GlassCard className="space-y-2">
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-[0.16em] text-muted-foreground">Параметры</h2>
      <dl class="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Окружение</dt><dd class="text-foreground">{data.environment}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">DEBUG</dt><dd class="text-foreground">{data.debug ? 'true' : 'false'}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Production</dt><dd class="text-foreground">{data.is_production ? 'да' : 'нет'}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Версия</dt><dd class="text-foreground">{data.version}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Uptime</dt><dd class="text-foreground">{formatUptime(data.uptime_seconds)}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Debug-дампы парсера</dt><dd class="text-foreground">{data.parser_debug_dumps_enabled ? 'вкл' : 'выкл'}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Alembic current</dt><dd class="font-mono text-xs text-foreground">{data.alembic_current ?? '—'}</dd></div>
        <div class="flex justify-between gap-2"><dt class="text-muted-foreground">Alembic head</dt><dd class="font-mono text-xs text-foreground">{data.alembic_head ?? '—'}</dd></div>
      </dl>
    </GlassCard>
  {/if}
</div>
