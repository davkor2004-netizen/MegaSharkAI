<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, Alert, LoadingSkeleton, ErrorState } from '$lib/components';
  import { AdminService, type AdminParserStatus } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminParserStatus | null = null;

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.parserStatus();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки статуса парсера';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Мониторинг"
    title="Мониторинг парсера"
    subtitle="Конфигурация парсинга маркетплейсов и пула прокси (read-only)"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="Статус из backend" />
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={4} />
  {:else if error}
    <ErrorState title="Не удалось загрузить статус" description={error} on:click={load} />
  {:else if data}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <GlassCard className="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="text-sm font-semibold text-foreground">Debug-дампы</p>
          <p class="truncate text-xs text-muted-foreground">{data.parser_debug_dir ?? 'каталог не задан'}</p>
        </div>
        <StatusBadge
          variant={data.parser_debug_dumps_enabled ? 'warning' : 'success'}
          label={data.parser_debug_dumps_enabled ? 'Включены' : 'Выключены'}
        />
      </GlassCard>
      <GlassCard className="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="text-sm font-semibold text-foreground">Пул прокси</p>
          <p class="text-xs text-muted-foreground">
            Всего: {data.proxy_pool.total} · доступно: {data.proxy_pool.available} · заблок.: {data.proxy_pool.blocked}
          </p>
        </div>
        <StatusBadge
          variant={data.proxy_pool.enabled ? 'success' : 'neutral'}
          label={data.proxy_pool.enabled ? 'Активен' : 'Не настроен'}
        />
      </GlassCard>
    </div>

    <GlassCard className="space-y-2">
      <h2 class="text-sm font-semibold uppercase tracking-[0.16em] text-muted-foreground">Поддерживаемые маркетплейсы</h2>
      <div class="flex flex-wrap gap-1.5">
        {#each data.supported_marketplaces as mp}
          <StatusBadge variant="info" label={mp} dot={false} />
        {/each}
      </div>
    </GlassCard>

    {#if data.recent_stats === null}
      <Alert variant="info" title="Статистика парсинга ещё не собирается">
        Счётчики успех/частично/ошибка, коды 403/429/captcha/timeout и использование прокси по запросам
        появятся после подключения сбора метрик парсинга. Логику парсера это не затрагивает.
      </Alert>
    {/if}
  {/if}
</div>
