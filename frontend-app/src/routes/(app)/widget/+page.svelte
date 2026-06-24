<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { apiJson, ApiError } from '$lib/utils/http';
  import {
    GlassCard,
    PageHeader,
    StatusBadge,
    Button,
    Alert,
    FormField,
    LoadingSkeleton,
    ErrorState
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';
  import { Copy, RefreshCw, Save, Eye, Lock, LayoutGrid, Code2 } from 'lucide-svelte';

  interface WidgetConfig {
    public_key: string;
    is_enabled: boolean;
    title: string;
    welcome_message: string;
    accent_color: string;
    allowed_origins: string | null;
    embed_code: string;
  }

  interface WidgetSaveResponse {
    status: string;
    public_key?: string;
    is_enabled?: boolean;
    embed_code?: string;
  }

  interface RotateKeyResponse {
    status: string;
    public_key: string;
    embed_code: string;
  }

  let loading = true;
  let saving = false;
  let rotating = false;
  let loadError = '';
  let actionError = '';
  let successMessage = '';
  let copyMessage = '';

  /** 402 → нет доступа по тарифу (widget_access). */
  let locked = false;

  let config: WidgetConfig = {
    public_key: '',
    is_enabled: true,
    title: 'Помощник магазина',
    welcome_message: 'Здравствуйте! Чем помочь?',
    accent_color: '#6d28d9',
    allowed_origins: '',
    embed_code: ''
  };

  let previewKey = 0;

  $: frameUrl = config.public_key ? `/api/v1/widget/public/${config.public_key}/frame` : '';

  async function loadConfig(): Promise<void> {
    loading = true;
    loadError = '';
    locked = false;

    try {
      const data = await apiJson<WidgetConfig>(
        '/api/v1/widget/config',
        {},
        'Не удалось загрузить настройки виджета'
      );
      config = { ...config, ...data, allowed_origins: data.allowed_origins ?? '' };
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 402) {
        locked = true;
        return;
      }
      loadError = err instanceof Error ? err.message : 'Ошибка загрузки виджета';
    } finally {
      loading = false;
    }
  }

  async function saveConfig(e: Event): Promise<void> {
    e.preventDefault();
    actionError = '';
    successMessage = '';
    saving = true;

    try {
      const data = await apiJson<WidgetSaveResponse>(
        '/api/v1/widget/config',
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            is_enabled: config.is_enabled,
            title: config.title,
            welcome_message: config.welcome_message,
            accent_color: config.accent_color,
            allowed_origins: config.allowed_origins || null
          })
        },
        'Не удалось сохранить настройки'
      );

      config.embed_code = data.embed_code ?? config.embed_code;
      successMessage = 'Настройки сохранены';
      previewKey += 1;
    } catch (err: unknown) {
      actionError = err instanceof Error ? err.message : 'Ошибка сохранения';
    } finally {
      saving = false;
    }
  }

  async function rotateKey(): Promise<void> {
    if (!confirm('Сгенерировать новый ключ? Старый код вставки перестанет работать.')) return;

    actionError = '';
    successMessage = '';
    rotating = true;

    try {
      const data = await apiJson<RotateKeyResponse>(
        '/api/v1/widget/rotate-key',
        { method: 'POST' },
        'Не удалось обновить ключ'
      );

      config.public_key = data.public_key ?? config.public_key;
      config.embed_code = data.embed_code ?? config.embed_code;
      successMessage = 'Сгенерирован новый ключ виджета';
      previewKey += 1;
    } catch (err: unknown) {
      actionError = err instanceof Error ? err.message : 'Ошибка обновления ключа';
    } finally {
      rotating = false;
    }
  }

  async function copyEmbed(): Promise<void> {
    copyMessage = '';
    try {
      await navigator.clipboard.writeText(config.embed_code);
      copyMessage = 'Код вставки скопирован в буфер обмена';
    } catch {
      copyMessage = 'Не удалось скопировать автоматически';
    }
  }

  onMount(loadConfig);
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Widget Control Center"
    title="Виджет на сайт"
    subtitle="MegaShark-ассистент, встраиваемый на ваш сайт одной строкой кода"
  >
    <svelte:fragment slot="meta">
      {#if locked}
        <StatusBadge variant="warning" label="Требуется тариф Business" dot />
      {:else if !loading}
        <StatusBadge variant={config.is_enabled ? 'success' : 'neutral'} label={config.is_enabled ? 'Виджет включён' : 'Виджет выключен'} dot={config.is_enabled} />
      {/if}
    </svelte:fragment>
  </PageHeader>

  {#if loading}
    <div class="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
      <GlassCard padding="lg" className="space-y-4">
        <LoadingSkeleton variant="text" lines={2} />
        <LoadingSkeleton variant="card" />
        <LoadingSkeleton variant="card" />
      </GlassCard>
      <GlassCard padding="lg">
        <LoadingSkeleton variant="card" className="!min-h-[540px]" />
      </GlassCard>
    </div>

  {:else if locked}
    <GlassCard glow padding="lg" className="mx-auto max-w-lg space-y-5 text-center">
      <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-warning/30 bg-warning/10">
        <Lock class="h-8 w-8 text-warning" aria-hidden="true" />
      </div>
      <div class="space-y-2">
        <h2 class="text-xl font-semibold text-foreground">Виджет доступен на тарифе Business</h2>
        <p class="text-sm text-muted-foreground">
          Встраиваемый AI-ассистент для вашего сайта — платная функция тарифа Business.
          На текущем тарифе настройка и вставка виджета недоступны.
        </p>
      </div>
      <Alert variant="info" title="Что даёт виджет">
        Умный чат-консультант на сайте магазина: отвечает покупателям на основе вашего ассортимента.
      </Alert>
      <Button variant="neural" on:click={() => goto('/billing')}>
        Перейти к тарифам
      </Button>
    </GlassCard>

  {:else if loadError}
    <ErrorState title="Не удалось загрузить настройки виджета" description={loadError} on:click={loadConfig} />

  {:else}
    {#if successMessage}
      <Alert variant="success" title="Готово">{successMessage}</Alert>
    {/if}
    {#if actionError}
      <Alert variant="error" title="Ошибка">{actionError}</Alert>
    {/if}
    {#if copyMessage}
      <Alert variant="info" title="Буфер обмена">{copyMessage}</Alert>
    {/if}

    <div class="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
      <!-- Настройки -->
      <GlassCard glow padding="lg" className="space-y-6">
        <div class="flex items-center gap-3">
          <span class="flex h-10 w-10 items-center justify-center rounded-xl border border-neural-purple/20 bg-neural-purple/10 text-neural-purple">
            <LayoutGrid class="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 class="text-lg font-semibold text-foreground">Настройки виджета</h2>
            <p class="text-sm text-muted-foreground">Внешний вид и поведение чата на сайте</p>
          </div>
        </div>

        <form on:submit={saveConfig} class="space-y-5">
          <label class="surface flex cursor-pointer items-center gap-3 p-4 text-sm font-medium text-foreground">
            <input type="checkbox" bind:checked={config.is_enabled} class="h-4 w-4 rounded border-border accent-primary" />
            Виджет включён на сайте
          </label>

          <FormField label="Заголовок чата" let:controlId>
            <input id={controlId} class="page-input" maxlength="120" bind:value={config.title} />
          </FormField>

          <FormField label="Приветственное сообщение" let:controlId>
            <textarea id={controlId} class="page-textarea" rows="3" maxlength="500" bind:value={config.welcome_message}></textarea>
          </FormField>

          <div class="grid gap-4 sm:grid-cols-2">
            <FormField label="Акцентный цвет" hint="HEX-формат, например #6d28d9" let:controlId>
              <div class="flex items-center gap-3">
                <input
                  id="{controlId}-picker"
                  type="color"
                  class="focus-ring h-11 w-16 shrink-0 cursor-pointer rounded-lg border border-border/60 bg-card"
                  bind:value={config.accent_color}
                  aria-label="Выбор цвета"
                />
                <input id={controlId} class="page-input" bind:value={config.accent_color} maxlength="9" />
              </div>
            </FormField>

            <FormField
              label="Разрешённые домены"
              hint="Через запятую. Оставьте пустым для любых доменов."
              let:controlId
            >
              <input
                id={controlId}
                class="page-input"
                bind:value={config.allowed_origins}
                placeholder="https://shop.ru, https://my.store"
              />
            </FormField>
          </div>

          <Button type="submit" variant="neural" loading={saving} disabled={saving}>
            <Save class="h-5 w-5" aria-hidden="true" />
            {saving ? 'Сохранение...' : 'Сохранить настройки'}
          </Button>
        </form>

        <div class="divider"></div>

        <!-- Код вставки -->
        <div class="space-y-4">
          <div class="flex items-center gap-2">
            <Code2 class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            <h3 class="text-sm font-semibold text-foreground">Код вставки на сайт</h3>
          </div>
          <p class="text-xs text-muted-foreground">
            Вставьте этот код перед закрывающим тегом &lt;/body&gt; вашего сайта.
          </p>

          {#if config.embed_code}
            <pre class="surface max-w-full overflow-x-auto p-4 text-xs leading-relaxed text-muted-foreground"><code class="break-all whitespace-pre-wrap sm:whitespace-pre">{config.embed_code}</code></pre>
          {:else}
            <p class="text-sm text-muted-foreground">Сохраните настройки — код вставки появится здесь.</p>
          {/if}

          <div class="flex flex-wrap gap-2">
            <Button variant="neural" size="sm" disabled={!config.embed_code} on:click={copyEmbed}>
              <Copy class="h-4 w-4" aria-hidden="true" />
              Копировать код
            </Button>
            <Button variant="ghost" size="sm" loading={rotating} disabled={rotating} on:click={rotateKey}>
              <RefreshCw class="h-4 w-4" aria-hidden="true" />
              {rotating ? 'Обновление...' : 'Новый ключ'}
            </Button>
          </div>
        </div>
      </GlassCard>

      <!-- Превью -->
      <GlassCard glow padding="lg" className="space-y-4">
        <div class="flex items-center gap-2">
          <Eye class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
          <h2 class="text-lg font-semibold text-foreground">Живое превью</h2>
        </div>

        {#if config.is_enabled && frameUrl}
          {#key previewKey}
            <div class="surface overflow-hidden rounded-xl border-neural-cyan/20 shadow-glow-sm">
              <iframe
                src={frameUrl}
                title="Превью виджета"
                class="h-[min(540px,70vh)] w-full bg-white"
              ></iframe>
            </div>
          {/key}
        {:else}
          <div class="flex h-[min(540px,70vh)] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border/60 bg-muted/20 p-6 text-center">
            <LayoutGrid class="h-10 w-10 text-muted-foreground/50" aria-hidden="true" />
            <p class="text-sm text-muted-foreground">
              {#if !config.is_enabled}
                Включите виджет и сохраните настройки, чтобы увидеть превью.
              {:else}
                Сохраните настройки, чтобы обновить превью.
              {/if}
            </p>
          </div>
        {/if}

        {#if config.public_key}
          <p class="text-xs text-muted-foreground">
            Публичный ключ:
            <span class="font-mono text-foreground">{config.public_key}</span>
          </p>
        {/if}
      </GlassCard>
    </div>
  {/if}
</div>

<AppPageStyles />
