<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, Alert, EmptyState, LoadingSkeleton, ErrorState } from '$lib/components';
  import { ScrollText } from 'lucide-svelte';
  import { AdminService, type AdminAuditResponse } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminAuditResponse | null = null;

  const futureEvents = [
    'Изменения тарифов администратором',
    'Блокировка / разблокировка пользователей',
    'Ручные корректировки подписок',
    'Изменения настроек AI',
    'Изменения ключей маркетплейсов',
    'Webhook-события платежей',
    'События безопасности'
  ];

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.audit({ limit: 50 });
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки журнала';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Безопасность"
    title="Журнал действий"
    subtitle="Аудит административных операций и важных событий платформы"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant={data?.available ? 'success' : 'info'} label={data?.available ? 'Журнал активен' : 'Журнал не создан'} />
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={5} />
  {:else if error}
    <ErrorState title="Не удалось загрузить журнал" description={error} on:click={load} />
  {:else if data}
    {#if !data.available}
      <Alert variant="info" title="Журнал действий ещё не создан">
        {data.note}
      </Alert>

      <GlassCard>
        <h2 class="mb-3 text-lg font-semibold text-foreground">Какие события будут фиксироваться</h2>
        <ul class="space-y-2 text-sm text-muted-foreground">
          {#each futureEvents as event}
            <li>• {event}</li>
          {/each}
        </ul>
      </GlassCard>

      <EmptyState
        icon={ScrollText}
        title="Записей журнала нет"
        description="После создания хранилища audit log здесь появится лента административных действий с фильтрами."
      />
    {/if}
  {/if}
</div>
