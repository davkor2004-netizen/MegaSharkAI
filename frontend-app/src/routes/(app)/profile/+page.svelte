<script lang="ts">
  import { onMount } from 'svelte';
  import { apiJson, apiNoContent } from '$lib/utils/http';
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
    KeyRound,
    Lock,
    Plus,
    RefreshCw,
    Save,
    Shield,
    ShieldCheck,
    Trash2,
    User,
    Zap
  } from 'lucide-svelte';

  interface ProfileData {
    email: string;
    full_name: string | null;
    phone: string | null;
    is_marketplace_seller: boolean;
    is_superuser: boolean;
  }

  interface MarketplaceKey {
    id: string;
    marketplace: string;
    api_key_masked: string;
    additional_credentials_masked?: Record<string, string>;
    is_active: boolean;
    is_valid: boolean | null;
    last_checked: string | null;
    created_at: string;
    updated_at: string;
  }

  interface MarketplaceKeysResponse {
    keys: MarketplaceKey[];
    total: number;
  }

  interface CheckKeyResponse {
    is_valid: boolean;
    message: string;
  }

  interface StatusResponse {
    status: string;
    message?: string;
  }

  let loading = true;
  let loadError = '';
  let saving = false;
  let keysLoading = false;
  let successMessage = '';
  let error = '';

  let email = '';
  let full_name = '';
  let phone = '';
  let is_marketplace_seller = false;
  let isSuperuser = false;

  let marketplaceKeys: MarketplaceKey[] = [];
  let showAddKeyForm = false;
  let selectedMarketplace = '';
  let newApiKey = '';
  let newOzonClientId = '';

  let current_password = '';
  let new_password = '';
  let confirm_password = '';
  let showPasswordForm = false;

  let two_factor_enabled = false;

  const ADMIN_SECURITY_EMAILS = ['admin@megashark.ai'];
  const DIRECTOR_MARKERS = ['директор', 'director'];

  const marketplaceOptions = [
    { id: 'wildberries', name: 'Wildberries', icon: '🔵', color: 'from-blue-500 to-purple-600' },
    { id: 'ozon', name: 'Ozon', icon: '🔷', color: 'from-blue-400 to-blue-600' },
    { id: 'yandex_market', name: 'Яндекс Маркет', icon: '🟡', color: 'from-yellow-400 to-red-500' },
    { id: 'avito', name: 'Avito', icon: '🟢', color: 'from-green-400 to-blue-500' }
  ];

  $: isDirectorAccount = DIRECTOR_MARKERS.some((marker) => {
    const normalizedEmail = email.trim().toLowerCase();
    const normalizedName = full_name.trim().toLowerCase();
    return normalizedEmail.includes(marker) || normalizedName.includes(marker);
  });

  $: hasAdminSecurityAccess =
    isSuperuser &&
    !isDirectorAccount &&
    ADMIN_SECURITY_EMAILS.includes(email.trim().toLowerCase());

  function resetActionMessages(): void {
    successMessage = '';
    error = '';
  }

  function getMarketplaceInfo(id: string) {
    return (
      marketplaceOptions.find((mp) => mp.id === id) || {
        name: id,
        icon: '🔌',
        color: 'from-gray-500 to-gray-600'
      }
    );
  }

  function getKeyValidityVariant(isValid: boolean | null): 'success' | 'error' | 'warning' {
    if (isValid === true) return 'success';
    if (isValid === false) return 'error';
    return 'warning';
  }

  function getKeyValidityLabel(isValid: boolean | null): string {
    if (isValid === true) return 'Валиден';
    if (isValid === false) return 'Недействителен';
    return 'Не проверен';
  }

  async function loadProfile(): Promise<void> {
    loading = true;
    loadError = '';

    try {
      const data = await apiJson<ProfileData>('/api/v1/auth/me', {}, 'Не удалось загрузить профиль');
      email = data.email || '';
      full_name = data.full_name || '';
      phone = data.phone || '';
      is_marketplace_seller = data.is_marketplace_seller || false;
      isSuperuser = data.is_superuser || false;
    } catch (err: unknown) {
      loadError = err instanceof Error ? err.message : 'Ошибка соединения с сервером';
    } finally {
      loading = false;
    }
  }

  async function loadMarketplaceKeys(): Promise<void> {
    keysLoading = true;

    try {
      const data = await apiJson<MarketplaceKeysResponse>(
        '/api/v1/marketplace-keys',
        {},
        'Не удалось загрузить ключи'
      );
      marketplaceKeys = data.keys || [];
    } catch (err) {
      console.error('Ошибка загрузки ключей:', err);
    } finally {
      keysLoading = false;
    }
  }

  async function loadPageData(): Promise<void> {
    await loadProfile();
    if (!loadError) {
      await loadMarketplaceKeys();
    }
  }

  async function handleAddKey(): Promise<void> {
    if (!selectedMarketplace || !newApiKey) {
      error = 'Выберите маркетплейс и введите ключ';
      return;
    }

    if (selectedMarketplace === 'ozon' && !newOzonClientId.trim()) {
      error = 'Для Ozon укажите Client-Id';
      return;
    }

    saving = true;
    resetActionMessages();

    try {
      await apiJson<MarketplaceKey>(
        '/api/v1/marketplace-keys',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            marketplace: selectedMarketplace,
            api_key: newApiKey,
            client_id: selectedMarketplace === 'ozon' ? newOzonClientId : undefined,
            is_active: true
          })
        },
        'Ошибка добавления ключа'
      );

      successMessage = 'Ключ успешно добавлен';
      showAddKeyForm = false;
      selectedMarketplace = '';
      newApiKey = '';
      newOzonClientId = '';
      await loadMarketplaceKeys();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка соединения с сервером';
    } finally {
      saving = false;
    }
  }

  async function handleDeleteKey(keyId: string): Promise<void> {
    if (!confirm('Вы уверены, что хотите удалить этот ключ?')) return;

    resetActionMessages();

    try {
      await apiNoContent(
        `/api/v1/marketplace-keys/${keyId}`,
        { method: 'DELETE' },
        'Ошибка удаления ключа'
      );
      successMessage = 'Ключ успешно удалён';
      await loadMarketplaceKeys();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка соединения с сервером';
    }
  }

  async function handleCheckKey(keyId: string): Promise<void> {
    resetActionMessages();

    try {
      const result = await apiJson<CheckKeyResponse>(
        `/api/v1/marketplace-keys/${keyId}/check`,
        { method: 'POST' },
        'Ошибка проверки ключа'
      );
      successMessage = result.message || 'Ключ проверен';
      await loadMarketplaceKeys();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка соединения с сервером';
    }
  }

  async function handleSaveProfile(e: Event): Promise<void> {
    e.preventDefault();
    saving = true;
    resetActionMessages();

    try {
      await apiJson<ProfileData>(
        '/api/v1/auth/profile',
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            full_name,
            phone,
            is_marketplace_seller
          })
        },
        'Ошибка обновления профиля'
      );

      successMessage = 'Профиль успешно обновлён';
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка соединения с сервером';
    } finally {
      saving = false;
    }
  }

  async function handleChangePassword(e: Event): Promise<void> {
    e.preventDefault();
    resetActionMessages();

    if (new_password !== confirm_password) {
      error = 'Пароли не совпадают';
      return;
    }

    if (new_password.length < 6) {
      error = 'Пароль должен быть не менее 6 символов';
      return;
    }

    saving = true;

    try {
      await apiJson<StatusResponse>(
        '/api/v1/auth/change-password',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            current_password,
            new_password
          })
        },
        'Ошибка смены пароля'
      );

      successMessage = 'Пароль успешно изменён';
      current_password = '';
      new_password = '';
      confirm_password = '';
      showPasswordForm = false;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Ошибка соединения с сервером';
    } finally {
      saving = false;
    }
  }

  function toggle2FA(): void {
    // TODO: Реализовать 2FA
    alert('Функция двухфакторной аутентификации в разработке');
  }

  onMount(loadPageData);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Secure Profile Center"
    title="Профиль"
    subtitle={hasAdminSecurityAccess
      ? 'Управление данными аккаунта, ключами маркетплейсов и безопасностью'
      : 'Управление данными аккаунта и ключами маркетплейсов'}
  >
    <svelte:fragment slot="meta">
      {#if is_marketplace_seller}
        <StatusBadge variant="success" label="Продавец МП" dot={false} />
      {/if}
      {#if isSuperuser}
        <StatusBadge variant="ai" label="Admin" dot={false} />
      {/if}
      {#if two_factor_enabled}
        <StatusBadge variant="info" label="2FA включена" dot />
      {:else if hasAdminSecurityAccess}
        <StatusBadge variant="neutral" label="2FA выключена" dot={false} />
      {/if}
    </svelte:fragment>
  </PageHeader>

  {#if successMessage}
    <Alert variant="success" title="Готово">{successMessage}</Alert>
  {/if}
  {#if error}
    <Alert variant="error" title="Ошибка">{error}</Alert>
  {/if}

  {#if loading}
    <div class="grid gap-6 xl:grid-cols-2">
      <LoadingSkeleton variant="card" />
      <LoadingSkeleton variant="card" />
    </div>
  {:else if loadError}
    <ErrorState title="Не удалось загрузить профиль" description={loadError} on:click={loadPageData} />
  {:else}
    <div class="grid gap-6 xl:grid-cols-2">
      <div class="space-y-6">
        <GlassCard glow padding="lg" className="space-y-6">
          <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
            <User class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
            Основная информация
          </h2>

          <form on:submit={handleSaveProfile} class="space-y-5">
            <div class="grid gap-4 md:grid-cols-2">
              <FormField label="Email" let:controlId>
                <input
                  id={controlId}
                  type="email"
                  bind:value={email}
                  class="page-input"
                  placeholder="seller@example.com"
                />
              </FormField>
              <FormField label="Полное имя" let:controlId>
                <input
                  id={controlId}
                  type="text"
                  bind:value={full_name}
                  class="page-input"
                  placeholder="Иван Петров"
                />
              </FormField>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <FormField label="Телефон" let:controlId>
                <input
                  id={controlId}
                  type="tel"
                  bind:value={phone}
                  class="page-input"
                  placeholder="+7 (999) 123-45-67"
                />
              </FormField>
              <div class="space-y-2">
                <p class="page-label">Продавец маркетплейса</p>
                <label class="surface flex cursor-pointer items-center gap-3 rounded-xl p-3">
                  <input
                    type="checkbox"
                    bind:checked={is_marketplace_seller}
                    class="h-5 w-5 rounded border-input bg-background text-primary focus:ring-primary"
                  />
                  <span class="text-sm text-foreground">Я продавец на маркетплейсе</span>
                </label>
                <p class="text-xs text-muted-foreground">
                  После сохранения вы сможете добавить API-ключи в разделе справа
                </p>
              </div>
            </div>

            {#if is_marketplace_seller}
              <Alert variant="info" title="Marketplace keys">
                Прокрутите к разделу «Подключённые маркетплейсы» для управления API-ключами.
              </Alert>
            {/if}

            <Button type="submit" variant="neural" loading={saving} disabled={saving}>
              <Save class="h-4 w-4" aria-hidden="true" />
              {saving ? 'Сохранение...' : 'Сохранить изменения'}
            </Button>
          </form>
        </GlassCard>

        {#if hasAdminSecurityAccess}
          <GlassCard glow padding="lg" className="space-y-6">
            <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
              <Shield class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
              Безопасность
            </h2>

            <div class="space-y-4">
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 class="font-medium text-foreground">Пароль</h3>
                  <p class="text-sm text-muted-foreground">Измените пароль для доступа к аккаунту</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  on:click={() => {
                    showPasswordForm = !showPasswordForm;
                    resetActionMessages();
                  }}
                >
                  {showPasswordForm ? 'Отмена' : 'Изменить'}
                </Button>
              </div>

              {#if showPasswordForm}
                <form on:submit={handleChangePassword} class="surface space-y-4 rounded-xl p-4">
                  <FormField label="Текущий пароль" let:controlId>
                    <input
                      id={controlId}
                      type="password"
                      bind:value={current_password}
                      class="page-input"
                      placeholder="••••••••"
                      autocomplete="current-password"
                    />
                  </FormField>
                  <div class="grid gap-4 md:grid-cols-2">
                    <FormField label="Новый пароль" hint="Минимум 6 символов" let:controlId>
                      <input
                        id={controlId}
                        type="password"
                        bind:value={new_password}
                        class="page-input"
                        placeholder="••••••••"
                        autocomplete="new-password"
                      />
                    </FormField>
                    <FormField label="Подтверждение пароля" let:controlId>
                      <input
                        id={controlId}
                        type="password"
                        bind:value={confirm_password}
                        class="page-input"
                        placeholder="••••••••"
                        autocomplete="new-password"
                      />
                    </FormField>
                  </div>
                  <Button type="submit" variant="neural" loading={saving} disabled={saving}>
                    <Lock class="h-4 w-4" aria-hidden="true" />
                    {saving ? 'Сохранение...' : 'Изменить пароль'}
                  </Button>
                </form>
              {/if}
            </div>

            <div class="flex flex-col gap-4 border-t border-border/60 pt-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 class="font-medium text-foreground">Двухфакторная аутентификация</h3>
                <p class="text-sm text-muted-foreground">
                  {two_factor_enabled ? 'Включена' : 'Отключена'}
                </p>
              </div>
              <Button variant="subtle" size="sm" on:click={toggle2FA}>
                {two_factor_enabled ? 'Отключить' : 'Включить'}
              </Button>
            </div>
          </GlassCard>
        {/if}
      </div>

      <div class="space-y-6">
        {#if is_marketplace_seller}
          <GlassCard glow padding="lg" className="space-y-6">
            <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
                <Zap class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
                Подключённые маркетплейсы
              </h2>
              <Button
                variant={showAddKeyForm ? 'subtle' : 'ghost'}
                size="sm"
                on:click={() => {
                  showAddKeyForm = !showAddKeyForm;
                  resetActionMessages();
                }}
              >
                <Plus class="h-4 w-4" aria-hidden="true" />
                {showAddKeyForm ? 'Отмена' : 'Добавить ключ'}
              </Button>
            </div>

            <Alert variant="warning" title="Безопасность ключей">
              Ключи отображаются только в маскированном виде. Не передавайте API-ключи третьим лицам.
              MegaSharkAI использует ключи только для интеграций маркетплейсов.
            </Alert>

            {#if showAddKeyForm}
              <div class="surface space-y-4 rounded-xl p-4">
                <h3 class="font-medium text-foreground">Новый API ключ</h3>

                <FormField label="Маркетплейс" let:controlId>
                  <select id={controlId} bind:value={selectedMarketplace} class="page-select">
                    <option value="">Выберите маркетплейс</option>
                    {#each marketplaceOptions as mp}
                      <option value={mp.id}>{mp.icon} {mp.name}</option>
                    {/each}
                  </select>
                </FormField>

                <FormField
                  label="API ключ"
                  hint="Ключ будет зашифрован перед сохранением"
                  let:controlId
                >
                  <input
                    id={controlId}
                    type="password"
                    bind:value={newApiKey}
                    class="page-input"
                    placeholder="Введите ваш API ключ"
                    autocomplete="off"
                  />
                </FormField>

                {#if selectedMarketplace === 'ozon'}
                  <FormField
                    label="Ozon Client-Id"
                    hint="Client-Id будет сохранён зашифрованным и нужен для Ozon Seller API"
                    let:controlId
                  >
                    <input
                      id={controlId}
                      type="password"
                      bind:value={newOzonClientId}
                      class="page-input"
                      placeholder="Client-Id из кабинета Ozon Seller"
                      autocomplete="off"
                    />
                  </FormField>
                {/if}

                <Button
                  variant="neural"
                  loading={saving}
                  disabled={saving || !selectedMarketplace || !newApiKey || (selectedMarketplace === 'ozon' && !newOzonClientId)}
                  on:click={handleAddKey}
                >
                  <KeyRound class="h-4 w-4" aria-hidden="true" />
                  {saving ? 'Сохранение...' : 'Добавить ключ'}
                </Button>
              </div>
            {/if}

            {#if keysLoading}
              <LoadingSkeleton variant="card" />
            {:else if marketplaceKeys.length === 0}
              <EmptyState
                title="Нет подключённых маркетплейсов"
                description="Добавьте API-ключ для начала работы с вашими товарами."
                icon={KeyRound}
              >
                <Button slot="action" variant="neural" size="sm" on:click={() => (showAddKeyForm = true)}>
                  <Plus class="h-4 w-4" aria-hidden="true" />
                  Добавить ключ
                </Button>
              </EmptyState>
            {:else}
              <div class="space-y-3">
                {#each marketplaceKeys as key (key.id)}
                  {@const mpInfo = getMarketplaceInfo(key.marketplace)}
                  <GlassCard padding="md" className="space-y-3">
                    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div class="flex items-start gap-3 min-w-0">
                        <div
                          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br {mpInfo.color} text-xl"
                          aria-hidden="true"
                        >
                          {mpInfo.icon}
                        </div>
                        <div class="min-w-0 space-y-2">
                          <div class="flex flex-wrap items-center gap-2">
                            <p class="font-semibold text-foreground">{mpInfo.name}</p>
                            <StatusBadge
                              variant={getKeyValidityVariant(key.is_valid)}
                              label={getKeyValidityLabel(key.is_valid)}
                              dot
                            />
                            {#if key.is_active}
                              <StatusBadge variant="info" label="Активен" dot={false} />
                            {/if}
                          </div>
                          <p class="font-mono text-sm text-muted-foreground break-all">
                            {key.api_key_masked}
                          </p>
                          {#if key.additional_credentials_masked?.client_id}
                            <p class="font-mono text-xs text-muted-foreground break-all">
                              Client-Id: {key.additional_credentials_masked.client_id}
                            </p>
                          {/if}
                          {#if key.last_checked}
                            <p class="text-xs text-muted-foreground">
                              Проверен: {new Date(key.last_checked).toLocaleString('ru-RU')}
                            </p>
                          {/if}
                        </div>
                      </div>

                      <div class="flex shrink-0 items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          title="Проверить ключ"
                          on:click={() => handleCheckKey(key.id)}
                        >
                          <RefreshCw class="h-4 w-4" aria-hidden="true" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:bg-destructive/10"
                          title="Удалить ключ"
                          on:click={() => handleDeleteKey(key.id)}
                        >
                          <Trash2 class="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </div>
                  </GlassCard>
                {/each}
              </div>
            {/if}
          </GlassCard>
        {:else}
          <GlassCard padding="lg" className="space-y-4">
            <div class="flex items-center gap-3">
              <div class="flex h-10 w-10 items-center justify-center rounded-xl border border-neural-cyan/20 bg-neural-cyan/10 text-neural-cyan">
                <ShieldCheck class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h2 class="text-lg font-semibold text-foreground">Trust & Security</h2>
                <p class="text-sm text-muted-foreground">Защита данных аккаунта</p>
              </div>
            </div>
            <Alert variant="info">
              Включите статус «Продавец маркетплейса» в профиле, чтобы подключить API-ключи Wildberries, Ozon и других площадок.
            </Alert>
          </GlassCard>
        {/if}

        <GlassCard padding="lg" className="space-y-3">
          <h3 class="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Lock class="h-4 w-4 text-neural-purple" aria-hidden="true" />
            Политика безопасности ключей
          </h3>
          <ul class="space-y-2 text-sm text-muted-foreground">
            <li class="surface rounded-lg px-3 py-2">Ключи отображаются только в маскированном виде</li>
            <li class="surface rounded-lg px-3 py-2">Не передавайте API-ключи третьим лицам</li>
            <li class="surface rounded-lg px-3 py-2">
              MegaSharkAI использует ключи только для интеграций маркетплейсов
            </li>
          </ul>
        </GlassCard>
      </div>
    </div>
  {/if}
</div>

<AppPageStyles />
