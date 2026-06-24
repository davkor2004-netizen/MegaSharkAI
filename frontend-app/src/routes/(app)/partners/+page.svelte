<script lang="ts">
  import {
    ArrowRight,
    Building2,
    Check,
    Globe,
    Layers,
    Mail,
    MessageCircle,
    Palette,
    Radar,
    Send,
    Shield,
    Sparkles,
    Users,
    Zap
  } from 'lucide-svelte';
  import type { ComponentType } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    Alert,
    Button,
    GlassCard,
    PageHeader,
    StatusBadge
  } from '$lib/components';

  const PARTNER_EMAIL = 'partner@megasharkai.online';

  interface AudienceItem {
    title: string;
    description: string;
    icon: ComponentType;
    badge: string;
    badgeVariant: 'info' | 'ai' | 'success' | 'neutral';
  }

  interface BenefitItem {
    title: string;
    description: string;
    icon: ComponentType;
  }

  interface StepItem {
    step: number;
    title: string;
    description: string;
  }

  const audience: AudienceItem[] = [
    {
      title: 'Маркетплейсы и SaaS',
      description: 'White-label AI-ассистент под вашим брендом для продавцов на площадке.',
      icon: Building2,
      badge: 'White-label',
      badgeVariant: 'ai'
    },
    {
      title: 'E-commerce агентства',
      description: 'Инструменты мониторинга, AI и аналитики для клиентов агентства.',
      icon: Users,
      badge: 'Agency',
      badgeVariant: 'info'
    },
    {
      title: 'Системные интеграторы',
      description: 'API и встраиваемый виджет для подключения к существующим продуктам.',
      icon: Layers,
      badge: 'Integration',
      badgeVariant: 'success'
    }
  ];

  const benefits: BenefitItem[] = [
    {
      title: 'Быстрый запуск',
      description: 'Интеграция с вашей платформой за 2–4 недели.',
      icon: Zap
    },
    {
      title: 'Ваш бренд',
      description: 'Полностью white-label: дизайн, домен и UX под ваш продукт.',
      icon: Palette
    },
    {
      title: 'Поддержка',
      description: 'Техническая поддержка, обновления и сопровождение включены.',
      icon: Shield
    }
  ];

  const steps: StepItem[] = [
    {
      step: 1,
      title: 'Связь и обсуждение',
      description: 'Короткий созвон или переписка — разбираем задачу, аудиторию и формат партнёрства.'
    },
    {
      step: 2,
      title: 'Пилот и настройка',
      description: 'Согласуем white-label, интеграции и сценарии для ваших пользователей.'
    },
    {
      step: 3,
      title: 'Запуск',
      description: 'Внедряем AI-ассистент под вашим брендом и подключаем нужные модули.'
    },
    {
      step: 4,
      title: 'Сопровождение',
      description: 'Обновления продукта, поддержка и развитие партнёрского решения.'
    }
  ];

  const partnerGets: string[] = [
    'AI-генерация названий и описаний товаров',
    'Парсинг маркетплейсов и мониторинг конкурентов',
    'Анализ конкурентов и умное ценообразование',
    'Личный кабинет продавца под вашим брендом',
    'API и встраиваемый виджет для интеграции',
    'Техническая поддержка и регулярные обновления'
  ];

  function openPartnerEmail(subject = 'Партнёрство MegaSharkAI'): void {
    window.location.href = `mailto:${PARTNER_EMAIL}?subject=${encodeURIComponent(subject)}`;
  }

  function openWhiteLabelInquiry(): void {
    openPartnerEmail('White-label внедрение MegaSharkAI');
  }
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Shark Partners"
    title="Партнёрская программа"
    subtitle="White-label AI-ассистент для маркетплейсов, агентств и интеграторов"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="ai" label="B2B" dot={false} />
      <StatusBadge variant="info" label="White-label" dot={false} />
      <StatusBadge variant="neutral" label="Early access" dot />
    </svelte:fragment>
  </PageHeader>

  <Alert variant="info" title="Заявки через email">
    Онлайн-форма партнёрства пока не подключена к backend. Напишите на
    <button
      type="button"
      class="font-medium text-neural-cyan underline-offset-2 hover:underline"
      on:click={() => openPartnerEmail()}
    >
      {PARTNER_EMAIL}
    </button>
    — мы ответим в течение 24 часов.
  </Alert>

  <GlassCard glow padding="lg" className="text-center">
    <div class="mx-auto flex max-w-2xl flex-col items-center gap-4">
      <div class="flex h-14 w-14 items-center justify-center rounded-2xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
        <Radar class="h-7 w-7" aria-hidden="true" />
      </div>
      <div class="space-y-2">
        <h2 class="text-2xl font-bold text-foreground sm:text-3xl">
          MegaSharkAI для вашей платформы
        </h2>
        <p class="text-base text-muted-foreground sm:text-lg">
          Командный центр под вашим брендом — мониторинг, AI и аналитика для продавцов маркетплейсов.
        </p>
      </div>
      <div class="flex flex-wrap justify-center gap-2 pt-1">
        <StatusBadge variant="ai" label="2–4 недели до запуска" dot={false} />
        <StatusBadge variant="success" label="Полный white-label" dot={false} />
      </div>
    </div>
  </GlassCard>

  <section class="space-y-4">
    <div class="space-y-1">
      <h2 class="text-lg font-semibold text-foreground">Для кого</h2>
      <p class="text-sm text-muted-foreground">
        Партнёрская программа для команд, которые масштабируют инструменты продавцов.
      </p>
    </div>
    <div class="grid gap-4 md:grid-cols-3">
      {#each audience as item}
        <GlassCard hoverable padding="lg" className="relative flex flex-col gap-4">
          <div class="flex items-start justify-between gap-3">
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
              <svelte:component this={item.icon} class="h-5 w-5" aria-hidden="true" />
            </div>
            <StatusBadge variant={item.badgeVariant} label={item.badge} dot={false} />
          </div>
          <div class="space-y-2">
            <h3 class="font-semibold text-foreground">{item.title}</h3>
            <p class="text-sm text-muted-foreground">{item.description}</p>
          </div>
        </GlassCard>
      {/each}
    </div>
  </section>

  <section class="space-y-4">
    <div class="space-y-1">
      <h2 class="text-lg font-semibold text-foreground">Преимущества</h2>
      <p class="text-sm text-muted-foreground">
        Запуск партнёрского решения без долгой разработки с нуля.
      </p>
    </div>
    <div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
      {#each benefits as item}
        <GlassCard padding="lg" className="text-center">
          <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-neural-purple/20 bg-neural-purple/10 text-neural-purple">
            <svelte:component this={item.icon} class="h-6 w-6" aria-hidden="true" />
          </div>
          <h3 class="font-semibold text-foreground">{item.title}</h3>
          <p class="mt-2 text-sm text-muted-foreground">{item.description}</p>
        </GlassCard>
      {/each}
    </div>
  </section>

  <GlassCard glow padding="lg" className="space-y-6">
    <div class="flex items-center gap-2">
      <Users class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
      <h2 class="text-lg font-semibold text-foreground">Как это работает</h2>
    </div>
    <ol class="grid gap-4 sm:grid-cols-2">
      {#each steps as item}
        <li class="surface flex gap-4 rounded-xl p-4">
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-neural-cyan/30 bg-neural-cyan/10 text-sm font-bold text-neural-cyan">
            {item.step}
          </span>
          <div class="min-w-0 space-y-1">
            <h3 class="font-medium text-foreground">{item.title}</h3>
            <p class="text-sm text-muted-foreground">{item.description}</p>
          </div>
        </li>
      {/each}
    </ol>
  </GlassCard>

  <GlassCard padding="lg" className="space-y-5">
    <div class="flex items-center gap-2">
      <Sparkles class="h-5 w-5 text-neural-purple" aria-hidden="true" />
      <h2 class="text-lg font-semibold text-foreground">Что получает партнёр</h2>
    </div>
    <ul class="grid gap-3 sm:grid-cols-2">
      {#each partnerGets as feature}
        <li class="flex items-start gap-2 text-sm text-muted-foreground">
          <Check class="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
          <span>{feature}</span>
        </li>
      {/each}
    </ul>
  </GlassCard>

  <GlassCard glow padding="lg" className="space-y-6">
    <div class="mx-auto max-w-xl space-y-3 text-center">
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
        <Send class="h-6 w-6" aria-hidden="true" />
      </div>
      <h2 class="text-xl font-bold text-foreground sm:text-2xl">Обсудить партнёрство</h2>
      <p class="text-sm text-muted-foreground">
        Расскажите о платформе, аудитории и задачах — подберём формат white-label или интеграции.
      </p>
    </div>
    <div class="flex flex-col gap-3 sm:flex-row sm:justify-center">
      <Button variant="neural" size="lg" fullWidth className="sm:w-auto sm:min-w-[240px]" on:click={openWhiteLabelInquiry}>
        <Mail class="h-5 w-5" aria-hidden="true" />
        Написать на {PARTNER_EMAIL}
      </Button>
      <Button variant="ghost" size="lg" fullWidth className="sm:w-auto" on:click={() => goto('/dashboard')}>
        <ArrowRight class="h-5 w-5" aria-hidden="true" />
        На дашборд
      </Button>
    </div>
  </GlassCard>

  <GlassCard padding="lg" className="space-y-6">
    <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
      <MessageCircle class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
      Контакты
    </h2>
    <div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
      <div class="surface space-y-3 rounded-xl p-4">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-neural-cyan/10 p-2 text-neural-cyan">
            <Mail class="h-5 w-5" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <p class="font-medium text-foreground">Email</p>
            <p class="truncate text-sm text-muted-foreground">{PARTNER_EMAIL}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" fullWidth on:click={() => openPartnerEmail()}>
          Написать
        </Button>
      </div>

      <div class="surface space-y-3 rounded-xl p-4">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-neural-cyan/10 p-2 text-neural-cyan">
            <Globe class="h-5 w-5" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <p class="font-medium text-foreground">Сайт</p>
            <p class="truncate text-sm text-muted-foreground">megasharkai.online</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          fullWidth
          on:click={() => window.open('https://megasharkai.online', '_blank', 'noopener,noreferrer')}
        >
          Открыть сайт
        </Button>
      </div>

      <div class="surface space-y-3 rounded-xl p-4 sm:col-span-2 md:col-span-1">
        <div class="flex items-center gap-3">
          <div class="rounded-lg bg-neural-cyan/10 p-2 text-neural-cyan">
            <MessageCircle class="h-5 w-5" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <p class="font-medium text-foreground">Telegram</p>
            <p class="truncate text-sm text-muted-foreground">@founderMegaSharkAI</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          fullWidth
          on:click={() => window.open('https://t.me/founderMegaSharkAI', '_blank', 'noopener,noreferrer')}
        >
          Написать в Telegram
        </Button>
      </div>
    </div>
  </GlassCard>
</div>
