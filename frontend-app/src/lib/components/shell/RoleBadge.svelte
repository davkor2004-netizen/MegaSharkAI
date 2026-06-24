<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /** Бейдж роли пользователя в AppShell. */
  export let isSuperuser = false;
  export let isMarketplaceSeller = false;
  export let className = '';

  $: role = isSuperuser
    ? { label: 'Admin', variant: 'admin' as const }
    : isMarketplaceSeller
      ? { label: 'Продавец', variant: 'seller' as const }
      : { label: 'Пользователь', variant: 'user' as const };

  const variantClasses = {
    admin: 'border-neural-purple/35 bg-neural-purple/15 text-neural-purple',
    seller: 'border-neural-cyan/35 bg-neural-cyan/10 text-neural-cyan',
    user: 'border-border bg-muted/40 text-muted-foreground'
  };
</script>

<span
  class={cn(
    'inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
    variantClasses[role.variant],
    className
  )}
>
  {role.label}
</span>
