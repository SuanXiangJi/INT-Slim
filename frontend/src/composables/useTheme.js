import { ref, computed, watch, onMounted } from 'vue'

const THEME_KEY = 'xbots-theme'
const LIGHT_THEME = 'light'
const DARK_THEME = 'dark'

function preferredTheme() {
  if (typeof window === 'undefined') return LIGHT_THEME
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === LIGHT_THEME || savedTheme === DARK_THEME) return savedTheme
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? DARK_THEME : LIGHT_THEME
}

const currentTheme = ref(preferredTheme())

export function useTheme() {
  const isDark = computed(() => currentTheme.value === DARK_THEME)

  function setTheme(theme) {
    currentTheme.value = theme
    localStorage.setItem(THEME_KEY, theme)
    applyTheme(theme)
  }

  function toggleTheme() {
    const newTheme = isDark.value ? LIGHT_THEME : DARK_THEME
    setTheme(newTheme)
  }

  function applyTheme(theme) {
    const root = document.documentElement
    if (theme === DARK_THEME) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    root.dataset.theme = theme
  }

  onMounted(() => {
    applyTheme(currentTheme.value)
  })

  watch(currentTheme, (newTheme) => {
    applyTheme(newTheme)
  })

  return {
    currentTheme,
    isDark,
    setTheme,
    toggleTheme
  }
}
