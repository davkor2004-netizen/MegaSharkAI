<script lang="ts">
  import { CheckCircle2, Circle } from 'lucide-svelte';
  import GlassCard from '$lib/components/GlassCard.svelte';
  import { cn } from '$lib/utils/cn';

  type ParsedItem = Record<string, unknown>;

  /** Блок «что MegaSharkAI нашёл у конкурента». */
  export let item: ParsedItem;
  export let className = '';

  $: findings = buildFindings(item);

  function buildFindings(data: ParsedItem): Array<{ label: string; value: string; found: boolean }> {
    const price = Number(data.price) || 0;
    const rating = Number(data.rating) || 0;
    const reviews = Number(data.reviews_count) || 0;
    const discount = Number(data.discount) || 0;
    const oldPrice = Number(data.old_price) || 0;
    const brand = String(data.brand || '');
    const category = String(data.category || '');
    const sales = Number(data.sales_per_day || data.sales_count) || 0;

    return [
      {
        label: 'Актуальная цена',
        value: price > 0 ? `${price.toLocaleString('ru-RU')} ₽` : 'Не извлечена',
        found: price > 0
      },
      {
        label: 'Рейтинг товара',
        value: rating > 0 ? `${rating} / 5` : 'Не найден',
        found: rating > 0
      },
      {
        label: 'Количество отзывов',
        value: reviews > 0 ? String(reviews) : 'Не найдено',
        found: reviews > 0
      },
      {
        label: 'Промо / скидка',
        value: discount > 0 ? `−${discount}%` : oldPrice > 0 ? 'Старая цена зафиксирована' : 'Без скидки',
        found: discount > 0 || oldPrice > 0
      },
      {
        label: 'Бренд и категория',
        value: [brand, category].filter(Boolean).join(' · ') || 'Не определены',
        found: Boolean(brand || category)
      },
      {
        label: 'Сигнал спроса',
        value: sales > 0 ? `${sales} продаж/день` : 'Нет данных о продажах',
        found: sales > 0
      }
    ];
  }
</script>

<GlassCard className={className} padding="md">
  <p class="text-xs font-semibold uppercase tracking-[0.2em] text-neural-cyan">Findings</p>
  <h2 class="mt-1 text-lg font-semibold text-foreground">Что MegaSharkAI нашёл у конкурента</h2>
  <p class="mt-1 text-sm text-muted-foreground">
    Сводка сигналов для repricing, AI-анализа и мониторинга карточки.
  </p>

  <ul class="mt-5 space-y-3">
    {#each findings as finding}
      <li
        class={cn(
          'flex items-start gap-3 rounded-xl border p-3',
          finding.found
            ? 'border-neural-cyan/20 bg-neural-cyan/5'
            : 'border-border/50 bg-background/20'
        )}
      >
        {#if finding.found}
          <CheckCircle2 class="mt-0.5 h-4 w-4 shrink-0 text-neural-cyan" aria-hidden="true" />
        {:else}
          <Circle class="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        {/if}
        <div class="min-w-0">
          <p class="text-sm font-medium text-foreground">{finding.label}</p>
          <p class="break-words text-xs text-muted-foreground">{finding.value}</p>
        </div>
      </li>
    {/each}
  </ul>
</GlassCard>
