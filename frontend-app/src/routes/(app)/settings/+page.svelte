<script lang="ts">
  import { onMount } from 'svelte';
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
    Bell,
    FlaskConical,
    Globe,
    Info,
    KeyRound,
    Lock,
    Save,
    Server,
    ShieldCheck
  } from 'lucide-svelte';

  interface AuthMeResponse {
    is_superuser?: boolean;
    full_name?: string;
    email?: string;
  }

  interface ProviderResponse {
    provider: string;
    status?: string;
  }

  interface AiSettingsResponse {
    provider: string;
    yandex_configured: string;
    yandex_api_key_masked?: string;
    deepseek_configured: string;
    deepseek_api_key_masked?: string;
    openai_configured: string;
    openai_api_key_masked?: string;
    error?: string;
  }

  interface SaveAiSettingsResponse {
    status: string;
    provider: string;
    message?: string;
  }

  interface NotificationSettingsResponse {
    email_notifications: boolean;
    telegram_notifications: boolean;
    telegram_chat_id: string | null;
  }

  interface SeoTitleTestResponse {
    seo_name?: string;
    message?: string;
    original_name?: string;
    provider?: string;
  }

  let pageLoading = true;
  let pageLoadError = '';

  let yandexApiKey = '';
  let yandexFolderId = '';
  let deepseekApiKey = '';
  let openaiApiKey = '';
  let currentProvider = 'none';
  let providerStatus = 'not_configured';

  let yandexConfigured = false;
  let yandexKeyMasked = '';
  let deepseekConfigured = false;
  let deepseekKeyMasked = '';
  let openaiConfigured = false;
  let openaiKeyMasked = '';

  let aiLoading = false;
  let aiError = '';
  let aiSuccessMessage = '';

  let isSuperuser = false;
  let userName = '';
  let userEmail = '';

  const ADMIN_AUDIT_EMAILS = ['admin@megashark.ai'];
  const DIRECTOR_MARKERS = ['директор', 'director'];

  let emailNotifications = true;
  let telegramNotifications = false;
  let telegramChatId = '';
  let notificationLoading = false;
  let notificationSuccessMessage = '';
  let notificationError = '';

  $: isDirectorAccount = DIRECTOR_MARKERS.some((marker) => {
    const normalizedEmail = userEmail.trim().toLowerCase();
    const normalizedName = userName.trim().toLowerCase();
    return normalizedEmail.includes(marker) || normalizedName.includes(marker);
  });

  $: hasAdminAuditAccess =
    isSuperuser &&
    !isDirectorAccount &&
    ADMIN_AUDIT_EMAILS.includes(userEmail.trim().toLowerCase());

  function isConfiguredFlag(value: string | undefined): boolean {
    return value === 'true';
  }

  function getProviderLabel(provider: string): string {
    if (provider === 'yandex') return 'YandexGPT';
    if (provider === 'deepseek') return 'DeepSeek';
    if (provider === 'openai') return 'OpenAI';
    return 'Не настроен';
  }

  function getProviderBadgeVariant(provider: string): 'success' | 'warning' | 'info' | 'error' | 'ai' {
    if (provider === 'yandex') return 'warning';
    if (provider === 'deepseek') return 'info';
    if (provider === 'openai') return 'success';
    if (provider === 'none') return 'error';
    return 'ai';
  }

  function resetAiMessages(): void {
    aiError = '';
    aiSuccessMessage = '';
  }

  async function loadAuthContext(): Promise<void> {
    const userData = await apiJson<AuthMeResponse>('/api/v1/auth/me', {}, 'Не удалось загрузить профиль');
    isSuperuser = userData.is_superuser || false;
    userName = userData.full_name || '';
    userEmail = userData.email || '';
  }

  async function loadNotificationSettings(): Promise<void> {
    const data = await apiJson<NotificationSettingsResponse>(
      '/api/v1/notifications/settings',
      {},
      'Не удалось загрузить настройки уведомлений'
    );
    emailNotifications = data.email_notifications;
    telegramNotifications = data.telegram_notifications;
    telegramChatId = data.telegram_chat_id ?? '';
  }

  async function loadAiSettings(): Promise<void> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    try {
      const [providerData, settingsData] = await Promise.all([
        apiJson<ProviderResponse>(
          '/api/v1/ai/provider',
          { signal: controller.signal },
          'Не удалось загрузить AI-провайдер'
        ),
        apiJson<AiSettingsResponse>(
          '/api/v1/ai/settings',
          { signal: controller.signal },
          'Не удалось загрузить AI-настройки'
        )
      ]);

      currentProvider = providerData.provider || settingsData.provider || 'none';
      providerStatus = providerData.status || (currentProvider !== 'none' ? 'configured' : 'not_configured');

      yandexConfigured = isConfiguredFlag(settingsData.yandex_configured);
      yandexKeyMasked = settingsData.yandex_api_key_masked || '';
      deepseekConfigured = isConfiguredFlag(settingsData.deepseek_configured);
      deepseekKeyMasked = settingsData.deepseek_api_key_masked || '';
      openaiConfigured = isConfiguredFlag(settingsData.openai_configured);
      openaiKeyMasked = settingsData.openai_api_key_masked || '';
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async function loadPageData(): Promise<void> {
    pageLoading = true;
    pageLoadError = '';

    try {
      await loadAuthContext();
      await loadNotificationSettings();
      if (isSuperuser) {
        await loadAiSettings();
      }
    } catch (err: unknown) {
      pageLoadError = err instanceof Error ? err.message : 'Ошибка загрузки настроек';
    } finally {
      pageLoading = false;
    }
  }

  async function handleSaveNotifications(): Promise<void> {
    notificationLoading = true;
    notificationSuccessMessage = '';
    notificationError = '';

    try {
      await apiJson<NotificationSettingsResponse>(
        '/api/v1/notifications/settings',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email_notifications: emailNotifications,
            telegram_notifications: telegramNotifications,
            telegram_chat_id: telegramNotifications ? telegramChatId : null
          })
        },
        'Не удалось сохранить настройки уведомлений'
      );
      notificationSuccessMessage = 'Настройки уведомлений сохранены';
    } catch (err: unknown) {
      notificationError = err instanceof Error ? err.message : 'Ошибка сохранения настроек уведомлений';
    } finally {
      notificationLoading = false;
    }
  }

  async function handleSave(e: Event): Promise<void> {
    e.preventDefault();
    aiLoading = true;
    resetAiMessages();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const data = await apiJson<SaveAiSettingsResponse>(
        '/api/v1/ai/settings',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            yandex_api_key: yandexApiKey,
            yandex_folder_id: yandexFolderId,
            deepseek_api_key: deepseekApiKey,
            openai_api_key: openaiApiKey
          })
        },
        'Ошибка сохранения AI-ключей'
      );

      clearTimeout(timeoutId);

      aiSuccessMessage = data.message || 'AI-настройки сохранены';
      currentProvider = data.provider;
      providerStatus = data.provider !== 'none' ? 'configured' : 'not_configured';

      yandexApiKey = '';
      deepseekApiKey = '';
      openaiApiKey = '';

      await loadAiSettings();
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        aiError = 'Превышено время ожидания (10 сек). Попробуйте ещё раз.';
      } else {
        aiError = err instanceof Error ? err.message : 'Ошибка сохранения AI-ключей';
      }
    } finally {
      aiLoading = false;
    }
  }

  async function handleTest(): Promise<void> {
    aiLoading = true;
    resetAiMessages();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      const data = await apiJson<SeoTitleTestResponse>(
        '/api/v1/ai/test',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            product_name: 'Футболка мужская',
            category: 'Одежда'
          })
        },
        'Ошибка теста AI-провайдера'
      );

      clearTimeout(timeoutId);
      alert(`Тест успешен!\n\nРезультат: ${data.seo_name || data.message || 'OK'}`);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        alert('Ошибка теста: превышено время ожидания (15 сек)');
      } else {
        alert('Ошибка теста: ' + (err instanceof Error ? err.message : String(err)));
      }
    } finally {
      aiLoading = false;
    }
  }

  onMount(loadPageData);
</script>

<div class="mx-auto max-w-[1200px] space-y-6 animate-fade-in">
  <PageHeader
    eyebrow="Командный центр · Настройки"
    title="Настройки приложения"
    subtitle={isSuperuser
      ? 'AI-провайдер (глобально), уведомления и инфраструктура'
      : 'Настройка уведомлений и профиля'}
  >
    <svelte:fragment slot="meta">
      {#if isSuperuser}
        <StatusBadge variant="ai" label="Admin / Global" dot={false} />
      {/if}
      {#if isSuperuser}
        <StatusBadge
          variant={providerStatus === 'configured' ? getProviderBadgeVariant(currentProvider) : 'error'}
          label="AI: {getProviderLabel(currentProvider)}"
          dot={providerStatus === 'configured'}
        />
      {/if}
    </svelte:fragment>
  </PageHeader>

  <Alert variant="info">
    Данные профиля (почта, телефон, пароль) можно изменить в
    <a href="/profile" class="font-medium text-neural-cyan underline-offset-2 hover:underline">личном кабинете</a>.
  </Alert>

  {#if pageLoading}
    <div class="grid gap-6 xl:grid-cols-2">
      <LoadingSkeleton variant="card" />
      <LoadingSkeleton variant="card" />
    </div>
  {:else if pageLoadError}
    <ErrorState title="Не удалось загрузить настройки" description={pageLoadError} on:click={loadPageData} />
  {:else}
    <div class="grid gap-6 xl:grid-cols-2">
      <GlassCard glow padding="lg" className="space-y-6 h-fit">
        <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Bell class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
          Уведомления
        </h2>

        {#if notificationSuccessMessage}
          <Alert variant="success">{notificationSuccessMessage}</Alert>
        {/if}
        {#if notificationError}
          <Alert variant="error">{notificationError}</Alert>
        {/if}

        <div class="space-y-4">
          <label class="surface flex cursor-pointer items-center justify-between rounded-xl p-4">
            <div>
              <p class="font-medium text-foreground">Email уведомления</p>
              <p class="text-xs text-muted-foreground">Получать уведомления на почту</p>
            </div>
            <input
              type="checkbox"
              bind:checked={emailNotifications}
              class="h-5 w-5 rounded border-input bg-background text-primary focus:ring-primary"
            />
          </label>

          <label class="surface flex cursor-pointer items-center justify-between rounded-xl p-4">
            <div>
              <p class="font-medium text-foreground">Telegram уведомления</p>
              <p class="text-xs text-muted-foreground">Получать уведомления в Telegram</p>
            </div>
            <input
              type="checkbox"
              bind:checked={telegramNotifications}
              class="h-5 w-5 rounded border-input bg-background text-primary focus:ring-primary"
            />
          </label>

          {#if telegramNotifications}
            <FormField label="Telegram Chat ID" hint="@username или числовой ID" let:controlId>
              <input
                id={controlId}
                type="text"
                bind:value={telegramChatId}
                class="page-input"
                placeholder="@username или ID"
              />
            </FormField>
          {/if}

          <Button
            variant="neural"
            loading={notificationLoading}
            disabled={notificationLoading}
            on:click={handleSaveNotifications}
          >
            <Save class="h-4 w-4" aria-hidden="true" />
            {notificationLoading ? 'Сохранение...' : 'Сохранить уведомления'}
          </Button>
        </div>
      </GlassCard>

      {#if isSuperuser}
        <div class="space-y-6">
          <GlassCard glow padding="lg" className="space-y-6">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <h2 class="flex items-center gap-2 text-lg font-semibold text-foreground">
                <KeyRound class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
                AI-провайдер
              </h2>
              <StatusBadge variant="ai" label="Global scope" dot={false} />
            </div>

            <Alert variant="warning" title="Безопасность ключей">
              Ключи не отображаются полностью — только маскированное состояние. Не публикуйте API-ключи и не отправляйте их в чат.
              Настройки AI глобальные для всего приложения (admin-level), не user-scoped.
            </Alert>

            {#if aiSuccessMessage}
              <Alert variant="success">{aiSuccessMessage}</Alert>
            {/if}
            {#if aiError}
              <Alert variant="error">{aiError}</Alert>
            {/if}

            <form on:submit={handleSave} class="space-y-6">
              <div class="space-y-4">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="text-base font-semibold text-foreground">YandexGPT</h3>
                  <StatusBadge
                    variant={yandexConfigured ? 'success' : 'neutral'}
                    label={yandexConfigured ? 'Настроен' : 'Не настроен'}
                    dot={yandexConfigured}
                  />
                </div>

                <FormField
                  label="API Key"
                  hint={yandexConfigured && yandexKeyMasked ? `Текущий: ${yandexKeyMasked}` : 'Введите новый ключ для замены'}
                  let:controlId
                >
                  <input
                    id={controlId}
                    type="password"
                    bind:value={yandexApiKey}
                    class="page-input"
                    placeholder={yandexConfigured ? '•••••••• (оставьте пустым, чтобы не менять)' : 'AQVN...'}
                    autocomplete="off"
                  />
                </FormField>

                <FormField label="Folder ID" let:controlId>
                  <input
                    id={controlId}
                    type="text"
                    bind:value={yandexFolderId}
                    class="page-input"
                    placeholder="b1g..."
                    autocomplete="off"
                  />
                </FormField>
              </div>

              <div class="space-y-4 border-t border-border/60 pt-4">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="text-base font-semibold text-foreground">DeepSeek</h3>
                  <StatusBadge
                    variant={deepseekConfigured ? 'success' : 'neutral'}
                    label={deepseekConfigured ? 'Настроен' : 'Не настроен'}
                    dot={deepseekConfigured}
                  />
                </div>

                <FormField
                  label="API Key"
                  hint={deepseekConfigured && deepseekKeyMasked ? `Текущий: ${deepseekKeyMasked}` : 'Введите новый ключ для замены'}
                  let:controlId
                >
                  <input
                    id={controlId}
                    type="password"
                    bind:value={deepseekApiKey}
                    class="page-input"
                    placeholder={deepseekConfigured ? '••••••••' : 'sk-...'}
                    autocomplete="off"
                  />
                </FormField>
              </div>

              <div class="space-y-4 border-t border-border/60 pt-4">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="text-base font-semibold text-foreground">OpenAI</h3>
                  <StatusBadge
                    variant={openaiConfigured ? 'success' : 'neutral'}
                    label={openaiConfigured ? 'Настроен' : 'Не настроен'}
                    dot={openaiConfigured}
                  />
                </div>

                <FormField
                  label="API Key"
                  hint={openaiConfigured && openaiKeyMasked ? `Текущий: ${openaiKeyMasked}` : 'Введите новый ключ для замены'}
                  let:controlId
                >
                  <input
                    id={controlId}
                    type="password"
                    bind:value={openaiApiKey}
                    class="page-input"
                    placeholder={openaiConfigured ? '••••••••' : 'sk-...'}
                    autocomplete="off"
                  />
                </FormField>
              </div>

              <div class="flex flex-col gap-3 sm:flex-row">
                <Button type="submit" variant="neural" className="flex-1" loading={aiLoading} disabled={aiLoading}>
                  <Save class="h-4 w-4" aria-hidden="true" />
                  {aiLoading ? 'Сохранение...' : 'Сохранить'}
                </Button>
                <Button type="button" variant="ghost" className="flex-1" loading={aiLoading} disabled={aiLoading} on:click={handleTest}>
                  <FlaskConical class="h-4 w-4" aria-hidden="true" />
                  Тест
                </Button>
              </div>
            </form>
          </GlassCard>

          <GlassCard padding="lg" className="space-y-4">
            <h3 class="flex items-center gap-2 text-base font-semibold text-foreground">
              <Info class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
              Статус провайдера
            </h3>

            <div class="flex flex-wrap gap-2">
              <StatusBadge
                variant={getProviderBadgeVariant(currentProvider)}
                label={getProviderLabel(currentProvider)}
                dot={currentProvider !== 'none'}
              />
              <StatusBadge
                variant={providerStatus === 'configured' ? 'success' : 'warning'}
                label={providerStatus === 'configured' ? 'Configured' : 'Not configured'}
                dot={false}
              />
            </div>

            <div class="surface space-y-2 rounded-xl p-4 text-sm text-muted-foreground">
              <p class="font-medium text-foreground">Ориентиры по стоимости API</p>
              <ul class="space-y-1.5">
                <li>YandexGPT: ~0.07₽ / 1000 токенов</li>
                <li>DeepSeek: ~0.02₽ / 1000 токенов</li>
                <li>OpenAI: ~0.15₽ / 1000 токенов</li>
              </ul>
            </div>

            <Alert variant="info">
              <span class="flex items-center gap-2">
                <ShieldCheck class="h-4 w-4 shrink-0" aria-hidden="true" />
                Ключи хранятся зашифрованными на сервере и не передаются третьим лицам.
              </span>
            </Alert>
          </GlassCard>
        </div>
      {:else}
        <GlassCard padding="lg" className="space-y-4 h-fit">
          <EmptyState
            icon={Lock}
            title="AI-настройки недоступны"
            description="Управление глобальным AI-провайдером доступно только администраторам."
          />
        </GlassCard>
      {/if}
    </div>

    {#if isSuperuser}
      <GlassCard padding="lg" className="space-y-6">
        <h3 class="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Server class="h-5 w-5 text-neural-cyan" aria-hidden="true" />
          Инфраструктура и сервисы
        </h3>

        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div class="surface space-y-3 rounded-xl p-5">
            <div class="flex items-center gap-3">
              <div class="rounded-lg bg-neural-cyan/10 p-2 text-neural-cyan">
                <Server class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h4 class="font-semibold text-foreground">Хостинг/Сервер</h4>
                <p class="text-xs text-neural-cyan">~600–1200₽/мес</p>
              </div>
            </div>
            <ul class="space-y-1.5 text-sm text-muted-foreground">
              <li>VPS (2 CPU, 4GB RAM, 40GB SSD)</li>
              <li>Выделенный IP</li>
            </ul>
            <div class="flex flex-wrap gap-2">
              <a href="https://timeweb.ru" target="_blank" rel="noopener noreferrer" class="chip text-xs">Timeweb</a>
              <a href="https://selectel.ru" target="_blank" rel="noopener noreferrer" class="chip text-xs">Selectel</a>
              <a href="https://reg.ru" target="_blank" rel="noopener noreferrer" class="chip text-xs">Reg.ru</a>
            </div>
          </div>

          <div class="surface space-y-3 rounded-xl p-5">
            <div class="flex items-center gap-3">
              <div class="rounded-lg bg-success/10 p-2 text-success">
                <Globe class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h4 class="font-semibold text-foreground">Домен + SSL</h4>
                <p class="text-xs text-success">~200–500₽/год</p>
              </div>
            </div>
            <ul class="space-y-1.5 text-sm text-muted-foreground">
              <li>Домен .ru</li>
              <li>SSL (Let's Encrypt)</li>
            </ul>
            <div class="flex flex-wrap gap-2">
              <a href="https://nic.ru" target="_blank" rel="noopener noreferrer" class="chip text-xs">Nic.ru</a>
              <a href="https://reg.ru" target="_blank" rel="noopener noreferrer" class="chip text-xs">Reg.ru</a>
            </div>
          </div>

          <div class="surface space-y-3 rounded-xl p-5">
            <div class="flex items-center gap-3">
              <div class="rounded-lg bg-neural-purple/10 p-2 text-neural-purple">
                <KeyRound class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h4 class="font-semibold text-foreground">AI сервисы</h4>
                <p class="text-xs text-neural-purple">~500–2000₽/мес</p>
              </div>
            </div>
            <ul class="space-y-1.5 text-sm text-muted-foreground">
              <li>YandexGPT (рекомендуется)</li>
              <li>DeepSeek (дешевле)</li>
              <li>OpenAI (премиум)</li>
            </ul>
          </div>

          <div class="surface space-y-3 rounded-xl p-5">
            <div class="flex items-center gap-3">
              <div class="rounded-lg bg-warning/10 p-2 text-warning">
                <ShieldCheck class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h4 class="font-semibold text-foreground">Прокси для парсинга</h4>
                <p class="text-xs text-warning">~2000–7000₽/мес</p>
              </div>
            </div>
            <ul class="space-y-1.5 text-sm text-muted-foreground">
              <li>Резидентные (Россия)</li>
              <li>Мобильные прокси</li>
            </ul>
          </div>

          <div class="surface space-y-3 rounded-xl p-5">
            <div class="flex items-center gap-3">
              <div class="rounded-lg bg-neural-blue/10 p-2 text-neural-blue">
                <Bell class="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h4 class="font-semibold text-foreground">Почта для уведомлений</h4>
                <p class="text-xs text-neural-blue">0–500₽/мес</p>
              </div>
            </div>
            <ul class="space-y-1.5 text-sm text-muted-foreground">
              <li>SendPulse (бесплатно до 3000)</li>
              <li>UniSender / Gmail SMTP</li>
            </ul>
          </div>

          {#if hasAdminAuditAccess}
            <div class="surface space-y-3 rounded-xl p-5">
              <div class="flex items-center gap-3">
                <div class="rounded-lg bg-success/10 p-2 text-success">
                  <Info class="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <h4 class="font-semibold text-foreground">Мониторинг и логи</h4>
                  <p class="text-xs text-success">0–1000₽/мес</p>
                </div>
              </div>
              <ul class="space-y-1.5 text-sm text-muted-foreground">
                <li>Sentry (ошибки)</li>
                <li>Grafana Cloud (метрики)</li>
              </ul>
            </div>
          {/if}
        </div>

        <div class="surface rounded-xl border border-neural-cyan/20 bg-neural-cyan/5 p-6">
          <div class="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h4 class="font-semibold text-foreground">Итого в месяц</h4>
              <p class="text-sm text-muted-foreground">Минимальный бюджет для запуска</p>
            </div>
            <div class="text-right">
              <p class="text-3xl font-bold text-neural-cyan">~3500–10000₽</p>
              <p class="text-xs text-muted-foreground">Зависит от нагрузки и тарифов</p>
            </div>
          </div>
        </div>
      </GlassCard>
    {/if}
  {/if}
</div>

<AppPageStyles />
