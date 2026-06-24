<script lang="ts">
  /** Логотип MegaSharkAI (фавикон компании). */
  export let size: 'sm' | 'md' | 'lg' = 'md';

  const sizeClasses = {
    sm: 'h-12 w-12',
    md: 'h-16 w-16',
    lg: 'h-20 w-20'
  };
</script>

<img
  src="/favicon-Photoroom.png"
  alt="MegaSharkAI"
  class="{sizeClasses[size]} rounded-2xl border border-primary/30 bg-background/40 object-contain p-1 shadow-glow"
  width="80"
  height="80"
  decoding="async"
/>
