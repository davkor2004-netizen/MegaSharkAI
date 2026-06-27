<script lang="ts">
  import { onMount } from 'svelte';
  import { GlassCard, PageHeader, StatusBadge, EmptyState, LoadingSkeleton, ErrorState, Button, Alert } from '$lib/components';
  import { Users, Search, ShieldX, ShieldCheck } from 'lucide-svelte';
  import { AdminService, type AdminUserRow } from '$lib/services/admin';

  let loading = true;
  let error = '';
  let rows: AdminUserRow[] = [];
  let total = 0;
  let search = '';

  // Состояние действия (блокировка/разблокировка) через модалку.
  let modalUser: AdminUserRow | null = null;
  let modalAction: 'block' | 'unblock' = 'block';
  let modalReason = '';
  let actionLoading = false;
  let actionError = '';
  let feedback: { variant: 'success' | 'error'; message: string } | null = null;

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

  function openModal(user: AdminUserRow, action: 'block' | 'unblock') {
    modalUser = user;
    modalAction = action;
    modalReason = '';
    actionError = '';
  }

  function closeModal() {
    modalUser = null;
    actionLoading = false;
    actionError = '';
  }

  async function confirmAction() {
    if (!modalUser) return;
    actionLoading = true;
    actionError = '';
    try {
      if (modalAction === 'block') {
        await AdminService.blockUser(modalUser.id, modalReason.trim());
        feedback = { variant: 'success', message: `Пользователь ${modalUser.email} заблокирован` };
      } else {
        await AdminService.unblockUser(modalUser.id, modalReason.trim());
        feedback = { variant: 'success', message: `Пользователь ${modalUser.email} разблокирован` };
      }
      closeModal();
      await load();
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'Не удалось выполнить действие';
    } finally {
      actionLoading = false;
    }
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

  {#if feedback}
    <Alert variant={feedback.variant} title={feedback.variant === 'success' ? 'Готово' : 'Ошибка'}>
      {feedback.message}
    </Alert>
  {/if}

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
              <th class="px-4 py-3 font-semibold text-right">Действия</th>
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
                <td class="px-4 py-3 text-right">
                  {#if user.is_active}
                    <Button variant="ghost" size="sm" on:click={() => openModal(user, 'block')}>
                      <ShieldX class="h-3.5 w-3.5" aria-hidden="true" />
                      Заблокировать
                    </Button>
                  {:else}
                    <Button variant="ghost" size="sm" on:click={() => openModal(user, 'unblock')}>
                      <ShieldCheck class="h-3.5 w-3.5" aria-hidden="true" />
                      Разблокировать
                    </Button>
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

{#if modalUser}
  <!-- Подтверждение опасного действия (block/unblock) -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
    <GlassCard className="w-full max-w-md space-y-4">
      <h2 class="text-lg font-semibold text-foreground">
        {modalAction === 'block' ? 'Заблокировать пользователя?' : 'Разблокировать пользователя?'}
      </h2>
      <p class="text-sm text-muted-foreground">
        {modalAction === 'block'
          ? 'Пользователь потеряет доступ к личному кабинету (is_active = false). Действие будет записано в журнал.'
          : 'Доступ пользователя будет восстановлен. Действие будет записано в журнал.'}
        <br />
        <span class="font-medium text-foreground">{modalUser.email}</span>
      </p>

      <label class="block space-y-1">
        <span class="text-xs font-medium text-muted-foreground">Причина (необязательно)</span>
        <input
          type="text"
          bind:value={modalReason}
          maxlength="500"
          placeholder="Например: нарушение правил, запрос пользователя…"
          class="w-full rounded-xl border border-border/80 bg-background/40 px-3 py-2 text-sm text-foreground outline-none focus:border-neural-cyan/40"
        />
      </label>

      {#if actionError}
        <Alert variant="error" title="Ошибка">{actionError}</Alert>
      {/if}

      <div class="flex justify-end gap-2">
        <Button variant="ghost" on:click={closeModal} disabled={actionLoading}>Отмена</Button>
        <Button
          variant={modalAction === 'block' ? 'danger' : 'success'}
          on:click={confirmAction}
          disabled={actionLoading}
        >
          {actionLoading ? 'Выполняется…' : modalAction === 'block' ? 'Заблокировать' : 'Разблокировать'}
        </Button>
      </div>
    </GlassCard>
  </div>
{/if}
