<style>
  /* Общие utility-классы страниц личного кабинета (Command Center). */
  :global(.page-input) {
    width: 100%;
    border-radius: 0.75rem;
    border: 1px solid hsl(var(--input) / 0.8);
    background: hsl(var(--background) / 0.45);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--foreground));
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  :global(.page-input:focus) {
    border-color: hsl(var(--neural-cyan) / 0.5);
    outline: none;
    box-shadow: 0 0 0 2px hsl(var(--neural-cyan) / 0.2);
  }

  :global(.page-input-error) {
    border-color: hsl(var(--destructive) / 0.5);
    box-shadow: 0 0 0 2px hsl(var(--destructive) / 0.15);
  }

  :global(.page-label) {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: hsl(var(--foreground));
  }

  :global(.page-select) {
    width: 100%;
    border-radius: 0.75rem;
    border: 1px solid hsl(var(--input) / 0.8);
    background: hsl(var(--background) / 0.45);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--foreground));
  }

  :global(.page-textarea) {
    width: 100%;
    min-height: 6rem;
    border-radius: 0.75rem;
    border: 1px solid hsl(var(--input) / 0.8);
    background: hsl(var(--background) / 0.45);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--foreground));
    resize: vertical;
  }

  :global(.page-alert-success) {
    border-radius: 0.75rem;
    border: 1px solid hsl(var(--success) / 0.3);
    background: hsl(var(--success) / 0.1);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--success));
  }

  :global(.page-alert-error) {
    border-radius: 0.75rem;
    border: 1px solid hsl(var(--destructive) / 0.3);
    background: hsl(var(--destructive) / 0.1);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: hsl(var(--destructive));
  }

  :global(.page-table) {
    width: 100%;
    min-width: 640px;
    font-size: 0.875rem;
  }

  :global(.page-table thead) {
    text-align: left;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: hsl(var(--muted-foreground));
  }

  :global(.page-table th) {
    padding-bottom: 0.75rem;
    font-weight: 500;
  }

  :global(.page-table td) {
    padding: 0.75rem 0.5rem 0.75rem 0;
    border-top: 1px solid hsl(var(--border) / 0.5);
  }

  :global(.page-table tbody tr) {
    transition: background 0.2s ease;
  }

  :global(.page-table tbody tr:hover) {
    background: hsl(var(--background) / 0.35);
  }

  :global(.page-tab) {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    border-radius: 0.75rem;
    padding: 0.625rem 1rem;
    font-size: 0.875rem;
    font-weight: 600;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  :global(.page-tab-active) {
    background: linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--neural-blue)) 100%);
    color: hsl(var(--primary-foreground));
    box-shadow: var(--shadow-glow-sm);
  }

  :global(.page-tab-inactive) {
    color: hsl(var(--muted-foreground));
  }

  :global(.page-tab-inactive:hover) {
    background: hsl(var(--background) / 0.45);
    color: hsl(var(--foreground));
  }
</style>
