<template>
  <AppLayout>
    <section class="diagnosis-page" v-loading="loading">
      <header class="page-header"><div><p class="eyebrow">LEARNING CHECK-IN</p><h3>学情诊断</h3><p>用一次简短自评更新学习状态；诊断结果会同步到学习路径和报告。</p></div><el-button @click="loadData">刷新诊断</el-button></header>
      <div class="score-grid"><article><strong>{{ overallMastery }}%</strong><span>平均掌握度</span></article><article><strong>{{ errorTotal }}</strong><span>错误记录</span></article><article><strong>{{ activeKps }}</strong><span>已评估知识点</span></article></div>
      <div class="workspace"><article class="diagnosis-card"><div class="card-title">更新一个知识点的掌握度</div><p class="help">根据最近一次学习或练习的真实感受选择掌握程度；后续可以随学习进展重新更新。</p><el-form label-position="top"><el-form-item label="知识点"><el-select v-model="form.kp_id" filterable placeholder="选择知识点"><el-option v-for="kp in knowledgePoints" :key="kp.id" :label="kp.name" :value="kp.id" /></el-select></el-form-item><el-form-item label="当前掌握度"><el-slider v-model="form.level" :step="10" :format-tooltip="value => `${value}%`" :marks="{0:'陌生',50:'了解',80:'熟练'}" /></el-form-item><el-form-item label="是否出现典型错误（可选）"><el-input v-model="form.error_type" placeholder="例如：循环边界判断错误" /></el-form-item><el-button type="primary" :loading="saving" @click="saveAssessment">保存诊断结果</el-button></el-form></article><article class="diagnosis-card"><div class="card-title">诊断建议</div><div class="suggestion"><span>1</span><p>{{ suggestionOne }}</p></div><div class="suggestion"><span>2</span><p>{{ suggestionTwo }}</p></div><div class="suggestion"><span>3</span><p>{{ suggestionThree }}</p></div><el-button text type="primary" @click="$router.push(nextRoute)">{{ nextAction }} →</el-button></article></div>
      <article v-if="masteryRows.length" class="diagnosis-card progress-card"><div class="card-title">掌握度记录</div><div v-for="row in rankedMastery" :key="row.id" class="mastery-row"><span>{{ kpName(row.kp_id) }}</span><el-progress :percentage="Math.round(row.level * 100)" :stroke-width="7" /><small>{{ Math.round(row.level * 100) }}%</small></div></article>
    </section>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import AppLayout from "../components/AppLayout.vue"
import { apiGet, apiPost } from "../utils/api"
import { ensureLearner } from "../utils/learner"

const loading=ref(false),saving=ref(false),learner=ref(null),knowledgePoints=ref([]),masteryRows=ref([]),errors=ref([])
const form=ref({kp_id:"",level:50,error_type:""})
const overallMastery=computed(()=>masteryRows.value.length?Math.round(masteryRows.value.reduce((sum,row)=>sum+Number(row.level||0),0)/masteryRows.value.length*100):0)
const errorTotal=computed(()=>errors.value.reduce((sum,row)=>sum+Number(row.count||0),0)); const activeKps=computed(()=>masteryRows.value.length); const rankedMastery=computed(()=>[...masteryRows.value].sort((a,b)=>a.level-b.level)); const weakest=computed(()=>rankedMastery.value[0])
const kpName=id=>knowledgePoints.value.find(k=>k.id===id)?.name||id
const suggestionOne=computed(()=>weakest.value?`优先复习“${kpName(weakest.value.kp_id)}”，当前掌握度为 ${Math.round(weakest.value.level*100)}%。` : "先完成一次知识点自评，建立你的第一条学习基线。")
const suggestionTwo=computed(()=>errorTotal.value?`你有 ${errorTotal.value} 次错误记录，建议先到错题薄弱项中针对性练习。` : "学习时遇到典型错误，可以在本页记录，方便下次集中复习。")
const suggestionThree=computed(()=>overallMastery.value>=80?"整体掌握良好，可以开始挑战综合练习或更高难度内容。":"每次学习后花 1 分钟更新一次掌握度，报告会逐步更准确。")
const nextRoute=computed(()=>errorTotal.value?"/mistakes":"/tasks"),nextAction=computed(()=>errorTotal.value?"处理薄弱项":"安排下一次学习")
async function loadData(){loading.value=true;try{learner.value ||= await ensureLearner();const [kps,mastery,errorData]=await Promise.all([apiGet("/learning/knowledge-points"),apiGet(`/learning/learners/${learner.value.id}/mastery`),apiGet(`/learning/learners/${learner.value.id}/errors`)]);knowledgePoints.value=kps||[];masteryRows.value=mastery.data||[];errors.value=errorData.data||[]}catch(error){ElMessage.error(error.message||"诊断数据加载失败")}finally{loading.value=false}}
async function saveAssessment(){if(!form.value.kp_id)return ElMessage.warning("请选择一个知识点");saving.value=true;try{await apiPost(`/learning/learners/${learner.value.id}/mastery`,{kp_id:form.value.kp_id,level:form.value.level/100,confidence:.8});if(form.value.error_type.trim())await apiPost(`/learning/learners/${learner.value.id}/errors`,{kp_id:form.value.kp_id,error_type:form.value.error_type.trim()});form.value={kp_id:"",level:50,error_type:""};await loadData();ElMessage.success("诊断结果已更新")}catch(error){ElMessage.error(error.message||"保存失败")}finally{saving.value=false}}
onMounted(loadData)
</script>

<style scoped>
.diagnosis-page { max-width:1000px;margin:0 auto }.page-header { display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:20px }.eyebrow{margin:0 0 4px;color:var(--accent-primary);font-size:11px;font-weight:700;letter-spacing:1.2px}.page-header h3{margin:0 0 6px;font-size:22px}.page-header p:not(.eyebrow){margin:0;color:var(--text-secondary);font-size:14px}.score-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}.score-grid article,.diagnosis-card{border:1px solid var(--border-color);border-radius:var(--radius-lg);background:var(--bg-secondary)}.score-grid article{padding:17px}.score-grid strong{display:block;font-size:27px}.score-grid span{color:var(--text-tertiary);font-size:12px}.workspace{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-bottom:16px}.diagnosis-card{padding:19px}.card-title{font-size:15px;font-weight:650;margin-bottom:12px}.help{margin:-3px 0 16px;color:var(--text-secondary);font-size:13px;line-height:1.55}.suggestion{display:flex;gap:10px;margin-bottom:13px}.suggestion span{width:23px;height:23px;display:grid;place-items:center;flex:0 0 23px;border-radius:50%;background:var(--bg-tertiary);color:var(--accent-primary);font-size:12px;font-weight:700}.suggestion p{margin:2px 0 0;color:var(--text-secondary);font-size:13px;line-height:1.55}.progress-card{margin-bottom:16px}.mastery-row{display:grid;grid-template-columns:minmax(105px,1fr) 2fr 40px;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border-color);font-size:13px}.mastery-row:last-child{border:0}.mastery-row small{color:var(--text-tertiary);text-align:right}@media(max-width:700px){.page-header{flex-direction:column}.workspace{grid-template-columns:1fr}.score-grid{gap:8px}.score-grid article{padding:14px}.mastery-row{grid-template-columns:90px 1fr 36px;gap:8px}}
</style>
