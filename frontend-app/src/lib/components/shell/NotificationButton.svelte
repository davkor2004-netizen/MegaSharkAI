<script lang="ts">
  import { Bell } from 'lucide-svelte';
  import { cn } from '$lib/utils/cn';

  /** Кнопка уведомлений в Topbar. */
  export let unreadCount = 0;
  export let className = '';
</script>

<a
  href="/notifications"
  class={cn(
    'relative flex h-10 w-10 items-center justify-center rounded-xl border border-border/80 bg-card/60 text-muted-foreground transition-neural hover:border-neural-cyan/30 hover:text-neural-cyan hover:shadow-glow-sm',
    className
  )}
  title="Уведомления"
  aria-label={unreadCount > 0 ? `Уведомления: ${unreadCount} непрочитанных` : 'Уведомления'}
>
  <Bell class="h-5 w-5" aria-hidden="true" />
  {#if unreadCount > 0}
    <span
      class="absolute -right-1 -top-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground"
    >
      {unreadCount > 99 ? '99+' : unreadCount}
    </span>
  {/if}
</a>

<style>
  .transition-neural {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
</style>
