<script lang="ts">
  export let params: Record<string, string> = {};

  import '../app.css';
  import { page } from '$app/stores';
  import { goto, afterNavigate } from '$app/navigation';
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { theme, toggleTheme as storeToggleTheme } from '../stores/theme';
  import ChatWidget from '$lib/components/chat/ChatWidget.svelte';
  import { clearSession, handleUnauthorized, resetLogoutGuard, initAuthStorage } from '$lib/utils/auth';
  import { apiFetch } from '$lib/utils/api';
  import { AnimatedBackground, LoadingSkeleton, NeuralGridBackground } from '$lib/components';
  import { Sidebar, Topbar } from '$lib/components/shell';
  import { getPageTitle } from '$lib/navigation/app-nav';

  let sidebarOpen = false;
  let isSuperuser = false;
  let isMarketplaceSeller = false;
  let isProfileLoaded = false;
  let profileMenuOpen = false;
  let userEmail = '';
  let userName = '';
  let supportUnreadCount = 0;
  let notificationUnreadCount = 0;
  let supportUnreadInterval: ReturnType<typeof setInterval> | null = null;
  let profileChecking = false;

  let currentTheme: 'dark' | 'light' = 'dark';

  theme.subscribe((value) => {
    currentTheme = value;
  });

  $: isAppRoute = $page.route.id?.startsWith('/(app)') || $page.route.id === '/';
  $: isAuthRoute = $page.route.id?.startsWith('/(auth)');
  $: pageTitle = getPageTitle($page.url.pathname);

  /** Загрузка профиля для AppShell (повторно после входа с /login). */
  function scheduleProfileLoad() {
    if (!browser) return;

    if (isAuthRoute || !isAppRoute) {
      isProfileLoaded = false;
      profileChecking = false;
      return;
    }

    if (isProfileLoaded || profileChecking) return;

    profileChecking = true;
    void loadUserProfile();
  }

  onMount(() => {
    initAuthStorage();
    resetLogoutGuard();
    scheduleProfileLoad();
  });

  afterNavigate(() => {
    scheduleProfileLoad();
  });

  onDestroy(() => {
    if (supportUnreadInterval) {
      clearInterval(supportUnreadInterval);
      supportUnreadInterval = null;
    }
  });

  function toggleTheme() {
    storeToggleTheme();
  }

  async function loadUserProfile() {
    try {
      const response = await apiFetch('/api/v1/auth/me');

      if (handleUnauthorized(response)) {
        isProfileLoaded = false;
        return;
      }

      if (response.ok) {
        try {
          const data = await response.json();
          userEmail = data.email || '';
          userName = data.full_name || '';
          isSuperuser = data.is_superuser || false;
          isMarketplaceSeller = data.is_marketplace_seller || false;
          isProfileLoaded = true;

          await loadNotificationUnreadCount();

          if (isSuperuser) {
            await loadSupportUnreadCount();
            startSupportUnreadPolling();
          } else {
            supportUnreadCount = 0;
            if (supportUnreadInterval) {
              clearInterval(supportUnreadInterval);
              supportUnreadInterval = null;
            }
          }
        } catch (jsonErr) {
          console.error('❌ Ошибка парсинга профиля:', jsonErr);
          isProfileLoaded = false;
        }
      } else {
        isProfileLoaded = false;
      }
    } catch (err) {
      console.error('❌ Ошибка загрузки профиля:', err);
      isProfileLoaded = false;
    } finally {
      profileChecking = false;
    }
  }

  async function loadNotificationUnreadCount() {
    try {
      const response = await apiFetch('/api/v1/notifications/unread-count');

      if (handleUnauthorized(response)) return;

      if (response.ok) {
        const data = await response.json();
        notificationUnreadCount = Number(data.unread_count) || 0;
      }
    } catch (error) {
      console.error('Ошибка загрузки счётчика уведомлений:', error);
    }
  }

  async function loadSupportUnreadCount() {
    try {
      if (!isSuperuser) {
        supportUnreadCount = 0;
        return;
      }

      const response = await apiFetch(
        '/api/v1/chat/admin/conversations?status=waiting_response&limit=200'
      );

      if (handleUnauthorized(response)) {
        supportUnreadCount = 0;
        return;
      }

      if (!response.ok) {
        throw new Error(`Ошибка загрузки чатов поддержки (${response.status})`);
      }

      const conversations = await response.json();
      if (!Array.isArray(conversations)) {
        supportUnreadCount = 0;
        return;
      }

      supportUnreadCount = conversations.reduce(
        (sum, conv) => sum + (Number(conv?.unread_count) || 0),
        0
      );
    } catch (error) {
      console.error('Ошибка загрузки индикатора новых сообщений поддержки:', error);
    }
  }

  function startSupportUnreadPolling() {
    if (supportUnreadInterval) {
      clearInterval(supportUnreadInterval);
    }

    supportUnreadInterval = setInterval(() => {
      loadSupportUnreadCount();
    }, 7000);
  }

  function toggleProfileMenu() {
    profileMenuOpen = !profileMenuOpen;
  }

  function closeProfileMenu() {
    profileMenuOpen = false;
  }

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }

  function closeSidebar() {
    sidebarOpen = false;
  }

  function handleLogout() {
    try {
      if (supportUnreadInterval) {
        clearInterval(supportUnreadInterval);
        supportUnreadInterval = null;
      }
      supportUnreadCount = 0;
      notificationUnreadCount = 0;
      isProfileLoaded = false;
      void clearSession().then(() => goto('/login', { replaceState: true }));
    } catch (error) {
      console.error('Ошибка при выходе:', error);
      window.location.href = '/login';
    }
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

{#if isAuthRoute}
  <slot />
{:else if isAppRoute}
  {#if profileChecking}
    <div class="flex min-h-screen items-center justify-center p-6">
      <div class="w-full max-w-md space-y-4">
        <LoadingSkeleton variant="metric" />
        <LoadingSkeleton variant="card" />
      </div>
    </div>
  {:else if isProfileLoaded}
  <div class="relative min-h-screen overflow-hidden">
    <AnimatedBackground variant="subtle" />
    <NeuralGridBackground animated opacity={0.25} />

    <div class="relative z-10 flex min-h-screen">
      <Sidebar
        pathname={$page.url.pathname}
        open={sidebarOpen}
        {isSuperuser}
        {isMarketplaceSeller}
        {supportUnreadCount}
        onNavigate={closeSidebar}
      />

      {#if sidebarOpen}
        <button
          type="button"
          class="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm lg:hidden"
          aria-label="Закрыть боковое меню"
          on:click={closeSidebar}
        ></button>
      {/if}

      <div class="flex min-w-0 flex-1 flex-col">
        <Topbar
          {pageTitle}
          {sidebarOpen}
          {profileMenuOpen}
          {currentTheme}
          {userEmail}
          {userName}
          {isSuperuser}
          {isMarketplaceSeller}
          {notificationUnreadCount}
          onToggleSidebar={toggleSidebar}
          onToggleProfileMenu={toggleProfileMenu}
          onCloseProfileMenu={closeProfileMenu}
          onToggleTheme={toggleTheme}
          onLogout={handleLogout}
        />

        <main class="flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          <slot />
        </main>
      </div>
    </div>

    {#if browser && !isSuperuser}
      <ChatWidget />
    {/if}
  </div>
  {:else}
    <slot />
  {/if}
{:else}
  <div class="min-h-screen gradient-dark">
    <slot />
  </div>
{/if}
