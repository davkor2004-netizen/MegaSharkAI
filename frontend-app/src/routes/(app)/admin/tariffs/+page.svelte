<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, LoadingSkeleton, ErrorState } from '$lib/components';
  import { AdminService, type AdminTariff } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let tariffs: AdminTariff[] = [];

  const flagLabels: Record<string, string> = {
    widget_access: 'Виджет',
    auto_repricing_access: 'Авторепрайсинг',
    white_label_reports_access: 'White-label отчёты',
    team_access: 'Командный доступ',
    agency_projects_access: 'Проекты агентства',
    priority_queue_access: 'Приоритетная очередь'
  };

  const limitLabels: Record<string, string> = {
    max_products: 'Товары',
    max_repricing_products: 'Репрайсинг',
    ai_generations_per_month: 'AI-генерации/мес',
    competitor_reports: 'Отчёты',
    max_users: 'Пользователи',
    price_update_frequency: 'Обновл./сутки'
  };

  function priceLabel(t: AdminTariff): string {
    if (t.price == null) return 'Индивидуально';
    if (t.price === 0) return '0 ₽';
    return `${t.price.toLocaleString('ru-RU')} ₽`;
  }

  function limitValue(value: number): string {
    return value === -1 ? '∞' : String(value);
  }

  async function load() {
    loading = true;
    error = '';
    try {
      const data = await AdminService.tariffs();
      tariffs = data.items;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки тарифов';
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Центр управления"
    title="Тарифы и лимиты"
    subtitle="Финальная тарифная сетка, лимиты и feature-флаги (read-only)"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="Данные из backend" />
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {#each Array(5) as _}
        <LoadingSkeleton variant="card" />
      {/each}
    </div>
  {:else if error}
    <ErrorState title="Не удалось загрузить тарифы" description={error} on:click={load} />
  {:else}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {#each tariffs as tariff}
        <GlassCard hoverable className="space-y-4">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-lg font-bold text-foreground">{tariff.name}</h3>
            <StatusBadge variant={tariff.billing_period === 'индивидуально' ? 'warning' : 'info'} label={tariff.billing_period} dot={false} />
          </div>
          <p class="text-2xl font-bold text-gradient">{priceLabel(tariff)}</p>

          {#if !tariff.is_public}
            <StatusBadge variant="ai" label="Только вручную" dot={false} />
          {/if}

          <div class="space-y-1 border-t border-border/50 pt-3">
            <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Лимиты</p>
            <div class="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
              {#each Object.entries(tariff.limits) as [key, value]}
                <div class="flex justify-between gap-2">
                  <span>{limitLabels[key] ?? key}</span>
                  <span class="font-mono text-foreground">{limitValue(value)}</span>
                </div>
              {/each}
            </div>
          </div>

          <div class="space-y-1 border-t border-border/50 pt-3">
            <p class="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Функции</p>
            <div class="flex flex-wrap gap-1.5">
              {#each Object.entries(tariff.feature_flags) as [flag, enabled]}
                <StatusBadge
                  variant={enabled ? 'success' : 'neutral'}
                  label={flagLabels[flag] ?? flag}
                  dot={false}
                />
              {/each}
            </div>
          </div>
        </GlassCard>
      {/each}
    </div>
  {/if}
</div>
