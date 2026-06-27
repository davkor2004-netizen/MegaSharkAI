<script lang="ts">
  import { goto } from '$app/navigation';
  import {
    ChevronDown,
    LogOut,
    Menu,
    Moon,
    Plus,
    Search,
    Sun,
    User,
    X
  } from 'lucide-svelte';
  import NotificationButton from './NotificationButton.svelte';
  import RoleBadge from './RoleBadge.svelte';
  import { cn } from '$lib/utils/cn';

  export let pageTitle = 'MegaSharkAI';
  export let sidebarOpen = false;
  export let profileMenuOpen = false;
  export let currentTheme: 'dark' | 'light' = 'dark';
  export let userEmail = '';
  export let userName = '';
  export let isSuperuser = false;
  export let isMarketplaceSeller = false;
  export let notificationUnreadCount = 0;

  export let onToggleSidebar: () => void = () => {};
  export let onToggleProfileMenu: () => void = () => {};
  export let onCloseProfileMenu: () => void = () => {};
  export let onToggleTheme: () => void = () => {};
  export let onLogout: () => void = () => {};

  let searchQuery = '';

  function handleSearchSubmit(event: Event) {
    event.preventDefault();
    const query = searchQuery.trim();
    if (query) {
      goto(`/products?search=${encodeURIComponent(query)}`);
    } else {
      goto('/products');
    }
    searchQuery = '';
  }

  const quickActions = [
    { href: '/parsing', label: 'Парсинг', icon: Search },
    { href: '/import', label: 'Импорт', icon: Plus },
    { href: '/repricing', label: 'Repricing', icon: Plus }
  ];
</script>

<header class="sticky top-0 z-30 border-b border-border/60 glass-card backdrop-blur-xl">
  <div class="flex h-16 items-center gap-3 px-4 lg:px-6">
    <!-- Mobile menu -->
    <button
      type="button"
      class="flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-card/60 text-foreground lg:hidden transition-neural hover:border-neural-cyan/30"
      on:click={onToggleSidebar}
      aria-label={sidebarOpen ? 'Закрыть меню' : 'Открыть меню'}
    >
      {#if sidebarOpen}
        <X class="h-5 w-5" />
      {:else}
        <Menu class="h-5 w-5" />
      {/if}
    </button>

    <!-- Page title -->
    <div class="min-w-0 flex-1">
      <p class="truncate text-xs font-medium uppercase tracking-wider text-muted-foreground hidden sm:block">
        Командный центр
      </p>
      <h1 class="truncate text-lg font-semibold text-foreground sm:text-xl">{pageTitle}</h1>
    </div>

    <!-- Search и быстрые действия — инструменты селлера, админу не показываем -->
    {#if !isSuperuser}
      <!-- Search -->
      <form
        on:submit={handleSearchSubmit}
        class="hidden md:flex max-w-xs flex-1 items-center gap-2 rounded-xl border border-border/80 bg-background/40 px-3 py-2 transition-neural focus-within:border-neural-cyan/40 focus-within:ring-2 focus-within:ring-neural-cyan/15"
        role="search"
      >
        <Search class="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <input
          type="search"
          bind:value={searchQuery}
          placeholder="Быстрый поиск товаров..."
          class="w-full bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground/70"
          aria-label="Поиск товаров"
        />
      </form>

      <!-- Quick actions -->
      <div class="hidden lg:flex items-center gap-1">
        {#each quickActions as action}
          <a
            href={action.href}
            class="rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-neural hover:bg-neural-cyan/10 hover:text-neural-cyan"
          >
            {action.label}
          </a>
        {/each}
      </div>
    {/if}

    {#if isSuperuser}
      <!-- Заполнитель, чтобы профиль/уведомления оставались справа -->
      <div class="flex-1"></div>
    {/if}

    <NotificationButton unreadCount={notificationUnreadCount} />

    <!-- Profile -->
    <div class="relative">
      <button
        type="button"
        on:click={onToggleProfileMenu}
        class="flex items-center gap-2 rounded-xl border border-border/80 bg-card/60 py-1.5 pl-1.5 pr-2 transition-neural hover:border-neural-cyan/30 hover:shadow-glow-sm"
        aria-expanded={profileMenuOpen}
        aria-haspopup="menu"
      >
        <span
          class="flex h-8 w-8 items-center justify-center rounded-lg gradient-neural text-xs font-bold text-primary-foreground"
        >
          {userEmail ? userEmail.charAt(0).toUpperCase() : '?'}
        </span>
        <span class="hidden sm:block max-w-[120px] truncate text-sm text-foreground">
          {userName || userEmail || 'Профиль'}
        </span>
        <ChevronDown class="hidden sm:block h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </button>

      {#if profileMenuOpen}
        <div
          class="absolute right-0 mt-2 w-64 overflow-hidden rounded-xl border border-border/80 glass-card shadow-glow-lg"
          role="menu"
        >
          <div class="border-b border-border/60 px-4 py-3">
            {#if userName}
              <p class="truncate text-sm font-semibold text-foreground">{userName}</p>
            {/if}
            <p class="truncate text-xs text-muted-foreground">{userEmail || 'Пользователь'}</p>
            <div class="mt-2">
              <RoleBadge {isSuperuser} {isMarketplaceSeller} />
            </div>
          </div>

          <div class="border-b border-border/60 px-4 py-3 flex items-center justify-between">
            <span class="flex items-center gap-2 text-sm text-foreground">
              {#if currentTheme === 'dark'}
                <Sun class="h-4 w-4 text-neural-cyan" />
              {:else}
                <Moon class="h-4 w-4 text-neural-purple" />
              {/if}
              Тема
            </span>
            <button
              type="button"
              on:click={onToggleTheme}
              class="relative inline-flex h-6 w-11 items-center rounded-full bg-muted transition-neural"
              aria-label="Переключить тему"
            >
              <span
                class={cn(
                  'inline-block h-4 w-4 transform rounded-full bg-primary transition-transform',
                  currentTheme === 'dark' ? 'translate-x-6' : 'translate-x-1'
                )}
              ></span>
            </button>
          </div>

          <div class="py-1">
            <a
              href="/profile"
              on:click={onCloseProfileMenu}
              class="flex items-center gap-3 px-4 py-2.5 text-sm text-foreground transition-neural hover:bg-neural-cyan/10 hover:text-neural-cyan"
              role="menuitem"
            >
              <User class="h-4 w-4" aria-hidden="true" />
              Профиль
            </a>
            {#if isSuperuser}
              <a
                href="/settings"
                on:click={onCloseProfileMenu}
                class="flex items-center gap-3 px-4 py-2.5 text-sm text-foreground transition-neural hover:bg-neural-cyan/10 hover:text-neural-cyan"
                role="menuitem"
              >
                Настройки AI
              </a>
            {/if}
          </div>

          <div class="border-t border-border/60">
            <button
              type="button"
              on:click={onLogout}
              class="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-destructive transition-neural hover:bg-destructive/10"
              role="menuitem"
            >
              <LogOut class="h-4 w-4" aria-hidden="true" />
              Выйти
            </button>
          </div>
        </div>

        <button
          type="button"
          class="fixed inset-0 z-[-1] cursor-default bg-transparent"
          aria-label="Закрыть меню профиля"
          on:click={onCloseProfileMenu}
        ></button>
      {/if}
    </div>
  </div>
</header>

<style>
  .transition-neural {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
</style>
