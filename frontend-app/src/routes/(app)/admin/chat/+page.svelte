<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { MessageSquare, Send, Shield, User } from 'lucide-svelte';
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
  import { ChatService, type ChatMessage, type ChatConversation } from '$lib/services/chat';
  import { handleUnauthorized as authHandleUnauthorized } from '$lib/utils/auth';

  let conversations: ChatConversation[] = [];
  let activeConversation: ChatConversation | null = null;
  let messages: ChatMessage[] = [];
  let newMessageText = '';
  let isLoading = false;
  let filterStatus: 'all' | 'active' | 'closed' | 'unassigned' | 'waiting_response' | 'in_progress' | 'answered' = 'all';
  let onlyMyChats = false;
  let ws: WebSocket | null = null;
  let isConnected = false;
  let isTyping = false;
  let autoRefreshTimer: ReturnType<typeof setInterval> | null = null;

  // Локальные сообщения об ошибках (presentation-only): загрузка списка и действия в активном чате.
  let listError = '';
  let chatError = '';

  // Сводка по текущему списку (реальные данные, без фейка): кол-во диалогов и суммарный unread.
  $: totalConversations = conversations.length;
  $: totalUnread = conversations.reduce((sum, conv) => sum + (conv.unread_count || 0), 0);

  function handleUnauthorized() {
    authHandleUnauthorized({ status: 401 } as Response);
  }

  onMount(() => {
    void loadConversations();

    autoRefreshTimer = setInterval(() => {
      void loadConversations(false);
    }, 7000);

    return () => {
      if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
      }
      if (ws) {
        ws.close();
      }
    };
  });

  async function loadConversations(showLoader = true) {
    if (showLoader) {
      isLoading = true;
    }
    try {
      conversations = await ChatService.getAdminConversations(filterStatus, onlyMyChats);
      listError = '';

      if (activeConversation) {
        const freshActive = conversations.find((c) => c.id === activeConversation?.id);
        if (freshActive) {
          activeConversation = { ...activeConversation, ...freshActive };
        }
      }
    } catch (error) {
      console.error('Не удалось загрузить список чатов:', error);
      if (error instanceof Error && error.message === 'UNAUTHORIZED') {
        if (autoRefreshTimer) {
          clearInterval(autoRefreshTimer);
          autoRefreshTimer = null;
        }
        handleUnauthorized();
        return;
      }
      // Не затираем уже загруженные диалоги при фоновой ошибке поллинга —
      // только показываем сообщение об ошибке.
      listError = error instanceof Error ? error.message : 'Не удалось загрузить список чатов';
    } finally {
      if (showLoader) {
        isLoading = false;
      }
    }
  }

  async function selectConversation(conv: ChatConversation) {
    activeConversation = conv;
    chatError = '';
    try {
      const full = await ChatService.getConversation(conv.id);
      messages = full.messages || [];
      await ChatService.assignConversation(conv.id);
      connectWebSocket(conv.id);
      await loadConversations();
    } catch (error) {
      console.error('Не удалось открыть чат:', error);
      chatError = error instanceof Error ? error.message : 'Не удалось открыть чат';
    }
  }

  function connectWebSocket(conversationId: number) {
    if (!browser) return;

    if (ws) {
      ws.close();
      ws = null;
      isConnected = false;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/chat?conversation_id=${conversationId}`;
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      ws?.send(JSON.stringify({ type: 'auth' }));
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'connected') {
        isConnected = true;
      } else if (data.type === 'message:new' || data.type === 'message:ack') {
        const newMessage = data.data;
        if (!messages.find(m => m.id === newMessage.id)) {
          messages = [...messages, newMessage];
        }
      } else if (data.type === 'typing') {
        isTyping = true;
        setTimeout(() => { isTyping = false; }, 2000);
      } else if (data.type === 'error') {
        isConnected = false;
        console.error('WebSocket error:', data.data?.message || data);
      }
      void loadConversations(false);
    };
    ws.onclose = () => { isConnected = false; };
  }

  async function sendMessage() {
    if (!newMessageText.trim() || !activeConversation) return;
    const text = newMessageText.trim();
    newMessageText = '';
    chatError = '';
    if (ws && isConnected) {
      ws.send(JSON.stringify({ type: 'message', conversation_id: activeConversation.id, text }));
    } else {
      try {
        const message = await ChatService.sendMessage(activeConversation.id, { text });
        messages = [...messages, message];
      } catch (error) {
        console.error('Не удалось отправить сообщение:', error);
        chatError = error instanceof Error ? error.message : 'Не удалось отправить сообщение';
        // Возвращаем текст в поле ввода, чтобы пользователь не потерял сообщение.
        newMessageText = text;
      }
      await loadConversations(false);
    }
  }

  // Enter — отправить, Shift+Enter — перенос строки. Сохраняем привычное поведение «Enter = отправить».
  function handleComposerKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void sendMessage();
    }
  }

  async function updateConversationStatus(status: 'waiting_response' | 'in_progress' | 'answered' | 'closed') {
    if (!activeConversation) return;
    chatError = '';
    try {
      await ChatService.updateConversationStatus(activeConversation.id, status);
      activeConversation = {
        ...activeConversation,
        status,
        is_closed: status === 'closed',
      };
      await loadConversations();
    } catch (error) {
      console.error('Не удалось обновить статус чата:', error);
      chatError = error instanceof Error ? error.message : 'Не удалось обновить статус чата';
    }
  }

  async function closeConversation() {
    await updateConversationStatus('closed');
    if (ws) ws.close();
  }

  function formatTime(date: string | Date): string {
    return new Date(date).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }

  function isOwnMessage(message: ChatMessage): boolean {
    return message.sender_role === 'admin';
  }

  type ConversationStatus = 'waiting_response' | 'in_progress' | 'answered' | 'closed';

  function getStatusVariant(
    status: ConversationStatus | undefined
  ): 'error' | 'warning' | 'success' | 'neutral' {
    switch (status) {
      case 'waiting_response':
        return 'error';
      case 'in_progress':
        return 'warning';
      case 'answered':
        return 'success';
      default:
        return 'neutral';
    }
  }

  function getStatusInfo(status: 'waiting_response' | 'in_progress' | 'answered' | 'closed') {
    switch (status) {
      case 'waiting_response':
        return { label: 'Ждёт ответа', className: 'bg-red-100 text-red-700' };
      case 'in_progress':
        return { label: 'В процессе', className: 'bg-amber-100 text-amber-700' };
      case 'answered':
        return { label: 'Отвечено', className: 'bg-emerald-100 text-emerald-700' };
      case 'closed':
        return { label: 'Закрыто', className: 'bg-gray-200 text-gray-700' };
      default:
        return { label: 'Неизвестно', className: 'bg-gray-100 text-gray-600' };
    }
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<AppPageStyles />

<div class="mx-auto max-w-[1400px] animate-fade-in">
  <PageHeader
    eyebrow="Командный центр · Поддержка"
    title="Чат поддержки"
    subtitle="Обрабатывайте обращения пользователей"
  >
    <svelte:fragment slot="meta">
      <StatusBadge
        variant={isConnected ? 'success' : 'neutral'}
        label={isConnected ? 'WebSocket онлайн' : 'WebSocket офлайн'}
        dot={isConnected}
      />
      {#if totalConversations > 0}
        <StatusBadge variant="info" label={`${totalConversations} диалогов`} dot={false} />
      {/if}
      {#if totalUnread > 0}
        <StatusBadge variant="error" label={`${totalUnread} непрочитанных`} dot={false} />
      {/if}
    </svelte:fragment>
  </PageHeader>

  <div class="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6 lg:h-[calc(100vh-220px)]">
    <!-- Список чатов -->
    <GlassCard padding="none" className="flex flex-col overflow-hidden lg:col-span-4 lg:h-full">
      <div class="space-y-3 border-b border-border/60 p-4">
        <FormField label="Фильтр" let:controlId>
          <select
            id={controlId}
            bind:value={filterStatus}
            on:change={() => loadConversations()}
            class="page-select"
          >
            <option value="all">Все</option>
            <option value="active">Активные</option>
            <option value="waiting_response">Ждёт ответа</option>
            <option value="in_progress">В процессе</option>
            <option value="answered">Отвечено</option>
            <option value="unassigned">Нераспределённые</option>
            <option value="closed">Закрытые</option>
          </select>
        </FormField>

        <label class="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            bind:checked={onlyMyChats}
            on:change={() => loadConversations()}
            class="rounded border-border"
          />
          Только мои чаты
        </label>
      </div>

      <div class="min-h-[280px] flex-1 overflow-y-auto lg:min-h-0">
        {#if isLoading}
          <div class="space-y-1 p-4">
            {#each Array(5) as _}
              <LoadingSkeleton variant="avatar" className="py-3" />
            {/each}
          </div>
        {:else if conversations.length === 0 && listError}
          <div class="p-4">
            <ErrorState title="Не удалось загрузить чаты" description={listError}>
              <svelte:fragment slot="action">
                <Button variant="neural" on:click={() => loadConversations()}>Повторить</Button>
              </svelte:fragment>
            </ErrorState>
          </div>
        {:else if conversations.length === 0}
          <div class="p-4">
            <EmptyState
              title="Нет чатов"
              description="Обращения пользователей появятся здесь. Попробуйте изменить фильтр."
              icon={MessageSquare}
            />
          </div>
        {:else}
          {#if listError}
            <div class="p-3">
              <Alert variant="warning" title="Обновление списка">{listError}</Alert>
            </div>
          {/if}
          {#each conversations as conv}
            <button
              type="button"
              class="w-full border-b border-border/40 px-4 py-3 text-left transition-neural hover:bg-background/40 {activeConversation?.id === conv.id
                ? 'border-l-2 border-l-neural-cyan bg-neural-cyan/5'
                : ''}"
              on:click={() => selectConversation(conv)}
            >
              <div class="flex items-center justify-between gap-2">
                <div class="min-w-0 truncate font-medium text-foreground">{conv.user_email}</div>
                {#if (conv.unread_count || 0) > 0}
                  <StatusBadge variant="error" label={String(conv.unread_count)} dot={false} />
                {/if}
              </div>
              <div class="truncate text-xs text-muted-foreground">
                {conv.last_message_preview || 'Нет сообщений'}
              </div>
              <div class="mt-1.5 flex flex-wrap items-center gap-2">
                <StatusBadge
                  variant={getStatusVariant(conv.status)}
                  label={getStatusInfo(conv.status || 'waiting_response').label}
                />
                {#if conv.admin_email}
                  <span class="truncate text-[11px] text-muted-foreground">{conv.admin_email}</span>
                {/if}
              </div>
            </button>
          {/each}
        {/if}
      </div>
    </GlassCard>

    <!-- Область переписки -->
    <GlassCard padding="none" className="flex min-h-[420px] flex-col overflow-hidden lg:col-span-8 lg:h-full">
      {#if activeConversation}
        <div class="flex flex-col gap-3 border-b border-border/60 bg-background/30 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0 space-y-1.5">
            <h2 class="truncate font-semibold text-foreground">{activeConversation.user_email}</h2>
            <StatusBadge
              variant={getStatusVariant(activeConversation.status)}
              label={getStatusInfo(activeConversation.status || 'waiting_response').label}
            />
          </div>
          <div class="flex flex-wrap items-center gap-2">
            {#if isConnected}
              <StatusBadge variant="success" label="Онлайн" />
            {:else}
              <StatusBadge variant="neutral" label="Офлайн" dot={false} />
            {/if}
            {#if !activeConversation.is_closed}
              <Button variant="ghost" size="sm" on:click={() => updateConversationStatus('in_progress')}>
                В процессе
              </Button>
              <Button variant="ghost" size="sm" on:click={() => updateConversationStatus('answered')}>
                Отвечено
              </Button>
              <Button variant="danger" size="sm" on:click={closeConversation}>
                Закрыть
              </Button>
            {/if}
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-4">
          {#if chatError}
            <div class="mb-3">
              <Alert variant="error" title="Ошибка">{chatError}</Alert>
            </div>
          {/if}

          {#if messages.length === 0 && !isTyping}
            <div class="flex h-full items-center justify-center">
              <EmptyState
                title="Сообщений пока нет"
                description="Начните диалог — отправьте первое сообщение пользователю."
                icon={MessageSquare}
              />
            </div>
          {/if}

          {#each messages as message}
            <div class="mb-3 flex items-end gap-2 {isOwnMessage(message) ? 'flex-row-reverse' : ''}">
              <div
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/60 bg-background/50 text-xs"
                aria-hidden="true"
              >
                {#if isOwnMessage(message)}
                  <Shield class="h-4 w-4 text-neural-cyan" />
                {:else}
                  <User class="h-4 w-4 text-muted-foreground" />
                {/if}
              </div>
              <div
                class="min-w-0 max-w-[85%] rounded-xl px-3 py-2 sm:max-w-[70%] {isOwnMessage(message)
                  ? 'gradient-neural text-primary-foreground shadow-glow-sm'
                  : 'glass-card'}"
              >
                <p class="whitespace-pre-wrap break-words text-sm">{message.text}</p>
                <p class="mt-1 text-xs opacity-70">{formatTime(message.created_at)}</p>
              </div>
            </div>
          {/each}

          {#if isTyping}
            <div class="flex items-end gap-2">
              <div
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/60 bg-background/50"
                aria-hidden="true"
              >
                <User class="h-4 w-4 text-muted-foreground" />
              </div>
              <div class="glass-card rounded-xl px-3 py-2">
                <div class="flex gap-1">
                  <span class="h-2 w-2 animate-bounce rounded-full bg-muted-foreground"></span>
                  <span class="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" style="animation-delay: 150ms"></span>
                  <span class="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" style="animation-delay: 300ms"></span>
                </div>
              </div>
            </div>
          {/if}
        </div>

        <div class="border-t border-border/60 p-3">
          {#if activeConversation.is_closed}
            <div class="rounded-xl border border-border/60 bg-muted/30 px-4 py-2 text-center text-sm text-muted-foreground">
              Чат закрыт
            </div>
          {:else}
            <form class="flex flex-col gap-2 sm:flex-row sm:items-end" on:submit|preventDefault={sendMessage}>
              <textarea
                bind:value={newMessageText}
                on:keydown={handleComposerKeydown}
                rows="2"
                placeholder="Введите сообщение… (Enter — отправить, Shift+Enter — новая строка)"
                class="page-input flex-1 resize-none"
              ></textarea>
              <Button type="submit" variant="neural" className="shrink-0" disabled={!newMessageText.trim()}>
                <Send class="h-4 w-4" aria-hidden="true" />
                Отправить
              </Button>
            </form>
          {/if}
        </div>
      {:else}
        <div class="flex flex-1 items-center justify-center p-6">
          <EmptyState
            title="Выберите чат"
            description="Выберите обращение из списка слева, чтобы начать общение с пользователем."
            icon={MessageSquare}
          />
        </div>
      {/if}
    </GlassCard>
  </div>
</div>
