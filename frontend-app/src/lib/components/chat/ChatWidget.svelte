<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { goto } from '$app/navigation';
  import { MessageCircle, Plus, Send, Shield, User, X } from 'lucide-svelte';
  import { ChatService, type ChatConversation, type ChatMessage } from '$lib/services/chat';
  import { apiFetch } from '$lib/utils/api';
  import { Alert, Button, EmptyState, LoadingSkeleton, StatusBadge } from '$lib/components';

  // Состояние
  let isOpen = false;
  let isConnected = false;
  let isConnecting = false;
  let conversations: ChatConversation[] = [];
  let activeConversation: ChatConversation | null = null;
  let messages: ChatMessage[] = [];
  let newMessageText = '';
  let isLoading = false;
  let hasLoadedConversations = false;
  let isTyping = false;
  let typingTimeout: ReturnType<typeof setTimeout> | null = null;

  // Локальные сообщения об ошибках (presentation-only).
  let sendError = '';
  let connectionError = false;

  // WebSocket
  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  const MAX_RECONNECT_ATTEMPTS = 5;

  // Пользователь
  let currentUser: { id: string; email: string; is_admin: boolean } | null = null;

  onMount(async () => {
    if (!browser) return;

    try {
      const response = await apiFetch('/api/v1/auth/me');
      if (response.ok) {
          const user = await response.json();
          currentUser = {
            id: user.id,
            email: user.email,
            is_admin: user.is_superuser || false,
          };
        }
      } catch (e) {
        console.error('Failed to get user:', e);
      }

    if (currentUser) {
      await loadConversations();
    }
  });

  onDestroy(() => {
    disconnectWebSocket();
  });

  async function loadConversations() {
    if (!currentUser) return;
    
    isLoading = true;
    try {
      conversations = await ChatService.getConversations(true, 100);

      if (conversations.length > 0 && !activeConversation) {
        // Сначала пытаемся открыть активный чат, где уже есть история сообщений,
        // чтобы пользователь не попадал в пустой диалог при наличии старой переписки.
        const conversationWithHistory = conversations.find(
          (c) => !c.is_closed && Boolean(c.last_message_preview)
        );

        activeConversation = conversationWithHistory || conversations.find(c => !c.is_closed) || conversations[0];
        await loadMessages(activeConversation.id);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      hasLoadedConversations = true;
      isLoading = false;
    }
  }

  async function createNewConversation() {
    if (!currentUser) return;

    try {
      const conversation = await ChatService.createConversation({
        topic: 'Новое обращение',
      });
      conversations.unshift(conversation);
      activeConversation = conversation;
      messages = [];
      connectWebSocket(conversation.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  }

  async function loadMessages(conversationId: number) {
    try {
      const conversation = await ChatService.getConversation(conversationId);
      activeConversation = conversation;
      messages = conversation.messages || [];
      connectWebSocket(conversationId);
      
      setTimeout(() => {
        const scrollArea = document.querySelector('[data-chat-messages]');
        if (scrollArea) {
          scrollArea.scrollTop = scrollArea.scrollHeight;
        }
      }, 100);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  }

  function connectWebSocket(conversationId: number) {
    if (!browser || !currentUser) return;

    isConnecting = true;

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/chat?conversation_id=${conversationId}`;
      
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        isConnecting = false;
        reconnectAttempts = 0;
        connectionError = false;
        ws?.send(JSON.stringify({ type: 'auth' }));
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };

      ws.onclose = () => {
        isConnected = false;
        if (activeConversation && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts++;
          // Сохраняем id таймера реконнекта, чтобы корректно очистить его в onDestroy (без утечек).
          reconnectTimer = setTimeout(() => connectWebSocket(activeConversation!.id), 2000 * reconnectAttempts);
        } else if (activeConversation) {
          // Реконнекты исчерпаны — показываем индикатор потери соединения (отправка работает через REST-fallback).
          connectionError = true;
        }
      };

      ws.onerror = () => {
        isConnected = false;
        isConnecting = false;
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      isConnecting = false;
    }
  }

  function disconnectWebSocket() {
    // Очищаем отложенный реконнект, иначе после размонтирования таймер откроет новый WebSocket.
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (typingTimeout) {
      clearTimeout(typingTimeout);
      typingTimeout = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    isConnected = false;
    isConnecting = false;
  }

  function handleWebSocketMessage(data: any) {
    switch (data.type) {
      case 'connected':
        isConnected = true;
        connectionError = false;
        break;

      case 'error':
        isConnected = false;
        isConnecting = false;
        console.error('WebSocket error:', data.data?.message || data);
        break;
      
      case 'message:new':
      case 'message:ack':
        const newMessage = data.data;
        if (!messages.find(m => m.id === newMessage.id)) {
          messages = [...messages, newMessage];
          setTimeout(() => {
            const scrollArea = document.querySelector('[data-chat-messages]');
            if (scrollArea) {
              scrollArea.scrollTop = scrollArea.scrollHeight;
            }
          }, 50);
        }
        break;
      
      case 'typing':
        if (data.data.sender_id !== currentUser?.id) {
          isTyping = true;
          if (typingTimeout) clearTimeout(typingTimeout);
          typingTimeout = setTimeout(() => { isTyping = false; }, 2000);
        }
        break;
      
      case 'conversation:closed':
        if (activeConversation) {
          activeConversation = { ...activeConversation, is_closed: true };
        }
        break;
    }
  }
      
  async function sendMessage() {
    if (!newMessageText.trim() || !activeConversation) return;
    
    const text = newMessageText.trim();
    newMessageText = '';
    sendError = '';

    if (ws && isConnected) {
      ws.send(JSON.stringify({
        type: 'message',
        conversation_id: activeConversation.id,
        text: text,
      }));
    } else {
      try {
        const message = await ChatService.sendMessage(activeConversation.id, { text });
        messages = [...messages, message];
      } catch (error) {
        console.error('Failed to send message:', error);
        sendError = error instanceof Error ? error.message : 'Не удалось отправить сообщение';
        // Возвращаем текст в поле, чтобы пользователь не потерял сообщение.
        newMessageText = text;
      }
    }
  }

  // Enter — отправить, Shift+Enter — перенос строки. Сохраняем привычное «Enter = отправить».
  function handleComposerKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void sendMessage();
    }
  }

  function goToLogin() {
    isOpen = false;
    void goto('/login');
  }

  function formatTime(date: string | Date): string {
    const d = new Date(date);
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }

  function isOwnMessage(message: ChatMessage): boolean {
    return message.sender_id === currentUser?.id;
  }

  function toggleChat() {
    isOpen = !isOpen;

    // Создаём новый диалог только если уже загрузили историю и реально нет ни одного диалога.
    // Это защищает от создания лишних пустых чатов при медленном ответе API.
    if (isOpen && currentUser && hasLoadedConversations && !activeConversation && conversations.length === 0) {
      createNewConversation();
    }
  }
</script>

<div class="fixed bottom-4 right-4 z-50">
  {#if !isOpen}
    <button
      on:click={toggleChat}
      aria-label="Открыть чат поддержки"
      class="flex h-14 w-14 items-center justify-center rounded-full gradient-neural text-primary-foreground shadow-glow-sm transition-transform hover:scale-105 focus-ring"
    >
      <MessageCircle class="h-6 w-6" aria-hidden="true" />
    </button>
  {/if}

  {#if isOpen}
    <div
      class="glass-card glass-card-glow flex max-h-[80vh] w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl shadow-2xl sm:h-[550px] sm:max-h-[80vh] sm:w-[380px]"
    >
      <!-- Заголовок -->
      <div class="flex items-center justify-between gap-2 border-b border-border/60 bg-background/40 p-4">
        <div class="flex min-w-0 items-center gap-3">
          <div
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full gradient-neural text-primary-foreground shadow-glow-sm"
            aria-hidden="true"
          >
            <Shield class="h-5 w-5" />
          </div>
          <div class="min-w-0">
            <h3 class="truncate text-sm font-semibold text-foreground">Поддержка MegaSharkAI</h3>
            {#if isConnected}
              <StatusBadge variant="success" label="Онлайн" dot={true} className="!px-1.5 !py-0 !text-[11px]" />
            {:else if isConnecting}
              <StatusBadge variant="ai" label="Подключение…" dot={true} className="!px-1.5 !py-0 !text-[11px]" />
            {:else}
              <StatusBadge variant="neutral" label="AI assistant" dot={false} className="!px-1.5 !py-0 !text-[11px]" />
            {/if}
          </div>
        </div>

        <div class="flex shrink-0 items-center gap-1">
          {#if currentUser}
            <button
              on:click={createNewConversation}
              class="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-background/60 hover:text-foreground focus-ring"
              title="Новый чат"
              aria-label="Новый чат"
            >
              <Plus class="h-4 w-4" aria-hidden="true" />
            </button>
          {/if}
          <button
            on:click={toggleChat}
            class="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-background/60 hover:text-foreground focus-ring"
            title="Закрыть"
            aria-label="Закрыть чат"
          >
            <X class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <!-- Сообщения -->
      <div class="min-h-0 flex-1 overflow-y-auto p-4" data-chat-messages>
        {#if !currentUser}
          <div class="flex h-full flex-col items-center justify-center text-center">
            <div class="mb-3 flex h-12 w-12 items-center justify-center rounded-full border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan" aria-hidden="true">
              <User class="h-6 w-6" />
            </div>
            <p class="text-sm font-medium text-foreground">Войдите в аккаунт</p>
            <p class="mt-1 text-xs text-muted-foreground">Чтобы написать в поддержку, необходимо авторизоваться</p>
            <Button variant="neural" size="sm" className="mt-3" on:click={goToLogin}>Войти</Button>
          </div>
        {:else if isLoading}
          <div class="space-y-3">
            <LoadingSkeleton variant="avatar" />
            <LoadingSkeleton lines={2} />
            <LoadingSkeleton variant="avatar" />
          </div>
        {:else if messages.length === 0}
          <div class="flex h-full items-center justify-center">
            <EmptyState
              title="Сообщений пока нет"
              description="Опишите вашу проблему — поддержка ответит здесь."
              icon={MessageCircle}
            />
          </div>
        {:else}
          <div class="space-y-3">
            {#each messages as message (message.id)}
              {#if !message.is_internal || currentUser?.is_admin}
                <div class="flex items-end gap-2 {isOwnMessage(message) ? 'flex-row-reverse' : ''}">
                  <div
                    class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border/60 bg-background/50 text-[11px]"
                    aria-hidden="true"
                  >
                    {#if isOwnMessage(message)}
                      <User class="h-3.5 w-3.5 text-muted-foreground" />
                    {:else}
                      <Shield class="h-3.5 w-3.5 text-neural-cyan" />
                    {/if}
                  </div>
                  <div
                    class="min-w-0 max-w-[78%] rounded-xl px-3 py-2 text-sm {isOwnMessage(message)
                      ? 'gradient-neural text-primary-foreground shadow-glow-sm'
                      : 'glass-card'}"
                  >
                    <p class="whitespace-pre-wrap break-words">{message.text}</p>
                    <p class="mt-1 text-xs opacity-70">
                      {formatTime(message.created_at)}
                      {#if isOwnMessage(message) && message.is_read}<span class="ml-1">✓✓</span>{/if}
                    </p>
                  </div>
                </div>
              {/if}
            {/each}

            {#if isTyping}
              <div class="flex items-end gap-2">
                <div class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border/60 bg-background/50" aria-hidden="true">
                  <Shield class="h-3.5 w-3.5 text-neural-cyan" />
                </div>
                <div class="glass-card rounded-xl px-3 py-2">
                  <div class="flex gap-1">
                    <span class="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50"></span>
                    <span class="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" style="animation-delay: 150ms"></span>
                    <span class="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" style="animation-delay: 300ms"></span>
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Ввод -->
      <div class="border-t border-border/60 bg-background/40 p-3">
        {#if !currentUser}
          <div class="py-2 text-center text-sm text-muted-foreground">
            <button type="button" class="text-neural-cyan hover:underline" on:click={goToLogin}>Войдите</button>, чтобы написать
          </div>
        {:else if activeConversation?.is_closed}
          <div class="rounded-xl border border-border/60 bg-muted/20 px-4 py-2 text-center text-sm text-muted-foreground">
            Чат закрыт
          </div>
        {:else}
          {#if connectionError}
            <div class="mb-2">
              <Alert variant="warning" title="Соединение потеряно">
                Realtime недоступен — сообщения отправляются обычным способом.
              </Alert>
            </div>
          {/if}
          {#if sendError}
            <div class="mb-2">
              <Alert variant="error" title="Ошибка отправки">{sendError}</Alert>
            </div>
          {/if}
          <form class="flex items-end gap-2" on:submit|preventDefault={sendMessage}>
            <textarea
              bind:value={newMessageText}
              on:keydown={handleComposerKeydown}
              rows="1"
              placeholder="Введите сообщение…"
              class="flex-1 resize-none rounded-lg border border-border/60 bg-background/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-neural-cyan/40"
            ></textarea>
            <Button type="submit" variant="neural" className="shrink-0" disabled={!newMessageText.trim()}>
              <Send class="h-4 w-4" aria-hidden="true" />
            </Button>
          </form>
        {/if}
      </div>
    </div>
  {/if}
</div>

