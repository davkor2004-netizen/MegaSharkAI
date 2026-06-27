<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, Alert, LoadingSkeleton, ErrorState } from '$lib/components';
  import { AdminService, type AdminAiStatus } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let data: AdminAiStatus | null = null;

  const providerNames: Record<string, string> = {
    yandex: 'YandexGPT',
    openai: 'OpenAI',
    deepseek: 'DeepSeek'
  };

  async function load() {
    loading = true;
    error = '';
    try {
      data = await AdminService.aiStatus();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки статуса AI';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Мониторинг"
    title="AI-провайдеры"
    subtitle="Состояние интеграций AI. Ключи отображаются только в маскированном виде"
  >
    <svelte:fragment slot="meta">
      {#if data}
        <StatusBadge variant="ai" label="Активный: {data.active_provider}" dot={false} />
      {/if}
    </svelte:fragment>
  </PageHeader>

  <Alert variant="warning" title="Секреты не раскрываются">
    API-ключи провайдеров никогда не отображаются целиком — только маскированный вид.
  </Alert>

  {#if loading}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {#each Array(3) as _}
        <LoadingSkeleton variant="card" />
      {/each}
    </div>
  {:else if error}
    <ErrorState title="Не удалось загрузить статус AI" description={error} on:click={load} />
  {:else if data}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {#each Object.entries(data.providers) as [key, provider]}
        <GlassCard hoverable className="space-y-3">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-base font-bold text-foreground">{providerNames[key] ?? key}</h3>
            <StatusBadge
              variant={provider.configured ? 'success' : 'neutral'}
              label={provider.configured ? 'Настроен' : 'Не настроен'}
              dot={false}
            />
          </div>
          <div class="flex items-center justify-between gap-2 text-sm">
            <span class="text-muted-foreground">Ключ</span>
            <span class="font-mono text-xs text-foreground">{provider.key_masked ?? '—'}</span>
          </div>
          {#if data.active_provider === key}
            <StatusBadge variant="ai" label="Активный провайдер" dot={false} />
          {/if}
        </GlassCard>
      {/each}
    </div>

    {#if data.usage_counters === null}
      <Alert variant="info" title="Использование и проверка соединения — следующий спринт">
        Счётчики использования/стоимости, безопасная проверка соединения и журнал ошибок провайдеров
        будут подключены позже. Логику AI-провайдеров это не затрагивает.
      </Alert>
    {/if}
  {/if}
</div>
