<template>
  <AppLayout>
    <div class="reports-page">
      <div class="page-header">
        <h3>📈 学习报告</h3>
        <p class="page-desc">查看你的学习进度与知识覆盖统计</p>
      </div>
      <div v-if="!hasData" class="empty-state">
        <div class="empty-icon">📊</div>
        <p>暂无学习数据，先去学点东西吧</p>
      </div>
      <div v-else class="reports-grid">
        <div class="r-card">
          <div class="r-card-header">📊 掌握度分布</div>
          <div class="chart-placeholder">图表区域</div>
        </div>
        <div class="r-card">
          <div class="r-card-header">📅 学习时间线</div>
          <div class="chart-placeholder">图表区域</div>
        </div>
        <div class="r-card full">
          <div class="r-card-header">📚 知识覆盖统计</div>
          <div class="chart-placeholder big">图表区域</div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
<script setup>
import { ref, onMounted } from "vue"
import AppLayout from "../components/AppLayout.vue"
import { apiGet } from "../utils/api"
const hasData = ref(false)
onMounted(async () => { try { const kps = await apiGet("/learning/knowledge-points"); if (kps?.length) hasData.value = true } catch {} })
</script>
<style scoped>
.reports-page { max-width:1000px; margin:0 auto; }
.page-header { margin-bottom:24px; }
.page-header h3 { font-size:20px; font-weight:600; margin-bottom:4px; }
.page-desc { font-size:14px; color:var(--text-secondary); margin:0; }
.empty-state { text-align:center; padding:80px 0; }
.empty-icon { font-size:48px; margin-bottom:12px; }
.empty-state p { color:var(--text-secondary); font-size:15px; }
.reports-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.r-card { background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:var(--radius-lg); padding:20px; }
.r-card.full { grid-column:1/-1; }
.r-card-header { font-size:14px; font-weight:600; margin-bottom:12px; }
.chart-placeholder { height:180px; background:var(--bg-tertiary); border-radius:var(--radius-md); display:flex; align-items:center; justify-content:center; color:var(--text-tertiary); font-size:13px; }
.chart-placeholder.big { height:250px; }
</style>
