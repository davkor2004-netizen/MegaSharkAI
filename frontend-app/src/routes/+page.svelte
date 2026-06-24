<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount } from 'svelte';
  import LogoMark from '$lib/components/LogoMark.svelte';
  
  onMount(() => {
    // Перенаправление на дашборд или логин
    window.location.href = '/dashboard';
  });
</script>

{#if false}{JSON.stringify(params)}{/if}

<div class="flex min-h-screen items-center justify-center">
  <div class="text-center">
    <div class="mb-4 flex justify-center">
      <LogoMark size="lg" />
    </div>
    <h1 class="text-4xl font-bold text-gradient">MegaSharkAI</h1>
    <p class="mt-4 text-lg text-muted-foreground">Загрузка...</p>
  </div>
</div>
