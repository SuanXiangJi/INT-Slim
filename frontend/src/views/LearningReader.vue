<template>
  <AppLayout>
    <main class="reader-page" v-loading="loading">
      <header class="reader-head"><div><el-button text @click="router.push(`/courses/${key}`)">返回课程目录</el-button><p class="eyebrow">{{ courseTitle }}</p><h1>{{ chapter.title }}</h1><p>第 {{ chapter.index }} 章 · 预计 {{ chapter.estimated_minutes }} 分钟</p></div><el-button v-if="chapter.completed" @click="router.push({path:'/code-practice',query:{chapter:chapter.doc_id}})">本章代码实训</el-button></header>
      <article class="reading-surface"><MarkdownRenderer :content="content"/><footer class="reading-actions"><div><strong>{{ statusCopy }}</strong><small v-if="chapter.status==='ready_for_quiz'">本章阅读已完成，测验将在独立页面进行。</small></div><el-button v-if="chapter.status==='reading'||chapter.status==='not_started'" type="primary" :loading="reading" @click="completeReading">完成阅读</el-button><el-button v-else-if="chapter.status==='ready_for_quiz'" type="primary" :loading="quizLoading" @click="startQuiz">进入本章测验</el-button><el-button v-else @click="router.push({path:'/code-practice',query:{chapter:chapter.doc_id}})">进入代码实训</el-button></footer></article>
      <button class="assist-toggle" @click="assistOpen=!assistOpen">{{ assistOpen ? '收起伴学' : '伴学提问' }}</button><aside v-if="assistOpen" class="assist"><strong>本章伴学</strong><p>有不理解的地方可以直接提问，问题会在 Agents 伴学中继续处理。</p><el-input v-model="question" type="textarea" :rows="4" placeholder="例如：这一节的核心概念是什么？"/><el-button type="primary" :disabled="!question.trim()" @click="ask">发送给伴学 Agent</el-button></aside>
      <el-dialog v-model="generating" width="min(92vw,520px)" :close-on-click-modal="false" :show-close="false"><GenerationSteps :active-step="activeStep" :done="generationDone" /></el-dialog>
    </main>
  </AppLayout>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import GenerationSteps from '../components/GenerationSteps.vue'
import { apiGet, apiPost } from '../utils/api'
const route=useRoute(),router=useRouter(),key=route.params.courseKey,docId=route.params.docId
const loading=ref(false),reading=ref(false),quizLoading=ref(false),assistOpen=ref(false),question=ref(''),courseTitle=ref('课程学习'),chapter=ref({}),content=ref(''),generating=ref(false),activeStep=ref(0),generationDone=ref(false)
const statusCopy=computed(()=>chapter.value.status==='passed'?'本章已通过':chapter.value.status==='ready_for_quiz'?'可以开始本章测验':'完成阅读后解锁本章测验')
async function load(){loading.value=true;try{const [course,data]=await Promise.all([apiGet(`/learning/curriculum/${key}/chapters`),apiGet(`/learning/curriculum/${key}/chapters/${docId}`)]);courseTitle.value=course.title;chapter.value=data.chapter;content.value=data.content||''}catch(error){ElMessage.error(error.message||'章节读取失败');router.push(`/courses/${key}`)}finally{loading.value=false}}
async function completeReading(){reading.value=true;try{await apiPost(`/learning/curriculum/${key}/chapters/${docId}/complete-reading`,{});chapter.value.status='ready_for_quiz';ElMessage.success('阅读完成，现在可以开始本章测验')}catch(error){ElMessage.error(error.message||'状态更新失败')}finally{reading.value=false}}
async function startQuiz(){quizLoading.value=true;generating.value=true;generationDone.value=false;activeStep.value=0;const timer=setInterval(()=>{if(activeStep.value<3)activeStep.value++},750);try{const data=await apiPost(`/learning/curriculum/${key}/chapters/${docId}/quiz`,{replace_previous:false});generationDone.value=true;activeStep.value=3;setTimeout(()=>router.push(`/assessments/${data.assessment.id}`),380)}catch(error){ElMessage.error(error.message||'题目生成失败');generating.value=false}finally{clearInterval(timer);quizLoading.value=false}}
async function ask(){try{const session=await apiPost(`/learning/curriculum/${key}/chapters/${docId}/assistant-session`,{});router.push({path:'/chat',query:{conversation_id:session.conversation_id,q:`我正在学习「${chapter.value.title||courseTitle.value}」。${question.value.trim()}`}})}catch(error){ElMessage.error(error.message||'伴学会话创建失败')}}
onMounted(load)
</script>
<style scoped>
.reader-page{max-width:920px;margin:0 auto}.reader-head{display:flex;align-items:end;justify-content:space-between;gap:20px;margin:0 0 18px}.eyebrow{margin:0;color:var(--accent-primary);font-size:11px;font-weight:800;letter-spacing:1.1px}.reader-head h1{margin:5px 0;font-size:30px;letter-spacing:-.5px}.reader-head p:not(.eyebrow){margin:0;color:var(--text-secondary)}.reading-surface{min-height:calc(100vh - 220px);padding:clamp(23px,5vw,56px);border:1px solid var(--border-color);border-radius:18px;background:var(--surface-card);line-height:1.9}.reading-actions{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:40px;padding-top:20px;border-top:1px solid var(--border-color)}.reading-actions strong,.reading-actions small{display:block}.reading-actions small{margin-top:4px;color:var(--text-secondary)}.assist-toggle{position:fixed;right:24px;bottom:22px;border:0;border-radius:999px;padding:11px 16px;background:var(--text-primary);color:#fff;cursor:pointer;box-shadow:var(--shadow-lg)}.assist{position:fixed;z-index:30;right:24px;bottom:72px;width:min(360px,calc(100vw - 32px));display:grid;gap:10px;padding:17px;border:1px solid var(--border-color);border-radius:15px;background:var(--surface-card);box-shadow:var(--shadow-lg)}.assist p{margin:0;color:var(--text-secondary);font-size:13px;line-height:1.6}@media(max-width:640px){.reader-head,.reading-actions{align-items:start;flex-direction:column}.reading-surface{min-height:0;padding:22px 17px}}
</style>
