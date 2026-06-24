<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount } from 'svelte';
  import { Calendar, ChevronLeft, ChevronRight, Download, Plus, RefreshCw } from 'lucide-svelte';
  import { apiJson, apiBlob, apiNoContent } from '$lib/utils/http';
  import {
    Alert,
    Button,
    EmptyState,
    ErrorState,
    FormField,
    GlassCard,
    LoadingSkeleton,
    PageHeader,
    StatusBadge
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';

  type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'ai';
  
  type CalendarEventType = 'sale' | 'promotion' | 'holiday' | 'deadline' | 'other';
  type RepeatType = 'none' | 'daily' | 'weekly' | 'monthly';
  type EventStatus = 'all' | 'upcoming' | 'active' | 'past';
  type ViewMode = 'day' | 'week' | 'month';

  interface CalendarEvent {
    id: number;
    title: string;
    description: string | null;
    marketplace: string | null;
    event_type: CalendarEventType;
    start_date: string;
    end_date: string;
    is_global: boolean;
    discount_percent: number | null;
    notes: string | null;
    is_owned: boolean;
    can_edit: boolean;
    can_delete: boolean;
    is_active: boolean;
    is_upcoming: boolean;
    is_past: boolean;
  }

  interface UpcomingEvent extends CalendarEvent {
    days_until: number;
  }

  interface CalendarFormModel {
    title: string;
    marketplace: string;
    event_type: CalendarEventType;
    start_date: string;
    end_date: string;
    discount_percent: number | null;
    description: string;
    notes: string;
    repeat_type: RepeatType;
    repeat_count: number;
    repeat_until: string;
  }

  // ... существующий код ...
  let events: CalendarEvent[] = [];
  let upcoming: UpcomingEvent[] = [];
  let loading = true;
  let loadingEvents = false;
  let loadingUpcoming = false;
  let showForm = false;
  
  let statusMessage = '';
  let errorMessage = '';
  let eventsLoadError = '';

  let viewMode: ViewMode = 'month';
  let viewAnchorDate = new Date();
  let marketplaceFilter = '';
  let typeFilter: '' | CalendarEventType = '';
  let statusFilter: EventStatus = 'all';
  let upcomingDays = 30;

  const weekdayLabels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  let creating = false;
  let updating = false;
  let deletingId: number | null = null;
  let editingEventId: number | null = null;
  let selectedDayIso: string | null = null;
  
  let formErrors: Record<string, string> = {};

  const emptyForm: CalendarFormModel = {
    title: '',
    marketplace: 'wildberries',
    event_type: 'sale',
    start_date: '',
    end_date: '',
    discount_percent: 10,
    description: '',
    notes: '',
    repeat_type: 'none',
    repeat_count: 1,
    repeat_until: ''
  };

  let eventForm: CalendarFormModel = { ...emptyForm };

  const viewModeLabels: Record<ViewMode, string> = {
    day: 'День',
    week: 'Неделя',
    month: 'Месяц'
  };

  const eventTypeLabels: Record<CalendarEventType, string> = {
    sale: 'Распродажа',
    promotion: 'Промо',
    holiday: 'Праздник',
    deadline: 'Дедлайн',
    other: 'Другое'
  };

  const eventTypeColors: Record<CalendarEventType, string> = {
    sale: 'bg-primary/20 text-primary',
    promotion: 'bg-success/20 text-success',
    holiday: 'bg-warning/20 text-warning',
    deadline: 'bg-destructive/20 text-destructive',
    other: 'bg-muted text-muted-foreground'
  };

  // ... существующий код ...
  $: filteredByView = events.filter((event) => matchesView(event, viewMode));
  $: monthGridDays = buildMonthGridDays(viewAnchorDate);
  $: selectedDayDate = selectedDayIso ? new Date(`${selectedDayIso}T00:00:00`) : null;
  $: selectedDayEvents = selectedDayDate ? getEventsForDay(selectedDayDate) : [];

  function showStatus(message: string): void {
    statusMessage = message;
    errorMessage = '';
  }

  function showError(message: string): void {
    errorMessage = message;
    statusMessage = '';
  }

  function getEventTypeVariant(type: CalendarEventType): BadgeVariant {
    if (type === 'sale') return 'info';
    if (type === 'promotion') return 'success';
    if (type === 'holiday') return 'warning';
    if (type === 'deadline') return 'error';
    return 'neutral';
  }

  function getEventStatusBadge(event: CalendarEvent): { label: string; variant: BadgeVariant } | null {
    if (event.is_active) return { label: 'Активно', variant: 'success' };
    if (event.is_upcoming) return { label: 'Предстоит', variant: 'info' };
    if (event.is_past) return { label: 'Завершено', variant: 'neutral' };
    return null;
  }

  function getMarketplaceLabel(marketplace: string | null): string {
    if (!marketplace) {
      return 'Не указан';
    }

    const labels: Record<string, string> = {
      wildberries: 'Wildberries',
      ozon: 'Ozon',
      avito: 'Avito',
      yandex_market: 'Яндекс Маркет'
    };

    return labels[marketplace] || marketplace;
  }

  function getMarketplaceColor(marketplace: string | null): string {
    const colors: Record<string, string> = {
      wildberries: 'bg-purple-500',
      ozon: 'bg-blue-500',
      avito: 'bg-green-500',
      yandex_market: 'bg-yellow-500'
    };
    return marketplace ? (colors[marketplace] || 'bg-gray-500') : 'bg-gray-500';
  }

  function toLocalDatetimeInputValue(isoValue: string): string {
    const date = new Date(isoValue);
    const offset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - offset).toISOString().slice(0, 16);
  }

  function toApiIso(value: string): string {
    return new Date(value).toISOString();
  }

  function formatDateRange(startIso: string, endIso: string): string {
    const start = new Date(startIso).toLocaleString('ru-RU');
    const end = new Date(endIso).toLocaleString('ru-RU');
    return `${start} — ${end}`;
  }

  function dateOnlyIso(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function normalizeWeekdayIndex(jsDay: number): number {
    return jsDay === 0 ? 6 : jsDay - 1;
  }

  function buildMonthGridDays(anchor: Date): Date[] {
    const firstDay = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const offsetToMonday = normalizeWeekdayIndex(firstDay.getDay());
    const gridStart = new Date(firstDay);
    gridStart.setDate(firstDay.getDate() - offsetToMonday);

    const result: Date[] = [];
    for (let i = 0; i < 42; i += 1) {
      const day = new Date(gridStart);
      day.setDate(gridStart.getDate() + i);
      result.push(day);
    }
    return result;
  }

  function getEventsForDay(day: Date): CalendarEvent[] {
    const dayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate());
    const dayEnd = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1);
    return filteredByView.filter((event) => {
      const start = new Date(event.start_date);
      const end = new Date(event.end_date);
      return start < dayEnd && end >= dayStart;
    });
  }

  function isToday(day: Date): boolean {
    const now = new Date();
    return day.getFullYear() === now.getFullYear() && day.getMonth() === now.getMonth() && day.getDate() === now.getDate();
  }

  function isCurrentMonth(day: Date): boolean {
    return day.getMonth() === viewAnchorDate.getMonth() && day.getFullYear() === viewAnchorDate.getFullYear();
  }

  function shiftCalendarPeriod(direction: 'prev' | 'next'): void {
    const diff = direction === 'prev' ? -1 : 1;
    if (viewMode === 'day') {
      viewAnchorDate = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth(), viewAnchorDate.getDate() + diff);
      return;
    }

    if (viewMode === 'week') {
      viewAnchorDate = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth(), viewAnchorDate.getDate() + (7 * diff));
      return;
    }

    viewAnchorDate = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth() + diff, 1);
  }

  function resetCalendarPeriodToToday(): void {
    viewAnchorDate = new Date();
  }

  function openDayModal(day: Date): void {
    selectedDayIso = dateOnlyIso(day);
  }

  function closeDayModal(): void {
    selectedDayIso = null;
  }

  function getSelectedDayTitle(): string {
    if (!selectedDayIso) {
      return '';
    }
    return new Date(`${selectedDayIso}T00:00:00`).toLocaleDateString('ru-RU', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
  }

  function getPeriodTitle(): string {
    if (viewMode === 'day') {
      return viewAnchorDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }

    if (viewMode === 'week') {
      const weekday = normalizeWeekdayIndex(viewAnchorDate.getDay());
      const monday = new Date(viewAnchorDate);
      monday.setDate(viewAnchorDate.getDate() - weekday);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      return `${monday.toLocaleDateString('ru-RU')} — ${sunday.toLocaleDateString('ru-RU')}`;
    }

    return viewAnchorDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
  }

  function matchesView(event: CalendarEvent, mode: ViewMode): boolean {
    const start = new Date(event.start_date);
    const end = new Date(event.end_date);

    if (mode === 'day') {
      const dayStart = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth(), viewAnchorDate.getDate());
      const dayEnd = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth(), viewAnchorDate.getDate() + 1);
      return start < dayEnd && end >= dayStart;
    }

    if (mode === 'week') {
      const weekday = normalizeWeekdayIndex(viewAnchorDate.getDay());
      const monday = new Date(viewAnchorDate);
      monday.setDate(viewAnchorDate.getDate() - weekday);
      monday.setHours(0, 0, 0, 0);

      const nextMonday = new Date(monday);
      nextMonday.setDate(monday.getDate() + 7);
      return start < nextMonday && end >= monday;
    }

    const monthStart = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth(), 1);
    const monthEnd = new Date(viewAnchorDate.getFullYear(), viewAnchorDate.getMonth() + 1, 1);
    return start < monthEnd && end >= monthStart;
  }

  function validateForm(): boolean {
    formErrors = {};

    if (!eventForm.title.trim()) {
      formErrors.title = 'Введите название события';
    }

    if (!eventForm.start_date) {
      formErrors.start_date = 'Укажите дату начала';
    }

    if (!eventForm.end_date) {
      formErrors.end_date = 'Укажите дату окончания';
    }

    if (eventForm.start_date && eventForm.end_date) {
      const start = new Date(eventForm.start_date);
      const end = new Date(eventForm.end_date);
      if (start >= end) {
        formErrors.end_date = 'Дата окончания должна быть позже даты начала';
      }
    }

    if (eventForm.discount_percent !== null && (eventForm.discount_percent < 0 || eventForm.discount_percent > 100)) {
      formErrors.discount_percent = 'Скидка должна быть от 0 до 100%';
    }

    if (eventForm.repeat_type !== 'none' && eventForm.repeat_count < 2) {
      formErrors.repeat_count = 'Для повторения укажите минимум 2 события';
    }

    return Object.keys(formErrors).length === 0;
  }

  async function loadEvents(): Promise<void> {
    loadingEvents = true;
    eventsLoadError = '';

    try {
      const params = new URLSearchParams({
        status: statusFilter,
        include_global: 'true',
        limit: '300'
      });

      if (marketplaceFilter) {
        params.set('marketplace', marketplaceFilter);
      }

      if (typeFilter) {
        params.set('event_type', typeFilter);
      }

      events = await apiJson<CalendarEvent[]>(
        `/api/v1/calendar/?${params.toString()}`,
        {},
        'Не удалось загрузить события'
      );
    } catch (error: unknown) {
      eventsLoadError = error instanceof Error ? error.message : 'Не удалось загрузить события';
      events = [];
    } finally {
      loadingEvents = false;
      loading = false;
    }
  }

  async function loadUpcoming(): Promise<void> {
    loadingUpcoming = true;

    try {
      const params = new URLSearchParams({ days: String(upcomingDays), limit: '12' });
      if (marketplaceFilter) {
        params.set('marketplace', marketplaceFilter);
      }
      if (typeFilter) {
        params.set('event_type', typeFilter);
      }

      upcoming = await apiJson<UpcomingEvent[]>(
        `/api/v1/calendar/upcoming?${params.toString()}`,
        {},
        'Не удалось загрузить ближайшие события'
      );
    } catch (error: unknown) {
      showError(error instanceof Error ? error.message : 'Не удалось загрузить ближайшие события');
      upcoming = [];
    } finally {
      loadingUpcoming = false;
    }
  }

  async function refreshCalendarData(): Promise<void> {
    await Promise.all([loadEvents(), loadUpcoming()]);
  }

  function openCreateForm(): void {
    editingEventId = null;
    eventForm = { ...emptyForm };
    formErrors = {};
    showForm = true;
  }

  function openEditForm(event: CalendarEvent): void {
    editingEventId = event.id;
    eventForm = {
      title: event.title,
      marketplace: event.marketplace || 'wildberries',
      event_type: event.event_type,
      start_date: toLocalDatetimeInputValue(event.start_date),
      end_date: toLocalDatetimeInputValue(event.end_date),
      discount_percent: event.discount_percent,
      description: event.description || '',
      notes: event.notes || '',
      repeat_type: 'none',
      repeat_count: 1,
      repeat_until: ''
    };
    formErrors = {};
    showForm = true;
  }

  function cancelForm(): void {
    showForm = false;
    editingEventId = null;
    formErrors = {};
    eventForm = { ...emptyForm };
  }

  async function createEvent(): Promise<void> {
    if (!validateForm()) {
      return;
    }

    creating = true;

    try {
      const payload = await apiJson<{ created_count: number }>(
        '/api/v1/calendar/',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: eventForm.title,
            marketplace: eventForm.marketplace,
            event_type: eventForm.event_type,
            start_date: toApiIso(eventForm.start_date),
            end_date: toApiIso(eventForm.end_date),
            discount_percent: eventForm.discount_percent,
            description: eventForm.description || null,
            notes: eventForm.notes || null,
            repeat_type: eventForm.repeat_type,
            repeat_count: eventForm.repeat_type === 'none' ? 1 : eventForm.repeat_count,
            repeat_until: eventForm.repeat_until ? toApiIso(eventForm.repeat_until) : null
          })
        },
        'Не удалось создать событие'
      );

      showStatus(`Создано событий: ${payload.created_count}`);
      cancelForm();
      await refreshCalendarData();
    } catch (error: unknown) {
      showError(error instanceof Error ? error.message : 'Не удалось создать событие');
    } finally {
      creating = false;
    }
  }

  async function updateEvent(): Promise<void> {
    if (!editingEventId) {
      return;
    }

    if (!validateForm()) {
      return;
    }

    updating = true;

    try {
      await apiJson(
        `/api/v1/calendar/${editingEventId}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            title: eventForm.title,
            marketplace: eventForm.marketplace,
            event_type: eventForm.event_type,
            start_date: toApiIso(eventForm.start_date),
            end_date: toApiIso(eventForm.end_date),
            discount_percent: eventForm.discount_percent,
            description: eventForm.description || null,
            notes: eventForm.notes || null
          })
        },
        'Не удалось обновить событие'
      );

      showStatus('Событие обновлено');
      cancelForm();
      await refreshCalendarData();
    } catch (error: unknown) {
      showError(error instanceof Error ? error.message : 'Не удалось обновить событие');
    } finally {
      updating = false;
    }
  }

  async function deleteEvent(eventId: number): Promise<void> {
    if (!confirm('Удалить событие? Это действие нельзя отменить.')) {
      return;
    }

    deletingId = eventId;

    try {
      await apiNoContent(
        `/api/v1/calendar/${eventId}`,
        { method: 'DELETE' },
        'Не удалось удалить событие'
      );

      showStatus('Событие удалено');
      await refreshCalendarData();
    } catch (error: unknown) {
      showError(error instanceof Error ? error.message : 'Не удалось удалить событие');
    } finally {
      deletingId = null;
    }
  }

  async function exportCalendar(type: 'csv' | 'ics'): Promise<void> {
    try {
      const blob = await apiBlob(
        `/api/v1/calendar/export/${type}`,
        {},
        `Не удалось экспортировать ${type.toUpperCase()}`
      );

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = type === 'csv' ? 'calendar_events.csv' : 'calendar_events.ics';
      anchor.click();
      URL.revokeObjectURL(url);

      showStatus(`Экспорт ${type.toUpperCase()} выполнен`);
    } catch (error: unknown) {
      showError(error instanceof Error ? error.message : 'Ошибка экспорта');
    }
  }

  onMount(async () => {
    await refreshCalendarData();
  });
</script>

{#if false}{JSON.stringify(params)}{/if}

<AppPageStyles />

<div class="mx-auto max-w-[1400px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Sales Calendar"
    title="Календарь распродаж"
    subtitle="Планирование акций, дедлайнов и повторяющихся событий с экспортом"
  >
    <svelte:fragment slot="actions">
      <Button variant="ghost" size="sm" on:click={() => exportCalendar('csv')}>
        <Download class="h-4 w-4" aria-hidden="true" />
        CSV
      </Button>
      <Button variant="ghost" size="sm" on:click={() => exportCalendar('ics')}>
        <Download class="h-4 w-4" aria-hidden="true" />
        ICS
      </Button>
      <Button variant="neural" size="sm" on:click={openCreateForm}>
        <Plus class="h-4 w-4" aria-hidden="true" />
        Добавить событие
      </Button>
    </svelte:fragment>
  </PageHeader>

  {#if statusMessage}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}
  {#if errorMessage}
    <Alert variant="error" title="Ошибка">{errorMessage}</Alert>
  {/if}

  <GlassCard padding="md">
    <div class="grid gap-3 sm:grid-cols-2 md:grid-cols-5 md:items-end">
      <FormField label="Маркетплейс" let:controlId>
        <select id={controlId} bind:value={marketplaceFilter} class="page-select">
          <option value="">Все маркетплейсы</option>
          <option value="wildberries">Wildberries</option>
          <option value="ozon">Ozon</option>
          <option value="avito">Avito</option>
          <option value="yandex_market">Яндекс Маркет</option>
        </select>
      </FormField>

      <FormField label="Тип" let:controlId>
        <select id={controlId} bind:value={typeFilter} class="page-select">
          <option value="">Все типы</option>
          <option value="sale">Распродажа</option>
          <option value="promotion">Промо</option>
          <option value="holiday">Праздник</option>
          <option value="deadline">Дедлайн</option>
          <option value="other">Другое</option>
        </select>
      </FormField>

      <FormField label="Статус" let:controlId>
        <select id={controlId} bind:value={statusFilter} class="page-select">
          <option value="all">Все статусы</option>
          <option value="upcoming">Предстоящие</option>
          <option value="active">Активные</option>
          <option value="past">Прошедшие</option>
        </select>
      </FormField>

      <FormField label="Режим" let:controlId>
        <select id={controlId} bind:value={viewMode} class="page-select">
          <option value="day">{viewModeLabels.day}</option>
          <option value="week">{viewModeLabels.week}</option>
          <option value="month">{viewModeLabels.month}</option>
        </select>
      </FormField>

      <Button variant="neural" loading={loadingEvents || loadingUpcoming} on:click={refreshCalendarData}>
        <RefreshCw class="h-4 w-4" aria-hidden="true" />
        Применить
      </Button>
    </div>
  </GlassCard>

  <GlassCard padding="md" glow>
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-xl font-semibold text-foreground">Календарная сетка</h2>
      <div class="flex items-center gap-2">
        <Button variant="ghost" size="sm" on:click={() => shiftCalendarPeriod('prev')} aria-label="Предыдущий период">
          <ChevronLeft class="h-4 w-4" aria-hidden="true" />
        </Button>
        <Button variant="ghost" size="sm" on:click={resetCalendarPeriodToToday}>Сегодня</Button>
        <Button variant="ghost" size="sm" on:click={() => shiftCalendarPeriod('next')} aria-label="Следующий период">
          <ChevronRight class="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    </div>

    <p class="mt-2 text-sm text-muted-foreground">{getPeriodTitle()}</p>

    <div class="mt-4 grid grid-cols-7 gap-2 text-center text-xs text-muted-foreground">
      {#each weekdayLabels as weekday}
        <div class="font-semibold">{weekday}</div>
      {/each}
    </div>

    <div class="mt-2 grid grid-cols-7 gap-2">
      {#each monthGridDays as day}
        {@const dayEvents = getEventsForDay(day)}
        <button
          type="button"
          on:click={() => openDayModal(day)}
          class="min-h-28 rounded-xl border border-input/60 p-2 text-left transition-neural hover:border-neural-cyan/40 hover:bg-neural-cyan/5 {isCurrentMonth(day) ? 'bg-background/40' : 'bg-background/20 opacity-60'} {isToday(day) ? 'ring-1 ring-neural-cyan' : ''}"
        >
          <div class="mb-2 flex items-center justify-between">
            <span class="text-xs font-semibold">{day.getDate()}</span>
            {#if dayEvents.length > 0}
              <StatusBadge label={String(dayEvents.length)} variant="info" dot={false} className="!px-1.5 !py-0 !text-[10px]" />
            {/if}
          </div>

          <div class="space-y-1">
            {#each dayEvents.slice(0, 3) as event}
              <div
                class="w-full truncate rounded px-1.5 py-0.5 text-left text-[10px] {eventTypeColors[event.event_type]}"
                title={event.title}
              >
                {event.title}
              </div>
            {/each}
            {#if dayEvents.length > 3}
              <p class="text-[10px] text-muted-foreground">+ ещё {dayEvents.length - 3}</p>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  </GlassCard>

  {#if showForm}
    <GlassCard padding="lg" glow>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <h2 class="text-xl font-semibold text-foreground">{editingEventId ? 'Редактирование события' : 'Новое событие'}</h2>
        {#if !editingEventId && eventForm.repeat_type !== 'none'}
          <StatusBadge label="Повторяющееся" variant="ai" dot={false} />
        {/if}
      </div>

      <div class="grid gap-3 md:grid-cols-2">
        <FormField label="Название" required error={formErrors.title} let:controlId let:invalid>
          <input id={controlId} type="text" bind:value={eventForm.title} class="page-input {invalid ? 'page-input-error' : ''}" />
        </FormField>

        <FormField label="Маркетплейс" let:controlId>
          <select id={controlId} bind:value={eventForm.marketplace} class="page-select">
            <option value="wildberries">Wildberries</option>
            <option value="ozon">Ozon</option>
            <option value="avito">Avito</option>
            <option value="yandex_market">Яндекс Маркет</option>
          </select>
        </FormField>

        <FormField label="Тип события" let:controlId>
          <select id={controlId} bind:value={eventForm.event_type} class="page-select">
            <option value="sale">Распродажа</option>
            <option value="promotion">Промо</option>
            <option value="holiday">Праздник</option>
            <option value="deadline">Дедлайн</option>
            <option value="other">Другое</option>
          </select>
        </FormField>

        <FormField label="Скидка, %" error={formErrors.discount_percent} let:controlId let:invalid>
          <input id={controlId} type="number" bind:value={eventForm.discount_percent} min="0" max="100" class="page-input {invalid ? 'page-input-error' : ''}" />
        </FormField>

        <FormField label="Начало" required error={formErrors.start_date} let:controlId let:invalid>
          <input id={controlId} type="datetime-local" bind:value={eventForm.start_date} class="page-input {invalid ? 'page-input-error' : ''}" />
        </FormField>

        <FormField label="Окончание" required error={formErrors.end_date} let:controlId let:invalid>
          <input id={controlId} type="datetime-local" bind:value={eventForm.end_date} class="page-input {invalid ? 'page-input-error' : ''}" />
        </FormField>

        {#if !editingEventId}
          <FormField label="Повтор" let:controlId>
            <select id={controlId} bind:value={eventForm.repeat_type} class="page-select">
              <option value="none">Без повтора</option>
              <option value="daily">Каждый день</option>
              <option value="weekly">Каждую неделю</option>
              <option value="monthly">Каждый месяц</option>
            </select>
          </FormField>

          <FormField label="Количество повторов" error={formErrors.repeat_count} let:controlId let:invalid>
            <input id={controlId} type="number" bind:value={eventForm.repeat_count} min="1" max="100" disabled={eventForm.repeat_type === 'none'} class="page-input {invalid ? 'page-input-error' : ''}" />
          </FormField>

          <div class="md:col-span-2">
            <FormField label="Повторять до (необязательно)" let:controlId>
              <input id={controlId} type="datetime-local" bind:value={eventForm.repeat_until} disabled={eventForm.repeat_type === 'none'} class="page-input" />
            </FormField>
          </div>
        {/if}
      </div>

      <div class="mt-3">
        <FormField label="Описание" let:controlId>
          <textarea id={controlId} bind:value={eventForm.description} rows="2" class="page-textarea"></textarea>
        </FormField>
      </div>

      <div class="mt-3">
        <FormField label="Заметки" let:controlId>
          <textarea id={controlId} bind:value={eventForm.notes} rows="2" class="page-textarea"></textarea>
        </FormField>
      </div>

      <div class="mt-4 flex flex-wrap gap-2">
        <Button
          variant="neural"
          loading={creating || updating}
          on:click={editingEventId ? updateEvent : createEvent}
        >
          {editingEventId ? 'Сохранить изменения' : 'Создать событие'}
        </Button>
        <Button variant="ghost" on:click={cancelForm}>Отмена</Button>
      </div>
    </GlassCard>
  {/if}

  {#if selectedDayIso}
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        class="absolute inset-0 bg-black/60"
        aria-label="Закрыть окно событий дня"
        on:click={closeDayModal}
      ></button>

      <GlassCard className="relative w-full max-w-2xl" padding="md" role="dialog" aria-modal="true" aria-label="События выбранного дня">
        <div class="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 class="text-xl font-semibold text-foreground">{getSelectedDayTitle()}</h3>
            <p class="text-sm text-muted-foreground">Событий: {selectedDayEvents.length}</p>
          </div>
          <Button variant="ghost" size="sm" on:click={closeDayModal}>Закрыть</Button>
        </div>

        {#if selectedDayEvents.length === 0}
          <EmptyState
            title="На этот день событий нет"
            description="Выберите другой день или создайте новое событие"
            icon={Calendar}
            className="!p-6"
          />
        {:else}
          <div class="max-h-[60vh] space-y-3 overflow-auto pr-1">
            {#each selectedDayEvents as event}
              <div class="glass-card rounded-xl p-3">
                <div class="mb-2 flex flex-wrap items-center gap-2">
                  <span class="h-3 w-3 rounded-full {getMarketplaceColor(event.marketplace)}"></span>
                  <h4 class="font-semibold text-foreground">{event.title}</h4>
                  <StatusBadge label={eventTypeLabels[event.event_type]} variant={getEventTypeVariant(event.event_type)} dot={false} />
                  {#if event.discount_percent !== null}
                    <StatusBadge label="-{event.discount_percent}%" variant="warning" dot={false} />
                  {/if}
                </div>

                <p class="text-xs text-muted-foreground">{formatDateRange(event.start_date, event.end_date)}</p>

                {#if event.description}
                  <p class="mt-2 text-sm text-muted-foreground">{event.description}</p>
                {/if}

                <div class="mt-3 flex flex-wrap gap-2">
                  {#if event.can_edit}
                    <Button
                      variant="ghost"
                      size="sm"
                      on:click={() => {
                        closeDayModal();
                        openEditForm(event);
                      }}
                    >
                      Изменить
                    </Button>
                  {/if}

                  {#if event.can_delete}
                    <Button
                      variant="danger"
                      size="sm"
                      loading={deletingId === event.id}
                      on:click={async () => {
                        await deleteEvent(event.id);
                      }}
                    >
                      Удалить
                    </Button>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </GlassCard>
    </div>
  {/if}

  {#if upcoming.length > 0 || loadingUpcoming}
    <section class="space-y-4">
      <h2 class="text-xl font-semibold text-foreground">Ближайшие события ({upcomingDays} дней)</h2>
      {#if loadingUpcoming}
        <div class="grid gap-4 md:grid-cols-3">
          {#each Array(3) as _}
            <LoadingSkeleton variant="card" />
          {/each}
        </div>
      {:else}
        <div class="grid gap-4 md:grid-cols-3">
          {#each upcoming as event}
            <GlassCard padding="md" hoverable>
              <div class="mb-2 flex items-center justify-between gap-2">
                <span class="inline-flex items-center gap-2 text-xs text-muted-foreground">
                  <span class="h-3 w-3 rounded-full {getMarketplaceColor(event.marketplace)}"></span>
                  {getMarketplaceLabel(event.marketplace)}
                </span>
                <StatusBadge label={eventTypeLabels[event.event_type]} variant={getEventTypeVariant(event.event_type)} dot={false} />
              </div>
              <h3 class="text-base font-semibold text-foreground">{event.title}</h3>
              <div class="mt-2 flex items-center gap-2">
                <StatusBadge label="Через {event.days_until} дн." variant="ai" dot={false} />
                {#if event.discount_percent !== null}
                  <StatusBadge label="-{event.discount_percent}%" variant="warning" dot={false} />
                {/if}
              </div>
              <p class="mt-2 text-xs text-muted-foreground">{formatDateRange(event.start_date, event.end_date)}</p>
            </GlassCard>
          {/each}
        </div>
      {/if}
    </section>
  {/if}

  <section class="space-y-4">
    <h2 class="text-xl font-semibold text-foreground">События ({viewModeLabels[viewMode]})</h2>

    {#if loading || loadingEvents}
      <div class="space-y-3">
        {#each Array(3) as _}
          <LoadingSkeleton variant="card" />
        {/each}
      </div>
    {:else if eventsLoadError}
      <ErrorState
        title="Не удалось загрузить события"
        description={eventsLoadError}
        on:click={refreshCalendarData}
      />
    {:else if filteredByView.length === 0}
      <EmptyState
        title="Нет событий"
        description="По выбранным фильтрам событий не найдено. Измените фильтры или добавьте новое событие."
        icon={Calendar}
      >
        <svelte:fragment slot="action">
          <Button variant="neural" on:click={openCreateForm}>
            <Plus class="h-4 w-4" aria-hidden="true" />
            Добавить событие
          </Button>
        </svelte:fragment>
      </EmptyState>
    {:else}
      <div class="space-y-3">
        {#each filteredByView as event}
          {@const statusBadge = getEventStatusBadge(event)}
          <GlassCard padding="md" hoverable>
            <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="h-3 w-3 rounded-full {getMarketplaceColor(event.marketplace)}"></span>
                  <h3 class="font-semibold text-foreground">{event.title}</h3>
                  <StatusBadge label={eventTypeLabels[event.event_type]} variant={getEventTypeVariant(event.event_type)} dot={false} />
                  {#if statusBadge}
                    <StatusBadge label={statusBadge.label} variant={statusBadge.variant} dot={false} />
                  {/if}
                  {#if event.is_global}
                    <StatusBadge label="Глобальное" variant="neutral" dot={false} />
                  {/if}
                </div>
                <p class="text-xs text-muted-foreground">{formatDateRange(event.start_date, event.end_date)}</p>
                {#if event.description}
                  <p class="text-sm text-muted-foreground">{event.description}</p>
                {/if}
              </div>

              <div class="flex items-center gap-2">
                {#if event.discount_percent !== null}
                  <StatusBadge label="-{event.discount_percent}%" variant="warning" dot={false} />
                {/if}

                {#if event.can_edit}
                  <Button variant="ghost" size="sm" on:click={() => openEditForm(event)}>Изменить</Button>
                {/if}

                {#if event.can_delete}
                  <Button variant="danger" size="sm" loading={deletingId === event.id} on:click={() => deleteEvent(event.id)}>Удалить</Button>
                {/if}
              </div>
            </div>
          </GlassCard>
        {/each}
      </div>
    {/if}
  </section>
</div>
