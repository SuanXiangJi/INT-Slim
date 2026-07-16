<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': collapsed, 'mobile-open': mobileOpen }">
    <button v-if="mobileOpen" class="sidebar-backdrop" aria-label="关闭导航" @click="mobileOpen = false"></button>
    <aside class="app-sidebar">
      <div class="sidebar-header">
        <div class="brand" @click="$router.push('/dashboard')">
          <div class="brand-icon">X</div>
          <span v-show="!collapsed" class="brand-text">XBots</span>
        </div>
        <button class="collapse-btn" :aria-label="collapsed ? '展开导航' : '收起导航'" @click="collapsed = !collapsed">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18L9 12L15 6"/></svg>
        </button>
      </div>
      <nav class="sidebar-nav">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item" :class="{ active: route.path === item.path }">
          <div class="nav-icon" v-html="item.icon"></div>
          <span v-show="!collapsed" class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <button class="theme-btn" @click="toggleTheme">
          <svg v-if="!isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
          <span v-show="!collapsed">{{ isDark ? "亮色" : "深色" }}</span>
        </button>
        <div class="user-section">
          <button class="user-btn" aria-haspopup="menu" :aria-expanded="showMenu" @click.stop="showMenu = !showMenu">
            <div class="user-avatar">{{ username[0] || "学" }}</div>
            <span v-show="!collapsed" class="user-name">{{ username }}</span>
          </button>
          <Transition name="menu-fade">
            <div v-if="showMenu" class="user-menu" role="menu" @click.stop>
              <div class="menu-item" @click="showProfile = true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <span>个人信息</span>
              </div>
              <div class="menu-divider"></div>
              <div class="menu-item logout" @click="handleLogout">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                <span>退出登录</span>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </aside>
    <div class="app-main">
      <header class="app-topbar">
        <div class="topbar-left">
          <button class="mobile-menu-btn" aria-label="打开导航" @click="mobileOpen = true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button>
          <div><h2 class="page-title">{{ pageTitle }}</h2></div>
        </div>
        <div class="topbar-right"></div>
      </header>
      <main class="app-content"><slot /></main>
    </div>
    <ProfilePanel v-if="showProfile" @close="showProfile = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { removeToken, getCurrentUser } from "../utils/api"
import { useTheme } from "../composables/useTheme"
import ProfilePanel from "./ProfilePanel.vue"

const route = useRoute()
const router = useRouter()
const collapsed = ref(localStorage.getItem("sidebar_collapsed") === "true")
const showMenu = ref(false)
const mobileOpen = ref(false)
const showProfile = ref(false)
const username = ref("学员")
const { isDark, toggleTheme } = useTheme()

const navItems = [
  { path: "/dashboard", label: "学习看板", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>' },
  { path: "/courses", label: "学习入口", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>' },
  { path: "/code-practice", label: "代码实训", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>' },
  { path: "/tasks", label: "学习任务", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>' },
  { path: "/chat", label: "Agents伴学", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' },
  { path: "/path", label: "学习路径", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>' },
  { path: "/diagnosis", label: "学情诊断", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>' },
  { path: "/mistakes", label: "错题薄弱项", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.6 2.4 17.1A2 2 0 0 0 4.1 20h15.8a2 2 0 0 0 1.7-2.9L13.7 3.6a2 2 0 0 0-3.4 0z"/></svg>' },
  { path: "/reports", label: "学习报告", icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' },
]

const pageTitle = computed(() => {
  const map = { "/dashboard":"学习看板", "/courses":"学习入口", "/code-practice":"代码实训", "/tasks":"学习任务", "/chat":"Agents伴学", "/path":"学习路径", "/diagnosis":"学情诊断", "/mistakes":"错题薄弱项", "/reports":"学习报告" }
  if (route.path.startsWith("/courses/")) return "课程学习"
  if (route.path.startsWith("/assessments/")) return "章节测验"
  if (route.path.startsWith("/study/")) return "沉浸学习"
  return map[route.path] || "XBots"
})

watch(collapsed, v => localStorage.setItem("sidebar_collapsed", v))
watch(() => route.path, () => { mobileOpen.value = false; showMenu.value = false })
const closeMenu = () => { showMenu.value = false }

onMounted(async () => {
  try { const u = await getCurrentUser(); if (u?.username) username.value = u.username } catch {}
  document.addEventListener("click", closeMenu)
})
onUnmounted(() => document.removeEventListener("click", closeMenu))

function handleLogout() { removeToken(); router.push("/") }
</script>

<style scoped>
.app-shell { display:flex; height:100vh; overflow:hidden; background:var(--bg-primary); }
.sidebar-backdrop { display:none; }

.app-sidebar {
  width:232px; min-width:232px; display:flex; flex-direction:column;
  background:var(--sidebar-bg); border-right:1px solid var(--sidebar-border);
  transition:width 0.3s cubic-bezier(0.4,0,0.2,1), min-width 0.3s cubic-bezier(0.4,0,0.2,1);
  position:relative; z-index:100; overflow:hidden;
}
.sidebar-collapsed .app-sidebar { width:64px; min-width:64px; }

.sidebar-header {
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 12px; border-bottom:1px solid var(--sidebar-border);
  height:60px; flex-shrink:0;
}
.brand { display:flex; align-items:center; gap:10px; cursor:pointer; flex:1; overflow:hidden; }
.brand-icon {
  width:32px; height:32px; min-width:32px;
  background:var(--text-primary); border-radius:10px;
  display:flex; align-items:center; justify-content:center;
  color:#fff; font-size:16px; font-weight:bold;
  box-shadow:none;
}
.brand-text { color:var(--sidebar-heading); font-size:16px; font-weight:800; letter-spacing:-0.03em; white-space:nowrap; }
.collapse-btn {
  width:24px; height:24px; min-width:24px; display:flex; align-items:center; justify-content:center;
  background:transparent; border:none; color:var(--sidebar-text);
  cursor:pointer; border-radius:4px; transition:all 0.2s; transform:rotate(0deg);
}
.sidebar-collapsed .collapse-btn { transform:rotate(180deg); }
.collapse-btn:hover { color:var(--sidebar-active); background:var(--sidebar-hover); }
.collapse-btn svg { width:16px; height:16px; }

.sidebar-nav { flex:1; padding:10px 8px; overflow-y:auto; overflow-x:hidden; }
.nav-item {
  display:flex; align-items:center; gap:10px; padding:10px 12px; margin-bottom:2px;
  border-radius:10px; cursor:pointer; color:var(--sidebar-text);
  text-decoration:none; transition:all 0.2s; white-space:nowrap;
}
.nav-item:hover { color:var(--sidebar-heading); background:var(--sidebar-hover); }
.nav-item.active { color:var(--sidebar-heading); background:var(--sidebar-hover); box-shadow:none; }
.nav-icon { width:20px; height:20px; min-width:20px; display:flex; align-items:center; }
.nav-icon :deep(svg) { width:20px; height:20px; }
.nav-label { font-size:14px; font-weight:500; }

.sidebar-footer { padding:8px; border-top:1px solid var(--sidebar-border); flex-shrink:0; }
.theme-btn {
  display:flex; align-items:center; gap:10px; width:100%; padding:9px 12px;
  border-radius:8px; border:none; background:transparent;
  color:var(--sidebar-text); cursor:pointer; transition:all 0.2s; font-size:13px; white-space:nowrap;
}
.theme-btn:hover { color:var(--sidebar-heading); background:var(--sidebar-hover); }
.theme-btn svg { width:18px; height:18px; flex-shrink:0; }

.user-section { margin-top:4px; position:relative; }
.user-btn {
  display:flex; align-items:center; gap:10px; width:100%; padding:8px 12px;
  border-radius:8px; border:none; background:transparent;
  color:var(--sidebar-text); cursor:pointer; transition:all 0.2s;
}
.user-btn:hover { background:var(--sidebar-hover); }
.user-avatar {
  width:28px; height:28px; min-width:28px; border-radius:50%;
  background:var(--accent-gradient); display:flex; align-items:center; justify-content:center;
  color:#fff; font-size:12px; font-weight:600;
}
.user-name { font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--sidebar-heading); }
.user-menu {
  position:absolute; bottom:100%; left:0; right:0; margin-bottom:8px;
  background:var(--bg-secondary); border:1px solid var(--border-color);
  border-radius:10px; box-shadow:var(--shadow-lg); overflow:hidden; z-index:200;
}
.menu-item { display:flex; align-items:center; gap:10px; padding:12px 16px; cursor:pointer; transition:background 0.15s; font-size:13px; color:var(--text-primary); }
.menu-item:hover { background:var(--bg-hover); }
.menu-item svg { width:16px; height:16px; color:var(--text-secondary); }
.menu-divider { height:1px; background:var(--border-color); margin:4px 0; }
.menu-item.logout { color:var(--error); }
.menu-item.logout svg { color:var(--error); }
.menu-fade-enter-active, .menu-fade-leave-active { transition:all 0.2s; }
.menu-fade-enter-from, .menu-fade-leave-to { opacity:0; transform:translateY(8px); }

.app-main { flex:1; display:flex; flex-direction:column; overflow:hidden; min-width:0; }
.app-topbar {
  display:flex; align-items:center; justify-content:space-between;
  padding:0 24px; height:56px; flex-shrink:0;
  background:var(--bg-primary); border-bottom:1px solid transparent;
}
.page-title { font-size:15px; font-weight:650; margin:0; color:var(--text-secondary); }
.app-content { flex:1; overflow-y:auto; overflow-x:hidden; padding:20px; }
.topbar-left { display:flex; align-items:center; gap:12px; }
.mobile-menu-btn { display:none; width:38px; height:38px; border:1px solid var(--border-color); border-radius:10px; background:var(--bg-tertiary); color:var(--text-primary); align-items:center; justify-content:center; cursor:pointer; }
.mobile-menu-btn svg { width:20px; height:20px; }

@media (max-width:760px) {
  .app-sidebar { position:fixed; inset:0 auto 0 0; width:min(82vw,288px); min-width:min(82vw,288px); transform:translateX(-105%); box-shadow:var(--shadow-xl); transition:transform .28s cubic-bezier(.4,0,.2,1); }
  .mobile-open .app-sidebar { transform:translateX(0); }
  .sidebar-collapsed .app-sidebar { width:min(82vw,288px); min-width:min(82vw,288px); }
  .sidebar-collapsed .brand-text, .sidebar-collapsed .nav-label, .sidebar-collapsed .theme-btn span, .sidebar-collapsed .user-name { display:block !important; }
  .sidebar-collapsed .collapse-btn { transform:none; }
  .sidebar-backdrop { display:block; position:fixed; inset:0; z-index:90; border:0; background:rgba(4,7,15,.52); backdrop-filter:blur(2px); }
  .mobile-menu-btn { display:flex; }
  .app-topbar { height:64px; padding:0 16px; }
  .app-content { padding:14px; }
}
@media (prefers-reduced-motion:reduce) { .app-sidebar, .nav-item, .menu-fade-enter-active, .menu-fade-leave-active { transition:none; } }
</style>
