<script lang="ts">
  /** Radar-анимация во время сканирования конкурента. */
  export let label = 'Сканирование конкурента...';
  export let sublabel = 'MegaSharkAI анализирует карточку на маркетплейсе';
</script>

<div class="flex flex-col items-center justify-center py-10" role="status" aria-live="polite">
  <div class="relative flex h-48 w-48 items-center justify-center" aria-hidden="true">
    <div class="absolute inset-0 rounded-full border border-neural-cyan/20"></div>
    <div class="absolute inset-[14%] rounded-full border border-neural-cyan/15"></div>
    <div class="absolute inset-[28%] rounded-full border border-neural-cyan/10"></div>
    <div class="absolute inset-[42%] rounded-full border border-neural-purple/15"></div>

    <div class="scan-radar-sweep absolute inset-0 rounded-full"></div>

    <div class="scan-radar-pulse absolute h-4 w-4 rounded-full bg-neural-cyan shadow-glow-sm"></div>

    <div class="relative z-10 text-center">
      <p class="text-xs font-semibold uppercase tracking-[0.25em] text-neural-cyan">Shark Radar</p>
      <p class="mt-1 text-[10px] text-muted-foreground">SCAN</p>
    </div>
  </div>

  <p class="mt-6 text-sm font-medium text-foreground">{label}</p>
  <p class="mt-1 max-w-sm text-center text-xs text-muted-foreground">{sublabel}</p>

  <div class="mt-4 flex gap-1.5">
    {#each [0, 1, 2] as i}
      <span
        class="h-1.5 w-1.5 rounded-full bg-neural-cyan scan-dot"
        style="animation-delay: {i * 0.2}s"
      ></span>
    {/each}
  </div>
</div>

<style>
  .scan-radar-sweep {
    background: conic-gradient(
      from 0deg,
      transparent 0deg,
      hsl(var(--neural-cyan) / 0.22) 35deg,
      transparent 70deg
    );
    animation: scanRadarRotate 2.2s linear infinite;
  }

  .scan-radar-pulse {
    animation: scanPulse 1.6s ease-in-out infinite;
  }

  .scan-dot {
    animation: scanDot 1.2s ease-in-out infinite;
  }

  @keyframes scanRadarRotate {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes scanPulse {
    0%,
    100% {
      transform: scale(0.85);
      opacity: 0.5;
    }
    50% {
      transform: scale(1.15);
      opacity: 1;
    }
  }

  @keyframes scanDot {
    0%,
    100% {
      opacity: 0.35;
      transform: translateY(0);
    }
    50% {
      opacity: 1;
      transform: translateY(-3px);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .scan-radar-sweep,
    .scan-radar-pulse,
    .scan-dot {
      animation: none !important;
    }
  }
</style>
