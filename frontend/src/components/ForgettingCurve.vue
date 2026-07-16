<template>
  <div class="forgetting-curve">
    <div class="fc-header">
      <h4>艾宾浩斯遗忘曲线</h4>
      <div class="fc-controls">
        <el-select v-model="timeRange" size="small" style="width:100px" @change="fetchData">
          <el-option label="7天" :value="168" />
          <el-option label="30天" :value="720" />
          <el-option label="60天" :value="1440" />
        </el-select>
      </div>
    </div>

    <div v-if="hasData" class="curve-chart" ref="chartRef" style="height:240px"></div>
    <div v-else class="curve-empty">
      <strong>暂无复习趋势</strong>
      <span>{{ emptyMessage }}</span>
    </div>
    
    <div v-if="optimalReviews.length" class="review-schedule">
      <h5>最佳复习时间</h5>
      <div class="review-timeline">
        <div v-for="(r, i) in optimalReviews" :key="i" class="review-point" :class="{ completed: r.completed }">
          <div class="review-dot" :class="{ active: !r.completed }"></div>
          <div class="review-info">
            <span class="review-interval">{{ r.interval_label }}</span>
            <span class="review-retention">保留率 {{ (r.retention_at_review * 100).toFixed(0) }}%</span>
            <span v-if="r.completed" class="review-status">已完成</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from "vue"
import * as echarts from "echarts"
import { apiGet } from "../utils/api"
import { useTheme } from "../composables/useTheme"

const props = defineProps({
  timeRange: { type: Number, default: 720 },
})

const chartRef = ref(null)
const timeRange = ref(props.timeRange)
const curveData = ref([])
const optimalReviews = ref([])
const hasData = ref(false)
const emptyMessage = ref("开始学习后，这里会根据你的真实学习记录生成复习趋势。")
let chart = null
let resizeObserver = null
const { isDark } = useTheme()

function formatHour(h) {
  if (h < 24) return `${h}h`
  if (h < 168) return `${h}h`
  return `${Math.round(h / 24)}d`
}

async function fetchData() {
  try {
    const data = await apiGet(`/learning/forgetting-curve?hours=${timeRange.value}`)
    curveData.value = data?.curve || []
    optimalReviews.value = data?.optimal_reviews || []
    hasData.value = Boolean(data?.has_data && curveData.value.length)
    emptyMessage.value = data?.message || emptyMessage.value
    await nextTick()
    if (hasData.value) renderChart()
    else {
      chart?.dispose()
      chart = null
      resizeObserver?.disconnect()
      resizeObserver = null
    }
  } catch {}
}

function renderChart() {
  if (!chartRef.value || !curveData.value.length) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  
  const times = curveData.value.map(d => formatHour(d.hour))
  const retentions = curveData.value.map(d => (d.retention * 100).toFixed(1))
  
  // Find 50% threshold point
  const halfLifeIdx = curveData.value.findIndex(d => d.retention <= 0.5)
  const halfLifeX = halfLifeIdx >= 0 ? formatHour(curveData.value[halfLifeIdx].hour) : null
  
  const text = isDark.value ? "#a6b2c5" : "#5c677d"
  const gridColor = isDark.value ? "#24324a" : "#dfe6ef"
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: "category",
      data: times,
      axisLine: { lineStyle: { color: gridColor } },
      axisLabel: { color: text, fontSize: 10, rotate: 45, interval: "auto" },
      name: "时间",
      nameTextStyle: { color: text, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: gridColor, type: "dashed" } },
      axisLabel: { color: text, fontSize: 10, formatter: "{value}%" },
      name: "保留率",
      nameTextStyle: { color: text, fontSize: 10 },
    },
    series: [
      {
        type: "line",
        data: retentions,
        smooth: true,
        lineStyle: { width: 2, color: "#6366f1" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(99,102,241,0.3)" },
            { offset: 1, color: "rgba(99,102,241,0.02)" },
          ]),
        },
        itemStyle: { color: "#6366f1" },
        markLine: halfLifeX ? {
          data: [
            { xAxis: halfLifeX, label: { formatter: `半衰期 ${halfLifeX}`, fontSize: 10 }, lineStyle: { type: "dashed", color: "#ef4444" } },
            { yAxis: 50, label: { formatter: "50% 阈值", fontSize: 10 }, lineStyle: { type: "dashed", color: "#f59e0b" } },
          ],
        } : {},
        markPoint: {
          data: optimalReviews.value.slice(0, 3).map(r => ({
            coord: [formatHour(r.interval_hours), (r.retention_at_review * 100).toFixed(1)],
            symbol: "circle",
            symbolSize: 10,
            itemStyle: { color: "#10b981" },
            label: { formatter: `复习\n${(r.retention_at_review * 100).toFixed(0)}%`, fontSize: 9 },
          })),
        },
      },
    ],
    tooltip: {
      trigger: "axis",
      backgroundColor: isDark.value ? "#18243a" : "#ffffff",
      borderColor: gridColor,
      textStyle: { color: isDark.value ? "#edf3fc" : "#172033" },
      formatter: (params) => {
        const p = params[0]
        const hour = curveData.value[p.dataIndex]?.hour
        if (hour !== undefined) {
          const days = Math.floor(hour / 24)
          const hrs = hour % 24
          const timeStr = days > 0 ? `${days}天${hrs}小时` : `${hrs}小时`
          return `<b>${timeStr}</b><br/>保留率: <b>${p.value}%</b>`
        }
        return ""
      },
    },
  }, true)
  
  // Resize observer
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartRef.value)
  }
}

onMounted(() => nextTick(fetchData))
watch(isDark, () => renderChart())
onUnmounted(() => { resizeObserver?.disconnect(); chart?.dispose(); chart = null })
</script>

<style scoped>
.forgetting-curve { background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:12px; padding:16px; }
.fc-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
.fc-header h4 { font-size:15px; font-weight:600; margin:0; }
.fc-controls { display:flex; gap:8px; }
.curve-chart { width:100%; }
.curve-empty { height:240px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; color:var(--text-secondary); border:1px dashed var(--border-color); border-radius:10px; background:var(--bg-tertiary); text-align:center; padding:18px; }
.curve-empty strong { color:var(--text-primary); font-size:14px; }
.curve-empty span { max-width:360px; font-size:12px; line-height:1.6; }
.review-schedule { margin-top:16px; border-top:1px solid var(--border-color); padding-top:12px; }
.review-schedule h5 { font-size:13px; margin-bottom:8px; color:var(--text-secondary); }
.review-timeline { display:flex; gap:12px; overflow-x:auto; }
.review-point { display:flex; align-items:flex-start; gap:8px; min-width:100px; }
.review-dot { width:10px; height:10px; border-radius:50%; background:var(--border-color); margin-top:4px; flex-shrink:0; }
.review-dot.active { background:var(--success); box-shadow:0 0 6px rgba(16,185,129,0.4); }
.review-info { display:flex; flex-direction:column; }
.review-interval { font-size:13px; font-weight:600; }
.review-retention { font-size:11px; color:var(--text-tertiary); }
.review-status { font-size:10px; color:var(--success); }
</style>
