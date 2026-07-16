<template>
  <div class="assistant-dock" :class="{ open }">
    <transition name="panel">
      <section v-if="open" class="assistant-panel">
        <header>
          <div>
            <p>LEARNING ASSISTANT</p>
            <h4>学习助手</h4>
          </div>
          <el-tag size="small" type="success" effect="plain">可用</el-tag>
        </header>

        <div class="assistant-state">
          <strong>{{ headline }}</strong>
          <span>{{ subline }}</span>
        </div>

        <div class="suggestions">
          <button v-for="item in displaySuggestions" :key="item.title" @click="go(item)">
            <strong>{{ item.title }}</strong>
            <small>{{ item.message }}</small>
          </button>
        </div>

        <footer>
          <button @click="router.push('/chat')">去提问</button>
          <button @click="router.push('/courses')">选学习内容</button>
        </footer>
      </section>
    </transition>

    <button class="assistant-trigger" aria-label="打开学习助手" @click="toggle">
      <span class="core"></span>
      <span class="ring"></span>
      <i v-if="displaySuggestions.length">{{ displaySuggestions.length }}</i>
    </button>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { useRouter } from "vue-router"
import { apiGet } from "../utils/api"

const router = useRouter()
const open = ref(false)
const suggestions = ref([])
const overview = ref({})
let timer = null

const headline = computed(() => {
  if (overview.value.pending_task_count) return `还有 ${overview.value.pending_task_count} 个学习计划待继续`
  if (overview.value.training_count) return `已准备 ${overview.value.training_count} 份可学习素材`
  return "先选择一个学习方向"
})

const subline = computed(() => {
  if (overview.value.training_count) return "我会根据你的学习进度和现有资料，提醒下一步适合做什么。"
  return "添加或选择学习素材后，这里会给出学习建议。"
})

const displaySuggestions = computed(() => {
  if (suggestions.value.length) return suggestions.value.map(normalizeSuggestion)
  return [
    { title: "选择学习内容", message: "从素材中挑一个方向，生成学习计划。", route: "/courses" },
    { title: "继续学习计划", message: "查看已经创建的计划和待完成事项。", route: "/tasks" },
  ]
})

function normalizeSuggestion(item) {
  return {
    ...item,
    title: cleanCopy(item.title),
    message: cleanCopy(item.message),
  }
}

function cleanCopy(text) {
  return String(text || "")
    .replace(/主动交互\s*Agent/g, "学习助手")
    .replace(/Agent\s*编排/g, "学习流程")
    .replace(/Agent/g, "助手")
    .replace(/训练工作台/g, "学习入口")
    .replace(/证据链/g, "参考资料")
    .replace(/证据/g, "资料")
    .replace(/RAG/g, "资料辅助")
    .replace(/检索/g, "查找")
}

async function loadAssistantState() {
  try {
    const data = await apiGet("/learning/training-workspace?limit=6")
    suggestions.value = data.proactive_agent?.suggestions || []
    overview.value = data.overview || {}
  } catch {
    suggestions.value = []
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) loadAssistantState()
}

function go(item) {
  if (item.route) router.push(item.route)
  open.value = false
}

onMounted(() => {
  loadAssistantState()
  timer = window.setInterval(loadAssistantState, 60000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.assistant-dock { position:fixed; right:22px; bottom:22px; z-index:999; display:flex; align-items:flex-end; gap:12px; }
.assistant-trigger { position:relative; width:54px; height:54px; border:1px solid rgba(148,163,184,.45); border-radius:18px; background:linear-gradient(145deg,#0f172a,#1e293b); box-shadow:0 14px 34px rgba(15,23,42,.28); cursor:pointer; }
.assistant-trigger:hover { transform:translateY(-2px); }
.core { position:absolute; inset:15px; border-radius:10px; background:linear-gradient(135deg,#38bdf8,#22c55e); box-shadow:0 0 18px rgba(56,189,248,.35); }
.ring { position:absolute; inset:8px; border:1px solid rgba(219,234,254,.38); border-radius:14px; }
.assistant-trigger i { position:absolute; right:-6px; top:-6px; display:flex; align-items:center; justify-content:center; min-width:19px; height:19px; padding:0 5px; border-radius:999px; color:#fff; background:#ef4444; border:2px solid var(--bg-primary); font-size:11px; font-style:normal; font-weight:700; }
.assistant-panel { width:min(360px, calc(100vw - 88px)); padding:14px; border:1px solid var(--border-color); border-radius:var(--radius-lg); background:var(--surface-card); box-shadow:var(--shadow-xl); }
.assistant-panel header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.assistant-panel p { margin:0 0 4px; color:var(--accent-primary); font-size:10px; font-weight:800; letter-spacing:1.2px; }
.assistant-panel h4 { margin:0; font-size:15px; color:var(--text-primary); }
.assistant-state { padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-md); background:var(--surface-raised); }
.assistant-state strong, .assistant-state span { display:block; }
.assistant-state strong { font-size:14px; color:var(--text-primary); }
.assistant-state span { margin-top:5px; color:var(--text-secondary); font-size:12px; line-height:1.5; }
.suggestions { display:grid; gap:8px; margin-top:10px; }
.suggestions button { padding:11px; border:1px solid var(--border-color); border-radius:var(--radius-md); color:var(--text-primary); background:var(--surface-raised); text-align:left; cursor:pointer; }
.suggestions button:hover { border-color:var(--accent-primary); background:var(--bg-hover); }
.suggestions strong, .suggestions small { display:block; }
.suggestions strong { font-size:13px; }
.suggestions small { margin-top:4px; color:var(--text-secondary); line-height:1.45; }
.assistant-panel footer { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:12px; }
.assistant-panel footer button { padding:9px 10px; border:1px solid var(--border-color); border-radius:var(--radius-md); color:var(--text-primary); background:var(--surface-raised); cursor:pointer; }
.assistant-panel footer button:last-child { color:#fff; border-color:var(--accent-primary); background:var(--accent-primary); }
.panel-enter-active, .panel-leave-active { transition:all .18s ease; }
.panel-enter-from, .panel-leave-to { opacity:0; transform:translateY(8px); }
@media (max-width:640px) { .assistant-dock { right:14px; bottom:14px; } .assistant-trigger { width:50px; height:50px; } }
</style>
