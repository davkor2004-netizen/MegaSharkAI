<script lang="ts">
  import {
    AlertTriangle,
    ExternalLink,
    MessageSquare,
    Shield,
    Star,
    Tag,
    TrendingDown
  } from 'lucide-svelte';
  import GlassCard from '$lib/components/GlassCard.svelte';
  import StatusBadge from '$lib/components/StatusBadge.svelte';
  import { cn } from '$lib/utils/cn';

  type ParsedItem = Record<string, unknown>;

  /** Карточка результата парсинга в стиле Competitor Scanner. */
  export let item: ParsedItem;
  export let className = '';

  const currencyFormatter = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0
  });

  $: name = String(item.name || 'Без названия');
  $: price = Number(item.price) || 0;
  $: oldPrice = Number(item.old_price) || 0;
  $: discount = Number(item.discount) || 0;
  $: rating = Number(item.rating) || 0;
  $: reviews = Number(item.reviews_count) || 0;
  $: sales = Number(item.sales_per_day || item.sales_count) || 0;
  $: brand = String(item.brand || '');
  $: category = String(item.category || '');
  $: productUrl = String(item.url || '');

  $: risk = assessRisk({ price, rating, reviews, discount, name });

  function assessRisk(data: {
    price: number;
    rating: number;
    reviews: number;
    discount: number;
    name: string;
  }): { level: 'low' | 'medium' | 'high'; label: string; hint: string } {
    let score = 0;
    if (!data.price || data.price <= 0) score += 3;
    if (data.rating > 0 && data.rating < 4) score += 2;
    if (data.reviews > 0 && data.reviews < 15) score += 1;
    if (data.discount >= 35) score += 1;
    if (data.name === 'Без названия') score += 2;

    if (score >= 4) {
      return {
        level: 'high',
        label: 'Высокий',
        hint: 'Неполные или слабые сигналы карточки — проверьте данные вручную.'
      };
    }
    if (score >= 2) {
      return {
        level: 'medium',
        label: 'Средний',
        hint: 'Есть пробелы в данных. Используйте как ориентир, не как финальное решение.'
      };
    }
    return {
      level: 'low',
      label: 'Низкий',
      hint: 'Карточка выглядит стабильной для сравнения цены и позиционирования.'
    };
  }

  function riskVariant(level: 'low' | 'medium' | 'high'): 'success' | 'warning' | 'error' {
    if (level === 'low') return 'success';
    if (level === 'medium') return 'warning';
    return 'error';
  }

  function formatPrice(value: number): string {
    if (!value || value <= 0) return '—';
    return currencyFormatter.format(value);
  }

  // Карточка считается частичной, если нет цены или названия.
  $: isPartial = price <= 0 || name === 'Без названия';
</script>

<GlassCard className={cn('relative overflow-hidden', className)} glow padding="lg">
  <div
    class="pointer-events-none absolute inset-0 bg-gradient-to-br from-neural-cyan/5 via-transparent to-neural-purple/5"
    aria-hidden="true"
  ></div>

  <div class="relative space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0 flex-1">
        <StatusBadge variant={isPartial ? 'warning' : 'info'} label={isPartial ? 'Partial scan' : 'Target locked'} dot={false} className="mb-3" />
        <h3 class="break-words text-xl font-bold leading-snug text-foreground sm:text-2xl">{name}</h3>
        {#if brand || category}
          <p class="mt-2 break-words text-sm text-muted-foreground">
            {#if brand}{brand}{/if}
            {#if brand && category} · {/if}
            {#if category}{category}{/if}
          </p>
        {/if}
      </div>
      <StatusBadge variant={riskVariant(risk.level)} label="Риск: {risk.label}" />
    </div>

    {#if isPartial}
      <div class="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
        <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <p>Данные извлечены частично. Проверьте карточку или попробуйте повторить сканирование.</p>
      </div>
    {/if}

    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <div class="min-w-0 rounded-xl border border-neural-cyan/20 bg-neural-cyan/5 p-4">
        <div class="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Tag class="h-3.5 w-3.5 text-neural-cyan" aria-hidden="true" />
          Цена
        </div>
        <p class="min-w-0 break-words font-bold text-neural-cyan {price > 0 ? 'text-2xl' : 'text-lg'}">{formatPrice(price)}</p>
        {#if oldPrice > 0}
          <p class="mt-1 break-words text-xs text-muted-foreground line-through">{formatPrice(oldPrice)}</p>
        {/if}
      </div>

      <div class="min-w-0 rounded-xl border border-border/60 bg-background/30 p-4">
        <div class="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Star class="h-3.5 w-3.5 text-warning" aria-hidden="true" />
          Рейтинг
        </div>
        <p class="text-2xl font-bold text-foreground">{rating > 0 ? rating.toFixed(1) : '—'}</p>
        <p class="mt-1 text-xs text-muted-foreground">{rating > 0 ? 'доверие к карточке' : 'нет данных'}</p>
      </div>

      <div class="min-w-0 rounded-xl border border-border/60 bg-background/30 p-4">
        <div class="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <MessageSquare class="h-3.5 w-3.5 text-neural-purple" aria-hidden="true" />
          Отзывы
        </div>
        <p class="text-2xl font-bold text-foreground">{reviews > 0 ? reviews : '—'}</p>
        <p class="mt-1 text-xs text-muted-foreground">{reviews > 0 ? 'социальное доказательство' : 'нет данных'}</p>
      </div>

      <div class="min-w-0 rounded-xl border border-border/60 bg-background/30 p-4">
        <div class="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Shield class="h-3.5 w-3.5" aria-hidden="true" />
          Карточка
        </div>
        <p class="break-words text-sm font-semibold text-foreground">
          {price > 0 && name !== 'Без названия' ? 'Данные получены' : 'Частично'}
        </p>
        {#if discount > 0}
          <p class="mt-1 flex items-center gap-1 text-xs text-warning">
            <TrendingDown class="h-3 w-3" aria-hidden="true" />
            Скидка {discount}%
          </p>
        {/if}
      </div>
    </div>

    {#if sales > 0}
      <p class="text-sm text-muted-foreground">
        Продажи/день: <span class="font-medium text-foreground">{sales}</span>
      </p>
    {/if}

    <div class="rounded-xl border border-border/60 bg-background/25 p-4 text-sm text-muted-foreground">
      <div class="flex items-start gap-2">
        <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
        <p>{risk.hint}</p>
      </div>
    </div>

    {#if productUrl}
      <a
        href={productUrl}
        target="_blank"
        rel="noopener noreferrer"
        class="btn-ghost-neural inline-flex w-fit text-sm"
      >
        <ExternalLink class="h-4 w-4" aria-hidden="true" />
        Открыть карточку конкурента
      </a>
    {/if}
  </div>
</GlassCard>
