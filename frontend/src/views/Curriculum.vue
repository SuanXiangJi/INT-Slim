<template>
  <AppLayout>
    <main class="curriculum" v-loading="loading">
      <header class="hero">
        <div><el-button text @click="$router.push('/courses')">返回学习入口</el-button><p class="eyebrow">COURSE ROADMAP</p><h1>{{ course.title }}</h1><p>按章节逐步学习。通过本章测验后，下一章才会解锁。</p></div>
        <div class="stat"><strong>{{ completedCount }}</strong><span>/ {{ course.chapters.length }} 已完成</span></div>
      </header>

      <section class="chapter-grid">
        <article v-for="chapter in course.chapters" :key="chapter.doc_id" :class="['chapter-card',{locked:!chapter.unlocked,done:chapter.completed}]">
          <div class="chapter-top"><span class="index">{{ chapter.completed ? '✓' : chapter.index }}</span><span class="state">{{ labelFor(chapter) }}</span></div>
          <h2>{{ chapter.title }}</h2>
          <p>{{ chapter.completed ? '本章已通过，可以进入实训或继续下一章。' : chapter.unlocked ? `预计 ${chapter.estimated_minutes} 分钟，完成阅读后开始测验。` : '通过上一章测验后解锁。' }}</p>
          <el-button v-if="chapter.unlocked" :type="chapter.completed ? 'default' : 'primary'" @click="openReader(chapter)">{{ chapter.completed ? '回顾本章' : chapter.status === 'ready_for_quiz' ? '继续本章' : '开始学习' }}</el-button>
          <el-button v-else disabled>暂未解锁</el-button>
        </article>
      </section>

      <section v-if="course.all_passed" class="final"><div><p class="eyebrow">FINAL EXAM</p><h2>课程章节已全部完成</h2><p>现在可以进行学科考试，完成后获得完整学习记录。</p></div><el-button type="primary" :loading="finalLoading" @click="startFinal">开始学科考试</el-button></section>
      <el-dialog v-model="generating" width="min(92vw,520px)" :close-on-click-modal="false" :show-close="false"><GenerationSteps :active-step="activeStep" :done="generationDone" /></el-dialog>
    </main>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import GenerationSteps from '../components/GenerationSteps.vue'
import { apiGet, apiPost } from '../utils/api'

const route=useRoute(), router=useRouter(), key=route.params.courseKey
const loading=ref(false), finalLoading=ref(false), generating=ref(false), activeStep=ref(0), generationDone=ref(false)
const course=ref({title:'',chapters:[],all_passed:false})
const completedCount=computed(()=>course.value.chapters.filter(chapter=>chapter.completed).length)
function labelFor(chapter){return chapter.completed?'已通过':!chapter.unlocked?'未解锁':chapter.status==='ready_for_quiz'?'待测验':'可学习'}
function openReader(chapter){router.push(`/courses/${key}/read/${chapter.doc_id}`)}
async function loadCourse(){loading.value=true;try{course.value=await apiGet(`/learning/curriculum/${key}/chapters`)}catch(error){ElMessage.error(error.message||'课程加载失败')}finally{loading.value=false}}
async function startFinal(){finalLoading.value=true;generating.value=true;generationDone.value=false;activeStep.value=0;const timer=setInterval(()=>{if(activeStep.value<3)activeStep.value++},750);try{const data=await apiPost(`/learning/curriculum/${key}/final-exam`,{});generationDone.value=true;activeStep.value=3;setTimeout(()=>router.push(`/assessments/${data.assessment.id}`),380)}catch(error){ElMessage.error(error.message||'学科考试暂不可开始');generating.value=false}finally{clearInterval(timer);finalLoading.value=false}}
onMounted(loadCourse)
</script>

<style scoped>
.curriculum{max-width:1180px;margin:0 auto}.hero{display:flex;align-items:end;justify-content:space-between;gap:24px;margin-bottom:26px;padding:22px 0}.eyebrow{margin:0;color:var(--accent-primary);font-size:11px;font-weight:800;letter-spacing:1.15px}.hero h1{margin:5px 0;font-size:30px;letter-spacing:-.6px}.hero p:not(.eyebrow),.final p{margin:0;color:var(--text-secondary);line-height:1.65}.stat{padding:14px 18px;border:1px solid var(--border-color);border-radius:14px;white-space:nowrap}.stat strong{font-size:24px;color:var(--accent-primary)}.stat span{font-size:13px;color:var(--text-secondary)}.chapter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.chapter-card,.final{border:1px solid var(--border-color);border-radius:16px;background:var(--surface-card)}.chapter-card{display:flex;min-height:205px;flex-direction:column;padding:20px}.chapter-card.locked{opacity:.54;background:var(--bg-secondary)}.chapter-card.done .index{background:#eaf8ef;color:#278049;border-color:#a3d8b4}.chapter-top{display:flex;justify-content:space-between;align-items:center}.index{display:grid;place-items:center;width:29px;height:29px;border:1px solid var(--border-color);border-radius:50%;font-size:12px;font-weight:800}.state{font-size:12px;color:var(--text-tertiary)}.chapter-card h2{margin:18px 0 8px;font-size:17px;line-height:1.45}.chapter-card p{margin:0 0 18px;color:var(--text-secondary);font-size:13px;line-height:1.65}.chapter-card .el-button{margin-top:auto;align-self:flex-start}.final{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:18px;padding:23px}.final h2{margin:5px 0;font-size:19px}@media(max-width:900px){.chapter-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.hero,.final{align-items:start;flex-direction:column}.chapter-grid{grid-template-columns:1fr}}
</style>
