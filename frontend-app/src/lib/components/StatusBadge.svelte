<script lang="ts">
  import { cn } from '$lib/utils/cn';

  type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'ai';

  /** Статусный бейдж Command Center. */
  export let label: string;
  export let variant: BadgeVariant = 'neutral';
  export let dot = true;
  export let className = '';

  const variantClasses: Record<BadgeVariant, string> = {
    success: 'border-success/30 bg-success/10 text-success',
    warning: 'border-warning/30 bg-warning/10 text-warning',
    error: 'border-destructive/30 bg-destructive/10 text-destructive',
    info: 'border-neural-blue/30 bg-neural-blue/10 text-neural-blue',
    neutral: 'border-border bg-muted/50 text-muted-foreground',
    ai: 'border-neural-purple/30 bg-neural-purple/10 text-neural-purple'
  };

  const dotClasses: Record<BadgeVariant, string> = {
    success: 'bg-success',
    warning: 'bg-warning',
    error: 'bg-destructive',
    info: 'bg-neural-blue',
    neutral: 'bg-muted-foreground',
    ai: 'bg-neural-purple'
  };
</script>

<span
  class={cn(
    'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
    variantClasses[variant],
    className
  )}
>
  {#if dot}
    <span class={cn('status-dot', dotClasses[variant])} aria-hidden="true"></span>
  {/if}
  {label}
</span>
