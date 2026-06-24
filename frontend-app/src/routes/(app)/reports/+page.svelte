<script lang="ts">
  import { apiBlob } from '$lib/utils/http';
  import { GlassCard, PageHeader, StatusBadge, Button, Alert } from '$lib/components';
  import { FileSpreadsheet, FileText, Download, Check, ShieldCheck } from 'lucide-svelte';

  type ReportFormat = 'xlsx' | 'pdf';

  let loadingFormat: ReportFormat | null = null;
  let error = '';
  let statusMessage = '';

  // Что входит в отчёт — статичное описание содержимого (без фейковых действий).
  const reportContents = [
    'Ваши товары: название, бренд, категория, цена',
    'Отслеживаемые конкуренты и их цены',
    'Рейтинги и количество отзывов',
    'Сводные метрики по ассортименту'
  ];

  function triggerDownload(blob: Blob, format: ReportFormat): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    link.download = `megashark_report_${stamp}.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadReport(format: ReportFormat): Promise<void> {
    error = '';
    statusMessage = '';
    loadingFormat = format;

    try {
      const blob = await apiBlob(
        `/api/v1/reports/competitors?fmt=${format}`,
        {},
        'Не удалось сформировать отчёт'
      );
      triggerDownload(blob, format);
      statusMessage = `Отчёт (${format.toUpperCase()}) сформирован и скачан`;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка формирования отчёта';
    } finally {
      loadingFormat = null;
    }
  }
</script>

<div class="mx-auto max-w-[1100px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр"
    title="Отчёты"
    subtitle="Выгрузка по товарам и конкурентам в Excel или PDF"
  >
    <svelte:fragment slot="meta">
      <StatusBadge variant="info" label="Лимит зависит от тарифа" dot={false} />
    </svelte:fragment>
  </PageHeader>

  {#if statusMessage}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}
  {#if error}
    <Alert variant="error" title="Не удалось сформировать отчёт">{error}</Alert>
  {/if}

  <div class="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
    <!-- Действия: формирование и скачивание -->
    <GlassCard glow padding="lg" className="space-y-6">
      <div class="space-y-1">
        <h2 class="text-lg font-semibold text-foreground">Сформировать отчёт</h2>
        <p class="text-sm text-muted-foreground">
          Отчёт собирается по актуальным данным мониторинга. Выберите формат выгрузки.
        </p>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <!-- XLSX -->
        <div class="surface flex flex-col gap-4 p-5">
          <div class="flex items-center gap-3">
            <span class="flex h-11 w-11 items-center justify-center rounded-xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
              <FileSpreadsheet class="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p class="font-semibold text-foreground">Excel</p>
              <p class="text-xs text-muted-foreground">Таблица товаров (.xlsx)</p>
            </div>
          </div>
          <Button
            variant="neural"
            size="lg"
            fullWidth
            loading={loadingFormat === 'xlsx'}
            disabled={loadingFormat !== null}
            on:click={() => downloadReport('xlsx')}
          >
            {#if loadingFormat !== 'xlsx'}
              <Download class="h-5 w-5" aria-hidden="true" />
            {/if}
            {loadingFormat === 'xlsx' ? 'Готовим Excel...' : 'Скачать XLSX'}
          </Button>
        </div>

        <!-- PDF -->
        <div class="surface flex flex-col gap-4 p-5">
          <div class="flex items-center gap-3">
            <span class="flex h-11 w-11 items-center justify-center rounded-xl border border-neural-purple/20 bg-neural-purple/10 text-neural-purple">
              <FileText class="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <p class="font-semibold text-foreground">PDF</p>
              <p class="text-xs text-muted-foreground">Сводный отчёт (.pdf)</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="lg"
            fullWidth
            loading={loadingFormat === 'pdf'}
            disabled={loadingFormat !== null}
            on:click={() => downloadReport('pdf')}
          >
            {#if loadingFormat !== 'pdf'}
              <FileText class="h-5 w-5" aria-hidden="true" />
            {/if}
            {loadingFormat === 'pdf' ? 'Готовим PDF...' : 'Скачать PDF'}
          </Button>
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        <StatusBadge variant="info" label="XLSX — таблица товаров" dot={false} />
        <StatusBadge variant="ai" label="PDF — сводный отчёт" dot={false} />
      </div>
    </GlassCard>

    <!-- Что входит в отчёт -->
    <GlassCard padding="lg" className="space-y-4">
      <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
        <ShieldCheck class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
        Что внутри
      </h2>
      <ul class="space-y-2.5">
        {#each reportContents as item}
          <li class="flex items-start gap-2.5 text-sm text-muted-foreground">
            <Check class="mt-0.5 h-4 w-4 shrink-0 text-neural-cyan" aria-hidden="true" />
            <span>{item}</span>
          </li>
        {/each}
      </ul>
      <div class="divider"></div>
      <p class="text-xs text-muted-foreground">
        Формирование может занять несколько секунд — отчёт собирается на сервере и скачивается автоматически.
      </p>
    </GlassCard>
  </div>
</div>
