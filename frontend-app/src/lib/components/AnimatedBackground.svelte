<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /** Анимированный океанический фон с орбами свечения. */
  export let className = '';
  export let variant: 'subtle' | 'vivid' = 'subtle';
</script>

<div
  class={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}
  aria-hidden="true"
>
  <div class="absolute inset-0 gradient-ocean opacity-90"></div>

  <div
    class={cn(
      'absolute -left-1/4 top-0 h-[420px] w-[420px] rounded-full bg-neural-cyan/20 blur-[100px]',
      variant === 'vivid' ? 'opacity-70 animate-float-orb' : 'opacity-40'
    )}
  ></div>

  <div
    class={cn(
      'absolute -right-1/4 top-1/4 h-[360px] w-[360px] rounded-full bg-neural-purple/20 blur-[90px]',
      variant === 'vivid' ? 'opacity-60 animate-float-orb' : 'opacity-30'
    )}
    style="animation-delay: -4s"
  ></div>

  <div
    class={cn(
      'absolute bottom-0 left-1/3 h-[280px] w-[280px] rounded-full bg-neural-blue/15 blur-[80px]',
      variant === 'vivid' ? 'opacity-50 animate-pulse-glow' : 'opacity-25'
    )}
  ></div>

  {#if variant === 'vivid'}
    <div
      class="absolute inset-0 opacity-30"
      style="background: radial-gradient(circle at 50% 120%, hsl(var(--neural-cyan) / 0.15), transparent 60%)"
    ></div>
  {/if}
</div>
