<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, EmptyState, LoadingSkeleton, ErrorState, Button } from '$lib/components';
  import { ScrollText, Search } from 'lucide-svelte';
  import { AdminService, type AdminAuditResponse, type AdminAuditRow } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminAuditResponse | null = null;

  // Фильтры
  let action = '';
  let entityType = '';
  let search = ''; // поиск по actor/target (email или ID)

  // Известные действия для подсказки в селекте (не ограничивает, можно очистить).
  const knownActions = ['auth.login', 'auth.logout'];
  const knownEntities = ['user'];

  function actionVariant(value: string): 'info' | 'warning' | 'error' | 'neutral' | 'success' {
    if (value.includes('logout')) return 'neutral';
    if (value.includes('login')) return 'success';
    if (value.includes('delete') || value.includes('block')) return 'error';
    if (value.includes('update') || value.includes('change')) return 'warning';
    return 'info';
  }

  function formatDateTime(value: string | null): string {
    if (!value) return '—';
    return new Date(value).toLocaleString('ru-RU');
  }

  function userLabel(user: AdminAuditRow['actor']): string {
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

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.audit({
        limit: 100,
        action: action.trim() || undefined,
        entity_type: entityType.trim() || undefined,
        actor: search.trim() || undefined
      });
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки журнала';
    } finally {
      loading = false;
    }
  }

  function onFilterSubmit(event: Event) {
    event.preventDefault();
    void load();
  }

  function resetFilters() {
    action = '';
    entityType = '';
    search = '';
    void load();
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Безопасность"
    title="Журнал действий"
    subtitle="Аудит административных операций и важных событий платформы"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant={data?.available ? 'success' : 'info'} label={data?.available ? `Записей: ${data?.total ?? 0}` : 'Журнал недоступен'} dot={false} />
    </svelte:fragment>
  </PageHeader>

  <form on:submit={onFilterSubmit} class="flex flex-wrap items-center gap-2" role="search">
    <div class="flex flex-1 min-w-[220px] items-center gap-2 rounded-xl border border-border/80 bg-background/40 px-3 py-2 focus-within:border-neural-cyan/40">
      <Search class="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <input
        type="search"
        bind:value={search}
        placeholder="Инициатор: email или ID…"
        class="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
        aria-label="Поиск по инициатору"
      />
    </div>
    <select bind:value={action} class="rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" aria-label="Фильтр по действию">
      <option value="">Все действия</option>
      {#each knownActions as a}
        <option value={a}>{a}</option>
      {/each}
    </select>
    <select bind:value={entityType} class="rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40" aria-label="Фильтр по типу сущности">
      <option value="">Все сущности</option>
      {#each knownEntities as e}
        <option value={e}>{e}</option>
      {/each}
    </select>
    <Button type="submit">Применить</Button>
    <Button type="button" variant="ghost" on:click={resetFilters}>Сбросить</Button>
  </form>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={6} />
  {:else if error}
    <ErrorState title="Не удалось загрузить журнал" description={error} on:click={load} />
  {:else if data && !data.available}
    <EmptyState
      icon={ScrollText}
      title="Журнал недоступен"
      description={data.note ?? 'Хранилище журнала действий недоступно.'}
    />
  {:else if data && data.items.length === 0}
    <EmptyState
      icon={ScrollText}
      title="Записей журнала нет"
      description="С выбранными фильтрами действий не найдено. Измените фильтры или совершите действие в системе."
    />
  {:else if data}
    <GlassCard padding="none">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border/60 text-left text-muted-foreground">
            <tr>
              <th class="px-4 py-3 font-semibold">Время</th>
              <th class="px-4 py-3 font-semibold">Действие</th>
              <th class="px-4 py-3 font-semibold">Инициатор</th>
              <th class="px-4 py-3 font-semibold">Цель</th>
              <th class="px-4 py-3 font-semibold">Сущность</th>
              <th class="px-4 py-3 font-semibold">IP</th>
              <th class="px-4 py-3 font-semibold">Детали</th>
            </tr>
          </thead>
          <tbody>
            {#each data.items as row}
              <tr class="border-b border-border/40 last:border-0">
                <td class="px-4 py-3 whitespace-nowrap text-muted-foreground">{formatDateTime(row.created_at)}</td>
                <td class="px-4 py-3">
                  <StatusBadge variant={actionVariant(row.action)} label={row.action} dot={false} />
                </td>
                <td class="px-4 py-3 text-foreground">{userLabel(row.actor)}</td>
                <td class="px-4 py-3 text-muted-foreground">{userLabel(row.target)}</td>
                <td class="px-4 py-3 text-muted-foreground">
                  {row.entity_type ?? '—'}{#if row.entity_id}<span class="text-muted-foreground/60"> · {row.entity_id}</span>{/if}
                </td>
                <td class="px-4 py-3 text-muted-foreground">{row.ip ?? '—'}</td>
                <td class="px-4 py-3 max-w-[280px] truncate text-muted-foreground/80" title={metaPreview(row.metadata)}>{metaPreview(row.metadata)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </GlassCard>
  {/if}
</div>
