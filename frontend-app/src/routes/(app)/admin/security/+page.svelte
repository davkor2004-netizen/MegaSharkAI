<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, Alert, EmptyState, LoadingSkeleton, ErrorState } from '$lib/components';
  import { ShieldCheck } from 'lucide-svelte';
  import { AdminService, type AdminSecurityEvents } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminSecurityEvents | null = null;

  const futureSignals = [
    'Неуспешные входы (failed logins)',
    'Успешные входы',
    'События refresh / logout',
    'Тренды ответов 401 / 403',
    'Подозрительные IP-адреса',
    'Отзыв сессий (session revoke)',
    'Принудительный сброс пароля'
  ];

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.securityEvents();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки событий';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Безопасность"
    title="Безопасность"
    subtitle="Мониторинг входов, сессий и подозрительной активности"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant={data?.available ? 'success' : 'info'} label={data?.available ? 'Данные подключены' : 'Сбор не подключён'} />
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={5} />
  {:else if error}
    <ErrorState title="Не удалось загрузить события" description={error} on:click={load} />
  {:else if data}
    {#if !data.available}
      <Alert variant="info" title="Сбор событий безопасности ещё не подключён">
        {data.note}
      </Alert>

      <GlassCard>
        <h2 class="mb-3 text-lg font-semibold text-foreground">Какие сигналы появятся</h2>
        <ul class="space-y-2 text-sm text-muted-foreground">
          {#each futureSignals as signal}
            <li>• {signal}</li>
          {/each}
        </ul>
      </GlassCard>

      <EmptyState
        icon={ShieldCheck}
        title="Событий пока нет"
        description="После подключения централизованного сбора событий лента входов и подозрительной активности появится здесь."
      />
    {/if}
  {/if}
</div>
