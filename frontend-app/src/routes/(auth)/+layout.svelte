<script lang="ts">
  export let params: Record<string, string> = {};

  import '../../app.css';
  import { theme, toggleTheme as storeToggleTheme } from '../../stores/theme';
  import {
    AnimatedBackground,
    NeuralGridBackground,
    StatusBadge
  } from '$lib/components';
  import LogoMark from '$lib/components/LogoMark.svelte';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';
  import {
    Brain,
    LineChart,
    Radar,
    Shield,
    Sparkles,
    Sun,
    Moon
  } from 'lucide-svelte';

  let currentTheme: 'dark' | 'light' = 'dark';

  theme.subscribe((value) => {
    currentTheme = value;
  });

  function toggleTheme() {
    storeToggleTheme();
  }

  const benefits = [
    {
      icon: Radar,
      title: 'Мониторинг конкурентов',
      description: 'Парсинг цен и карточек в реальном времени на Wildberries, Ozon и других площадках.'
    },
    {
      icon: Brain,
      title: 'AI-рекомендации',
      description: 'Умный анализ рынка и подсказки по ценообразованию на основе ваших данных.'
    },
    {
      icon: LineChart,
      title: 'Repricing & аналитика',
      description: 'Автоматическое управление ценами и дашборд с ключевыми метриками продаж.'
    },
    {
      icon: Shield,
      title: 'Безопасность данных',
      description: 'API-ключи шифруются, доступ к данным только у владельца аккаунта.'
    }
  ];
</script>

{#if false}{JSON.stringify(params)}{/if}

<!-- Глобальные utility-классы форм (page-input/page-label) для FormField на auth-страницах -->
<AppPageStyles />

<div class="relative min-h-screen overflow-hidden">
  <AnimatedBackground variant="vivid" />
  <NeuralGridBackground animated opacity={0.45} />

  <!-- Radar sweep — декоративный элемент Command Center -->
  <div class="auth-radar pointer-events-none absolute left-1/2 top-1/2 z-0 h-[min(90vw,640px)] w-[min(90vw,640px)] -translate-x-1/2 -translate-y-1/2 opacity-20 lg:left-[28%]" aria-hidden="true">
    <div class="auth-radar-ring absolute inset-0 rounded-full border border-neural-cyan/20"></div>
    <div class="auth-radar-ring absolute inset-[12%] rounded-full border border-neural-cyan/15"></div>
    <div class="auth-radar-ring absolute inset-[24%] rounded-full border border-neural-cyan/10"></div>
    <div class="auth-radar-sweep absolute inset-0 rounded-full"></div>
  </div>

  <!-- Переключатель темы -->
  <div class="fixed right-4 top-4 z-50">
    <button
      type="button"
      on:click={toggleTheme}
      class="glass-card flex h-11 w-11 items-center justify-center rounded-full border-glow-cyan transition-neural hover:shadow-glow-sm"
      title="Переключить тему"
      aria-label="Переключить тему"
    >
      {#if currentTheme === 'dark'}
        <Sun class="h-5 w-5 text-neural-cyan" />
      {:else}
        <Moon class="h-5 w-5 text-neural-purple" />
      {/if}
    </button>
  </div>

  <div class="relative z-10 flex min-h-screen flex-col lg:flex-row">
    <!-- Блок преимуществ — desktop -->
    <aside class="hidden lg:flex lg:w-[44%] xl:w-[42%] flex-col justify-center px-10 xl:px-16 py-12">
      <div class="max-w-lg space-y-8 animate-slide-in">
        <div class="flex items-center gap-4">
          <LogoMark size="lg" />
          <div>
            <h2 class="text-2xl font-bold text-foreground xl:text-3xl">
              Командный центр<br />
              <span class="text-gradient-ai">для продавцов</span>
            </h2>
          </div>
        </div>

        <p class="text-base leading-relaxed text-muted-foreground">
          MegaSharkAI — AI-платформа для мониторинга конкурентов, умного repricing и управления
          товарами на маркетплейсах из одного кабинета.
        </p>

        <div class="flex flex-wrap gap-2">
          <StatusBadge variant="info" label="Wildberries" />
          <StatusBadge variant="info" label="Ozon" />
          <StatusBadge variant="ai" label="AI Insights" />
        </div>

        <ul class="space-y-5">
          {#each benefits as benefit}
            <li class="flex gap-4">
              <div
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan"
                aria-hidden="true"
              >
                <svelte:component this={benefit.icon} class="h-5 w-5" />
              </div>
              <div>
                <h3 class="font-semibold text-foreground">{benefit.title}</h3>
                <p class="mt-1 text-sm text-muted-foreground">{benefit.description}</p>
              </div>
            </li>
          {/each}
        </ul>

        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <Sparkles class="h-4 w-4 text-neural-purple" aria-hidden="true" />
          <span>Premium AI SaaS для e-commerce команд</span>
        </div>
      </div>
    </aside>

    <!-- Мобильный brand strip -->
    <div class="flex items-center justify-center gap-3 border-b border-border/40 px-4 py-4 lg:hidden">
      <LogoMark size="sm" />
      <div>
        <p class="text-sm font-bold text-gradient">MegaSharkAI</p>
        <p class="text-xs text-muted-foreground">Командный центр</p>
      </div>
    </div>

    <!-- Контент страницы -->
    <main class="flex flex-1 items-center justify-center px-4 py-8 sm:px-6 lg:py-12">
      <slot />
    </main>
  </div>
</div>

<style>
  .auth-radar-ring {
    box-shadow: inset 0 0 40px hsl(var(--neural-cyan) / 0.05);
  }

  .auth-radar-sweep {
    background: conic-gradient(
      from 0deg,
      transparent 0deg,
      hsl(var(--neural-cyan) / 0.12) 30deg,
      transparent 60deg
    );
    animation: authRadarSweep 8s linear infinite;
  }

  @keyframes authRadarSweep {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .auth-radar-sweep {
      animation: none;
      opacity: 0.35;
    }
  }
</style>
