<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, EmptyState, LoadingSkeleton, ErrorState, Button } from '$lib/components';
  import { Users, Search } from 'lucide-svelte';
  import { AdminService, type AdminUserRow } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let rows: AdminUserRow[] = [];
  let total = 0;
  let search = '';

  function statusVariant(status: string): 'success' | 'warning' | 'neutral' {
    if (status === 'active') return 'success';
    if (status === 'trial') return 'warning';
    return 'neutral';
  }

  function statusLabel(status: string): string {
    const map: Record<string, string> = {
      active: 'Активна',
      trial: 'Trial',
      none: 'Нет подписки',
      expired: 'Истекла',
      cancelled: 'Отменена',
      blocked: 'Заблокирована'
    };
    return map[status] ?? status;
  }

  function formatDate(value: string | null): string {
    if (!value) return '—';
    return new Date(value).toLocaleDateString('ru-RU');
  }

  async function load() {
    loading = true;
    error = '';
    try {
      const data = await AdminService.users({ search: search.trim(), limit: 100 });
      rows = data.items;
      total = data.total;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Ошибка загрузки пользователей';
    } finally {
      loading = false;
    }
  }

  function onSearchSubmit(event: Event) {
    event.preventDefault();
    void load();
  }

  onMount(load);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Центр управления"
    title="Пользователи"
    subtitle="Аккаунты селлеров: роли, подписки, лимиты и доступы"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="Всего: {total}" dot={false} />
    </svelte:fragment>
  </PageHeader>

  <form on:submit={onSearchSubmit} class="flex items-center gap-2" role="search">
    <div class="flex flex-1 items-center gap-2 rounded-xl border border-border/80 bg-background/40 px-3 py-2 focus-within:border-neural-cyan/40">
      <Search class="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <input
        type="search"
        bind:value={search}
        placeholder="Поиск по email, имени или ID…"
        class="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
        aria-label="Поиск пользователей"
      />
    </div>
    <Button type="submit">Найти</Button>
  </form>

  {#if loading}
    <LoadingSkeleton variant="card" />
    <LoadingSkeleton lines={6} />
  {:else if error}
    <ErrorState title="Не удалось загрузить пользователей" description={error} on:click={load} />
  {:else if rows.length === 0}
    <EmptyState icon={Users} title="Пользователи не найдены" description="Измените поисковый запрос или сбросьте фильтр." />
  {:else}
    <GlassCard padding="none">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="border-b border-border/60 text-left text-muted-foreground">
            <tr>
              <th class="px-4 py-3 font-semibold">Email</th>
              <th class="px-4 py-3 font-semibold">Имя</th>
              <th class="px-4 py-3 font-semibold">Тариф</th>
              <th class="px-4 py-3 font-semibold">Подписка</th>
              <th class="px-4 py-3 font-semibold">Товары</th>
              <th class="px-4 py-3 font-semibold">Ключи</th>
              <th class="px-4 py-3 font-semibold">Создан</th>
              <th class="px-4 py-3 font-semibold">Роль</th>
            </tr>
          </thead>
          <tbody>
            {#each rows as user}
              <tr class="border-b border-border/40 last:border-0">
                <td class="px-4 py-3 text-foreground">{user.email}</td>
                <td class="px-4 py-3 text-muted-foreground">{user.full_name ?? '—'}</td>
                <td class="px-4 py-3 text-muted-foreground">{user.current_tariff ?? '—'}</td>
                <td class="px-4 py-3">
                  <StatusBadge variant={statusVariant(user.subscription_status)} label={statusLabel(user.subscription_status)} dot={false} />
                </td>
                <td class="px-4 py-3 text-muted-foreground">{user.products_count}</td>
                <td class="px-4 py-3 text-muted-foreground">{user.marketplace_keys_count}</td>
                <td class="px-4 py-3 text-muted-foreground">{formatDate(user.created_at)}</td>
                <td class="px-4 py-3">
                  {#if user.is_superuser}
                    <StatusBadge variant="ai" label="Админ" dot={false} />
                  {:else if !user.is_active}
                    <StatusBadge variant="error" label="Неактивен" dot={false} />
                  {:else}
                    <StatusBadge variant="neutral" label="Селлер" dot={false} />
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </GlassCard>
  {/if}
</div>
