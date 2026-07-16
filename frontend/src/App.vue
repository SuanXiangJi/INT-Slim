<template>
  <router-view />
</template>

<script setup>
import { useTheme } from "@/composables/useTheme"
useTheme()
</script>

<style>
:root {
  /* Learning Platform Palette - Light */
  color-scheme: light;
  --bg-primary: #f6f8fb;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f0f4f8;
  --bg-hover: #e8eef5;
  --bg-glass: rgba(255, 255, 255, 0.86);
  --surface-card: #ffffff;
  --surface-raised: #fbfdff;
  --surface-muted: #f3f6fb;
  --text-primary: #172033;
  --text-secondary: #5c677d;
  --text-tertiary: #8a96aa;
  --border-color: #dfe6ef;
  --border-hover: #4b83f5;
  --accent-primary: #2563eb;
  --accent-secondary: #3b82f6;
  --accent-gradient: linear-gradient(135deg, #1d4ed8 0%, #2563eb 55%, #0ea5e9 100%);
  --accent-gradient-warm: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
  --accent-glow: 0 12px 34px rgba(37, 99, 235, 0.2);
  --accent-soft: rgba(37, 99, 235, 0.1);
  --warm-accent: #f59e0b;
  --success: #10b981;
  --success-soft: rgba(16, 185, 129, 0.12);
  --error: #ef4444;
  --error-soft: rgba(239, 68, 68, 0.12);
  --warning: #f59e0b;
  --warning-soft: rgba(245, 158, 11, 0.13);
  --info: #3b82f6;
  --info-soft: rgba(59, 130, 246, 0.12);
  --sidebar-bg: #ffffff;
  --sidebar-text: #64748b;
  --sidebar-heading: #172033;
  --sidebar-border: #dfe6ef;
  --sidebar-hover: #eff6ff;
  --sidebar-active: #2563eb;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.12);
  --shadow-xl: 0 16px 48px rgba(0,0,0,0.15);
  --transition-fast: 0.15s ease;
  --transition-base: 0.25s ease;
  --transition-slow: 0.4s cubic-bezier(0.4,0,0.2,1);
  --blur-glass: blur(20px) saturate(180%);

  --el-color-primary: var(--accent-primary);
  --el-color-success: var(--success);
  --el-color-warning: var(--warning);
  --el-color-danger: var(--error);
  --el-color-info: var(--info);
  --el-bg-color: var(--bg-secondary);
  --el-bg-color-page: var(--bg-primary);
  --el-bg-color-overlay: var(--surface-card);
  --el-fill-color: var(--surface-muted);
  --el-fill-color-light: var(--bg-tertiary);
  --el-fill-color-lighter: var(--bg-primary);
  --el-fill-color-blank: var(--bg-secondary);
  --el-border-color: var(--border-color);
  --el-border-color-light: var(--border-color);
  --el-border-color-lighter: var(--border-color);
  --el-text-color-primary: var(--text-primary);
  --el-text-color-regular: var(--text-secondary);
  --el-text-color-secondary: var(--text-tertiary);
  --el-text-color-placeholder: var(--text-tertiary);
  --el-mask-color: rgba(15, 23, 42, 0.42);
  --el-box-shadow-light: var(--shadow-md);
  --el-box-shadow: var(--shadow-lg);
  --el-border-radius-base: var(--radius-md);
}
.dark {
  color-scheme: dark;
  --bg-primary: #0b1120;
  --bg-secondary: #111a2d;
  --bg-tertiary: #18243a;
  --bg-hover: #20304a;
  --bg-glass: rgba(17, 26, 45, 0.88);
  --surface-card: #101a2d;
  --surface-raised: #142039;
  --surface-muted: #18243a;
  --text-primary: #edf3fc;
  --text-secondary: #a6b2c5;
  --text-tertiary: #718099;
  --border-color: #24324a;
  --border-hover: #60a5fa;
  --accent-primary: #60a5fa;
  --accent-secondary: #38bdf8;
  --accent-gradient: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%);
  --accent-glow: 0 12px 38px rgba(14, 165, 233, 0.2);
  --accent-soft: rgba(96, 165, 250, 0.14);
  --success-soft: rgba(16, 185, 129, 0.16);
  --error-soft: rgba(239, 68, 68, 0.16);
  --warning-soft: rgba(245, 158, 11, 0.16);
  --info-soft: rgba(56, 189, 248, 0.15);
  --sidebar-bg: #0e1729;
  --sidebar-text: #91a0b8;
  --sidebar-heading: #f3f7fd;
  --sidebar-border: #24324a;
  --sidebar-hover: #182640;
  --sidebar-active: #60a5fa;
  --shadow-xs: 0 1px 2px rgba(0,0,0,0.2);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.5);
  --shadow-xl: 0 16px 48px rgba(0,0,0,0.6);
}

* { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background var(--transition-slow), color var(--transition-slow);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  line-height: 1.6;
}
button, input, textarea, select { font:inherit; }

#app { width:100%; height:100vh; }

::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(0,0,0,0.1); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:rgba(0,0,0,0.2); }
.dark ::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.08); }
.dark ::-webkit-scrollbar-thumb:hover { background:rgba(255,255,255,0.15); }

::selection { background:rgba(99,102,241,0.2); color:inherit; }

/* Element Plus overrides */
.el-button--primary {
  --el-button-bg-color: var(--accent-primary);
  --el-button-border-color: var(--accent-primary);
  --el-button-hover-bg-color: var(--accent-secondary);
  --el-button-hover-border-color: var(--accent-secondary);
  --el-button-active-bg-color: var(--accent-primary);
  --el-button-active-border-color: var(--accent-primary);
}
.el-button:not(.el-button--primary) {
  --el-button-bg-color: var(--surface-card);
  --el-button-border-color: var(--border-color);
  --el-button-text-color: var(--text-primary);
  --el-button-hover-bg-color: var(--bg-hover);
  --el-button-hover-border-color: var(--border-hover);
  --el-button-hover-text-color: var(--text-primary);
}
.el-card,
.el-dialog,
.el-drawer,
.el-message-box,
.el-popover,
.el-popper,
.el-dropdown__popper .el-dropdown-menu {
  --el-card-bg-color: var(--surface-card);
  --el-card-border-color: var(--border-color);
  background-color: var(--surface-card);
  color: var(--text-primary);
  border-color: var(--border-color);
}
.el-input,
.el-select,
.el-textarea,
.el-input__wrapper,
.el-select__wrapper,
.el-textarea__inner {
  --el-fill-color-blank: var(--bg-secondary);
  --el-bg-color: var(--bg-secondary);
  --el-border-color: var(--border-color);
  --el-input-bg-color: var(--bg-secondary);
  --el-input-border-color: var(--border-color);
  --el-input-text-color: var(--text-primary);
  --el-input-placeholder-color: var(--text-tertiary);
  color: var(--text-primary);
}
.el-table,
.el-table tr,
.el-table th.el-table__cell,
.el-table td.el-table__cell {
  background-color: var(--surface-card);
  color: var(--text-primary);
  border-color: var(--border-color);
}
.el-table__body tr:hover > td.el-table__cell { background-color: var(--bg-hover); }
.el-tag { border-color: var(--border-color); background: var(--accent-soft); color: var(--accent-primary); }
.el-progress__text { color: var(--text-secondary); }
.el-empty__description p { color: var(--text-tertiary); }
.el-menu { --el-menu-bg-color: transparent !important; }
.el-collapse-item__header { font-size:13px; font-weight:500; }
</style>
