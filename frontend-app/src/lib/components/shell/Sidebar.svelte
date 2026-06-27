<script lang="ts">
  import type { ComponentType } from 'svelte';
  import {
    BarChart3,
    Bell,
    Briefcase,
    Calendar,
    CreditCard,
    Cpu,
    FileText,
    Image,
    LayoutDashboard,
    LineChart,
    MessageSquare,
    Package,
    Radar,
    ScrollText,
    Server,
    Settings,
    ShieldCheck,
    Sparkles,
    Tags,
    Upload,
    User,
    Users,
    Wallet,
    LayoutGrid
  } from 'lucide-svelte';
  import LogoMark from '$lib/components/LogoMark.svelte';
  import RoleBadge from './RoleBadge.svelte';
  import {
    getAdminNavGroups,
    getNavGroups,
    isNavItemActive,
    type AppNavItem
  } from '$lib/navigation/app-nav';
  import { cn } from '$lib/utils/cn';

  const navGroups = getNavGroups();
  const adminNavGroups = getAdminNavGroups();

  export let pathname: string;
  export let open = false;
  export let isSuperuser = false;
  export let isMarketplaceSeller = false;
  export let supportUnreadCount = 0;
  export let onNavigate: () => void = () => {};

  const iconMap: Record<string, ComponentType> = {
    // Seller workspace
    '/dashboard': BarChart3,
    '/parsing': Radar,
    '/products': Package,
    '/import': Upload,
    '/repricing': Wallet,
    '/calendar': Calendar,
    '/ai': Sparkles,
    '/ai-studio': Image,
    '/analytics': LineChart,
    '/reports': FileText,
    '/widget': LayoutGrid,
    '/notifications': Bell,
    '/billing': CreditCard,
    '/partners': Users,
    '/profile': User,
    '/settings': Settings,
    // Admin Control Center
    '/admin': LayoutDashboard,
    '/admin/users': Users,
    '/admin/billing': CreditCard,
    '/admin/tariffs': Tags,
    '/admin/system': Server,
    '/admin/parser': Radar,
    '/admin/ai': Cpu,
    '/admin/security': ShieldCheck,
    '/admin/audit': ScrollText,
    '/admin/chat': MessageSquare
  };

  function getIcon(item: AppNavItem): ComponentType {
    return iconMap[item.href] ?? Package;
  }

  function navLinkClass(active: boolean): string {
    return cn(
      'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-neural',
      active
        ? 'bg-neural-cyan/10 text-neural-cyan shadow-glow-sm border border-neural-cyan/20'
        : 'text-muted-foreground hover:bg-card/80 hover:text-foreground border border-transparent'
    );
  }
</script>

<aside
  class={cn(
    'fixed inset-y-0 left-0 z-40 flex w-[272px] flex-col border-r border-border/60 glass-card p-5 transition-transform duration-300 lg:static lg:translate-x-0',
    open ? 'translate-x-0' : '-translate-x-full'
  )}
  aria-label="Основная навигация"
>
  <!-- Brand -->
  <div class="mb-6 flex items-center gap-3 px-1">
    <LogoMark size="sm" />
    <div class="min-w-0 flex-1">
      <p class="truncate text-base font-bold text-gradient">MegaSharkAI</p>
      <p class="truncate text-[11px] text-muted-foreground">
        {isSuperuser ? 'Центр управления' : 'Командный центр'}
      </p>
    </div>
  </div>

  <div class="mb-4 px-1">
    <RoleBadge {isSuperuser} {isMarketplaceSeller} />
  </div>

  {#if isSuperuser}
    <!-- Admin Control Center: только админское меню, без инструментов селлера -->
    <nav class="flex-1 space-y-5 overflow-y-auto pr-1" aria-label="Admin Control Center">
      {#each adminNavGroups as group}
        <div class="space-y-1">
          <p class="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-neural-purple">
            {group.label}
          </p>
          {#each group.items as item}
            {@const active = isNavItemActive(pathname, item)}
            {@const Icon = getIcon(item)}
            <a
              href={item.href}
              class={navLinkClass(active)}
              aria-current={active ? 'page' : undefined}
              on:click={onNavigate}
            >
              {#if active}
                <span class="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-neural-cyan" aria-hidden="true"></span>
              {/if}
              <Icon class="h-4 w-4 shrink-0 {active ? 'text-neural-cyan' : ''}" aria-hidden="true" />
              <span>{item.label}</span>
              {#if item.href === '/admin/chat' && supportUnreadCount > 0}
                <span
                  class="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground"
                >
                  {supportUnreadCount > 99 ? '99+' : supportUnreadCount}
                </span>
              {/if}
            </a>
          {/each}
        </div>
      {/each}
    </nav>

    <!-- Доступ админа к клиентскому кабинету (отдельно от admin-меню) -->
    <div class="mt-4 border-t border-border/60 pt-4">
      <a
        href="/dashboard"
        class={navLinkClass(false)}
        on:click={onNavigate}
      >
        <Briefcase class="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>Клиентский кабинет</span>
      </a>
    </div>
  {:else}
    <!-- Seller workspace: меню обычного пользователя (без изменений) -->
    <nav class="flex-1 space-y-5 overflow-y-auto pr-1" aria-label="Seller workspace">
      {#each navGroups as group}
        <div class="space-y-1">
          <p class="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            {group.label}
          </p>
          {#each group.items as item}
            {@const active = isNavItemActive(pathname, item)}
            {@const Icon = getIcon(item)}
            <a
              href={item.href}
              class={navLinkClass(active)}
              aria-current={active ? 'page' : undefined}
              on:click={onNavigate}
            >
              {#if active}
                <span class="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-neural-cyan" aria-hidden="true"></span>
              {/if}
              <Icon class="h-4 w-4 shrink-0 {active ? 'text-neural-cyan' : ''}" aria-hidden="true" />
              <span>{item.label}</span>
            </a>
          {/each}
        </div>
      {/each}
    </nav>

    <!-- Footer: быстрые ссылки дублируются в меню выше -->
    <div class="mt-4 border-t border-border/60 pt-4">
      <p class="px-2 text-[10px] text-muted-foreground">
        Поддержка — виджет чата в правом нижнем углу
      </p>
    </div>
  {/if}
</aside>

<style>
  .transition-neural {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
</style>
