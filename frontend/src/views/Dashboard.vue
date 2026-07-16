<template>
  <AppLayout>
    <div class="dashboard" :class="{ 'is-loading': loading }">
      <!-- Welcome Hero -->
      <div class="hero-section">
        <div class="hero-text">
          <h1>👋 欢迎回来，{{ username }}</h1>
          <p v-if="pendingTasks">今天还有 <strong>{{ pendingTasks }}</strong> 个学习任务待完成，完成一项就离目标更近一步。</p>
          <p v-else>共有 <strong>{{ totalKps }}</strong> 个知识点等你探索，已整理为 <strong>{{ catCount }}</strong> 个分类</p>
          <el-button type="primary" size="large" @click="$router.push(pendingTasks ? '/tasks' : '/courses')" round>{{ pendingTasks ? "查看任务 →" : "开始学习 →" }}</el-button>
        </div>
        <div class="hero-stats">
          <div class="stat-card"><span class="stat-num">{{ totalKps }}</span><span class="stat-label">知识点</span></div>
          <div class="stat-card"><span class="stat-num">{{ totalDocs }}</span><span class="stat-label">文档</span></div>
          <div class="stat-card"><span class="stat-num">{{ catCount }}</span><span class="stat-label">分类</span></div>
          <div class="stat-card"><span class="stat-num">{{ pendingTasks }}</span><span class="stat-label">待办</span></div>
        </div>
      </div>

      <!-- Charts Row -->
      <div v-if="loading" class="skeleton-grid" aria-label="正在加载学习数据"><div></div><div></div></div>
      <div v-else-if="totalKps" class="charts-row">
        <div class="chart-card">
          <div class="chart-header">📊 知识点分类</div>
          <div ref="catChart" class="chart-body"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header">📈 难度分布</div>
          <div ref="diffChart" class="chart-body"></div>
        </div>
      </div>
      <div v-else class="empty-state"><div class="empty-icon">◇</div><h3>学习空间还是空的</h3><p>导入知识内容后，这里会生成分类、难度与复习趋势。</p><el-button type="primary" @click="$router.push('/courses')">前往课程中心</el-button></div>

      <!-- Forgetting Curve -->
      <div class="curve-section"><ForgettingCurve :timeRange="720" /></div>

      <section v-if="pendingTaskList.length" class="today-section">
        <div class="section-title"><span>今日待办</span><el-button text type="primary" @click="$router.push('/tasks')">全部任务</el-button></div>
        <div class="today-list"><button v-for="task in pendingTaskList" :key="task.id" class="today-task" @click="$router.push('/tasks')"><span class="task-check"></span><span>{{ task.title }}</span><small v-if="task.due_date">{{ new Date(task.due_date).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'}) }}</small></button></div>
      </section>

      <!-- Category Grid -->
      <div class="section-title">📂 课程分类</div>
      <div class="cat-grid">
        <div v-for="c in topCats" :key="c.name" class="cat-card" @click="$router.push({path:'/courses',query:{cat:c.name}})">
          <div class="cat-icon" :style="{background:c.bg}">{{ c.emoji }}</div>
          <div class="cat-info"><div class="cat-name">{{ c.name }}</div><div class="cat-count">{{ c.count }} 项</div></div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted, watch } from "vue"
import * as echarts from "echarts"
import AppLayout from "../components/AppLayout.vue"
import ForgettingCurve from "../components/ForgettingCurve.vue"
import { apiGet } from "../utils/api"
import { useTheme } from "../composables/useTheme"

const username = ref("学员")
const totalKps = ref(0); const totalDocs = ref(0); const catCount = ref(0)
const pendingTasks = ref(0); const pendingTaskList = ref([])
const topCats = ref([])
const loading = ref(true)
const catChart = ref(null); const diffChart = ref(null)
let cc = null; let dc = null
let chartData = null
const { isDark } = useTheme()
const COLORS = {"ai-agent":"#8b5cf6","python3":"#6366f1","cplusplus":"#ec4899","java":"#ef4444","js":"#f59e0b","vue3":"#10b981","react":"#3b82f6","html":"#f97316","css":"#06b6d4","pytorch":"#ef4444","docker":"#3b82f6","linux":"#1e293b","ml":"#ec4899","nlp":"#8b5cf6","go":"#22c55e","rust":"#64748b","sql":"#0ea5e9","php":"#6366f1","mongodb":"#16a34a","sklearn":"#3b82f6","pandas":"#14b8a6","fastapi":"#10b981","flask":"#14b8a6"}
const EMOJIS = {"ai-agent":"🤖","python3":"🐍","cplusplus":"🔧","java":"☕","js":"📜","vue3":"💚","react":"⚛️","html":"🌐","css":"🎨","pytorch":"🔥","docker":"🐳","linux":"🐧","ml":"🧠","nlp":"📝","go":"🔷","rust":"🦀","sql":"📋","php":"🐘","mongodb":"🍃","sklearn":"📊","pandas":"🐼","fastapi":"⚡","flask":"🧪"}

function renderCharts() {
  if (!chartData || !catChart.value || !diffChart.value) return
  const { sorted, diff } = chartData
  const text = isDark.value ? "#a6b2c5" : "#5c677d"
  const grid = isDark.value ? "#24324a" : "#dfe6ef"
  const tooltip = { backgroundColor:isDark.value ? "#18243a" : "#ffffff", borderColor:grid, textStyle:{ color:isDark.value ? "#edf3fc" : "#172033" } }
  if (!cc) cc = echarts.init(catChart.value)
  if (!dc) dc = echarts.init(diffChart.value)
  cc.setOption({ backgroundColor:"transparent", tooltip:{...tooltip,trigger:"item",formatter:"{b}: {c} ({d}%)"}, series:[{ type:"pie", radius:["38%","68%"], center:["50%","52%"], data:sorted.slice(0,10).map(([n,v])=>({name:n,value:v,itemStyle:{color:COLORS[n]||"#2563eb"}})), itemStyle:{borderColor:isDark.value ? "#111a2d" : "#fff",borderWidth:3,borderRadius:5}, label:{color:text,fontSize:11,formatter:"{b}\n{d}%"} }] }, true)
  dc.setOption({ backgroundColor:"transparent", tooltip:{...tooltip,trigger:"axis"}, xAxis:{type:"category",data:Object.keys(diff),axisLine:{lineStyle:{color:grid}},axisTick:{show:false},axisLabel:{color:text}}, yAxis:{type:"value",axisLine:{show:false},axisLabel:{color:text},splitLine:{lineStyle:{color:grid,type:"dashed"}}}, series:[{ type:"bar", data:Object.entries(diff).map(([k,v])=>({value:v,itemStyle:{color:{"初级":"#22c55e","中级":"#f59e0b","高级":"#ef4444"}[k],borderRadius:[6,6,0,0]}})), barWidth:"42%", label:{show:true,position:"top",color:text} }], grid:{left:44,right:20,top:24,bottom:32} }, true)
}

onMounted(async () => {
  try { const u = await apiGet("/auth/me"); if (u?.username) username.value = u.username } catch {}
  try {
    const [kps, workspace, tasks] = await Promise.allSettled([
      apiGet("/learning/knowledge-points"),
      apiGet("/learning/training-workspace?limit=1&fast=true"),
      apiGet("/learning/tasks")
    ])
    const kpData = kps.status === "fulfilled" ? (kps.value || []) : []
    const workspaceData = workspace.status === "fulfilled" ? (workspace.value || {}) : {}
    totalKps.value = kpData.length
    totalDocs.value = workspaceData.overview?.training_count || 0
    const taskData = tasks.value || []; pendingTasks.value = taskData.filter(task => task.status === "todo").length; pendingTaskList.value = taskData.filter(task => task.status === "todo").slice(0,3)
    if (kpData.length) {
      const cm = {}; kpData.forEach(k => { const c = k.category||"其他"; cm[c] = (cm[c]||0)+1 })
      const sorted = Object.entries(cm).sort((a,b) => b[1]-a[1])
      catCount.value = sorted.length
      topCats.value = sorted.slice(0,8).map(([n,c]) => ({ name:n, count:c, emoji:EMOJIS[n]||"📚", bg:`linear-gradient(135deg,${COLORS[n]||"#6366f1"},${COLORS[n]||"#6366f1"}22)` }))
      const diff = {"初级":0,"中级":0,"高级":0}; kpData.forEach(k => { const d = k.difficulty||0.3; if (d<0.35) diff["初级"]++; else if (d<0.65) diff["中级"]++; else diff["高级"]++ })
      chartData = { sorted, diff }
    }
  } catch {} finally { loading.value = false }
  await nextTick()
  renderCharts()
  window.addEventListener("resize", resizeCharts)
})
const resizeCharts = () => { cc?.resize(); dc?.resize() }
watch(isDark, async () => { await nextTick(); renderCharts() })
onUnmounted(() => { window.removeEventListener("resize", resizeCharts); cc?.dispose(); dc?.dispose() })
</script>
<style scoped>
.dashboard { max-width:1100px; margin:0 auto; }
.hero-section {
  display:flex; justify-content:space-between; align-items:center;
  padding:28px 32px; margin-bottom:20px;
  background:var(--accent-gradient); border-radius:var(--radius-xl);
  color:#fff; position:relative; overflow:hidden;
}
.hero-section::before {
  content:""; position:absolute; inset:0;
  background:radial-gradient(circle at 80% 20%, rgba(255,255,255,0.15) 0%, transparent 60%);
}
.hero-text { position:relative; z-index:1; }
.hero-text h1 { font-size:22px; margin-bottom:4px; }
.hero-text p { font-size:14px; opacity:.85; margin-bottom:14px; }
.hero-text :deep(.el-button--primary) { background:#fff; color:var(--accent-primary); border:none; font-weight:600; }
.hero-stats { display:flex; gap:16px; position:relative; z-index:1; }
.stat-card { text-align:center; padding:8px 20px; background:rgba(255,255,255,0.12); border-radius:12px; }
.stat-num { display:block; font-size:24px; font-weight:700; }
.stat-label { font-size:12px; opacity:.8; }

.charts-row { display:flex; gap:16px; margin-bottom:20px; }
.chart-card { flex:1; min-width:0; background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:var(--radius-lg); padding:18px; box-shadow:var(--shadow-xs); }
.chart-header { font-size:14px; font-weight:600; margin-bottom:8px; }
.chart-body { height:220px; }
.curve-section { margin-bottom:20px; }
.section-title { display:flex; justify-content:space-between; align-items:center; font-size:16px; font-weight:600; margin-bottom:12px; }
.today-section { margin-bottom:20px; }.today-list { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }.today-task { display:flex; align-items:center; gap:9px; min-width:0; padding:13px; color:var(--text-primary); text-align:left; border:1px solid var(--border-color); border-radius:var(--radius-md); background:var(--bg-secondary); cursor:pointer; transition:.2s; }.today-task:hover { border-color:var(--accent-primary); transform:translateY(-1px); }.task-check { width:16px; height:16px; flex:0 0 16px; border:2px solid var(--accent-primary); border-radius:50%; }.today-task span:nth-child(2) { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:13px; }.today-task small { margin-left:auto; color:var(--text-tertiary); font-size:11px; }
.cat-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:10px; }
.cat-card {
  background:var(--bg-secondary); border:1px solid var(--border-color);
  border-radius:var(--radius-lg); padding:14px; text-align:center;
  cursor:pointer; transition:all 0.25s;
}
.cat-card:hover { transform:translateY(-3px); box-shadow:var(--shadow-md); border-color:var(--accent-primary); }
.cat-icon { width:40px; height:40px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:20px; margin:0 auto 8px; }
.cat-name { font-size:13px; font-weight:600; }
.cat-count { font-size:11px; color:var(--text-tertiary); }
.skeleton-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }
.skeleton-grid div { height:270px; border-radius:var(--radius-lg); background:linear-gradient(100deg,var(--bg-secondary) 20%,var(--bg-hover) 40%,var(--bg-secondary) 60%); background-size:220% 100%; animation:shimmer 1.35s infinite linear; }
.empty-state { padding:54px 24px; margin-bottom:20px; text-align:center; border:1px dashed var(--border-color); border-radius:var(--radius-xl); background:var(--bg-secondary); }
.empty-icon { width:48px; height:48px; margin:0 auto 14px; display:grid; place-items:center; border-radius:14px; color:var(--accent-primary); background:var(--bg-tertiary); font-size:28px; }
.empty-state h3 { font-size:17px; margin-bottom:5px; }
.empty-state p { color:var(--text-secondary); font-size:13px; margin-bottom:18px; }
@keyframes shimmer { to { background-position:-220% 0; } }
@media (max-width:760px) {
  .hero-section { align-items:flex-start; padding:24px; }
  .hero-stats { display:none; }
  .hero-text h1 { font-size:20px; }
  .charts-row, .skeleton-grid { grid-template-columns:1fr; display:grid; }
  .chart-body { height:240px; }
  .cat-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.today-list { grid-template-columns:1fr; }
}
@media (prefers-reduced-motion:reduce) { .skeleton-grid div { animation:none; } }
</style>
