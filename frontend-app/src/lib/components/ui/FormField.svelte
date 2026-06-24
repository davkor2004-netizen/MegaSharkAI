<script lang="ts">
  import { cn } from '$lib/utils/cn';

  /**
   * Обёртка поля формы: label + control (slot) + hint/error.
   *
   * Использование:
   *   <FormField label="Email" required error={emailError} let:id let:invalid>
   *     <input {id} class={invalid ? 'page-input page-input-error' : 'page-input'} bind:value={email} />
   *   </FormField>
   */
  export let label = '';
  export let hint = '';
  export let error = '';
  export let required = false;
  export let id: string | undefined = undefined;
  export let className = '';

  // Стабильный id для связи label↔control и aria-describedby.
  const uid = `ff-${Math.random().toString(36).slice(2, 9)}`;
  $: controlId = id ?? uid;
  $: invalid = Boolean(error);
  $: describedById = invalid ? `${controlId}-error` : hint ? `${controlId}-hint` : undefined;
</script>

<div class={cn('space-y-2', className)}>
  {#if label}
    <label for={controlId} class="page-label">
      {label}
      {#if required}
        <span class="text-destructive" aria-hidden="true">*</span>
      {/if}
    </label>
  {/if}

  <slot {controlId} {invalid} {describedById} />

  {#if invalid}
    <p id={`${controlId}-error`} class="text-xs text-destructive" role="alert">{error}</p>
  {:else if hint}
    <p id={`${controlId}-hint`} class="text-xs text-muted-foreground">{hint}</p>
  {/if}
</div>
