<script lang="ts">
  export let params: Record<string, string> = {};

  import { goto } from '$app/navigation';
  import {
    AlertCircle,
    CheckCircle2,
    Download,
    FileSpreadsheet,
    Package,
    Trash2,
    Upload
  } from 'lucide-svelte';
  import { apiJson, apiBlob } from '$lib/utils/http';
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

  interface ImportRowError {
    row: number;
    errors: string[];
  }

  interface ImportResponse {
    status: 'success' | 'partial_success';
    imported: number;
    skipped?: number;
    total_rows?: number;
    errors?: ImportRowError[];
    message: string;
  }

  let uploading = false;
  let templateDownloading = false;
  let result: ImportResponse | null = null;
  let error = '';
  let statusMessage = '';
  let dragOver = false;

  let fileInput: HTMLInputElement | null = null;

  const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

  function showError(message: string): void {
    error = message;
    statusMessage = '';
  }

  function showStatus(message: string): void {
    statusMessage = message;
    error = '';
  }

  function isXlsxFile(file: File): boolean {
    return file.name.toLowerCase().endsWith('.xlsx');
  }

  function validateFile(file: File): string | null {
    if (!isXlsxFile(file)) {
      return 'Пожалуйста, загрузите файл в формате .xlsx';
    }

    if (file.size <= 0) {
      return 'Файл пустой';
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      return 'Файл слишком большой. Максимальный размер — 10 МБ';
    }

    return null;
  }

  function resetFileInputValue(): void {
    if (fileInput) {
      fileInput.value = '';
    }
  }

  function clearImport(): void {
    result = null;
    error = '';
    statusMessage = '';
    resetFileInputValue();
  }

  async function handleFileSelect(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      await uploadFile(input.files[0]);
      resetFileInputValue();
    }
  }

  async function handleDrop(event: DragEvent): Promise<void> {
    event.preventDefault();
    dragOver = false;

    if (uploading) {
      return;
    }

    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
      await uploadFile(event.dataTransfer.files[0]);
      resetFileInputValue();
    }
  }

  function handleDragOver(event: DragEvent): void {
    event.preventDefault();
    if (!uploading) {
      dragOver = true;
    }
  }

  function handleDragLeave(): void {
    dragOver = false;
  }

  function triggerFileSelect(): void {
    if (!uploading) {
      fileInput?.click();
    }
  }

  async function uploadFile(file: File): Promise<void> {
    const validationError = validateFile(file);
    if (validationError) {
      showError(validationError);
      return;
    }

    uploading = true;
    showStatus('');
    result = null;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // apiJson без Content-Type: браузер сам выставит multipart boundary для FormData.
      const data = await apiJson<ImportResponse>(
        '/api/v1/products/import',
        {
          method: 'POST',
          body: formData,
          signal: controller.signal
        },
        'Не удалось выполнить импорт'
      );

      result = data;

      if (data.status === 'partial_success') {
        showStatus(`Импорт завершён частично: ${data.imported} успешно, ${data.skipped || 0} пропущено.`);
      } else {
        showStatus(`Импорт успешно завершён: добавлено ${data.imported} товаров.`);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        showError('Сервер долго отвечает. Попробуйте ещё раз.');
      } else {
        showError(err instanceof Error ? err.message : 'Не удалось выполнить импорт');
      }
    } finally {
      clearTimeout(timeoutId);
      uploading = false;
    }
  }

  async function downloadTemplate(): Promise<void> {
    showStatus('');
    templateDownloading = true;

    try {
      const blob = await apiBlob(
        '/api/v1/products/import/template',
        {},
        'Не удалось скачать шаблон'
      );

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'megashark_import_template.xlsx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      showStatus('Шаблон успешно скачан');
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Не удалось скачать шаблон');
    } finally {
      templateDownloading = false;
    }
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<AppPageStyles />

<div class="mx-auto max-w-[1400px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр · Импорт"
    title="Импорт из Excel"
    subtitle="Массовая загрузка товаров в каталог"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label=".xlsx" dot={false} />
      <StatusBadge variant="neutral" label="до 10 МБ" dot={false} />
    </svelte:fragment>

    <svelte:fragment slot="actions">
      <Button variant="ghost" size="sm" loading={templateDownloading} disabled={uploading} on:click={downloadTemplate}>
        <Download class="h-4 w-4" aria-hidden="true" />
        Скачать шаблон
      </Button>
    </svelte:fragment>
  </PageHeader>

  {#if statusMessage}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}
  {#if error && result}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}

  <div class="grid gap-6 xl:grid-cols-12">
    <!-- Зона загрузки -->
    <div class="space-y-4 xl:col-span-7">
      <GlassCard padding="md" className="border-warning/30 bg-warning/5">
        <div class="flex flex-wrap items-center gap-2">
          <AlertCircle class="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <p class="font-semibold text-foreground">Быстрая подсказка</p>
          <StatusBadge variant="warning" label="Формат" dot={false} />
        </div>
        <div class="mt-3 space-y-2 break-words text-sm text-foreground/90">
          <p>
            <span class="font-semibold text-foreground">Маркетплейс:</span>
            Wildberries, Ozon, Avito, Яндекс Маркет, KazanExpress
          </p>
          <p>
            <span class="font-semibold text-foreground">Свой товар:</span>
            укажите «да» или «нет» (также подходят true/false, 1/0, yes/no)
          </p>
        </div>
      </GlassCard>

      <div
        role="region"
        aria-label="Зона загрузки Excel файла"
        on:dragover={handleDragOver}
        on:dragleave={handleDragLeave}
        on:drop={handleDrop}
      >
        <GlassCard
          padding="lg"
          glow
          className="border-2 border-dashed {dragOver ? 'border-neural-cyan bg-neural-cyan/5' : 'border-border'}"
        >
          <FormField label="Файл Excel (.xlsx)" hint="Перетащите файл в зону ниже или выберите через кнопку" let:controlId>
            <input
              id={controlId}
              bind:this={fileInput}
              type="file"
              accept=".xlsx"
              class="hidden"
              on:change={handleFileSelect}
            />
          </FormField>

          {#if uploading}
            <div class="flex flex-col items-center py-6">
              <LoadingSkeleton variant="avatar" className="mx-auto" />
              <p class="mt-4 text-lg font-medium text-foreground">Импорт файла…</p>
              <p class="mt-1 text-sm text-muted-foreground">Это может занять до минуты</p>
            </div>
          {:else}
            <div class="text-center">
              <div class="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
                <Upload class="h-8 w-8" aria-hidden="true" />
              </div>
              <h3 class="mt-4 text-xl font-semibold text-foreground">Перетащите файл сюда</h3>
              <p class="mt-2 text-muted-foreground">или выберите файл на диске</p>
              <div class="mt-4 flex flex-wrap items-center justify-center gap-2">
                <StatusBadge variant="info" label=".xlsx" dot={false} />
                <StatusBadge variant="neutral" label="макс. 10 МБ" dot={false} />
              </div>

              <div class="mt-6 flex flex-wrap items-center justify-center gap-2">
                <Button variant="neural" disabled={uploading} on:click={triggerFileSelect}>
                  <FileSpreadsheet class="h-4 w-4" aria-hidden="true" />
                  Выбрать файл
                </Button>
                <Button variant="ghost" size="sm" loading={templateDownloading} on:click={downloadTemplate}>
                  <Download class="h-4 w-4" aria-hidden="true" />
                  Шаблон
                </Button>
                {#if result}
                  <Button variant="ghost" size="sm" on:click={clearImport}>
                    <Trash2 class="h-4 w-4" aria-hidden="true" />
                    Очистить
                  </Button>
                {/if}
              </div>
            </div>
          {/if}
        </GlassCard>
      </div>

      {#if error && !result && !uploading}
        <ErrorState title="Ошибка импорта" description={error}>
          <svelte:fragment slot="action">
            <Button variant="neural" on:click={triggerFileSelect}>
              <Upload class="h-4 w-4" aria-hidden="true" />
              Выбрать файл
            </Button>
          </svelte:fragment>
        </ErrorState>
      {/if}
    </div>

    <!-- Требования к файлу -->
    <GlassCard padding="lg" className="xl:col-span-5">
      <h3 class="flex items-center gap-2 text-lg font-semibold text-foreground">
        <FileSpreadsheet class="h-5 w-5 shrink-0 text-neural-cyan" aria-hidden="true" />
        Требования к файлу
      </h3>

      <p class="mt-3 break-words text-sm text-muted-foreground">
        Для импорта достаточно двух обязательных колонок:
        <span class="font-semibold text-foreground">name</span> и
        <span class="font-semibold text-foreground">price</span>.
        Остальные поля можно не заполнять.
      </p>

      <div class="mt-4 space-y-3 text-sm">
        <div class="flex items-start gap-3">
          <StatusBadge variant="success" label="Обязательно" dot={false} />
          <div class="min-w-0 break-words">
            <span class="font-medium text-foreground">Название товара</span>
            <span class="text-muted-foreground"> — колонка: name</span>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <StatusBadge variant="success" label="Обязательно" dot={false} />
          <div class="min-w-0 break-words">
            <span class="font-medium text-foreground">Цена в рублях</span>
            <span class="text-muted-foreground"> — больше 0 (колонка: price)</span>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <StatusBadge variant="neutral" label="Необязательно" dot={false} />
          <div class="min-w-0 break-words">
            <span class="font-medium text-foreground">Маркетплейс</span>
            <span class="text-muted-foreground"> — Wildberries, Ozon, Avito, Яндекс Маркет, KazanExpress (по умолчанию Wildberries; колонка: marketplace)</span>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <StatusBadge variant="neutral" label="Необязательно" dot={false} />
          <div class="min-w-0 break-words">
            <span class="font-medium text-foreground">Категория</span>
            <span class="text-muted-foreground"> — колонка: category</span>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <StatusBadge variant="neutral" label="Необязательно" dot={false} />
          <div class="min-w-0 break-words">
            <span class="font-medium text-foreground">Бренд</span>
            <span class="text-muted-foreground"> — колонка: brand</span>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <StatusBadge variant="neutral" label="Необязательно" dot={false} />
          <div class="min-w-0 break-words">
            <span class="font-medium text-foreground">Свой товар</span>
            <span class="text-muted-foreground"> — «да»/«нет» (также: true/false, 1/0, yes/no), по умолчанию «нет» (колонка: is_own)</span>
          </div>
        </div>
      </div>
    </GlassCard>
  </div>

  <!-- Результат импорта -->
  {#if result}
    <GlassCard padding="lg" glow>
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
        <span
          class="flex h-16 w-16 shrink-0 items-center justify-center rounded-full {result.status === 'partial_success'
            ? 'bg-warning/20 text-warning'
            : 'bg-success/20 text-success'}"
        >
          {#if result.status === 'partial_success'}
            <AlertCircle class="h-8 w-8" aria-hidden="true" />
          {:else}
            <CheckCircle2 class="h-8 w-8" aria-hidden="true" />
          {/if}
        </span>
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="text-xl font-semibold text-foreground">
              {result.status === 'partial_success' ? 'Импорт завершён с пропусками' : 'Импорт завершён!'}
            </h3>
            <StatusBadge
              variant={result.status === 'partial_success' ? 'warning' : 'success'}
              label={result.status === 'partial_success' ? 'Частичный успех' : 'Успех'}
              dot={false}
            />
          </div>
          <p class="mt-1 break-words text-muted-foreground">{result.message}</p>
        </div>
      </div>

      <div class="mt-6 grid gap-4 sm:grid-cols-3">
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-sm text-muted-foreground">Обработано строк</p>
          <p class="mt-1 text-2xl font-bold text-foreground">{result.total_rows ?? 0}</p>
        </div>
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-sm text-muted-foreground">Импортировано</p>
          <p class="mt-1 text-2xl font-bold text-success">{result.imported}</p>
        </div>
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-sm text-muted-foreground">Пропущено</p>
          <p class="mt-1 text-2xl font-bold {result.skipped ? 'text-warning' : 'text-foreground'}">
            {result.skipped ?? 0}
          </p>
        </div>
      </div>

      {#if result.errors && result.errors.length > 0}
        <Alert variant="warning" title="Ошибки по строкам (первые {result.errors.length})" className="mt-6">
          <ul class="mt-2 space-y-2 text-sm">
            {#each result.errors as rowError}
              <li class="break-words">
                <span class="font-medium text-foreground">Строка {rowError.row}:</span>
                {rowError.errors.join('; ')}
              </li>
            {/each}
          </ul>
        </Alert>
      {/if}

      <div class="mt-6 flex flex-wrap gap-2">
        <Button variant="neural" on:click={() => goto('/products')}>
          <Package class="h-4 w-4" aria-hidden="true" />
          Перейти к товарам
        </Button>
        <Button variant="ghost" on:click={clearImport}>
          <Trash2 class="h-4 w-4" aria-hidden="true" />
          Загрузить другой файл
        </Button>
      </div>
    </GlassCard>
  {:else if !uploading}
    <EmptyState
      title="Результат импорта"
      description="Загрузите файл .xlsx — здесь появится статистика: обработанные строки, импорт и пропуски."
      icon={Package}
    />
  {/if}
</div>
