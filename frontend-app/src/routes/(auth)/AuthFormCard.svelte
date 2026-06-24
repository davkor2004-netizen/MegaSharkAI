<script lang="ts">
  import LogoMark from '$lib/components/LogoMark.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';

  /** Обёртка формы авторизации в glass-карточке. */
  export let title: string;
  export let subtitle = '';
  export let maxWidth: 'md' | 'lg' | '2xl' = 'md';
  export let eyebrow = 'MegaSharkAI';

  const maxWidthClasses = {
    md: 'max-w-md',
    lg: 'max-w-lg',
    '2xl': 'max-w-2xl'
  };
</script>

<div class="w-full {maxWidthClasses[maxWidth]} animate-fade-in">
  <div class="glass-card glass-card-glow rounded-2xl p-6 sm:p-8">
    <div class="mb-8 text-center">
      <div class="mb-4 flex items-center justify-center">
        <LogoMark size="md" />
      </div>
      <StatusBadge variant="ai" label={eyebrow} dot={false} className="mb-3" />
      <h1 class="text-2xl font-bold tracking-tight text-gradient sm:text-3xl">{title}</h1>
      {#if subtitle}
        <p class="mt-2 text-sm text-muted-foreground sm:text-base">{subtitle}</p>
      {/if}
    </div>

    <slot />

    {#if $$slots.footer}
      <div class="mt-6 border-t border-border/60 pt-6 text-center">
        <slot name="footer" />
      </div>
    {/if}
  </div>
</div>

<style>
  /* Локальные стили auth-форм без @apply — совместимо с postcss в Svelte. */
  :global(.auth-input) {
    width: 100%;
    border-radius: 0.5rem;
    border: 1px solid hsl(var(--input) / 0.8);
    background: hsl(var(--background) / 0.4);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--foreground));
    backdrop-filter: blur(8px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  :global(.auth-input::placeholder) {
    color: hsl(var(--muted-foreground) / 0.6);
  }

  :global(.auth-input:focus) {
    border-color: hsl(var(--neural-cyan) / 0.5);
    outline: none;
    box-shadow: 0 0 0 2px hsl(var(--neural-cyan) / 0.2);
  }

  :global(.auth-input-error) {
    border-color: hsl(var(--destructive) / 0.5);
    box-shadow: 0 0 0 2px hsl(var(--destructive) / 0.15);
  }

  :global(.auth-label) {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: hsl(var(--foreground));
  }

  :global(.auth-alert-error) {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid hsl(var(--destructive) / 0.3);
    background: hsl(var(--destructive) / 0.1);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--destructive));
  }

  :global(.auth-alert-success) {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid hsl(var(--success) / 0.3);
    background: hsl(var(--success) / 0.1);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--success));
  }

  :global(.auth-alert-warning) {
    border-radius: 0.5rem;
    border: 1px solid hsl(var(--warning) / 0.3);
    background: hsl(var(--warning) / 0.1);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--warning));
  }

  :global(.auth-btn-primary) {
    display: inline-flex;
    width: 100%;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: hsl(var(--primary-foreground));
    background: linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--neural-blue)) 100%);
    box-shadow: var(--shadow-glow-sm);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  :global(.auth-btn-primary:hover:not(:disabled)) {
    filter: brightness(1.08);
    box-shadow: var(--shadow-glow-md);
  }

  :global(.auth-btn-primary:disabled) {
    cursor: not-allowed;
    opacity: 0.5;
  }

  :global(.auth-btn-secondary) {
    display: inline-flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    border-radius: 0.5rem;
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: hsl(var(--foreground));
    background: hsl(var(--glass-bg));
    border: 1px solid hsl(var(--glass-border));
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  :global(.auth-btn-secondary:hover) {
    border-color: hsl(var(--neural-cyan) / 0.35);
    box-shadow: var(--shadow-glow-sm);
  }

  :global(.auth-link) {
    font-weight: 500;
    color: hsl(var(--neural-cyan));
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  :global(.auth-link:hover) {
    color: hsl(var(--neural-cyan) / 0.8);
    text-decoration: underline;
  }
</style>
