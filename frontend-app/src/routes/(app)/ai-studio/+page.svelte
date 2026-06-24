<script lang="ts">
  import { apiJson } from '$lib/utils/http';
  import {
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
    ClipboardCheck,
    Copy,
    Image as ImageIcon,
    MessageCircle,
    Search,
    Sparkles
  } from 'lucide-svelte';

  type Tab = 'image' | 'keywords' | 'audit' | 'review';

  interface ImageGenResponse {
    status: string;
    model?: string;
    images: string[];
    count: number;
  }

  interface KeywordsResult {
    keywords?: string[];
    clusters?: Record<string, string[]>;
    provider?: string;
  }

  interface AuditResult {
    score: number;
    issues?: string[];
    recommendations?: string[];
    provider?: string;
  }

  interface ReviewAnswerResponse {
    answer: string;
    provider?: string;
  }

  let activeTab: Tab = 'image';
  let loading = false;
  let error = '';
  let copyMessage = '';

  // Images
  let imagePrompt = '';
  let imageSize: '1024x1024' | '1024x1536' | '1536x1024' = '1024x1024';
  let imageCount = 1;
  let imageQuality: 'low' | 'medium' | 'high' = 'high';
  let images: string[] = [];
  let imageAttempted = false;

  // Keywords
  let kwProduct = '';
  let kwCategory = '';
  let kwResult: KeywordsResult | null = null;
  let kwAttempted = false;

  // SKU audit
  let auditProduct = '';
  let auditDescription = '';
  let auditCharacteristics = '';
  let auditImages = 3;
  let auditResult: AuditResult | null = null;
  let auditAttempted = false;

  // Review answer
  let reviewProduct = '';
  let reviewText = '';
  let reviewRating: number | null = 5;
  let reviewIsQuestion = false;
  let reviewAnswer = '';
  let reviewAttempted = false;

  const auditCharsHint = 'Например: {"Материал":"Хлопок"}';

  function switchTab(tab: Tab): void {
    activeTab = tab;
    error = '';
    copyMessage = '';
  }

  function isKeywordsEmpty(result: KeywordsResult): boolean {
    const hasKeywords = (result.keywords?.length ?? 0) > 0;
    const hasClusters = Boolean(result.clusters && Object.keys(result.clusters).length > 0);
    return !hasKeywords && !hasClusters;
  }

  function getAuditScoreVariant(score: number): 'success' | 'warning' | 'error' {
    if (score >= 80) return 'success';
    if (score >= 50) return 'warning';
    return 'error';
  }

  async function copyText(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      copyMessage = 'Скопировано в буфер обмена';
    } catch {
      copyMessage = 'Не удалось скопировать';
    }
  }

  async function generateImage(e: Event): Promise<void> {
    e.preventDefault();
    error = '';
    copyMessage = '';
    images = [];

    if (!imagePrompt.trim()) {
      error = 'Введите описание изображения';
      return;
    }

    imageAttempted = true;
    loading = true;

    try {
      const data = await apiJson<ImageGenResponse>(
        '/api/v1/ai/generate-image',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt: imagePrompt.trim(),
            size: imageSize,
            n: imageCount,
            quality: imageQuality
          })
        },
        'Ошибка генерации изображения'
      );
      images = data.images ?? [];
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка генерации изображения';
    } finally {
      loading = false;
    }
  }

  async function generateKeywords(e: Event): Promise<void> {
    e.preventDefault();
    error = '';
    copyMessage = '';
    kwResult = null;

    if (!kwProduct.trim()) {
      error = 'Введите название товара';
      return;
    }

    kwAttempted = true;
    loading = true;

    try {
      kwResult = await apiJson<KeywordsResult>(
        '/api/v1/ai/seo-keywords',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_name: kwProduct.trim(),
            category: kwCategory.trim() || undefined
          })
        },
        'Ошибка подбора ключей'
      );
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка подбора ключей';
    } finally {
      loading = false;
    }
  }

  async function runAudit(e: Event): Promise<void> {
    e.preventDefault();
    error = '';
    copyMessage = '';
    auditResult = null;

    if (!auditProduct.trim()) {
      error = 'Введите название товара';
      return;
    }

    let chars: Record<string, unknown> | undefined;
    if (auditCharacteristics.trim()) {
      try {
        const parsed = JSON.parse(auditCharacteristics);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error();
        chars = parsed;
      } catch {
        error = 'Характеристики должны быть JSON-объектом';
        return;
      }
    }

    auditAttempted = true;
    loading = true;

    try {
      auditResult = await apiJson<AuditResult>(
        '/api/v1/ai/sku-audit',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_name: auditProduct.trim(),
            description: auditDescription.trim() || undefined,
            characteristics: chars,
            images_count: auditImages
          })
        },
        'Ошибка аудита карточки'
      );
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка аудита карточки';
    } finally {
      loading = false;
    }
  }

  async function answerReview(e: Event): Promise<void> {
    e.preventDefault();
    error = '';
    copyMessage = '';
    reviewAnswer = '';

    if (!reviewProduct.trim() || !reviewText.trim()) {
      error = 'Заполните товар и текст отзыва/вопроса';
      return;
    }

    reviewAttempted = true;
    loading = true;

    try {
      const data = await apiJson<ReviewAnswerResponse>(
        '/api/v1/ai/answer-review',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_name: reviewProduct.trim(),
            review_text: reviewText.trim(),
            rating: reviewIsQuestion ? null : reviewRating,
            is_question: reviewIsQuestion
          })
        },
        'Ошибка генерации ответа'
      );
      reviewAnswer = data.answer ?? '';
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка генерации ответа';
    } finally {
      loading = false;
    }
  }
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="AI Studio"
    title="AI Студия"
    subtitle="Генерация изображений, SEO-ключи, аудит карточек и ответы на отзывы"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="OpenAI · LLM" dot={false} />
    </svelte:fragment>
  </PageHeader>

  {#if error && !(
    (activeTab === 'image' && imageAttempted && images.length === 0) ||
    (activeTab === 'keywords' && kwAttempted && !kwResult) ||
    (activeTab === 'audit' && auditAttempted && !auditResult) ||
    (activeTab === 'review' && reviewAttempted && !reviewAnswer)
  )}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}
  {#if copyMessage}
    <Alert variant="success" title="Готово">{copyMessage}</Alert>
  {/if}

  <GlassCard glow padding="lg" className="space-y-6">
    <div class="flex flex-wrap gap-2">
      <Button
        variant={activeTab === 'image' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('image')}
      >
        <ImageIcon class="h-4 w-4" aria-hidden="true" />
        Изображения
      </Button>
      <Button
        variant={activeTab === 'keywords' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('keywords')}
      >
        <Search class="h-4 w-4" aria-hidden="true" />
        SEO-ключи
      </Button>
      <Button
        variant={activeTab === 'audit' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('audit')}
      >
        <ClipboardCheck class="h-4 w-4" aria-hidden="true" />
        SKU-аудит
      </Button>
      <Button
        variant={activeTab === 'review' ? 'neural' : 'subtle'}
        size="sm"
        type="button"
        on:click={() => switchTab('review')}
      >
        <MessageCircle class="h-4 w-4" aria-hidden="true" />
        Ответы на отзывы
      </Button>
    </div>

    {#if activeTab === 'image'}
      <form on:submit={generateImage} class="space-y-6">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-foreground">Генерация изображений</h2>
          <p class="text-sm text-muted-foreground">
            Предметные фото и инфографика через OpenAI. Генерация может занять до минуты.
          </p>
        </div>

        <FormField label="Описание изображения" required let:controlId>
          <textarea
            id={controlId}
            class="page-textarea"
            rows="4"
            bind:value={imagePrompt}
            placeholder="Предметное фото белой хлопковой футболки на нейтральном фоне, студийный свет, высокое качество"
          ></textarea>
        </FormField>

        <div class="grid gap-4 sm:grid-cols-3">
          <FormField label="Размер" let:controlId>
            <select id={controlId} class="page-input" bind:value={imageSize}>
              <option value="1024x1024">1024×1024 (квадрат)</option>
              <option value="1024x1536">1024×1536 (вертикаль)</option>
              <option value="1536x1024">1536×1024 (горизонталь)</option>
            </select>
          </FormField>
          <FormField label="Качество" let:controlId>
            <select id={controlId} class="page-input" bind:value={imageQuality}>
              <option value="high">Высокое</option>
              <option value="medium">Среднее</option>
              <option value="low">Низкое</option>
            </select>
          </FormField>
          <FormField label="Вариантов" hint="От 1 до 4" let:controlId>
            <input id={controlId} class="page-input" type="number" min="1" max="4" bind:value={imageCount} />
          </FormField>
        </div>

        <Button type="submit" variant="neural" loading={loading} disabled={loading}>
          <ImageIcon class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Генерация (до 1 мин)...' : 'Сгенерировать (OpenAI)'}
        </Button>
      </form>

      {#if loading}
        <div class="grid gap-4 sm:grid-cols-2">
          <LoadingSkeleton variant="card" />
          {#if imageCount > 1}
            <LoadingSkeleton variant="card" />
          {/if}
        </div>
      {:else if error && imageAttempted && images.length === 0}
        <ErrorState
          title="Не удалось сгенерировать изображение"
          description={error}
          on:click={(e) => generateImage(e)}
        />
      {:else if imageAttempted && images.length === 0}
        <EmptyState
          icon={ImageIcon}
          title="Изображения не получены"
          description="Попробуйте изменить описание или параметры генерации."
        />
      {:else if images.length > 0}
        <div class="space-y-4">
          <Alert variant="info" title="AI-контент">
            Изображения сгенерированы моделью OpenAI. Проверьте результат перед публикацией на маркетплейсе.
          </Alert>
          <div class="grid gap-4 sm:grid-cols-2">
            {#each images as src}
              <GlassCard padding="none" className="overflow-hidden">
                <img {src} alt="Сгенерированное изображение" class="w-full" loading="lazy" />
                <div class="p-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    on:click={() => window.open(src, '_blank', 'noopener,noreferrer')}
                  >
                    Открыть / скачать
                  </Button>
                </div>
              </GlassCard>
            {/each}
          </div>
        </div>
      {/if}

    {:else if activeTab === 'keywords'}
      <form on:submit={generateKeywords} class="space-y-6">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-foreground">Подбор SEO-ключей</h2>
          <p class="text-sm text-muted-foreground">
            AI подберёт поисковые запросы и сгруппирует их по смысловым кластерам.
          </p>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <FormField label="Название товара" required let:controlId>
            <input
              id={controlId}
              class="page-input"
              bind:value={kwProduct}
              placeholder="Футболка мужская базовая"
            />
          </FormField>
          <FormField label="Категория" let:controlId>
            <input id={controlId} class="page-input" bind:value={kwCategory} placeholder="Одежда" />
          </FormField>
        </div>

        <Button type="submit" variant="neural" loading={loading} disabled={loading}>
          <Search class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Подбор...' : 'Подобрать ключи'}
        </Button>
      </form>

      {#if loading}
        <LoadingSkeleton variant="card" />
        <div class="grid gap-4 sm:grid-cols-2">
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
        </div>
      {:else if error && kwAttempted && !kwResult}
        <ErrorState title="Не удалось подобрать ключи" description={error} on:click={(e) => generateKeywords(e)} />
      {:else if kwResult}
        {#if isKeywordsEmpty(kwResult)}
          <EmptyState
            icon={Search}
            title="Ключи не найдены"
            description="AI не вернул ключевые слова. Попробуйте уточнить название или категорию."
          >
            <Button slot="action" variant="ghost" size="sm" on:click={(e) => generateKeywords(e)}>
              Повторить
            </Button>
          </EmptyState>
        {:else}
          <div class="space-y-4">
            {#if kwResult.provider}
              <StatusBadge variant="neutral" label="Провайдер: {kwResult.provider}" dot={false} />
            {/if}

            {#if kwResult.keywords?.length}
              <GlassCard padding="lg" className="space-y-4">
                <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 class="text-sm font-semibold text-foreground">Ключевые слова</h3>
                    <p class="text-xs text-muted-foreground">{kwResult.keywords.length} запросов</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    on:click={() => copyText((kwResult?.keywords ?? []).join(', '))}
                  >
                    <Copy class="h-4 w-4" aria-hidden="true" />
                    Копировать все
                  </Button>
                </div>
                <div class="flex flex-wrap gap-2">
                  {#each kwResult.keywords as kw}
                    <span class="chip">{kw}</span>
                  {/each}
                </div>
              </GlassCard>
            {/if}

            {#if kwResult.clusters && Object.keys(kwResult.clusters).length}
              <div class="grid gap-4 sm:grid-cols-2">
                {#each Object.entries(kwResult.clusters) as [name, items]}
                  <GlassCard padding="lg" className="space-y-3">
                    <h3 class="text-sm font-semibold text-foreground">{name}</h3>
                    <ul class="space-y-1.5 text-sm text-muted-foreground">
                      {#each items as item}
                        <li class="flex items-start gap-2">
                          <Sparkles class="mt-0.5 h-3.5 w-3.5 shrink-0 text-neural-purple" aria-hidden="true" />
                          <span>{item}</span>
                        </li>
                      {/each}
                    </ul>
                  </GlassCard>
                {/each}
              </div>
            {/if}

            <Alert variant="warning" title="Проверьте перед публикацией">
              Ключи сгенерированы AI — сверьте их с реальным спросом и правилами маркетплейса.
            </Alert>
          </div>
        {/if}
      {/if}

    {:else if activeTab === 'audit'}
      <form on:submit={runAudit} class="space-y-6">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-foreground">SKU-аудит карточки</h2>
          <p class="text-sm text-muted-foreground">
            Оценка качества карточки товара с проблемами и рекомендациями по улучшению.
          </p>
        </div>

        <FormField label="Название товара" required let:controlId>
          <input id={controlId} class="page-input" bind:value={auditProduct} />
        </FormField>

        <FormField label="Описание" let:controlId>
          <textarea id={controlId} class="page-textarea" rows="4" bind:value={auditDescription}></textarea>
        </FormField>

        <div class="grid gap-4 sm:grid-cols-2">
          <FormField
            label="Характеристики (JSON)"
            hint={auditCharsHint}
            let:controlId
          >
            <textarea
              id={controlId}
              class="page-textarea"
              rows="3"
              bind:value={auditCharacteristics}
              placeholder={'{"Материал":"Хлопок"}'}
            ></textarea>
          </FormField>
          <FormField label="Количество фото" let:controlId>
            <input
              id={controlId}
              class="page-input"
              type="number"
              min="0"
              max="100"
              bind:value={auditImages}
            />
          </FormField>
        </div>

        <Button type="submit" variant="neural" loading={loading} disabled={loading}>
          <ClipboardCheck class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Аудит...' : 'Проверить карточку'}
        </Button>
      </form>

      {#if loading}
        <LoadingSkeleton variant="card" />
        <div class="grid gap-4 sm:grid-cols-2">
          <LoadingSkeleton variant="metric" />
          <LoadingSkeleton variant="metric" />
        </div>
      {:else if error && auditAttempted && !auditResult}
        <ErrorState title="Не удалось провести аудит" description={error} on:click={(e) => runAudit(e)} />
      {:else if auditResult}
        <div class="space-y-4">
          <GlassCard glow padding="lg" className="space-y-4">
            <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div class="space-y-1">
                <p class="text-xs font-semibold uppercase tracking-wider text-neural-cyan">Оценка карточки</p>
                <p class="text-4xl font-bold text-foreground">{auditResult.score}/100</p>
              </div>
              <StatusBadge
                variant={getAuditScoreVariant(auditResult.score)}
                label={auditResult.score >= 80 ? 'Хорошо' : auditResult.score >= 50 ? 'Средне' : 'Нужны правки'}
                dot
              />
            </div>
            {#if auditResult.provider}
              <StatusBadge variant="neutral" label="Провайдер: {auditResult.provider}" dot={false} />
            {/if}
          </GlassCard>

          {#if auditResult.issues?.length}
            <GlassCard padding="lg" className="space-y-3">
              <h3 class="text-sm font-semibold text-foreground">Проблемы</h3>
              <ul class="space-y-2 text-sm text-muted-foreground">
                {#each auditResult.issues as issue}
                  <li class="surface rounded-lg px-3 py-2">{issue}</li>
                {/each}
              </ul>
            </GlassCard>
          {/if}

          {#if auditResult.recommendations?.length}
            <GlassCard padding="lg" className="space-y-3">
              <h3 class="text-sm font-semibold text-foreground">Рекомендации</h3>
              <ul class="space-y-2 text-sm text-muted-foreground">
                {#each auditResult.recommendations as recommendation}
                  <li class="flex items-start gap-2">
                    <Sparkles class="mt-0.5 h-4 w-4 shrink-0 text-neural-cyan" aria-hidden="true" />
                    <span>{recommendation}</span>
                  </li>
                {/each}
              </ul>
            </GlassCard>
          {/if}

          <Alert variant="info" title="AI-оценка">
            Аудит носит рекомендательный характер. Финальные правки карточки принимайте с учётом правил площадки.
          </Alert>
        </div>
      {/if}

    {:else}
      <form on:submit={answerReview} class="space-y-6">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold text-foreground">Ответ на отзыв или вопрос</h2>
          <p class="text-sm text-muted-foreground">
            AI сформирует вежливый ответ продавца для маркетплейса.
          </p>
        </div>

        <FormField label="Название товара" required let:controlId>
          <input id={controlId} class="page-input" bind:value={reviewProduct} />
        </FormField>

        <FormField label="Текст отзыва / вопроса" required let:controlId>
          <textarea id={controlId} class="page-textarea" rows="4" bind:value={reviewText}></textarea>
        </FormField>

        <div class="flex flex-wrap items-end gap-4">
          <label class="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" bind:checked={reviewIsQuestion} class="rounded border-border" />
            Это вопрос (а не отзыв)
          </label>
          {#if !reviewIsQuestion}
            <FormField label="Оценка" className="min-w-[120px]" let:controlId>
              <select id={controlId} class="page-input" bind:value={reviewRating}>
                {#each [5, 4, 3, 2, 1] as r}
                  <option value={r}>{r}</option>
                {/each}
              </select>
            </FormField>
          {/if}
        </div>

        <Button type="submit" variant="neural" loading={loading} disabled={loading}>
          <MessageCircle class="h-5 w-5" aria-hidden="true" />
          {loading ? 'Генерация...' : 'Сгенерировать ответ'}
        </Button>
      </form>

      {#if loading}
        <LoadingSkeleton variant="card" />
      {:else if error && reviewAttempted && !reviewAnswer}
        <ErrorState title="Не удалось сгенерировать ответ" description={error} on:click={(e) => answerReview(e)} />
      {:else if reviewAttempted && !reviewAnswer}
        <EmptyState
          icon={MessageCircle}
          title="Ответ не получен"
          description="AI не вернул текст. Попробуйте переформулировать отзыв или вопрос."
        />
      {:else if reviewAnswer}
        <GlassCard glow padding="lg" className="space-y-4">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 class="text-sm font-semibold text-foreground">Ответ продавца</h3>
              <p class="text-xs text-muted-foreground">Проверьте текст перед публикацией</p>
            </div>
            <Button variant="ghost" size="sm" on:click={() => copyText(reviewAnswer)}>
              <Copy class="h-4 w-4" aria-hidden="true" />
              Копировать
            </Button>
          </div>
          <p class="whitespace-pre-wrap rounded-xl border border-border/60 bg-card/40 p-4 text-sm text-muted-foreground">
            {reviewAnswer}
          </p>
          <Alert variant="warning" title="Перед отправкой">
            Отредактируйте ответ при необходимости — AI может не знать деталей вашего товара и политики магазина.
          </Alert>
        </GlassCard>
      {/if}
    {/if}
  </GlassCard>
</div>

<AppPageStyles />
