<script lang="ts">
  import { Loader2 } from 'lucide-svelte';
  import { cn } from '$lib/utils/cn';

  type ButtonVariant = 'neural' | 'ghost' | 'danger' | 'success' | 'warning' | 'subtle';
  type ButtonSize = 'sm' | 'md' | 'lg';

  /** Универсальная кнопка Command Center. */
  export let variant: ButtonVariant = 'neural';
  export let size: ButtonSize = 'md';
  export let type: 'button' | 'submit' | 'reset' = 'button';
  export let loading = false;
  export let disabled = false;
  export let fullWidth = false;
  export let className = '';

  // Базовый класс варианта берётся из дизайн-системы (app.css),
  // чтобы цвета/градиенты/состояния были консистентны со всем проектом.
  const variantClass: Record<ButtonVariant, string> = {
    neural: 'btn-neural',
    ghost: 'btn-ghost-neural',
    danger: 'btn-danger',
    success: 'btn-success',
    warning: 'btn-warning',
    subtle: 'btn-subtle'
  };

  // Размеры переопределяют padding/высоту базового класса (twMerge снимает конфликты).
  const sizeClass: Record<ButtonSize, string> = {
    sm: 'h-8 px-3 text-xs gap-1.5',
    md: 'h-10 px-4 text-sm gap-2',
    lg: 'h-12 px-6 text-base gap-2'
  };

  const spinnerSize: Record<ButtonSize, string> = {
    sm: 'h-3.5 w-3.5',
    md: 'h-4 w-4',
    lg: 'h-5 w-5'
  };

  $: isDisabled = disabled || loading;
</script>

<button
  {type}
  disabled={isDisabled}
  aria-busy={loading}
  class={cn(
    variantClass[variant],
    sizeClass[size],
    'focus-ring',
    fullWidth && 'w-full',
    className
  )}
  on:click
  {...$$restProps}
>
  {#if loading}
    <Loader2 class={cn('animate-spin', spinnerSize[size])} aria-hidden="true" />
  {/if}
  <slot />
</button>
