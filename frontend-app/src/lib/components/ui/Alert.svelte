<script lang="ts">
  import type { ComponentType } from 'svelte';
  import { CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-svelte';
  import { cn } from '$lib/utils/cn';

  type AlertVariant = 'success' | 'error' | 'warning' | 'info';

  /** Информационный блок (success/error/warning/info). */
  export let variant: AlertVariant = 'info';
  export let title = '';
  /** Показывать иконку слева. */
  export let icon = true;
  export let className = '';

  const variantClass: Record<AlertVariant, string> = {
    success: 'border-success/30 bg-success/10 text-success',
    error: 'border-destructive/30 bg-destructive/10 text-destructive',
    warning: 'border-warning/30 bg-warning/10 text-warning',
    info: 'border-neural-blue/30 bg-neural-blue/10 text-neural-blue'
  };

  const variantIcon: Record<AlertVariant, ComponentType> = {
    success: CheckCircle2,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info
  };

  $: role = variant === 'error' || variant === 'warning' ? 'alert' : 'status';
</script>

<div
  {role}
  class={cn('flex gap-3 rounded-xl border px-4 py-3 text-sm', variantClass[variant], className)}
>
  {#if icon}
    <svelte:component this={variantIcon[variant]} class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
  {/if}
  <div class="min-w-0 flex-1 space-y-0.5">
    {#if title}
      <p class="font-semibold">{title}</p>
    {/if}
    {#if $$slots.default}
      <div class="opacity-90">
        <slot />
      </div>
    {/if}
  </div>
</div>
