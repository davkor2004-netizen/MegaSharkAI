/**
 * Хранилище темы
 */
import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

// Получаем тему из localStorage
function getSavedTheme(): 'dark' | 'light' {
  if (!browser) return 'dark';
  return (localStorage.getItem('theme') as 'dark' | 'light') || 'dark';
}

// Создаём store
export const theme = writable<'dark' | 'light'>(getSavedTheme());

// Функция переключения
export function toggleTheme() {
  const current = get(theme);
  const newValue = current === 'dark' ? 'light' : 'dark';
  
  theme.set(newValue);
  localStorage.setItem('theme', newValue);
  
  // Применяем сразу
  applyTheme(newValue);
}

// Применяем тему к document
export function applyTheme(value: 'dark' | 'light') {
  if (!browser) return;
  
  if (value === 'light') {
    document.documentElement.classList.add('light');
  } else {
    document.documentElement.classList.remove('light');
  }
}

// Авто-применение при изменении store
theme.subscribe((value) => {
  if (browser) {
    applyTheme(value);
  }
});

// Синхронизация при загрузке страницы
if (browser) {
  const saved = getSavedTheme();
  applyTheme(saved);
}

