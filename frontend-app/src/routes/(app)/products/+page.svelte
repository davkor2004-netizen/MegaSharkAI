<script lang="ts">
  export let params: Record<string, string> = {};

  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/stores';
  import {
    Boxes,
    ChevronLeft,
    ChevronRight,
    Download,
    History,
    Package,
    Search,
    Trash2,
    X,
    Zap
  } from 'lucide-svelte';
  import { apiJson, apiBlob, apiNoContent } from '$lib/utils/http';
  import {
    Alert,
    Button,
    EmptyState,
    ErrorState,
    FormField,
    GlassCard,
    LoadingSkeleton,
    MetricCard,
    PageHeader,
    StatusBadge
  } from '$lib/components';
  import AppPageStyles from '$lib/components/layout/AppPageStyles.svelte';
  
  type ProductSortField = 'created_at' | 'name' | 'price';
  type SortOrder = 'asc' | 'desc';
  type ProductFilterType = 'all' | 'own' | 'competitor';

  interface ProductItem {
    id: number;
    name: string;
    price: number | null;
    old_price: number | null;
    brand: string | null;
    marketplace: string | null;
    image_url: string | null;
    is_own: boolean;
    created_at: string | null;
  }

  interface ProductsListResponse {
    items: ProductItem[];
    total: number;
    limit?: number;
    offset?: number;
  }

  interface PriceHistoryRecord {
    id: number;
    price: number | null;
    old_price: number | null;
    discount: number | null;
    created_at: string | null;
  }

  let products: ProductItem[] = [];
  let loading = true;
  let refreshing = false;
  let deleting = false;
  let error = '';
  let statusMessage = '';

  let selectedProduct: ProductItem | null = null;
  let priceHistory: PriceHistoryRecord[] = [];
  let priceHistoryLoading = false;
  let showHistoryModal = false;
  
  // Массовые операции
  let selectedIds: number[] = [];
  let selectAll = false;
  
  // Фильтры
  let searchQuery = '';
  let filterMarketplace = 'all';
  let filterType: ProductFilterType = 'all';
  let sortBy: ProductSortField = 'created_at';
  let sortOrder: SortOrder = 'desc';

  // Пагинация
  let currentPage = 1;
  let pageSize = 30;
  let totalProducts = 0;

  // Техническое состояние для debounce и защиты от гонок запросов.
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let activeRequestController: AbortController | null = null;
  let lastRequestId = 0;

  /**
   * Guard для реакции на внешние изменения URL (Topbar goto).
   * replaceState из syncFiltersToUrl() не обновляет $page — отслеживаем только $page.url.search.
   * До первого onMount реактивный блок не срабатывает, чтобы не дублировать начальную загрузку.
   */
  let urlFiltersHydrated = false;
  let previousPageUrlSearch = '';

  const currencyFormatter = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  });

  $: totalPages = Math.max(1, Math.ceil(totalProducts / pageSize));
  $: pageStart = totalProducts === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  $: pageEnd = Math.min(currentPage * pageSize, totalProducts);

  // Сводка по текущей странице (без доп. запросов к API): сколько своих/конкурентов
  // среди загруженных товаров. Используется в MetricCard как контекст текущей выборки.
  $: ownOnPage = products.filter((item) => item.is_own).length;
  $: competitorOnPage = products.filter((item) => !item.is_own).length;
  $: hasActiveFilters =
    searchQuery.trim() !== '' || filterMarketplace !== 'all' || filterType !== 'all';

  onMount(async () => {
    restoreFiltersFromUrl();
    previousPageUrlSearch = $page.url.search;
    urlFiltersHydrated = true;
    await loadProducts({ fullScreen: true });
  });

  /**
   * Повторно применяет фильтры, если SvelteKit-навигация изменила query (например, поиск из Topbar),
   * пока компонент уже смонтирован. replaceState в syncFiltersToUrl() $page не трогает — цикл не возникает.
   */
  $: if (urlFiltersHydrated && $page.url.search !== previousPageUrlSearch) {
    previousPageUrlSearch = $page.url.search;

    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }

    restoreFiltersFromUrl();
    clearSelection();
    void loadProducts({ fullScreen: false });
  }
  
  onDestroy(() => {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }

    activeRequestController?.abort();
  });
  
  /**
   * Восстанавливает состояние фильтров/сортировки/страницы из URL,
   * чтобы пользователь мог обновлять страницу без потери контекста.
   */
  function restoreFiltersFromUrl(): void {
    const params = new URLSearchParams(window.location.search);

    searchQuery = params.get('search') || '';
    filterMarketplace = params.get('marketplace') || 'all';

    const typeParam = params.get('type');
    if (typeParam === 'own' || typeParam === 'competitor' || typeParam === 'all') {
      filterType = typeParam;
    }

    const sortByParam = params.get('sort_by');
    if (sortByParam === 'created_at' || sortByParam === 'name' || sortByParam === 'price') {
      sortBy = sortByParam;
    }

    const sortOrderParam = params.get('sort_order');
    if (sortOrderParam === 'asc' || sortOrderParam === 'desc') {
      sortOrder = sortOrderParam;
    }

    const pageParam = Number(params.get('page'));
    if (Number.isFinite(pageParam) && pageParam > 0) {
      currentPage = Math.floor(pageParam);
    }

    const pageSizeParam = Number(params.get('page_size'));
    if (Number.isFinite(pageSizeParam) && [20, 30, 50, 100].includes(pageSizeParam)) {
      pageSize = pageSizeParam;
    }
  }

  /**
   * Синхронизирует текущее состояние фильтров с URL.
   * Используем replaceState, чтобы не засорять историю браузера при каждом вводе символа.
   */
  function syncFiltersToUrl(): void {
    const params = new URLSearchParams();

    if (searchQuery.trim()) params.set('search', searchQuery.trim());
    if (filterMarketplace !== 'all') params.set('marketplace', filterMarketplace);
    if (filterType !== 'all') params.set('type', filterType);
    params.set('sort_by', sortBy);
    params.set('sort_order', sortOrder);
    params.set('page', String(currentPage));
    params.set('page_size', String(pageSize));

    const url = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', url);
  }

  function showError(message: string): void {
    error = message;
    statusMessage = '';
  }

  function showStatus(message: string): void {
    statusMessage = message;
    error = '';
  }

  /**
   * Загружает список товаров.
   * Важно: есть защита от гонок запросов — применяем только последний ответ.
   */
  async function loadProducts(options: { fullScreen?: boolean } = {}): Promise<void> {
    const fullScreen = options.fullScreen ?? false;

    if (fullScreen) {
      loading = true;
    } else {
      refreshing = true;
    }

    showStatus('');
    syncFiltersToUrl();

    // Отменяем предыдущий запрос: если пользователь быстро меняет фильтры,
    // серверные ответы не должны перетирать более свежие данные.
    activeRequestController?.abort();
    activeRequestController = new AbortController();
    const requestId = ++lastRequestId;

    const timeoutId = setTimeout(() => activeRequestController?.abort(), 15000);

    try {
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.set('search', searchQuery.trim());
      if (filterMarketplace !== 'all') params.set('marketplace', filterMarketplace);
      if (filterType !== 'all') params.set('is_own', filterType === 'own' ? 'true' : 'false');
      params.set('sort_by', sortBy);
      params.set('sort_order', sortOrder);
      params.set('limit', String(pageSize));
      params.set('offset', String((currentPage - 1) * pageSize));

      const data = await apiJson<ProductsListResponse>(
        `/api/v1/products/list?${params.toString()}`,
        { signal: activeRequestController.signal },
        'Не удалось загрузить товары'
      );

      if (requestId !== lastRequestId) return;

      products = Array.isArray(data.items) ? data.items : [];
      totalProducts = Number(data.total ?? products.length);

      // Если после удаления/фильтра страница стала пустой, возвращаемся на предыдущую.
      if (products.length === 0 && currentPage > 1) {
        currentPage = currentPage - 1;
        await loadProducts({ fullScreen: false });
        return;
      }

      // Сбрасываем выделение для строк, которых уже нет на текущей странице.
      selectedIds = selectedIds.filter((id) => products.some((item) => item.id === id));
      selectAll = products.length > 0 && selectedIds.length === products.length;

      showStatus(`Загружено ${products.length} из ${totalProducts} товаров`);
    } catch (err) {
      if (requestId !== lastRequestId) return;

      console.error('Ошибка загрузки товаров:', err);
      if (err instanceof DOMException && err.name === 'AbortError') {
        showError('Сервер долго отвечает. Попробуйте ещё раз.');
      } else {
        showError(err instanceof Error ? err.message : 'Ошибка соединения с сервером');
      }
      products = [];
      totalProducts = 0;
    } finally {
      clearTimeout(timeoutId);
      if (requestId === lastRequestId) {
        loading = false;
        refreshing = false;
      }
    }
  }

  async function deleteProductById(id: number): Promise<void> {
    await apiNoContent(`/api/v1/products/${id}`, { method: 'DELETE' }, 'Ошибка удаления товара');
  }

  async function deleteProduct(id: number): Promise<void> {
    if (!confirm('Удалить этот товар?')) return;

    deleting = true;
    showStatus('');

    try {
      await deleteProductById(id);
      showStatus('Товар успешно удалён');

      if (selectedIds.includes(id)) {
        selectedIds = selectedIds.filter((itemId) => itemId !== id);
      }

      await loadProducts({ fullScreen: false });
    } catch (err) {
      console.error('Ошибка удаления:', err);
      showError(err instanceof Error ? err.message : 'Не удалось удалить товар');
    } finally {
      deleting = false;
    }
  }

  function toggleSelect(id: number): void {
    const index = selectedIds.indexOf(id);
    if (index > -1) {
      selectedIds.splice(index, 1);
    } else {
      selectedIds.push(id);
    }

    selectedIds = [...selectedIds];
    selectAll = products.length > 0 && selectedIds.length === products.length;
  }

  function toggleSelectAll(): void {
    selectAll = !selectAll;
    selectedIds = selectAll ? products.map((item) => item.id) : [];
  }

  function clearSelection(): void {
    selectedIds = [];
    selectAll = false;
  }

  async function deleteSelected(): Promise<void> {
    if (selectedIds.length === 0) return;
    if (!confirm(`Удалить ${selectedIds.length} выбранных товаров?`)) return;

    deleting = true;
    showStatus('');

    try {
      const deleteResults = await Promise.allSettled(selectedIds.map((id) => deleteProductById(id)));
      const successCount = deleteResults.filter((result) => result.status === 'fulfilled').length;
      const failedCount = deleteResults.length - successCount;

      clearSelection();
      await loadProducts({ fullScreen: false });

      if (failedCount > 0) {
        showStatus(`Удалено ${successCount} из ${deleteResults.length}. ${failedCount} не удалось удалить.`);
      } else {
        showStatus(`Удалено ${successCount} товаров.`);
      }
    } catch (err) {
      console.error('Ошибка массового удаления:', err);
      showError('Не удалось выполнить массовое удаление');
    } finally {
      deleting = false;
    }
  }

  async function viewPriceHistory(product: ProductItem): Promise<void> {
    selectedProduct = product;
    showHistoryModal = true;
    priceHistory = [];
    priceHistoryLoading = true;

    try {
      const data = await apiJson<PriceHistoryRecord[]>(
        `/api/v1/products/${product.id}/price-history?limit=30`,
        {},
        'Не удалось загрузить историю цен'
      );
      priceHistory = Array.isArray(data) ? data : [];
    } catch (err) {
      console.error('Ошибка загрузки истории:', err);
      priceHistory = [];
      showError(err instanceof Error ? err.message : 'Не удалось загрузить историю цен');
    } finally {
      priceHistoryLoading = false;
    }
  }

  function closeHistoryModal(): void {
    showHistoryModal = false;
    selectedProduct = null;
    priceHistory = [];
    priceHistoryLoading = false;
  }

  async function exportToExcel(): Promise<void> {
    showStatus('');

    try {
      const params = new URLSearchParams();
      if (filterMarketplace !== 'all') params.set('marketplace', filterMarketplace);
      if (filterType !== 'all') params.set('is_own', filterType === 'own' ? 'true' : 'false');

      const blob = await apiBlob(
        `/api/v1/products/export?${params.toString()}`,
        {},
        'Не удалось экспортировать товары'
      );

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `megashark_products_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);

      showStatus('Экспорт успешно завершён');
    } catch (err) {
      console.error('Ошибка экспорта:', err);
      showError(err instanceof Error ? err.message : 'Не удалось экспортировать товары');
    }
  }

  function onSearchInput(): void {
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }

    searchDebounceTimer = setTimeout(async () => {
      currentPage = 1;
      await loadProducts({ fullScreen: false });
    }, 400);
  }

  async function applyFilters(): Promise<void> {
    currentPage = 1;
    clearSelection();
    await loadProducts({ fullScreen: false });
  }

  async function clearFilters(): Promise<void> {
    searchQuery = '';
    filterMarketplace = 'all';
    filterType = 'all';
    sortBy = 'created_at';
    sortOrder = 'desc';
    currentPage = 1;
    clearSelection();
    await loadProducts({ fullScreen: false });
  }

  async function goToPage(page: number): Promise<void> {
    if (page < 1 || page > totalPages || page === currentPage) return;
    currentPage = page;
    clearSelection();
    await loadProducts({ fullScreen: false });
  }

  async function onPageSizeChange(): Promise<void> {
    currentPage = 1;
    clearSelection();
    await loadProducts({ fullScreen: false });
  }

  function handleWindowKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && showHistoryModal) {
      closeHistoryModal();
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';

    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    });
  }
  
  function formatDateTime(dateStr: string | null): string {
    if (!dateStr) return '—';

    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function formatPrice(price: number | null | undefined): string {
    if (price === null || price === undefined || price <= 0) return 'Не указана';
    return currencyFormatter.format(price);
  }

  function getMarketplaceLabel(marketplace: string | null | undefined): string {
    const labels: Record<string, string> = {
      wildberries: 'Wildberries',
      ozon: 'Ozon',
      avito: 'Avito',
      yandex_market: 'Яндекс Маркет',
      kazanexpress: 'KazanExpress',
    };

    if (!marketplace) return '—';
    return labels[marketplace] || marketplace;
  }

  function getMarketplaceBadgeClass(marketplace: string | null | undefined): string {
    if (marketplace === 'wildberries') return 'bg-purple-500/20 text-purple-400';
    if (marketplace === 'ozon') return 'bg-blue-500/20 text-blue-400';
    if (marketplace === 'avito') return 'bg-green-500/20 text-green-400';
    if (marketplace === 'yandex_market') return 'bg-yellow-500/20 text-yellow-300';
    return 'bg-gray-500/20 text-gray-400';
  }
</script>

{#if false}{JSON.stringify(params)}{/if}

<svelte:window on:keydown={handleWindowKeydown} />

<div class="mx-auto max-w-[1400px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр · Товары"
    title="Товары"
    subtitle="Управление вашими товарами и конкурентами"
  >
    <svelte:fragment slot="meta">
      {#if !loading && totalProducts > 0}
        <StatusBadge variant="info" label={`${totalProducts} SKU`} dot={false} />
      {/if}
      {#if refreshing}
        <StatusBadge variant="ai" label="Обновление…" dot={true} />
      {/if}
    </svelte:fragment>

    <svelte:fragment slot="actions">
      <Button variant="ghost" size="sm" disabled={refreshing || deleting} on:click={exportToExcel}>
        <Download class="h-4 w-4" aria-hidden="true" />
        Экспорт в Excel
      </Button>
      <Button variant="neural" size="sm" on:click={() => (window.location.href = '/parsing')}>
        <Zap class="h-4 w-4" aria-hidden="true" />
        Спарсить товар
      </Button>
    </svelte:fragment>
  </PageHeader>

  {#if statusMessage}
    <Alert variant="success" title="Готово">{statusMessage}</Alert>
  {/if}
  {#if error && !loading && products.length > 0}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}

  {#if !loading && !error && totalProducts > 0}
    <div class="grid gap-4 sm:grid-cols-3">
      <MetricCard title="Всего товаров" value={totalProducts} subtitle="в мониторинге" icon={Boxes} glow />
      <MetricCard title="Свои (на странице)" value={ownOnPage} subtitle="из текущей выборки" icon={Package} />
      <MetricCard title="Конкуренты (на странице)" value={competitorOnPage} subtitle="из текущей выборки" icon={Search} />
    </div>
  {/if}

  <!-- Фильтры -->
  <GlassCard padding="lg" glow>
    <!-- Массовые операции -->
    {#if selectedIds.length > 0}
      <div class="mb-4 flex flex-col gap-3 rounded-xl border border-neural-cyan/30 bg-neural-cyan/10 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-center gap-3">
          <span class="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
            {selectedIds.length}
          </span>
          <span class="font-medium text-primary">выбрано товаров</span>
        </div>
        <div class="flex gap-2">
          <Button variant="ghost" size="sm" disabled={deleting} on:click={clearSelection}>
            Снять выделение
          </Button>
          <Button variant="danger" size="sm" loading={deleting} on:click={deleteSelected}>
            <Trash2 class="h-4 w-4" aria-hidden="true" />
            Удалить выбранные
          </Button>
        </div>
      </div>
    {/if}

    <div class="mb-4 flex items-center gap-2">
      <Boxes class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
      <h2 class="text-lg font-semibold text-foreground">Фильтры</h2>
    </div>

    <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
      <div class="lg:col-span-1 md:col-span-2">
        <FormField label="Поиск" let:controlId>
          <div class="relative">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <input
              id={controlId}
              type="text"
              bind:value={searchQuery}
              on:input={onSearchInput}
              class="page-input !pl-9"
              placeholder="Название товара..."
            />
          </div>
        </FormField>
      </div>

      <FormField label="Маркетплейс" let:controlId>
        <select id={controlId} bind:value={filterMarketplace} on:change={applyFilters} class="page-select">
          <option value="all">Все</option>
          <option value="wildberries">Wildberries</option>
          <option value="ozon">Ozon</option>
          <option value="avito">Avito</option>
          <option value="yandex_market">Яндекс Маркет</option>
        </select>
      </FormField>

      <FormField label="Тип" let:controlId>
        <select id={controlId} bind:value={filterType} on:change={applyFilters} class="page-select">
          <option value="all">Все</option>
          <option value="own">Свои</option>
          <option value="competitor">Конкуренты</option>
        </select>
      </FormField>

      <FormField label="Сортировка" let:controlId>
        <select id={controlId} bind:value={sortBy} on:change={applyFilters} class="page-select">
          <option value="created_at">По дате</option>
          <option value="name">По названию</option>
          <option value="price">По цене</option>
        </select>
      </FormField>

      <FormField label="Порядок" let:controlId>
        <select id={controlId} bind:value={sortOrder} on:change={applyFilters} class="page-select">
          <option value="desc">Сначала новые</option>
          <option value="asc">Сначала старые</option>
        </select>
      </FormField>
    </div>

    {#if hasActiveFilters}
      <div class="mt-4 flex items-center gap-2">
        <StatusBadge variant="ai" label="Активны фильтры" dot={false} />
        <Button variant="ghost" size="sm" disabled={refreshing} on:click={clearFilters}>
          <X class="h-4 w-4" aria-hidden="true" />
          Сбросить
        </Button>
      </div>
    {/if}
  </GlassCard>
  
  <!-- Таблица -->
  {#if loading}
    <div class="space-y-4">
      <LoadingSkeleton variant="card" />
      {#each Array(6) as _}
        <LoadingSkeleton variant="avatar" className="py-2" />
      {/each}
    </div>
  {:else if error}
    <ErrorState title="Не удалось загрузить товары" description={error}>
      <svelte:fragment slot="action">
        <Button variant="neural" on:click={() => loadProducts({ fullScreen: false })}>
          Попробовать снова
        </Button>
      </svelte:fragment>
    </ErrorState>
  {:else if products.length === 0 && hasActiveFilters}
    <EmptyState
      title="Ничего не найдено"
      description="По текущим фильтрам нет товаров. Попробуйте изменить условия поиска."
      icon={Search}
    >
      <svelte:fragment slot="action">
        <Button variant="ghost" on:click={clearFilters}>
          <X class="h-4 w-4" aria-hidden="true" />
          Сбросить фильтры
        </Button>
      </svelte:fragment>
    </EmptyState>
  {:else if products.length === 0}
    <EmptyState
      title="Нет товаров"
      description="Спарсите товар или добавьте вручную"
      icon={Package}
    >
      <svelte:fragment slot="action">
        <Button variant="neural" on:click={() => (window.location.href = '/parsing')}>
          <Zap class="h-4 w-4" aria-hidden="true" />
          Спарсить товар
        </Button>
      </svelte:fragment>
    </EmptyState>
  {:else}
    <div class="glass-card flex flex-col gap-3 rounded-xl px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <div class="text-muted-foreground">
        Показано <span class="font-semibold text-foreground">{pageStart}</span>–<span class="font-semibold text-foreground">{pageEnd}</span>
        из <span class="font-semibold text-foreground">{totalProducts}</span>
      </div>

      <div class="flex items-center gap-2">
        <label for="products-page-size" class="page-label !mb-0 text-muted-foreground">На странице:</label>
        <select
          id="products-page-size"
          bind:value={pageSize}
          on:change={onPageSizeChange}
          class="page-select !w-auto py-1"
        >
          <option value={20}>20</option>
          <option value={30}>30</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
      </div>
    </div>

    <!-- Desktop: таблица -->
    <GlassCard padding="none" className="hidden overflow-hidden md:block">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-primary/10">
            <tr>
              <th class="px-6 py-4 text-left font-semibold text-foreground">
                <input
                  type="checkbox"
                  checked={selectAll}
                  on:click={toggleSelectAll}
                  class="h-4 w-4 rounded border-input bg-background text-primary focus:ring-primary"
                  aria-label="Выбрать все товары на странице"
                />
              </th>
              <th class="px-6 py-4 text-left font-semibold text-foreground">Товар</th>
              <th class="px-6 py-4 text-left font-semibold text-foreground">Цена</th>
              <th class="px-6 py-4 text-left font-semibold text-foreground">Маркетплейс</th>
              <th class="px-6 py-4 text-left font-semibold text-foreground">Тип</th>
              <th class="px-6 py-4 text-left font-semibold text-foreground">Дата</th>
              <th class="px-6 py-4 text-right font-semibold text-foreground">Действия</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each products as product}
              <tr class="transition-colors hover:bg-primary/5 {selectedIds.includes(product.id) ? 'bg-primary/10' : ''}">
                <td class="px-6 py-4">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(product.id)}
                    on:change={() => toggleSelect(product.id)}
                    class="h-4 w-4 rounded border-input bg-background text-primary focus:ring-primary"
                    aria-label={`Выбрать товар ${product.name}`}
                  />
                </td>
                <td class="px-6 py-4">
                  <div class="flex items-center gap-3">
                    {#if product.image_url}
                      <img
                        src={product.image_url}
                        alt={product.name}
                        class="h-12 w-12 shrink-0 rounded-lg object-cover"
                        on:error={(event) => {
                          const target = event.currentTarget;
                          if (target instanceof HTMLImageElement) {
                            target.style.display = 'none';
                          }
                        }}
                      />
                    {/if}
                    <div class="min-w-0">
                      <p class="font-medium text-foreground break-words">{product.name}</p>
                      {#if product.brand}
                        <p class="text-xs text-muted-foreground break-words">{product.brand}</p>
                      {/if}
                    </div>
                  </div>
                </td>
                <td class="px-6 py-4">
                  <span class="font-semibold text-success">
                    {formatPrice(product.price)}
                  </span>
                  {#if product.old_price}
                    <p class="text-xs text-muted-foreground line-through">
                      {formatPrice(product.old_price)}
                    </p>
                  {/if}
                </td>
                <td class="px-6 py-4">
                  <StatusBadge
                    variant="neutral"
                    label={getMarketplaceLabel(product.marketplace)}
                    dot={false}
                    className={getMarketplaceBadgeClass(product.marketplace)}
                  />
                </td>
                <td class="px-6 py-4">
                  <StatusBadge
                    variant={product.is_own ? 'info' : 'warning'}
                    label={product.is_own ? 'Свои' : 'Конкуренты'}
                    dot={false}
                  />
                </td>
                <td class="px-6 py-4 text-muted-foreground">
                  {formatDate(product.created_at)}
                </td>
                <td class="px-6 py-4 text-right">
                  <div class="flex justify-end gap-2">
                    <button
                      on:click={() => viewPriceHistory(product)}
                      class="rounded-lg p-2 text-primary hover:bg-primary/10 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                      title="История цен"
                      aria-label={`История цен: ${product.name}`}
                      disabled={deleting}
                    >
                      <History class="h-5 w-5" aria-hidden="true" />
                    </button>
                    <button
                      on:click={() => deleteProduct(product.id)}
                      class="rounded-lg p-2 text-destructive hover:bg-destructive/10 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                      title="Удалить"
                      aria-label={`Удалить товар ${product.name}`}
                      disabled={deleting}
                    >
                      <Trash2 class="h-5 w-5" aria-hidden="true" />
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </GlassCard>

    <!-- Mobile: карточки товаров (без горизонтального overflow) -->
    <div class="space-y-3 md:hidden">
      {#each products as product}
        <GlassCard padding="md" className={selectedIds.includes(product.id) ? 'ring-1 ring-neural-cyan/40' : ''}>
          <div class="flex items-start gap-3">
            <input
              type="checkbox"
              checked={selectedIds.includes(product.id)}
              on:change={() => toggleSelect(product.id)}
              class="mt-1 h-4 w-4 shrink-0 rounded border-input bg-background text-primary focus:ring-primary"
              aria-label={`Выбрать товар ${product.name}`}
            />
            {#if product.image_url}
              <img
                src={product.image_url}
                alt={product.name}
                class="h-14 w-14 shrink-0 rounded-lg object-cover"
                on:error={(event) => {
                  const target = event.currentTarget;
                  if (target instanceof HTMLImageElement) {
                    target.style.display = 'none';
                  }
                }}
              />
            {/if}
            <div class="min-w-0 flex-1">
              <p class="font-medium text-foreground break-words">{product.name}</p>
              {#if product.brand}
                <p class="text-xs text-muted-foreground break-words">{product.brand}</p>
              {/if}
              <div class="mt-2 flex flex-wrap items-center gap-2">
                <StatusBadge
                  variant="neutral"
                  label={getMarketplaceLabel(product.marketplace)}
                  dot={false}
                  className={getMarketplaceBadgeClass(product.marketplace)}
                />
                <StatusBadge
                  variant={product.is_own ? 'info' : 'warning'}
                  label={product.is_own ? 'Свои' : 'Конкуренты'}
                  dot={false}
                />
              </div>
              <div class="mt-3 flex items-end justify-between gap-3">
                <div>
                  <p class="font-semibold text-success">{formatPrice(product.price)}</p>
                  {#if product.old_price}
                    <p class="text-xs text-muted-foreground line-through">{formatPrice(product.old_price)}</p>
                  {/if}
                  <p class="mt-1 text-xs text-muted-foreground">{formatDate(product.created_at)}</p>
                </div>
                <div class="flex shrink-0 gap-2">
                  <button
                    on:click={() => viewPriceHistory(product)}
                    class="rounded-lg p-2 text-primary hover:bg-primary/10 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                    title="История цен"
                    aria-label={`История цен: ${product.name}`}
                    disabled={deleting}
                  >
                    <History class="h-5 w-5" aria-hidden="true" />
                  </button>
                  <button
                    on:click={() => deleteProduct(product.id)}
                    class="rounded-lg p-2 text-destructive hover:bg-destructive/10 transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                    title="Удалить"
                    aria-label={`Удалить товар ${product.name}`}
                    disabled={deleting}
                  >
                    <Trash2 class="h-5 w-5" aria-hidden="true" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>
      {/each}
    </div>

    {#if totalPages > 1}
      <div class="glass-card flex items-center justify-center gap-2 rounded-xl p-3">
        <Button
          variant="ghost"
          size="sm"
          disabled={currentPage <= 1 || refreshing}
          on:click={() => goToPage(currentPage - 1)}
        >
          <ChevronLeft class="h-4 w-4" aria-hidden="true" />
          Назад
        </Button>

        <span class="px-3 text-sm text-muted-foreground">
          Страница <span class="font-semibold text-foreground">{currentPage}</span> из <span class="font-semibold text-foreground">{totalPages}</span>
        </span>

        <Button
          variant="ghost"
          size="sm"
          disabled={currentPage >= totalPages || refreshing}
          on:click={() => goToPage(currentPage + 1)}
        >
          Вперёд
          <ChevronRight class="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    {/if}
  {/if}
</div>
      
<!-- Модальное окно истории цен -->
{#if showHistoryModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <button
      type="button"
      class="absolute inset-0 bg-black/50 backdrop-blur-sm"
      on:click={closeHistoryModal}
      aria-label="Закрыть окно истории цен"
    ></button>

    <div
      class="glass-card glass-card-glow relative w-full max-w-2xl rounded-2xl p-8"
      role="dialog"
      aria-modal="true"
      aria-label="История цен товара"
    >
      <div class="mb-6 flex items-center justify-between">
        <h2 class="text-2xl font-bold text-foreground flex items-center gap-2">
          <History class="h-7 w-7 text-neural-cyan" aria-hidden="true" />
          История цен
        </h2>
        <button on:click={closeHistoryModal} class="btn-ghost-neural !p-2" aria-label="Закрыть">
          <X class="h-6 w-6" aria-hidden="true" />
        </button>
      </div>
      
      {#if selectedProduct}
        <div class="mb-6 rounded-lg bg-background/30 p-4">
          <p class="font-semibold text-foreground">{selectedProduct.name}</p>
          <p class="text-sm text-muted-foreground">
            {getMarketplaceLabel(selectedProduct.marketplace)} • {selectedProduct.brand || '—'}
          </p>
        </div>
      {/if}
      
      {#if priceHistoryLoading}
        <div class="space-y-3 py-6">
          <LoadingSkeleton variant="card" />
          <LoadingSkeleton lines={4} />
        </div>
      {:else if priceHistory.length > 0}
        <div class="max-h-96 overflow-y-auto">
          <table class="w-full text-sm">
            <thead class="sticky top-0 bg-primary/10">
              <tr>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Дата</th>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Цена</th>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Старая цена</th>
                <th class="px-4 py-3 text-left font-semibold text-foreground">Скидка</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              {#each priceHistory as record}
                <tr class="transition-colors hover:bg-primary/5">
                  <td class="px-4 py-3 text-muted-foreground">
                    {formatDateTime(record.created_at)}
                  </td>
                  <td class="px-4 py-3 font-semibold text-success">
                    {formatPrice(record.price)}
                  </td>
                  <td class="px-4 py-3 text-muted-foreground line-through">
                    {formatPrice(record.old_price)}
                  </td>
                  <td class="px-4 py-3">
                    {#if record.discount}
                      <span class="rounded bg-warning/20 px-2 py-1 text-xs font-medium text-warning">
                        -{record.discount}%
                      </span>
                    {:else}
                      —
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <EmptyState
          title="Нет данных об изменении цен"
          description="История формируется при каждом парсинге"
        />
      {/if}
    </div>
  </div>
{/if}

<AppPageStyles />
