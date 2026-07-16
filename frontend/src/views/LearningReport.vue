<template>
  <AppLayout>
    <section class="report-page" v-loading="loading">
      <header class="page-header"><div><p class="eyebrow">LEARNING INSIGHTS</p><h3>学习报告</h3><p>基于你的任务、学习记录和薄弱项，持续追踪这一阶段的学习效果。</p></div><el-button @click="loadReport">刷新数据</el-button></header>
      <div class="metric-grid"><article class="metric"><span>任务完成率</span><strong>{{ taskRate }}%</strong><small>{{ doneTasks }}/{{ totalTasks }} 个任务已完成</small></article><article class="metric"><span>已学习知识点</span><strong>{{ masteredCount }}</strong><small>累计记录 {{ studyEvents.length }} 次学习</small></article><article class="metric"><span>平均掌握度</span><strong>{{ averageMastery }}%</strong><small>{{ masteryRows.length }} 个已评估知识点</small></article><article class="metric"><span>待复习薄弱项</span><strong>{{ errorTotal }}</strong><small>{{ errors.length }} 类错误需要关注</small></article></div>
      <div class="chart-grid"><article class="report-card"><div class="card-title">任务完成情况</div><div ref="taskChart" class="chart"></div></article><article class="report-card"><div class="card-title">近 7 天学习活跃度</div><div ref="activityChart" class="chart"></div></article></div>
      <article class="report-card action-card"><div><div class="card-title">下一步建议</div><p>{{ recommendation }}</p></div><el-button type="primary" @click="$router.push(nextRoute)">{{ nextAction }}</el-button></article>
      <article v-if="weaknesses.length" class="report-card"><div class="card-title">优先复习的薄弱项</div><div class="weakness-list"><button v-for="item in weaknesses" :key="item.id" @click="$router.push('/mistakes')"><span class="rank">{{ item.count }}</span><span><strong>{{ item.error_type }}</strong><small>{{ item.kp_id ? `关联知识点：${kpName(item.kp_id)}` : '建议补充关联知识点' }}</small></span><span>去复习 →</span></button></div></article>
      <el-empty v-if="!loading && !totalTasks && !studyEvents.length && !errors.length" description="还没有足够的学习数据，完成任务或记录错题后就能看到报告。"><el-button type="primary" @click="$router.push('/tasks')">创建学习任务</el-button></el-empty>
    </section>
  </AppLayout>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue"
import * as echarts from "echarts"
import AppLayout from "../components/AppLayout.vue"
import { apiGet } from "../utils/api"
import { ElMessage } from "element-plus"
import { ensureLearner } from "../utils/learner"
import { useTheme } from "../composables/useTheme"

const loading = ref(false), learner = ref(null), tasks = ref([]), studyEvents = ref([]), errors = ref([]), masteryRows = ref([]), knowledgePoints = ref([])
const taskChart = ref(null), activityChart = ref(null); let taskInstance, activityInstance
const { isDark } = useTheme()
const totalTasks = computed(() => tasks.value.length), doneTasks = computed(() => tasks.value.filter(t => t.status === "done").length)
const taskRate = computed(() => totalTasks.value ? Math.round(doneTasks.value / totalTasks.value * 100) : 0)
const masteredCount = computed(() => masteryRows.value.filter(row => row.level >= .6).length)
const averageMastery = computed(() => masteryRows.value.length ? Math.round(masteryRows.value.reduce((sum,row) => sum + Number(row.level || 0), 0) / masteryRows.value.length * 100) : 0)
const errorTotal = computed(() => errors.value.reduce((sum,row) => sum + Number(row.count || 0), 0))
const weaknesses = computed(() => [...errors.value].sort((a,b) => b.count - a.count).slice(0,4))
const recommendation = computed(() => errorTotal.value ? `先处理“${weaknesses.value[0]?.error_type}”等 ${errors.value.length} 类薄弱项，再完成待办任务，学习效果会更稳定。` : totalTasks.value && taskRate.value < 100 ? `还有 ${totalTasks.value - doneTasks.value} 个待办任务，建议从截止时间最近的一项开始。` : "继续保持学习节奏；完成一次练习或记录一个知识点，就能获得更准确的建议。")
const nextRoute = computed(() => errorTotal.value ? "/mistakes" : "/tasks"), nextAction = computed(() => errorTotal.value ? "复习薄弱项" : "查看学习任务")
const kpName = id => knowledgePoints.value.find(k => k.id === id)?.name || id

function dayLabels() { const days=[]; for(let i=6;i>=0;i--) { const d=new Date(); d.setDate(d.getDate()-i); days.push({ key:d.toISOString().slice(0,10), label:`${d.getMonth()+1}/${d.getDate()}` }) } return days }
function renderCharts() { if (!taskChart.value || !activityChart.value) return; const text=isDark.value?"#a6b2c5":"#5c677d", grid=isDark.value?"#24324a":"#dfe6ef"; taskInstance ||= echarts.init(taskChart.value); activityInstance ||= echarts.init(activityChart.value); taskInstance.setOption({ tooltip:{trigger:"item"}, series:[{ type:"pie", radius:["55%","75%"], label:{color:text,formatter:"{b} {d}%"}, data:[{name:"已完成",value:doneTasks.value,itemStyle:{color:"#22c55e"}},{name:"待完成",value:Math.max(totalTasks.value-doneTasks.value,0),itemStyle:{color:"#6366f1"}}] }] },true); const days=dayLabels(); const counts=days.map(day=>studyEvents.value.filter(event=>event.studied_at?.slice(0,10)===day.key).length); activityInstance.setOption({ tooltip:{trigger:"axis"}, grid:{left:35,right:16,top:24,bottom:28}, xAxis:{type:"category",data:days.map(d=>d.label),axisLabel:{color:text},axisLine:{lineStyle:{color:grid}}}, yAxis:{type:"value",minInterval:1,axisLabel:{color:text},splitLine:{lineStyle:{color:grid,type:"dashed"}}}, series:[{type:"bar",data:counts,itemStyle:{color:"#6366f1",borderRadius:[5,5,0,0]},barWidth:"42%"}] },true) }
async function loadReport() { loading.value=true; try { learner.value ||= await ensureLearner(); const [taskData,eventData,errorData,masteryData,kpData] = await Promise.all([apiGet("/learning/tasks"),apiGet("/learning/study-events"),apiGet(`/learning/learners/${learner.value.id}/errors`),apiGet(`/learning/learners/${learner.value.id}/mastery`),apiGet("/learning/knowledge-points")]); tasks.value=taskData||[]; studyEvents.value=eventData||[]; errors.value=errorData.data||[]; masteryRows.value=masteryData.data||[]; knowledgePoints.value=kpData||[] } catch (error) { ElMessage.error(error.message || "报告数据加载失败") } finally { loading.value=false; await nextTick(); renderCharts() } }
const resize = () => { taskInstance?.resize(); activityInstance?.resize() }
onMounted(async()=>{ await loadReport(); window.addEventListener("resize",resize) }); onUnmounted(()=>{window.removeEventListener("resize",resize);taskInstance?.dispose();activityInstance?.dispose()})
</script>

<style scoped>
.report-page { max-width:1100px; margin:0 auto }.page-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:20px }.eyebrow { margin:0 0 4px; color:var(--accent-primary); font-size:11px; font-weight:700; letter-spacing:1.2px }.page-header h3 { margin:0 0 6px; font-size:22px }.page-header p:not(.eyebrow) { margin:0; color:var(--text-secondary); font-size:14px }.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px }.metric,.report-card { border:1px solid var(--border-color); border-radius:var(--radius-lg); background:var(--bg-secondary) }.metric { padding:17px }.metric span,.metric small { display:block; color:var(--text-tertiary); font-size:12px }.metric strong { display:block; margin:7px 0; color:var(--text-primary); font-size:27px }.chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px }.report-card { padding:18px }.card-title { font-size:15px; font-weight:650 }.chart { height:240px }.action-card { display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:16px }.action-card p { margin:8px 0 0; color:var(--text-secondary); font-size:13px; line-height:1.55 }.weakness-list { margin-top:10px }.weakness-list button { width:100%; display:flex; align-items:center; gap:12px; padding:12px 0; color:var(--text-primary); text-align:left; border:0; border-bottom:1px solid var(--border-color); background:transparent; cursor:pointer }.weakness-list button:last-child { border:0 }.rank { width:30px; height:30px; display:grid; flex:0 0 30px; place-items:center; color:#b45309; border-radius:9px; background:#fef3c7; font-weight:700; font-size:13px }.weakness-list button div,.weakness-list button span:nth-child(2) { flex:1 }.weakness-list strong,.weakness-list small { display:block }.weakness-list small { margin-top:3px; color:var(--text-tertiary); font-size:12px }.weakness-list button > span:last-child { color:var(--accent-primary); font-size:12px } @media(max-width:760px){.page-header{flex-direction:column}.metric-grid{grid-template-columns:1fr 1fr}.chart-grid{grid-template-columns:1fr}.action-card{align-items:flex-start;flex-direction:column}.chart{height:220px}} 
</style>
