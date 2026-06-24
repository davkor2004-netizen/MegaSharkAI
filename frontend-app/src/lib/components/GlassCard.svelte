<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /** Стеклянная карточка Command Center с опциональным свечением. */
  export let className = '';
  export let glow = false;
  export let hoverable = false;
  export let padding: 'none' | 'sm' | 'md' | 'lg' = 'md';

  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8'
  };
</script>

<div
  class={cn(
    'glass-card rounded-xl transition-neural',
    paddingClasses[padding],
    glow && 'glass-card-glow',
    hoverable && 'hover:border-glow-cyan hover:shadow-glow-sm cursor-default',
    className
  )}
  {...$$restProps}
>
  <slot />
</div>
