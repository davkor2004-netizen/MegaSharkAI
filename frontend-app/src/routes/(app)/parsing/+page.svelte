<script lang="ts">
  export let params: Record<string, string> = {};

  import { onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    BarChart3,
    Bot,
    CheckCircle2,
    KeyRound,
    Package,
    Radar,
    ScanSearch,
    Sparkles
  } from 'lucide-svelte';
  import { apiJson } from '$lib/utils/http';
  import {
    Alert,
    Button,
    EmptyState,
    ErrorState,
    FormField,
    GlassCard,
    PageHeader,
    StatusBadge
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';
  import ScanRadarLoader from '$lib/components/parsing/ScanRadarLoader.svelte';
  import ParseResultCard from '$lib/components/parsing/ParseResultCard.svelte';
  import CompetitorFindings from '$lib/components/parsing/CompetitorFindings.svelte';

  let parseMode: 'api' | 'url' = 'url';

  let url = '';
  let urlMarketplace = 'wildberries';

  let apiMarketplace = 'wildberries';
  let productId = '';

  type ParsedProductPreview = {
    name?: string;
    url?: string;
  };

  type RawParsedItem = Record<string, unknown>;

  // Берём первое валидное положительное число среди возможных alias-полей.
  function pickNumber(source: RawParsedItem, keys: string[]): number {
    for (const key of keys) {
      const value = source[key];
      if (value === undefined || value === null || value === '') {
        continue;
      }
      const num = Number(value);
      if (Number.isFinite(num) && num > 0) {
        return num;
      }
    }
    return 0;
  }

  // WB-подобные поля *U приходят в копейках — возвращаем рубли, если нашли.
  function pickKopecks(source: RawParsedItem, keys: string[]): number {
    const raw = pickNumber(source, keys);
    return raw > 0 ? Math.round(raw / 100) : 0;
  }

  function pickString(source: RawParsedItem, keys: string[]): string {
    for (const key of keys) {
      const value = source[key];
      if (typeof value === 'string' && value.trim()) {
        return value.trim();
      }
      if (typeof value === 'number' && Number.isFinite(value)) {
        return String(value);
      }
    }
    return '';
  }

  /**
   * Безопасный фронтенд-нормализатор: приводит alias-поля ответа парсера
   * к каноничным именам, которые ожидают карточки. Значения не выдумываются —
   * берутся только реально присутствующие в ответе. Контракт API не меняется.
   */
  function normalizeParsedItem(raw: RawParsedItem): RawParsedItem {
    const price =
      pickNumber(raw, ['price', 'current_price', 'sale_price', 'salePrice']) ||
      pickKopecks(raw, ['salePriceU', 'priceU']);
    const oldPrice =
      pickNumber(raw, ['old_price', 'oldPrice', 'basic_price']) ||
      pickKopecks(raw, ['basicPriceU']);
    const rating = pickNumber(raw, ['rating', 'review_rating', 'product_rating', 'reviewRating']);
    const reviews = pickNumber(raw, [
      'reviews_count',
      'reviews',
      'feedbacks',
      'feedback_count',
      'feedbackCount'
    ]);
    const discount = pickNumber(raw, ['discount', 'discount_percent', 'sale']);
    const sales = pickNumber(raw, ['sales_per_day', 'sales_count', 'salesPerDay']);
    const name = pickString(raw, ['name', 'title', 'product_name', 'imt_name']);
    const brand = pickString(raw, ['brand', 'brand_name', 'brandName']);
    const category = pickString(raw, ['category', 'subject', 'subject_name', 'subjectName']);
    const url = pickString(raw, ['url', 'link', 'product_url']);

    return {
      ...raw,
      name: name || (raw.name as string | undefined) || '',
      price,
      old_price: oldPrice,
      rating,
      reviews_count: reviews,
      discount,
      sales_per_day: sales,
      brand,
      category,
      url
    };
  }

  let loading = false;
  let result: any = null;
  let error = '';
  let statusMessage = '';

  // Этапы сканирования — визуальная индикация прогресса (без обращения к backend).
  const scanStages = [
    'Определяем маркетплейс',
    'Извлекаем карточку',
    'Проверяем цену',
    'Сравниваем показатели',
    'Готовим вывод'
  ];
  let scanStageIndex = 0;
  let scanTimer: ReturnType<typeof setInterval> | null = null;

  function startScanStages(): void {
    stopScanStages();
    scanStageIndex = 0;
    scanTimer = setInterval(() => {
      if (scanStageIndex < scanStages.length - 1) {
        scanStageIndex += 1;
      }
    }, 850);
  }

  function stopScanStages(): void {
    if (scanTimer) {
      clearInterval(scanTimer);
      scanTimer = null;
    }
  }

  onDestroy(stopScanStages);

  type SharkSignalLevel = 'calm' | 'opportunity' | 'watch' | 'attack' | 'critical';

  interface SharkSignal {
    level: SharkSignalLevel;
    label: string;
    variant: 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'ai';
    description: string;
  }

  // Интерпретация уже извлечённых данных карточки в «сигнал акулы».
  // Это визуальная подсказка поверх реальных полей, без выдуманных данных с backend.
  function computeSharkSignal(item: Record<string, unknown> | null): SharkSignal | null {
    if (!item) {
      return null;
    }

    const price = Number(item.price) || 0;
    const rating = Number(item.rating) || 0;
    const reviews = Number(item.reviews_count) || 0;
    const discount = Number(item.discount) || 0;

    if (price <= 0) {
      return {
        level: 'calm',
        label: 'Недостаточно данных',
        variant: 'neutral',
        description: 'Цена не извлечена — для сигнала недостаточно данных. Проверьте карточку или повторите сканирование.'
      };
    }

    if (rating > 0 && rating < 3.8) {
      return {
        level: 'attack',
        label: 'Attack',
        variant: 'info',
        description: 'Слабый рейтинг конкурента — есть шанс перехватить клиентов ценой и качеством карточки.'
      };
    }

    if (discount >= 35) {
      return {
        level: 'watch',
        label: 'Watch',
        variant: 'warning',
        description: 'Конкурент агрессивно демпингует. Следите за ценой и не уходите в минус.'
      };
    }

    if (rating >= 4.6 && reviews >= 100) {
      return {
        level: 'watch',
        label: 'Watch',
        variant: 'warning',
        description: 'Сильная карточка с доверием покупателей. Берите как ориентир, конкурируйте контентом.'
      };
    }

    if (discount > 0 && discount < 20) {
      return {
        level: 'opportunity',
        label: 'Opportunity',
        variant: 'ai',
        description: 'Умеренная скидка конкурента — есть пространство для репрайсинга в вашу пользу.'
      };
    }

    return {
      level: 'calm',
      label: 'Calm',
      variant: 'success',
      description: 'Карточка стабильна, резких сигналов нет. Подходит для спокойного сравнения позиций.'
    };
  }

  function getOtherProductNames(items: unknown[]): string {
    return items
      .map((item) => {
        if (item && typeof item === 'object' && 'name' in item) {
          const nameValue = (item as ParsedProductPreview).name;
          return nameValue || 'Без названия';
        }
        return 'Без названия';
      })
      .join(', ');
  }

  function showError(message: string): void {
    error = message;
    statusMessage = '';
  }

  function showStatus(message: string): void {
    statusMessage = message;
    error = '';
  }

  function resetResults(): void {
    showStatus('');
    result = null;
    error = '';
  }

  async function handleUrlParse(e: Event) {
    e.preventDefault();
    showStatus('');
    result = null;
    loading = true;
    startScanStages();

    try {
      result = await apiJson('/api/v1/parsing/parse-url', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url,
          is_competitor: true
        })
      });
      showStatus('Парсинг завершён успешно');
    } catch (err: any) {
      console.error('Parse error:', err);

      if (err?.name === 'AbortError' || err?.message?.includes('aborted')) {
        showError('Парсинг занял слишком много времени и был остановлен. Попробуйте ещё раз или другой URL.');
      } else {
        showError(err?.message || 'Не удалось спарсить товар. Проверьте URL.');
      }
    } finally {
      stopScanStages();
      loading = false;
    }
  }

  async function handleApiParse(e: Event) {
    e.preventDefault();
    showStatus('');
    result = null;
    loading = true;

    try {
      result = await apiJson('/api/v1/parsing/my-products', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          marketplace: apiMarketplace,
          product_id: productId || undefined
        })
      });
      showStatus('Данные успешно получены');
    } catch (err: any) {
      console.error('API Parse error:', err);
      showError(err.message || 'Не удалось получить данные. Проверьте подключение API ключа.');
    } finally {
      loading = false;
    }
  }

  function scanAnotherCompetitor(): void {
    resetResults();
    url = '';
  }

  $: urlResultItem =
    result?.data && !Array.isArray(result.data) ? (result.data as Record<string, unknown>) : null;
  $: apiResultItems =
    result?.data && Array.isArray(result.data) ? (result.data as Record<string, unknown>[]) : [];
  $: primaryApiItem = apiResultItems.length > 0 ? apiResultItems[0] : null;
  $: urlItemNormalized = urlResultItem ? normalizeParsedItem(urlResultItem) : null;
  $: apiItemNormalized = primaryApiItem ? normalizeParsedItem(primaryApiItem) : null;
  $: urlSharkSignal = computeSharkSignal(urlItemNormalized);
  $: apiSharkSignal = computeSharkSignal(apiItemNormalized);
</script>

{#if false}{JSON.stringify(params)}{/if}

<AppPageStyles />

<div class="mx-auto max-w-5xl space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Competitor Scanner"
    title="Shark Radar"
    subtitle="Сканируйте карточки конкурентов и получайте сигналы для repricing"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="ai" label="Live parsing" dot={loading} />
    </svelte:fragment>
  </PageHeader>

  <!-- Mode switch -->
  <GlassCard padding="sm" className="!p-2">
    <div class="grid grid-cols-2 gap-2">
      <button
        type="button"
        on:click={() => {
          parseMode = 'url';
          resetResults();
        }}
        class="flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-neural {parseMode === 'url'
          ? 'gradient-neural text-primary-foreground shadow-glow-sm'
          : 'text-muted-foreground hover:bg-background/40 hover:text-foreground'}"
      >
        <Radar class="h-4 w-4" aria-hidden="true" />
        Конкуренты (URL)
      </button>
      <button
        type="button"
        on:click={() => {
          parseMode = 'api';
          resetResults();
        }}
        class="flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition-neural {parseMode === 'api'
          ? 'gradient-neural text-primary-foreground shadow-glow-sm'
          : 'text-muted-foreground hover:bg-background/40 hover:text-foreground'}"
      >
        <Package class="h-4 w-4" aria-hidden="true" />
        Мои товары (API)
      </button>
    </div>
  </GlassCard>

  {#if statusMessage && !error}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}

  {#if parseMode === 'url'}
    <!-- Premium URL scanner -->
    <GlassCard glow padding="none" className="overflow-hidden">
      <div
        class="border-b border-border/60 bg-gradient-to-r from-neural-cyan/10 via-transparent to-neural-purple/10 px-6 py-5 sm:px-8"
      >
        <div class="flex items-center gap-3">
          <div class="flex h-11 w-11 items-center justify-center rounded-xl gradient-neural shadow-glow-sm">
            <ScanSearch class="h-5 w-5 text-primary-foreground" aria-hidden="true" />
          </div>
          <div>
            <h2 class="text-lg font-semibold text-foreground">Сканер URL конкурента</h2>
            <p class="text-sm text-muted-foreground">Вставьте ссылку — MegaSharkAI извлечёт цену, рейтинг и сигналы карточки</p>
          </div>
        </div>
      </div>

      {#if loading}
        <div class="px-6 py-6 sm:px-8">
          <ScanRadarLoader />
          <ol class="mx-auto mt-4 max-w-sm space-y-2">
            {#each scanStages as stage, i}
              <li
                class="flex items-center gap-3 rounded-xl border px-3 py-2 text-sm transition-neural {i < scanStageIndex
                  ? 'border-neural-cyan/25 bg-neural-cyan/5 text-foreground'
                  : i === scanStageIndex
                    ? 'border-neural-cyan/40 bg-neural-cyan/10 text-foreground'
                    : 'border-border/50 bg-background/20 text-muted-foreground'}"
              >
                {#if i < scanStageIndex}
                  <CheckCircle2 class="h-4 w-4 shrink-0 text-neural-cyan" aria-hidden="true" />
                {:else if i === scanStageIndex}
                  <span class="h-2 w-2 shrink-0 animate-pulse rounded-full bg-neural-cyan" aria-hidden="true"></span>
                {:else}
                  <span class="h-2 w-2 shrink-0 rounded-full bg-border" aria-hidden="true"></span>
                {/if}
                {stage}
              </li>
            {/each}
          </ol>
        </div>
      {:else}
        <form on:submit={handleUrlParse} class="space-y-5 px-6 py-6 sm:px-8">
          <div class="grid gap-4 sm:grid-cols-[220px_1fr]">
            <FormField label="Маркетплейс" let:controlId>
              <select id={controlId} bind:value={urlMarketplace} class="page-select">
                <option value="wildberries">Wildberries</option>
                <option value="ozon">Ozon</option>
                <option value="avito">Avito</option>
                <option value="kazanexpress">KazanExpress</option>
                <option value="yandex_market">Яндекс Маркет</option>
              </select>
            </FormField>

            <FormField label="Ссылка на товар конкурента" let:controlId>
              <input
                id={controlId}
                type="url"
                bind:value={url}
                class="page-input text-base {error ? 'page-input-error' : ''}"
                placeholder="https://www.wildberries.ru/catalog/12345678/detail.aspx"
                required
                aria-invalid={Boolean(error)}
              />
            </FormField>
          </div>

          {#if error}
            <Alert variant="error" title="Сканирование не удалось">{error}</Alert>
          {/if}

          <Button type="submit" variant="neural" disabled={!url} className="w-full sm:w-auto">
            <Radar class="h-4 w-4" aria-hidden="true" />
            Запустить Shark Radar
          </Button>
        </form>
      {/if}
    </GlassCard>

    <!-- Value props -->
    {#if !loading && !urlResultItem}
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {#each [
          { title: 'Цена', desc: 'Актуальная и старая цена для repricing' },
          { title: 'Рейтинг', desc: 'Сила карточки и доверие покупателей' },
          { title: 'Отзывы', desc: 'Социальное доказательство конкурента' },
          { title: 'Карточка', desc: 'Название, бренд, категория, скидки' },
          { title: 'Риск', desc: 'Оценка полноты и надёжности данных' }
        ] as block}
          <div class="glass-card rounded-xl p-4">
            <p class="text-sm font-semibold text-neural-cyan">{block.title}</p>
            <p class="mt-1 text-xs text-muted-foreground">{block.desc}</p>
          </div>
        {/each}
      </div>
    {/if}

    {#if urlResultItem}
      {#if urlSharkSignal}
        <GlassCard padding="md" glow>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-neural-cyan/15 text-neural-cyan">
                <Radar class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <p class="text-xs font-semibold uppercase tracking-[0.2em] text-neural-cyan">Shark Signal</p>
                <p class="text-sm text-muted-foreground">Интерпретация сигналов карточки конкурента</p>
              </div>
            </div>
            <StatusBadge variant={urlSharkSignal.variant} label={urlSharkSignal.label} />
          </div>
          <p class="mt-3 text-sm text-foreground">{urlSharkSignal.description}</p>
        </GlassCard>
      {/if}

      <div class="grid gap-4 lg:grid-cols-5">
        <div class="min-w-0 lg:col-span-3">
          <ParseResultCard item={urlItemNormalized ?? urlResultItem} />
        </div>
        <div class="min-w-0 lg:col-span-2">
          <CompetitorFindings item={urlItemNormalized ?? urlResultItem} />
        </div>
      </div>

      <GlassCard padding="md">
        <p class="mb-3 text-sm font-semibold text-foreground">Дальнейшие действия</p>
        <div class="flex flex-wrap gap-2">
          <Button variant="neural" size="sm" on:click={scanAnotherCompetitor}>
            <Radar class="h-4 w-4" aria-hidden="true" />
            Сканировать ещё конкурента
          </Button>
          <Button variant="ghost" size="sm" on:click={() => goto('/products')}>
            <Package class="h-4 w-4" aria-hidden="true" />
            Перейти к товарам
          </Button>
          <Button variant="ghost" size="sm" on:click={() => goto('/repricing')}>
            <BarChart3 class="h-4 w-4" aria-hidden="true" />
            Рассчитать репрайсинг
          </Button>
          <Button variant="ghost" size="sm" on:click={() => goto('/ai')}>
            <Bot class="h-4 w-4" aria-hidden="true" />
            Проанализировать через AI
          </Button>
        </div>
      </GlassCard>
    {/if}
  {:else}
    <!-- API mode -->
    <GlassCard glow padding="lg">
      <div class="mb-6 flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-neural-purple/15 text-neural-purple">
          <KeyRound class="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-foreground">Мои товары через API</h2>
          <p class="text-sm text-muted-foreground">Загрузка каталога с подключённого маркетплейса</p>
        </div>
      </div>

      {#if loading}
        <ScanRadarLoader
          label="Загрузка каталога..."
          sublabel="Подключение к API маркетплейса через ваш ключ"
        />
      {:else}
        <form on:submit={handleApiParse} class="space-y-5">
          <div class="grid gap-4 sm:grid-cols-2">
            <FormField label="Маркетплейс" let:controlId>
              <select id={controlId} bind:value={apiMarketplace} class="page-select">
                <option value="wildberries">Wildberries</option>
                <option value="ozon">Ozon</option>
                <option value="yandex_market">Яндекс Маркет</option>
              </select>
            </FormField>
            <FormField label="ID товара (необязательно)" let:controlId>
              <input
                id={controlId}
                type="text"
                bind:value={productId}
                class="page-input"
                placeholder="Пусто = все товары"
              />
            </FormField>
          </div>

          <Alert variant="info" title="">
            <span class="inline-flex items-start gap-2">
              <Sparkles class="mt-0.5 h-4 w-4 shrink-0 text-neural-purple" aria-hidden="true" />
              <span>
                Для работы требуется API-ключ в разделе
                <a href="/profile" class="font-medium text-neural-cyan hover:underline">Профиль</a>.
              </span>
            </span>
          </Alert>

          {#if error}
            <ErrorState title="Ошибка API" description={error}>
              <svelte:fragment slot="action">
                <Button type="submit" variant="neural">
                  <Package class="h-4 w-4" aria-hidden="true" />
                  Повторить
                </Button>
              </svelte:fragment>
            </ErrorState>
          {:else}
            <Button type="submit" variant="neural">
              <Package class="h-4 w-4" aria-hidden="true" />
              Получить данные
            </Button>
          {/if}
        </form>
      {/if}
    </GlassCard>

    {#if primaryApiItem}
      <div class="space-y-4">
        {#if apiSharkSignal}
          <GlassCard padding="md" glow>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-neural-cyan/15 text-neural-cyan">
                  <Radar class="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <p class="text-xs font-semibold uppercase tracking-[0.2em] text-neural-cyan">Shark Signal</p>
                  <p class="text-sm text-muted-foreground">Интерпретация сигналов вашей карточки</p>
                </div>
              </div>
              <StatusBadge variant={apiSharkSignal.variant} label={apiSharkSignal.label} />
            </div>
            <p class="mt-3 text-sm text-foreground">{apiSharkSignal.description}</p>
          </GlassCard>
        {/if}

        <ParseResultCard item={apiItemNormalized ?? primaryApiItem} />

        {#if apiResultItems.length > 1}
          <GlassCard padding="md">
            <p class="text-sm text-foreground">
              Показан первый товар из {apiResultItems.length}.
              Остальные: {getOtherProductNames(apiResultItems.slice(1))}
            </p>
          </GlassCard>
        {/if}

        <CompetitorFindings item={apiItemNormalized ?? primaryApiItem} />

        <GlassCard padding="md">
          <p class="mb-3 text-sm font-semibold text-foreground">Дальнейшие действия</p>
          <div class="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" on:click={() => goto('/products')}>
              <Package class="h-4 w-4" aria-hidden="true" />
              Перейти к товарам
            </Button>
            <Button variant="ghost" size="sm" on:click={() => goto('/repricing')}>
              <BarChart3 class="h-4 w-4" aria-hidden="true" />
              Рассчитать репрайсинг
            </Button>
            <Button variant="ghost" size="sm" on:click={() => goto('/ai')}>
              <Bot class="h-4 w-4" aria-hidden="true" />
              Проанализировать через AI
            </Button>
          </div>
        </GlassCard>
      </div>
    {:else if result && !loading && !error}
      <EmptyState
        title="Нет данных"
        description={result.message || 'API вернул пустой ответ. Проверьте ключ и маркетплейс.'}
        icon={Package}
      />
    {/if}
  {/if}

  {#if result}
    <details class="rounded-xl border border-border/60 bg-background/30">
      <summary class="cursor-pointer select-none px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground">
        Показать ответ парсера (raw JSON)
      </summary>
      <pre class="max-h-80 overflow-auto border-t border-border/60 px-4 py-3 text-xs text-muted-foreground">{JSON.stringify(result, null, 2)}</pre>
    </details>
  {/if}
</div>

<style>
  .transition-neural {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
</style>
