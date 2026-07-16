<template>
  <AppLayout>
    <div class="diag-page">
      <div class="page-header">
        <h3>📊 学情诊断</h3>
        <p class="page-desc">分析你的学习情况，发现知识薄弱点</p>
      </div>
      <div class="diag-card">
        <div class="diag-hd">
          <span>诊断报告</span>
          <el-button type="primary" @click="runDiag" :loading="running" round>{{ running?"诊断中...":"开始诊断" }}</el-button>
        </div>
        <div v-if="!result" class="empty">
          <div class="empty-icon">🔍</div>
          <p>点击上方按钮开始诊断</p>
        </div>
        <div v-else>
          <div class="diag-stats">
            <div class="ds-card"><span class="ds-num">{{ Math.round(result.mastery*100) }}%</span><span class="ds-label">掌握度</span><div class="ds-bar"><div class="ds-fill" :style="{width:(result.mastery*100)+'%'}"></div></div></div>
            <div class="ds-card"><span class="ds-num">{{ result.errorCount||0 }}</span><span class="ds-label">错误类型</span></div>
            <div class="ds-card"><span class="ds-num">{{ result.cognitiveLoad||"低" }}</span><span class="ds-label">认知负荷</span></div>
          </div>
          <div v-if="result.suggestions?.length" class="diag-suggest">
            <div class="suggest-title">💡 建议</div>
            <div v-for="s in result.suggestions" :key="s" class="suggest-item">{{ s }}</div>
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>
<script setup>
import { ref } from "vue"
import AppLayout from "../components/AppLayout.vue"
import { apiGet, apiPost } from "../utils/api"
const running = ref(false); const result = ref(null)
async function runDiag() {
  running.value = true
  try {
    const users = await apiGet("/learning/learners"); let l = users?.[0]
    if (!l) l = await apiPost("/learning/learners",{name:"default"})
    const m = await apiPost("/learning/learners/"+l.id+"/mastery",{})
    const e = await apiPost("/learning/learners/"+l.id+"/errors",{})
    result.value = { mastery:m?.mastery||0.5, errorCount:(e||[]).length, cognitiveLoad:"低", suggestions:["建议每天学习 1-2 个新知识点","加强复习已学内容"] }
  } catch { result.value = { mastery:0.5, errorCount:0, cognitiveLoad:"低", suggestions:["诊断数据暂不可用"] } }
  running.value = false
}
</script>
<style scoped>
.diag-page { max-width:700px; margin:0 auto; }
.page-header { margin-bottom:24px; }
.page-header h3 { font-size:20px; font-weight:600; margin-bottom:4px; }
.page-desc { font-size:14px; color:var(--text-secondary); margin:0; }
.diag-card { background:var(--bg-secondary); border:1px solid var(--border-color); border-radius:var(--radius-xl); padding:24px; }
.diag-hd { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; font-size:16px; font-weight:600; }
.empty { text-align:center; padding:60px 0; color:var(--text-secondary); }
.empty-icon { font-size:40px; margin-bottom:8px; }
.diag-stats { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:20px; }
.ds-card { background:var(--bg-tertiary); border-radius:12px; padding:16px; text-align:center; }
.ds-num { display:block; font-size:24px; font-weight:700; color:var(--accent-primary); margin-bottom:4px; }
.ds-label { font-size:12px; color:var(--text-tertiary); }
.ds-bar { height:4px; background:var(--border-color); border-radius:2px; margin-top:8px; overflow:hidden; }
.ds-fill { height:100%; background:var(--accent-gradient); border-radius:2px; transition:width 1s ease; }
.diag-suggest { background:var(--bg-tertiary); border-radius:12px; padding:16px; }
.suggest-title { font-size:14px; font-weight:600; margin-bottom:8px; }
.suggest-item { font-size:13px; padding:6px 0; color:var(--text-secondary); border-bottom:1px solid var(--border-color); }
.suggest-item:last-child { border-bottom:none; }
</style>
