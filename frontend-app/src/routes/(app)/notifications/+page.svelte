<script lang="ts">
  import { onMount } from 'svelte';
  import {
    Bell,
    CheckCheck,
    RefreshCw,
    AlertTriangle,
    FileText,
    Monitor,
    TrendingUp,
    Filter
  } from 'lucide-svelte';
  import type { ComponentType } from 'svelte';
  import { apiJson } from '$lib/utils/http';
  import {
    EmptyState,
    ErrorState,
    GlassCard,
    LoadingSkeleton,
    PageHeader,
    StatusBadge,
    Button,
    Alert
  } from '$lib/components';

  type NotificationType = 'price_change' | 'low_stock' | 'report_ready' | 'competitor_analysis' | 'system';

  interface NotificationItem {
    id: number;
    title: string;
    message: string;
    type: NotificationType | string;
    is_read: boolean;
    created_at: string | null;
  }

  interface UnreadCountResponse {
    unread_count: number;
  }

  interface ActionResponse {
    status: string;
  }

  let notifications: NotificationItem[] = [];
  let unreadCount = 0;
  let loading = true;
  let refreshing = false;
  let unreadOnly = false;
  let loadError = '';
  let actionError = '';
  let successMessage = '';

  onMount(async () => {
    await refreshPageData();
  });

  async function refreshPageData(): Promise<void> {
    refreshing = true;
    loadError = '';

    try {
      await Promise.all([loadNotifications(), loadUnreadCount()]);
    } catch (err: unknown) {
      loadError = err instanceof Error ? err.message : 'Не удалось загрузить уведомления';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function loadNotifications(): Promise<void> {
    const params = new URLSearchParams({ limit: '50' });
    if (unreadOnly) {
      params.set('unread_only', 'true');
    }

    notifications = await apiJson<NotificationItem[]>(
      `/api/v1/notifications/?${params.toString()}`,
      {},
      'Ошибка загрузки списка уведомлений'
    );
  }

  async function loadUnreadCount(): Promise<void> {
    const data = await apiJson<UnreadCountResponse>(
      '/api/v1/notifications/unread-count',
      {},
      'Ошибка загрузки количества непрочитанных уведомлений'
    );
    unreadCount = data.unread_count || 0;
  }

  async function markAsRead(id: number): Promise<void> {
    actionError = '';
    successMessage = '';

    try {
      await apiJson<ActionResponse>(
        `/api/v1/notifications/mark-read/${id}`,
        { method: 'POST' },
        'Не удалось пометить уведомление прочитанным'
      );
      successMessage = 'Уведомление помечено прочитанным';
      await refreshPageData();
    } catch (err: unknown) {
      actionError = err instanceof Error ? err.message : 'Ошибка при обновлении уведомления';
    }
  }

  async function markAllAsRead(): Promise<void> {
    actionError = '';
    successMessage = '';

    try {
      await apiJson<ActionResponse>(
        '/api/v1/notifications/mark-all-read',
        { method: 'POST' },
        'Не удалось пометить все уведомления прочитанными'
      );
      successMessage = 'Все уведомления помечены прочитанными';
      await refreshPageData();
    } catch (err: unknown) {
      actionError = err instanceof Error ? err.message : 'Ошибка при массовом обновлении уведомлений';
    }
  }

  async function toggleUnreadOnly(): Promise<void> {
    unreadOnly = !unreadOnly;
    loading = true;
    await refreshPageData();
  }

  function getTimeAgo(dateStr: string | null): string {
    if (!dateStr) return 'Дата неизвестна';

    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Только что';
    if (minutes < 60) return `${minutes} мин. назад`;
    if (hours < 24) return `${hours} ч. назад`;
    return `${days} дн. назад`;
  }

  function getTypeIcon(type: string): ComponentType {
    const icons: Record<string, ComponentType> = {
      price_change: TrendingUp,
      low_stock: AlertTriangle,
      report_ready: FileText,
      competitor_analysis: Monitor,
      system: Bell
    };
    return icons[type] ?? Bell;
  }

  function getTypeBadgeVariant(type: string): 'success' | 'warning' | 'info' | 'ai' | 'neutral' {
    const variants: Record<string, 'success' | 'warning' | 'info' | 'ai' | 'neutral'> = {
      price_change: 'success',
      low_stock: 'warning',
      report_ready: 'info',
      competitor_analysis: 'ai',
      system: 'neutral'
    };
    return variants[type] ?? 'neutral';
  }

  function getTypeLabel(type: string): string {
    const labels: Record<string, string> = {
      price_change: 'Изменение цены',
      low_stock: 'Низкий остаток',
      report_ready: 'Отчёт готов',
      competitor_analysis: 'Анализ конкурентов',
      system: 'Система'
    };
    return labels[type] ?? type.replace(/_/g, ' ');
  }

  function getIconAccentClass(type: string): string {
    const classes: Record<string, string> = {
      price_change: 'border-success/20 bg-success/10 text-success',
      low_stock: 'border-warning/20 bg-warning/10 text-warning',
      report_ready: 'border-neural-blue/20 bg-neural-blue/10 text-neural-blue',
      competitor_analysis: 'border-neural-purple/20 bg-neural-purple/10 text-neural-purple',
      system: 'border-border/60 bg-muted/40 text-muted-foreground'
    };
    return classes[type] ?? classes.system;
  }
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Alert Center"
    title="Уведомления"
    subtitle="Важные события по товарам, конкурентам и системе"
  >
    <svelte:fragment slot="meta">
      {#if unreadCount > 0}
        <StatusBadge variant="info" label="{unreadCount} непрочитанных" dot />
      {:else}
        <StatusBadge variant="neutral" label="Все прочитаны" dot={false} />
      {/if}
      {#if unreadOnly}
        <StatusBadge variant="warning" label="Фильтр: непрочитанные" dot={false} />
      {/if}
    </svelte:fragment>

    <svelte:fragment slot="actions">
      <Button variant="ghost" size="sm" loading={refreshing} disabled={refreshing} on:click={toggleUnreadOnly}>
        <Filter class="h-4 w-4" aria-hidden="true" />
        {unreadOnly ? 'Показать все' : 'Только непрочитанные'}
      </Button>

      {#if unreadCount > 0}
        <Button variant="neural" size="sm" loading={refreshing} disabled={refreshing} on:click={markAllAsRead}>
          <CheckCheck class="h-4 w-4" aria-hidden="true" />
          Прочитать все ({unreadCount})
        </Button>
      {/if}
    </svelte:fragment>
  </PageHeader>

  {#if successMessage}
    <Alert variant="success" title="Готово">{successMessage}</Alert>
  {/if}
  {#if actionError}
    <Alert variant="error" title="Ошибка действия">{actionError}</Alert>
  {/if}

  {#if loading}
    <GlassCard padding="lg" className="space-y-4">
      {#each Array(4) as _}
        <LoadingSkeleton variant="card" />
      {/each}
    </GlassCard>

  {:else if loadError && notifications.length === 0}
    <ErrorState title="Не удалось загрузить уведомления" description={loadError} on:click={refreshPageData} />

  {:else if notifications.length === 0 && unreadOnly}
    <EmptyState
      title="Нет непрочитанных"
      description="Все уведомления прочитаны. Покажите все или дождитесь новых событий."
      icon={Bell}
    >
      <Button slot="action" variant="ghost" size="sm" on:click={toggleUnreadOnly}>
        Показать все
      </Button>
    </EmptyState>

  {:else if notifications.length === 0}
    <EmptyState
      title="Нет уведомлений"
      description="Здесь появятся события: изменения цен, отчёты, анализ конкурентов и системные сообщения."
      icon={Bell}
    />

  {:else}
    <GlassCard glow padding="lg" className="space-y-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold text-foreground">Лента событий</h2>
          <p class="text-sm text-muted-foreground">
            {notifications.length} {notifications.length === 1 ? 'уведомление' : notifications.length < 5 ? 'уведомления' : 'уведомлений'}
          </p>
        </div>
        <Button variant="subtle" size="sm" loading={refreshing} disabled={refreshing} on:click={refreshPageData}>
          <RefreshCw class="h-4 w-4" aria-hidden="true" />
          Обновить
        </Button>
      </div>

      {#if loadError}
        <Alert variant="warning" title="Частичная ошибка">{loadError}</Alert>
      {/if}

      <div class="space-y-3">
        {#each notifications as notification (notification.id)}
          {@const TypeIcon = getTypeIcon(notification.type)}
          <article
            class="surface p-4 transition-neural {notification.is_read ? 'opacity-70' : 'border-neural-cyan/25 shadow-glow-sm'}"
          >
            <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div class="flex min-w-0 flex-1 items-start gap-3 sm:gap-4">
                <span
                  class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border {getIconAccentClass(notification.type)}"
                  aria-hidden="true"
                >
                  <svelte:component this={TypeIcon} class="h-5 w-5" />
                </span>

                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <h3 class="text-base font-semibold text-foreground sm:text-lg">{notification.title}</h3>
                    {#if !notification.is_read}
                      <StatusBadge variant="info" label="Новое" dot />
                    {/if}
                    <StatusBadge
                      variant={getTypeBadgeVariant(notification.type)}
                      label={getTypeLabel(notification.type)}
                      dot={false}
                    />
                  </div>

                  <p class="mt-2 break-words text-sm text-muted-foreground">{notification.message}</p>

                  <p class="mt-3 text-xs text-muted-foreground">{getTimeAgo(notification.created_at)}</p>
                </div>
              </div>

              {#if !notification.is_read}
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0 self-start !text-success hover:!bg-success/10"
                  loading={refreshing}
                  disabled={refreshing}
                  on:click={() => markAsRead(notification.id)}
                  title="Пометить как прочитанное"
                  aria-label="Пометить как прочитанное"
                >
                  <CheckCheck class="h-4 w-4" aria-hidden="true" />
                  <span class="hidden sm:inline">Прочитано</span>
                </Button>
              {/if}
            </div>
          </article>
        {/each}
      </div>
    </GlassCard>
  {/if}
</div>
