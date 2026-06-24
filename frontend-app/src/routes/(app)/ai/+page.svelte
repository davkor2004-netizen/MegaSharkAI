<script lang="ts">
  import { onMount } from 'svelte';
  import { apiJson } from '$lib/utils/http';
  import {
    AIInsightCard,
    Alert,
    Button,
    EmptyState,
    ErrorState,
    FormField,
    GlassCard,
    LoadingSkeleton,
    PageHeader,
    StatusBadge
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';
  import {
    Copy,
    History,
    Lightbulb,
    Monitor,
    Radar,
    Sparkles,
    Trash2,
    Users
  } from 'lucide-svelte';

  type AIProvider = 'yandex' | 'openai' | 'deepseek' | 'none' | string;

  interface SeoTitleResult {
    original_name: string;
    seo_name: string;
    provider: AIProvider;
  }

  interface ProviderStatusResponse {
    provider: AIProvider;
    status: 'configured' | 'not_configured' | string;
  }

  interface CompetitorInputItem {
    name: string;
    price: number;
    rating?: number;
  }

  interface CompetitorAnalysisResponse {
    product_name: string;
    analysis: Record<string, unknown>;
    competitors_count: number;
  }

  interface AIHistoryItem {
    id: string;
    type: 'seo' | 'competitors';
    title: string;
    description: string;
    createdAt: string;
  }

  let activeTab: 'seo' | 'competitors' = 'seo';

  let productName = '';
  let category = '';
  let brand = '';
  let characteristics = '';

  let competitorProductName = '';
  let competitorsText = '';
  let competitorAnalysisResult: CompetitorAnalysisResponse | null = null;

  let loading = false;
  let result: SeoTitleResult | null = null;
  let seoAttempted = false;
  let competitorsAttempted = false;

  let error = '';
  let statusMessage = '';
  let copyMessage = '';

  let aiHistory: AIHistoryItem[] = [];

  let configuredProvider: AIProvider = 'none';
  let providerStatus: ProviderStatusResponse['status'] | 'error' = 'not_configured';
  let providerLoading = true;
  let providerLoadError = '';

  let lastUsedProvider: AIProvider = 'none';

  const charsHint = 'JSON-объект, например: {"Материал":"Хлопок","Цвет":"Белый"}';
  const competitorsHint = 'Массив объектов: name (строка), price (число), rating (необязательно)';

  function resetMessages(): void {
    error = '';
    statusMessage = '';
    copyMessage = '';
  }

  function formatDateTime(date: Date): string {
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }

  function saveHistoryToStorage(): void {
    try {
      localStorage.setItem('ai-history-v1', JSON.stringify(aiHistory));
    } catch {
      // Игнорируем ошибку записи в localStorage (например, переполнение).
    }
  }

  function loadHistoryFromStorage(): void {
    try {
      const raw = localStorage.getItem('ai-history-v1');
      if (!raw) {
        return;
      }

      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return;
      }

      aiHistory = parsed
        .filter((item: unknown) => item && typeof item === 'object')
        .map((item: unknown) => {
          const typedItem = item as Record<string, unknown>;
          return {
            id: typeof typedItem.id === 'string' ? typedItem.id : crypto.randomUUID(),
            type: typedItem.type === 'competitors' ? 'competitors' : 'seo',
            title: typeof typedItem.title === 'string' ? typedItem.title : 'Запрос',
            description: typeof typedItem.description === 'string' ? typedItem.description : '',
            createdAt: typeof typedItem.createdAt === 'string' ? typedItem.createdAt : formatDateTime(new Date())
          } as AIHistoryItem;
        })
        .slice(0, 12);
    } catch {
      aiHistory = [];
    }
  }

  function addHistoryItem(item: Omit<AIHistoryItem, 'id' | 'createdAt'>): void {
    const historyItem: AIHistoryItem = {
      id: crypto.randomUUID(),
      createdAt: formatDateTime(new Date()),
      ...item
    };

    aiHistory = [historyItem, ...aiHistory].slice(0, 12);
    saveHistoryToStorage();
  }

  function switchTab(tab: 'seo' | 'competitors'): void {
    activeTab = tab;
    resetMessages();
  }

  function applyExampleData(): void {
    productName = 'Футболка мужская базовая';
    category = 'Одежда';
    brand = 'MegaBrand';
    characteristics = JSON.stringify(
      {
        Материал: 'Хлопок',
        Цвет: 'Белый',
        Размер: 'L',
        Сезон: 'Всесезонный'
      },
      null,
      2
    );
    copyMessage = '';
  }

  function applyCompetitorExampleData(): void {
    competitorProductName = 'Футболка мужская базовая';
    competitorsText = JSON.stringify(
      [
        { name: 'Футболка Premium Cotton', price: 1990, rating: 4.7 },
        { name: 'Футболка Casual Fit', price: 1790, rating: 4.5 },
        { name: 'Футболка Comfort', price: 1650, rating: 4.3 }
      ],
      null,
      2
    );
  }

  function clearForm(): void {
    productName = '';
    category = '';
    brand = '';
    characteristics = '';
    result = null;
    seoAttempted = false;
    resetMessages();
  }

  function clearCompetitorForm(): void {
    competitorProductName = '';
    competitorsText = '';
    competitorAnalysisResult = null;
    competitorsAttempted = false;
    resetMessages();
  }

  function clearHistory(): void {
    aiHistory = [];
    saveHistoryToStorage();
  }

  function getProviderLabel(provider: AIProvider): string {
    if (provider === 'yandex') return 'YandexGPT';
    if (provider === 'openai') return 'OpenAI';
    if (provider === 'deepseek') return 'DeepSeek';
    return 'Не настроен';
  }

  function getConfiguredProviderVariant(): 'success' | 'warning' | 'error' | 'ai' {
    if (providerLoadError) return 'error';
    if (configuredProvider === 'none' || providerStatus === 'not_configured') return 'warning';
    return 'ai';
  }

  function formatAnalysisValue(value: unknown): string {
    if (Array.isArray(value)) {
      return value
        .map((item) => (typeof item === 'string' ? `• ${item}` : `• ${JSON.stringify(item)}`))
        .join('\n');
    }
    if (typeof value === 'object' && value !== null) {
      return JSON.stringify(value, null, 2);
    }
    return String(value ?? '');
  }

  async function loadConfiguredProvider(): Promise<void> {
    providerLoading = true;
    providerLoadError = '';

    try {
      const payload = await apiJson<ProviderStatusResponse>(
        '/api/v1/ai/provider',
        {},
        'Не удалось загрузить статус AI-провайдера'
      );
      configuredProvider = payload.provider || 'none';
      providerStatus = payload.status || 'not_configured';
    } catch (err: unknown) {
      configuredProvider = 'none';
      providerStatus = 'error';
      providerLoadError = err instanceof Error ? err.message : 'Ошибка загрузки провайдера';
    } finally {
      providerLoading = false;
    }
  }

  async function copySeoTitle(): Promise<void> {
    if (!result?.seo_name) {
      return;
    }

    try {
      await navigator.clipboard.writeText(result.seo_name);
      copyMessage = 'Название скопировано в буфер обмена';
    } catch {
      copyMessage = 'Не удалось скопировать автоматически';
    }
  }

  async function copyCompetitorAnalysis(): Promise<void> {
    if (!competitorAnalysisResult) {
      return;
    }

    try {
      await navigator.clipboard.writeText(JSON.stringify(competitorAnalysisResult.analysis, null, 2));
      copyMessage = 'Анализ конкурентов скопирован в буфер обмена';
    } catch {
      copyMessage = 'Не удалось скопировать анализ автоматически';
    }
  }

  function getAnalysisEntryLabel(key: string): string {
    const mapping: Record<string, string> = {
      pricing_strategy: 'Стратегия ценообразования',
      positioning: 'Позиционирование',
      strengths: 'Сильные стороны',
      weaknesses: 'Слабые стороны',
      recommendations: 'Рекомендации',
      target_audience: 'Целевая аудитория',
      usp: 'УТП',
      next_steps: 'Следующий шаг'
    };

    return mapping[key] || key;
  }

  function isHighlightAnalysisKey(key: string): boolean {
    return ['recommendations', 'next_steps', 'usp'].includes(key);
  }

  async function handleGenerate(e: Event): Promise<void> {
    e.preventDefault();
    resetMessages();
    result = null;

    if (!productName.trim()) {
      error = 'Введите название товара';
      return;
    }

    seoAttempted = true;
    loading = true;

    try {
      let chars: Record<string, unknown> | undefined = undefined;
      if (characteristics.trim()) {
        try {
          const parsed = JSON.parse(characteristics);
          if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            throw new Error('Характеристики должны быть JSON-объектом');
          }
          chars = parsed as Record<string, unknown>;
        } catch {
          throw new Error('Неверный формат JSON в характеристиках');
        }
      }

      const payload = {
        product_name: productName.trim(),
        category: category.trim() || undefined,
        brand: brand.trim() || undefined,
        characteristics: chars
      };

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const payloadResult = await apiJson<SeoTitleResult>(
        '/api/v1/ai/generate-seo-title',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify(payload)
        },
        'Ошибка генерации названия'
      );

      clearTimeout(timeoutId);

      result = payloadResult;
      lastUsedProvider = payloadResult.provider || 'none';
      statusMessage = 'Название успешно сгенерировано';

      addHistoryItem({
        type: 'seo',
        title: payloadResult.seo_name,
        description: `Исходное: ${payloadResult.original_name}`
      });
    } catch (err: unknown) {
      console.error('AI error:', err);
      if (err instanceof Error && err.name === 'AbortError') {
        error = 'Превышено время ожидания (30 сек). Попробуйте ещё раз.';
      } else {
        error = err instanceof Error ? err.message : 'Не удалось сгенерировать название. Проверьте данные.';
      }
    } finally {
      loading = false;
    }
  }

  async function handleAnalyzeCompetitors(e: Event): Promise<void> {
    e.preventDefault();
    resetMessages();
    competitorAnalysisResult = null;

    if (!competitorProductName.trim()) {
      error = 'Введите название товара для анализа конкурентов';
      return;
    }

    competitorsAttempted = true;
    loading = true;

    try {
      let parsedCompetitors: unknown;
      try {
        parsedCompetitors = JSON.parse(competitorsText);
      } catch {
        throw new Error('Неверный JSON в списке конкурентов');
      }

      if (!Array.isArray(parsedCompetitors) || parsedCompetitors.length === 0) {
        throw new Error('Список конкурентов должен быть непустым массивом');
      }

      const competitors: CompetitorInputItem[] = parsedCompetitors.map((item: unknown, index: number) => {
        if (!item || typeof item !== 'object') {
          throw new Error(`Конкурент #${index + 1}: неверный формат`);
        }

        const typedItem = item as Record<string, unknown>;
        const rawName = typedItem.name;
        const rawPrice = typedItem.price;
        const rawRating = typedItem.rating;

        if (typeof rawName !== 'string' || !rawName.trim()) {
          throw new Error(`Конкурент #${index + 1}: поле name обязательно`);
        }

        if (typeof rawPrice !== 'number' || Number.isNaN(rawPrice) || rawPrice <= 0) {
          throw new Error(`Конкурент #${index + 1}: поле price должно быть числом > 0`);
        }

        const competitor: CompetitorInputItem = {
          name: rawName.trim(),
          price: rawPrice
        };

        if (typeof rawRating === 'number' && !Number.isNaN(rawRating)) {
          competitor.rating = rawRating;
        }

        return competitor;
      });

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const payloadResult = await apiJson<CompetitorAnalysisResponse>(
        '/api/v1/ai/analyze-competitors',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            product_name: competitorProductName.trim(),
            competitors
          })
        },
        'Ошибка анализа конкурентов'
      );

      clearTimeout(timeoutId);

      competitorAnalysisResult = payloadResult;
      statusMessage = 'Анализ конкурентов успешно выполнен';

      addHistoryItem({
        type: 'competitors',
        title: payloadResult.product_name,
        description: `Конкурентов: ${payloadResult.competitors_count}`
      });
    } catch (err: unknown) {
      console.error('Competitor analysis error:', err);
      if (err instanceof Error && err.name === 'AbortError') {
        error = 'Превышено время ожидания (30 сек). Попробуйте ещё раз.';
      } else {
        error = err instanceof Error ? err.message : 'Не удалось выполнить анализ конкурентов';
      }
    } finally {
      loading = false;
    }
  }

  onMount(async () => {
    loadHistoryFromStorage();
    await loadConfiguredProvider();
  });
</script>

<div class="mx-auto max-w-[1400px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="AI Profit Agent"
    title="AI Генератор названий"
    subtitle="SEO-названия и анализ конкурентов для роста прибыли на маркетплейсах"
  >
    <svelte:fragment slot="meta">
      {#if providerLoading}
        <StatusBadge variant="neutral" label="Провайдер: загрузка..." dot={false} />
      {:else}
        <StatusBadge
          variant={getConfiguredProviderVariant()}
          label="Провайдер: {getProviderLabel(configuredProvider)}"
          dot={configuredProvider !== 'none' && !providerLoadError}
        />
        {#if lastUsedProvider !== 'none' && lastUsedProvider !== configuredProvider}
          <StatusBadge variant="info" label="Fallback: {getProviderLabel(lastUsedProvider)}" dot />
        {/if}
      {/if}
    </svelte:fragment>
  </PageHeader>

  {#if providerLoadError}
    <Alert variant="warning" title="Статус провайдера недоступен">
      {providerLoadError}. Генерация может быть недоступна, пока AI не настроен администратором.
    </Alert>
  {:else if configuredProvider === 'none' && !providerLoading}
    <Alert variant="warning" title="AI-провайдер не настроен">
      Администратор ещё не подключил YandexGPT, OpenAI или DeepSeek. Запросы могут завершиться ошибкой.
    </Alert>
  {/if}

  {#if error && !(
    (activeTab === 'seo' && seoAttempted && !result) ||
    (activeTab === 'competitors' && competitorsAttempted && !competitorAnalysisResult)
  )}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}
  {#if statusMessage}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}
  {#if copyMessage}
    <Alert variant="info" title="Буфер обмена">{copyMessage}</Alert>
  {/if}

  <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
    <div class="space-y-6">
      <GlassCard glow padding="lg" className="space-y-6">
        <div class="flex flex-wrap gap-2">
          <Button
            variant={activeTab === 'seo' ? 'neural' : 'subtle'}
            size="sm"
            type="button"
            on:click={() => switchTab('seo')}
          >
            <Sparkles class="h-4 w-4" aria-hidden="true" />
            SEO генерация
          </Button>
          <Button
            variant={activeTab === 'competitors' ? 'neural' : 'subtle'}
            size="sm"
            type="button"
            on:click={() => switchTab('competitors')}
          >
            <Users class="h-4 w-4" aria-hidden="true" />
            Анализ конкурентов
          </Button>
        </div>

        {#if activeTab === 'seo'}
          <form on:submit={handleGenerate} class="space-y-6">
            <div class="space-y-1">
              <h2 class="text-lg font-semibold text-foreground">SEO-название товара</h2>
              <p class="text-sm text-muted-foreground">
                AI сформирует оптимизированное название с учётом категории, бренда и характеристик.
              </p>
            </div>

            <FormField label="Название товара" required let:controlId>
              <input
                id={controlId}
                type="text"
                bind:value={productName}
                class="page-input"
                placeholder="Футболка мужская"
                required
              />
            </FormField>

            <div class="grid gap-4 md:grid-cols-2">
              <FormField label="Категория" let:controlId>
                <input id={controlId} type="text" bind:value={category} class="page-input" placeholder="Одежда" />
              </FormField>
              <FormField label="Бренд" let:controlId>
                <input id={controlId} type="text" bind:value={brand} class="page-input" placeholder="Nike" />
              </FormField>
            </div>

            <FormField label="Характеристики (JSON)" hint={charsHint} let:controlId>
              <textarea
                id={controlId}
                bind:value={characteristics}
                class="page-textarea font-mono text-sm"
                rows="6"
                placeholder={'{\n  "Материал": "Хлопок",\n  "Цвет": "Белый"\n}'}
              ></textarea>
            </FormField>

            <div class="flex flex-wrap gap-2">
              <Button variant="ghost" size="sm" type="button" on:click={applyExampleData}>
                Заполнить пример
              </Button>
              <Button variant="subtle" size="sm" type="button" on:click={clearForm}>
                Очистить
              </Button>
            </div>

            <Button type="submit" variant="neural" fullWidth loading={loading} disabled={loading || !productName.trim()}>
              <Sparkles class="h-5 w-5" aria-hidden="true" />
              {loading ? 'Генерация...' : 'Сгенерировать название'}
            </Button>
          </form>

          {#if loading}
            <LoadingSkeleton variant="card" />
          {:else if error && seoAttempted && !result}
            <ErrorState title="Не удалось сгенерировать название" description={error} on:click={handleGenerate} />
          {:else if seoAttempted && !result}
            <EmptyState
              icon={Sparkles}
              title="Результат пока пуст"
              description="Заполните форму и запустите генерацию SEO-названия."
            />
          {/if}

        {:else}
          <form on:submit={handleAnalyzeCompetitors} class="space-y-6">
            <div class="space-y-1">
              <h2 class="text-lg font-semibold text-foreground">Анализ конкурентов</h2>
              <p class="text-sm text-muted-foreground">
                Сравните ваш товар с конкурентами и получите рекомендации по цене и позиционированию.
              </p>
            </div>

            <FormField label="Название вашего товара" required let:controlId>
              <input
                id={controlId}
                type="text"
                bind:value={competitorProductName}
                class="page-input"
                placeholder="Футболка мужская базовая"
                required
              />
            </FormField>

            <FormField label="Список конкурентов (JSON массив)" required hint={competitorsHint} let:controlId>
              <textarea
                id={controlId}
                bind:value={competitorsText}
                class="page-textarea font-mono text-sm"
                rows="8"
                placeholder={'[\n  {"name": "Товар 1", "price": 1990, "rating": 4.7},\n  {"name": "Товар 2", "price": 1790, "rating": 4.5}\n]'}
              ></textarea>
            </FormField>

            <div class="flex flex-wrap gap-2">
              <Button variant="ghost" size="sm" type="button" on:click={applyCompetitorExampleData}>
                Заполнить пример
              </Button>
              <Button variant="subtle" size="sm" type="button" on:click={clearCompetitorForm}>
                Очистить
              </Button>
            </div>

            <Button
              type="submit"
              variant="neural"
              fullWidth
              loading={loading}
              disabled={loading || !competitorProductName.trim() || !competitorsText.trim()}
            >
              <Monitor class="h-5 w-5" aria-hidden="true" />
              {loading ? 'Анализ...' : 'Анализировать конкурентов'}
            </Button>
          </form>

          {#if loading}
            <LoadingSkeleton variant="card" />
            <div class="grid gap-4 sm:grid-cols-2">
              <LoadingSkeleton variant="metric" />
              <LoadingSkeleton variant="metric" />
            </div>
          {:else if error && competitorsAttempted && !competitorAnalysisResult}
            <ErrorState
              title="Не удалось выполнить анализ"
              description={error}
              on:click={handleAnalyzeCompetitors}
            />
          {:else if competitorsAttempted && !competitorAnalysisResult}
            <EmptyState
              icon={Radar}
              title="Анализ ещё не выполнен"
              description="Добавьте JSON со списком конкурентов и запустите анализ."
            />
          {/if}
        {/if}
      </GlassCard>

      {#if activeTab === 'seo' && result}
        <div class="space-y-4">
          <div class="surface p-4">
            <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Исходное название</p>
            <p class="mt-1 text-sm text-foreground">{result.original_name}</p>
          </div>

          <AIInsightCard title="SEO-название" insight={result.seo_name} variant="highlight">
            <svelte:fragment slot="actions">
              <Button variant="ghost" size="sm" on:click={copySeoTitle}>
                <Copy class="h-4 w-4" aria-hidden="true" />
                Копировать
              </Button>
            </svelte:fragment>
          </AIInsightCard>

          <div class="flex flex-wrap gap-2">
            <StatusBadge variant="ai" label="Ответ: {getProviderLabel(lastUsedProvider)}" dot={false} />
            <StatusBadge variant="neutral" label="Основной: {getProviderLabel(configuredProvider)}" dot={false} />
            {#if lastUsedProvider !== 'none' && lastUsedProvider !== configuredProvider}
              <StatusBadge variant="info" label="Использован fallback-провайдер" dot />
            {/if}
          </div>

          <Alert variant="warning" title="Проверьте перед публикацией">
            AI может не знать актуальных правил маркетплейса. Сверьте название с лимитами символов и запретами площадки.
          </Alert>
        </div>
      {/if}

      {#if activeTab === 'competitors' && competitorAnalysisResult}
        <div class="space-y-4">
          <GlassCard glow padding="lg" className="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-xs font-semibold uppercase tracking-wider text-neural-cyan">Результат анализа</p>
                <h2 class="text-lg font-semibold text-foreground">{competitorAnalysisResult.product_name}</h2>
              </div>
              <StatusBadge
                variant="info"
                label="Конкурентов: {competitorAnalysisResult.competitors_count}"
                dot={false}
              />
            </div>
          </GlassCard>

          <div class="grid gap-4 md:grid-cols-2">
            {#each Object.entries(competitorAnalysisResult.analysis) as [key, value]}
              <div class={isHighlightAnalysisKey(key) ? 'md:col-span-2' : ''}>
                <AIInsightCard
                  title={getAnalysisEntryLabel(key)}
                  insight={formatAnalysisValue(value)}
                  variant={isHighlightAnalysisKey(key) ? 'highlight' : 'default'}
                />
              </div>
            {/each}
          </div>

          <details class="surface rounded-xl p-4">
            <summary class="cursor-pointer text-sm font-medium text-foreground">Показать сырой JSON анализа</summary>
            <div class="mt-3 overflow-auto">
              <pre class="whitespace-pre-wrap break-words text-xs text-muted-foreground">{JSON.stringify(competitorAnalysisResult.analysis, null, 2)}</pre>
            </div>
          </details>

          <div class="flex flex-wrap gap-2">
            <Button variant="ghost" size="sm" on:click={copyCompetitorAnalysis}>
              <Copy class="h-4 w-4" aria-hidden="true" />
              Копировать анализ
            </Button>
          </div>

          <Alert variant="info" title="AI-оценка">
            Анализ носит рекомендательный характер. Проверяйте выводы по фактическим данным конкурентов и вашей unit-экономике.
          </Alert>
        </div>
      {/if}
    </div>

    <aside class="space-y-6">
      <GlassCard padding="lg" className="space-y-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <History class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            <h3 class="text-lg font-semibold text-foreground">История запросов</h3>
          </div>
          {#if aiHistory.length > 0}
            <Button variant="subtle" size="sm" on:click={clearHistory}>
              <Trash2 class="h-4 w-4" aria-hidden="true" />
              Очистить
            </Button>
          {/if}
        </div>

        {#if aiHistory.length === 0}
          <EmptyState
            icon={History}
            title="История пуста"
            description="Выполните первый AI-запрос — результат появится здесь."
            className="!border-0 !bg-transparent !p-0 !shadow-none"
          />
        {:else}
          <div class="space-y-2">
            {#each aiHistory as item (item.id)}
              <div class="surface rounded-xl p-3 transition-neural hover:border-neural-cyan/20">
                <div class="flex items-start justify-between gap-2">
                  <p class="line-clamp-2 text-sm font-medium text-foreground">{item.title}</p>
                  <span class="shrink-0 text-[11px] text-muted-foreground">{item.createdAt}</span>
                </div>
                <p class="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
                <StatusBadge
                  variant={item.type === 'seo' ? 'ai' : 'info'}
                  label={item.type === 'seo' ? 'SEO' : 'Конкуренты'}
                  dot={false}
                  className="mt-2"
                />
              </div>
            {/each}
          </div>
        {/if}
      </GlassCard>

      <GlassCard padding="lg" className="space-y-4">
        <h3 class="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Lightbulb class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
          Советы по SEO
        </h3>
        <ul class="space-y-2 text-sm text-muted-foreground">
          <li class="surface rounded-lg px-3 py-2">
            Длина названия: <span class="font-medium text-foreground">50–100 символов</span>
          </li>
          <li class="surface rounded-lg px-3 py-2">
            Структура: <span class="font-medium text-foreground">Бренд + тип + характеристики + цвет/размер</span>
          </li>
          <li class="surface rounded-lg px-3 py-2">Используйте популярные поисковые запросы</li>
          <li class="surface rounded-lg px-3 py-2">Избегайте спецсимволов и CAPS</li>
          <li class="surface rounded-lg px-3 py-2">Указывайте важные для покупателя характеристики</li>
        </ul>
      </GlassCard>
    </aside>
  </div>
</div>

<AppPageStyles />
