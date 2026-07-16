<template>
  <AppLayout>
    <main class="assessment" v-loading="loading">
      <template v-if="assessment && !result">
        <header class="assessment-head">
          <div>
            <el-button text @click="backToCourse">返回课程</el-button>
            <p class="eyebrow">{{ assessment.type === 'course_exam' ? 'FINAL ASSESSMENT' : 'CHAPTER CHECK' }}</p>
            <h1>{{ assessment.type === 'course_exam' ? '学科考试' : '章节测验' }}</h1>
            <p>完成全部题目后统一判分，{{ assessment.passing_score }} 分及格。</p>
          </div>
          <div class="progress-copy">{{ answeredCount }} / {{ questions.length }} 已作答</div>
        </header>

        <section class="assessment-layout">
          <aside class="question-nav" aria-label="题目导航">
            <span>题目</span>
            <div>
              <button v-for="(question, index) in questions" :key="question.id" :class="{ active: index === currentIndex, answered: hasAnswer(question) }" @click="currentIndex = index">{{ index + 1 }}</button>
            </div>
            <details v-if="trace.length" class="trace">
              <summary>题集生成记录</summary>
              <ol>
                <li v-for="step in trace" :key="step.name"><strong>{{ step.name }}</strong><small>{{ step.detail }}</small></li>
              </ol>
            </details>
          </aside>

          <article v-if="currentQuestion" class="question-card">
            <div class="question-meta"><span>第 {{ currentIndex + 1 }} 题</span><span>单选题</span></div>
            <h2>{{ currentQuestion.data.question }}</h2>
            <el-radio-group v-model="answers[currentQuestion.id]" class="options">
              <el-radio v-for="(option, index) in currentQuestion.data.options || []" :key="index" :value="String(index)">
                <b>{{ optionLabel(index) }}</b><span>{{ option }}</span>
              </el-radio>
            </el-radio-group>
            <footer class="question-actions">
              <el-button :disabled="currentIndex === 0" @click="currentIndex--">上一题</el-button>
              <el-button v-if="currentIndex < questions.length - 1" type="primary" @click="currentIndex++">下一题</el-button>
              <el-button v-else type="primary" :loading="submitting" @click="submit">提交并判分</el-button>
            </footer>
          </article>
        </section>
      </template>

      <section v-else-if="result && assessment" class="result-card">
        <p class="eyebrow">RESULT</p>
        <h1>{{ result.passed ? '本次测验通过' : '还差一点，再来一次' }}</h1>
        <div class="score"><strong>{{ result.score }}</strong><span>/ 100</span></div>
        <p>及格线 {{ result.passing_score }} 分。{{ result.agent_feedback }}</p>
        <div v-if="wrongResults.length" class="wrong-list">
          <h2>需要回顾</h2>
          <article v-for="item in wrongResults" :key="item.question_id">
            <strong>{{ questionById(item.question_id)?.data?.question }}</strong>
            <p>正确答案：{{ optionText(questionById(item.question_id), item.correct_answer) }}</p>
            <p>{{ item.explanation || '建议回到对应章节，复习相关概念后再尝试。' }}</p>
          </article>
        </div>
        <div class="result-actions">
          <el-button @click="backToCourse">返回课程</el-button>
          <el-button :loading="retrying" @click="retryAssessment">重做本套题</el-button>
          <el-button v-if="!result.passed" type="primary" :loading="replacing" @click="replaceAssessment">换套题重做</el-button>
          <el-button v-else type="primary" @click="$router.push('/code-practice')">进入代码实训</el-button>
        </div>
      </section>

      <el-empty v-else-if="!loading" description="未找到这套题目" />
    </main>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import { apiGet, apiPost } from '../utils/api'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const replacing = ref(false)
const retrying = ref(false)
const assessment = ref(null)
const answers = ref({})
const currentIndex = ref(0)
const result = ref(null)

const questions = computed(() => assessment.value?.questions || [])
const currentQuestion = computed(() => questions.value[currentIndex.value])
const trace = computed(() => assessment.value?.blueprint?.trace || [])
const answeredCount = computed(() => questions.value.filter(hasAnswer).length)
const wrongResults = computed(() => (result.value?.results || []).filter(item => !item.correct))

function hasAnswer(question) { return answers.value[question.id] !== undefined }
function optionLabel(index) { return String.fromCharCode(65 + index) }
function questionById(id) { return questions.value.find(question => question.id === id) }
function optionText(question, index) {
  const option = question?.data?.options?.[Number(index)]
  return option ? `${optionLabel(Number(index))}. ${option}` : '未提供'
}

async function load() {
  loading.value = true
  try {
    assessment.value = await apiGet(`/learning/assessments/${route.params.assessmentId}`)
    if (assessment.value.status !== 'active') {
      result.value = assessment.value.latest_result || null
      ElMessage.info('已恢复这套题目的作答结果。')
    }
  } catch (error) {
    ElMessage.error(error.message || '题目加载失败')
  } finally {
    loading.value = false
  }
}

async function submit() {
  const unanswered = questions.value.length - answeredCount.value
  if (unanswered > 0) {
    try {
      await ElMessageBox.confirm(`还有 ${unanswered} 题未作答，仍要提交吗？`, '确认提交', { confirmButtonText: '提交', cancelButtonText: '继续作答' })
    } catch { return }
  }
  submitting.value = true
  try {
    result.value = await apiPost(`/learning/assessments/${assessment.value.id}/submit`, { answers: answers.value })
    assessment.value.status = result.value.passed ? 'passed' : 'failed'
  } catch (error) {
    ElMessage.error(error.message || '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

async function replaceAssessment() {
  replacing.value = true
  try {
    const endpoint = assessment.value.type === 'course_exam'
      ? `/learning/curriculum/${assessment.value.course_key}/final-exam`
      : `/learning/curriculum/${assessment.value.course_key}/chapters/${assessment.value.chapter_doc_id}/quiz`
    const data = await apiPost(endpoint, { replace_previous: true })
    router.replace(`/assessments/${data.assessment.id}`)
    assessment.value = data.assessment
    answers.value = {}
    currentIndex.value = 0
    result.value = null
  } catch (error) {
    ElMessage.error(error.message || '暂时无法更换题目')
  } finally {
    replacing.value = false
  }
}

async function retryAssessment() {
  retrying.value = true
  try {
    const data = await apiPost(`/learning/assessments/${assessment.value.id}/retry`, {})
    assessment.value = data.assessment
    answers.value = {}
    currentIndex.value = 0
    result.value = null
  } catch (error) {
    ElMessage.error(error.message || '暂时无法重新开始本套题')
  } finally {
    retrying.value = false
  }
}

function backToCourse() { router.push(`/courses/${assessment.value?.course_key || ''}`) }
onMounted(load)
</script>

<style scoped>
.assessment{max-width:1120px;margin:0 auto}.assessment-head{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:18px}.assessment-head h1{margin:5px 0;font-size:28px;letter-spacing:-.5px}.assessment-head p:not(.eyebrow){margin:0;color:var(--text-secondary)}.eyebrow{margin:0;color:var(--accent-primary);font-size:11px;font-weight:800;letter-spacing:1.1px}.progress-copy{padding:10px 13px;border:1px solid var(--border-color);border-radius:999px;color:var(--text-secondary);font-size:13px;white-space:nowrap}.assessment-layout{display:grid;grid-template-columns:205px minmax(0,1fr);gap:18px}.question-nav,.question-card,.result-card{border:1px solid var(--border-color);border-radius:18px;background:var(--surface-card)}.question-nav{align-self:start;padding:18px}.question-nav>span{font-size:12px;font-weight:700;color:var(--text-secondary)}.question-nav>div{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 20px}.question-nav button{width:32px;height:32px;border:1px solid var(--border-color);border-radius:9px;background:transparent;color:var(--text-secondary);cursor:pointer}.question-nav button.active{border-color:var(--accent-primary);background:var(--accent-primary);color:#fff}.question-nav button.answered:not(.active){border-color:#9bcaaa;background:#eff9f1;color:#24663a}.trace{border-top:1px solid var(--border-color);padding-top:13px;color:var(--text-secondary);font-size:12px}.trace summary{cursor:pointer;font-weight:700}.trace ol{display:grid;gap:10px;margin:12px 0 0;padding:0;list-style:none}.trace strong,.trace small{display:block}.trace small{margin-top:2px;color:var(--text-tertiary);line-height:1.45}.question-card{min-height:500px;display:flex;flex-direction:column;padding:clamp(24px,4vw,48px)}.question-meta{display:flex;justify-content:space-between;color:var(--text-tertiary);font-size:13px}.question-card h2{max-width:780px;margin:28px 0 26px;font-size:clamp(19px,2.4vw,25px);line-height:1.55;font-weight:650}.options{display:grid;gap:11px}.options :deep(.el-radio){display:flex;align-items:flex-start;height:auto;min-height:52px;margin:0;padding:14px;border:1px solid var(--border-color);border-radius:12px;white-space:normal}.options :deep(.el-radio__label){display:flex;gap:12px;padding-left:10px;line-height:1.6}.options b{color:var(--accent-primary)}.question-actions{display:flex;justify-content:space-between;gap:10px;margin-top:auto;padding-top:32px}.question-actions .el-button:last-child{margin-left:auto}.result-card{max-width:770px;margin:42px auto;padding:clamp(25px,5vw,52px)}.result-card h1{margin:6px 0 14px;font-size:30px}.score{display:flex;align-items:baseline;gap:6px;margin:24px 0}.score strong{font-size:62px;line-height:1;color:var(--accent-primary);letter-spacing:-3px}.score span{color:var(--text-tertiary)}.result-card>p{color:var(--text-secondary);line-height:1.7}.wrong-list{margin-top:30px;border-top:1px solid var(--border-color);padding-top:22px}.wrong-list h2{margin:0 0 12px;font-size:17px}.wrong-list article{margin-top:10px;padding:15px;border-radius:12px;background:var(--bg-tertiary)}.wrong-list p{margin:7px 0 0;color:var(--text-secondary);line-height:1.6;font-size:13px}.result-actions{display:flex;gap:10px;margin-top:28px}@media(max-width:760px){.assessment-head{align-items:start;flex-direction:column}.assessment-layout{grid-template-columns:1fr}.question-nav{position:static}.question-nav>div{margin-bottom:0}.trace{display:none}.question-card{min-height:480px;padding:24px 19px}.result-card{margin-top:18px}.result-actions{flex-wrap:wrap}}
</style>
