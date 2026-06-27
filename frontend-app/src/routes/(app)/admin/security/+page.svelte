<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, MetricCard, PageHeader, StatusBadge, Alert, EmptyState, LoadingSkeleton, ErrorState, Button } from '$lib/components';
  import { ShieldCheck, ShieldAlert, ShieldX, Info, AlertTriangle } from 'lucide-svelte';
  import { AdminService, type AdminSecurityEvents, type AdminSecurityEventRow } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminSecurityEvents | null = null;

  // Фильтры
  let severity = '';
  let eventType = '';

  const knownEventTypes = [
    'login_success',
    'login_failed',
    'logout',
    'token_refresh',
    'token_refresh_failed'
  ];

  function severityVariant(value: string): 'info' | 'warning' | 'error' {
    if (value === 'critical' || value === 'high') return 'error';
    if (value === 'warning') return 'warning';
    return 'info';
  }

  function severityLabel(value: string): string {
    const map: Record<string, string> = {
      info: 'Инфо',
      warning: 'Предупреждение',
      high: 'Высокий',
      critical: 'Критический'
    };
    return map[value] ?? value;
  }

  function eventTypeLabel(value: string): string {
    const map: Record<string, string> = {
      login_success: 'Успешный вход',
      login_failed: 'Неудачный вход',
      logout: 'Выход',
      token_refresh: 'Обновление сессии',
      token_refresh_failed: 'Сбой обновления'
    };
    return map[value] ?? value;
  }

  function formatDateTime(value: string | null): string {
    if (!value) return '—';
    return new Date(value).toLocaleString('ru-RU');
  }

  function userLabel(user: AdminSecurityEventRow['user']): string {
    if (!user) return '—';
    return user.email ?? user.id;
  }

  function metaPreview(meta: Record<string, unknown> | null): string {
    if (!meta || Object.keys(meta).length === 0) return '—';
    try {
      return JSON.stringify(meta);
    } catch {
      return '—';
    }
  }

  $: hasCritical = data ? (data.summary.high + data.summary.critical) > 0 : false;

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.securityEvents({
        limit: 100,
        severity: severity.trim() || undefined,
        event_type: eventType.trim() || undefined
      });
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки событий';
    } finally {
      loading = false;
    }
  }

  function onFilterSubmit(event: Event) {
    event.preventDefault();
    void load();
  }

  function resetFilters() {
    severity = '';
    eventType = '';
    void load();
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Безопасность"
    title="Безопасность"
    subtitle="Мониторинг входов, сессий и подозрительной активности"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant={data?.available ? 'success' : 'info'} label={data?.available ? `Событий: ${data?.total ?? 0}` : 'Сбор недоступен'} dot={false} />
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {#each Array(4) as _}
        <LoadingSkeleton variant="metric" />
      {/each}
    </div>
    <LoadingSkeleton lines={6} />
  {:else if error}
    <ErrorState title="Не удалось загрузить события" description={error} on:click={load} />
  {:else if data && !data.available}
    <EmptyState
      icon={ShieldCheck}
      title="Сбор событий недоступен"
      description={data.note ?? 'Хранилище событий безопасности недоступно.'}
    />
  {:else if data}
    {#if hasCritical}
      <Alert variant="error" title="Есть события повышенной важности">
        Обнаружены события уровня high/critical: {data.summary.high + data.summary.critical}.
        Проверьте неудачные входы и подозрительную активность ниже.
      </Alert>
    {/if}

    <section class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard title="Инфо" value={data.summary.info} subtitle="Штатные события" icon={Info} />
      <MetricCard title="Предупреждения" value={data.summary.warning} subtitle="Неудачные входы и т.п." icon={AlertTriangle} />
      <MetricCard title="Высокий" value={data.summary.high} subtitle="Требуют внимания" icon={ShieldAlert} />
      <MetricCard title="Критический" value={data.summary.critical} subtitle="Срочная проверка" icon={ShieldX} />
    </section>

    <form on:submit={onFilterSubmit} class="flex flex-wrap items-center gap-2">
      <select bind:value={severity} class="rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" aria-label="Фильтр по важности">
        <option value="">Любая важность</option>
        <option value="info">Инфо</option>
        <option value="warning">Предупреждение</option>
        <option value="high">Высокий</option>
        <option value="critical">Критический</option>
      </select>
      <select bind:value={eventType} class="rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" aria-label="Фильтр по типу события">
        <option value="">Все типы</option>
        {#each knownEventTypes as t}
          <option value={t}>{eventTypeLabel(t)}</option>
        {/each}
      </select>
      <Button type="submit">Применить</Button>
      <Button type="button" variant="ghost" on:click={resetFilters}>Сбросить</Button>
    </form>

    {#if data.items.length === 0}
      <EmptyState
        icon={ShieldCheck}
        title="Событий нет"
        description="С выбранными фильтрами событий безопасности не найдено."
      />
    {:else}
      <GlassCard padding="none">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="border-b border-border/60 text-left text-muted-foreground">
              <tr>
                <th class="px-4 py-3 font-semibold">Время</th>
                <th class="px-4 py-3 font-semibold">Событие</th>
                <th class="px-4 py-3 font-semibold">Важность</th>
                <th class="px-4 py-3 font-semibold">Пользователь</th>
                <th class="px-4 py-3 font-semibold">IP</th>
                <th class="px-4 py-3 font-semibold">Код</th>
                <th class="px-4 py-3 font-semibold">Детали</th>
              </tr>
            </thead>
            <tbody>
              {#each data.items as row}
                <tr class="border-b border-border/40 last:border-0">
                  <td class="px-4 py-3 whitespace-nowrap text-muted-foreground">{formatDateTime(row.created_at)}</td>
                  <td class="px-4 py-3 text-foreground">{eventTypeLabel(row.event_type)}</td>
                  <td class="px-4 py-3">
                    <StatusBadge variant={severityVariant(row.severity)} label={severityLabel(row.severity)} dot={false} />
                  </td>
                  <td class="px-4 py-3 text-muted-foreground">{userLabel(row.user)}</td>
                  <td class="px-4 py-3 text-muted-foreground">{row.ip ?? '—'}</td>
                  <td class="px-4 py-3 text-muted-foreground">{row.status_code ?? '—'}</td>
                  <td class="px-4 py-3 max-w-[260px] truncate text-muted-foreground/80" title={metaPreview(row.metadata)}>{metaPreview(row.metadata)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </GlassCard>
    {/if}
  {/if}
</div>
