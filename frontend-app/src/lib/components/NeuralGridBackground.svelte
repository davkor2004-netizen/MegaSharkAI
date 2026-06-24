<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /** Фоновая нейро-сетка для Command Center. */
  export let className = '';
  export let animated = true;
  export let opacity = 0.6;
</script>

<div
  class={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}
  aria-hidden="true"
>
  <div
    class={cn('absolute inset-0 neural-grid', animated && 'animate-neural-pulse')}
    style="opacity: {opacity}"
  ></div>

  <!-- Узлы сетки -->
  <svg class="absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <radialGradient id="neural-node-glow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="hsl(var(--neural-cyan))" stop-opacity="0.8" />
        <stop offset="100%" stop-color="hsl(var(--neural-cyan))" stop-opacity="0" />
      </radialGradient>
    </defs>
    {#each [
      { cx: '12%', cy: '18%' },
      { cx: '78%', cy: '22%' },
      { cx: '45%', cy: '55%' },
      { cx: '88%', cy: '72%' },
      { cx: '22%', cy: '80%' },
      { cx: '62%', cy: '88%' }
    ] as node}
      <circle cx={node.cx} cy={node.cy} r="3" fill="url(#neural-node-glow)" opacity="0.5" />
    {/each}
  </svg>

  <!-- Диагональные связи -->
  <svg class="absolute inset-0 h-full w-full opacity-20" xmlns="http://www.w3.org/2000/svg">
    <line x1="12%" y1="18%" x2="45%" y2="55%" stroke="hsl(var(--neural-cyan))" stroke-width="0.5" />
    <line x1="78%" y1="22%" x2="45%" y2="55%" stroke="hsl(var(--neural-purple))" stroke-width="0.5" />
    <line x1="45%" y1="55%" x2="88%" y2="72%" stroke="hsl(var(--neural-cyan))" stroke-width="0.5" />
    <line x1="22%" y1="80%" x2="45%" y2="55%" stroke="hsl(var(--neural-blue))" stroke-width="0.5" />
    <line x1="62%" y1="88%" x2="88%" y2="72%" stroke="hsl(var(--neural-purple))" stroke-width="0.5" />
  </svg>
</div>
