<template>
  <AppLayout>
    <section class="tasks-page">
      <header class="page-header">
        <div>
          <p class="eyebrow">MY LEARNING PLAN</p>
          <h3>学习任务</h3>
          <p class="page-desc">把当前要学的内容拆清楚，完成后留下复盘记录。</p>
        </div>
        <el-button type="primary" @click="dialogVisible = true">新建任务</el-button>
      </header>

      <div class="summary-grid">
        <div class="summary-card"><span class="summary-value">{{ todoTasks.length }}</span><span>待完成</span></div>
        <div class="summary-card"><span class="summary-value">{{ todayTasks.length }}</span><span>今日到期</span></div>
        <div class="summary-card"><span class="summary-value">{{ doneTasks.length }}</span><span>已完成</span></div>
      </div>

      <div class="task-toolbar">
        <el-radio-group v-model="filter" size="small">
          <el-radio-button value="todo">待完成</el-radio-button>
          <el-radio-button value="done">已完成</el-radio-button>
          <el-radio-button value="all">全部</el-radio-button>
        </el-radio-group>
        <el-button text :loading="loading" @click="loadTasks">刷新</el-button>
      </div>

      <div v-loading="loading" class="task-list">
        <article v-for="task in visibleTasks" :key="task.id" class="task-card" :class="{ done: task.status === 'done' }">
          <el-checkbox :model-value="task.status === 'done'" :aria-label="`完成 ${task.title}`" :disabled="task.status === 'done'" @change="openCompletion(task)" />
          <div class="task-main">
            <div class="task-title-row">
              <h4>{{ task.title }}</h4>
              <el-tag size="small" effect="plain">{{ taskTypeLabel(task.task_type) }}</el-tag>
            </div>
            <p v-if="task.description">{{ cleanTaskDescription(task.description) }}</p>
            <div class="task-meta">
              <span v-if="task.kp_id">知识点：{{ task.kp_id }}</span>
              <span v-if="task.due_date" :class="{ overdue: isOverdue(task) }">{{ dueText(task.due_date) }}</span>
            </div>
          </div>
          <el-button text type="danger" aria-label="删除任务" @click="removeTask(task)">删除</el-button>
        </article>
        <el-empty v-if="!loading && !visibleTasks.length" :description="filter === 'done' ? '还没有已完成的任务' : '没有任务，创建一个开始学习吧'" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="新建学习任务" width="min(92vw, 520px)" @closed="resetForm">
      <el-form label-position="top" :model="form" @submit.prevent="createTask">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.title" maxlength="160" show-word-limit placeholder="例如：完成函数基础练习" />
        </el-form-item>
        <el-form-item label="任务说明">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="2000" placeholder="写下本次学习的目标或要求" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="类型">
            <el-select v-model="form.task_type">
              <el-option label="学习" value="study" />
              <el-option label="练习" value="practice" />
              <el-option label="复习" value="review" />
              <el-option label="测验" value="assessment" />
            </el-select>
          </el-form-item>
          <el-form-item label="截止时间">
            <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="可选" style="width:100%" />
          </el-form-item>
        </div>
        <el-form-item label="关联知识点">
          <el-select v-model="form.kp_id" clearable filterable placeholder="可选">
            <el-option v-for="kp in knowledgePoints" :key="kp.id" :label="kp.name" :value="kp.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createTask">创建任务</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="completionVisible" title="提交学习复盘" width="min(92vw, 480px)">
      <p class="completion-tip">完成任务前，简单记录本次学到了什么，方便后续复习。</p>
      <el-form label-position="top">
        <el-form-item label="实际学习时长（分钟）" required>
          <el-input-number v-model="completion.minutes" :min="3" :max="480" />
        </el-form-item>
        <el-form-item label="本次学到了什么 / 遇到了什么问题" required>
          <el-input
            v-model="completion.reflection"
            type="textarea"
            :rows="4"
            minlength="10"
            placeholder="至少 10 个字，例如：理解了状态更新的顺序，但还需要练习边界情况。"
          />
        </el-form-item>
        <el-form-item label="测验得分（可选）">
          <el-input-number v-model="completion.quiz_score" :min="0" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completionVisible = false">取消</el-button>
        <el-button type="primary" :loading="completing" @click="completeTask">提交复盘并完成</el-button>
      </template>
    </el-dialog>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import AppLayout from "../components/AppLayout.vue"
import { apiDelete, apiGet, apiPost } from "../utils/api"

const tasks = ref([])
const knowledgePoints = ref([])
const loading = ref(false)
const saving = ref(false)
const filter = ref("todo")
const dialogVisible = ref(false)
const completionVisible = ref(false)
const completing = ref(false)
const completingTask = ref(null)
const completion = ref({ minutes: 20, reflection: "", quiz_score: null })
const blankForm = () => ({ title: "", description: "", task_type: "study", kp_id: "", due_date: null })
const form = ref(blankForm())

const todoTasks = computed(() => tasks.value.filter(t => t.status === "todo"))
const doneTasks = computed(() => tasks.value.filter(t => t.status === "done"))
const todayTasks = computed(() => todoTasks.value.filter(t => t.due_date && new Date(t.due_date).toDateString() === new Date().toDateString()))
const visibleTasks = computed(() => filter.value === "all" ? tasks.value : tasks.value.filter(t => t.status === filter.value))

const taskTypeLabel = type => ({ study: "学习", practice: "练习", review: "复习", assessment: "测验", guided: "学习" }[type] || "学习")
const isOverdue = task => task.status === "todo" && task.due_date && new Date(task.due_date) < new Date(new Date().toDateString())
const dueText = date => `${isOverdue({ status: "todo", due_date: date }) ? "已逾期" : "截止"}：${new Date(date).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })}`

function cleanTaskDescription(text) {
  return String(text || "")
    .replace(/RAG\s*证据/g, "参考资料")
    .replace(/RAG/g, "资料辅助")
    .replace(/证据片段/g, "资料片段")
    .replace(/证据/g, "资料")
    .replace(/Agent/g, "助手")
    .replace(/训练计划/g, "学习安排")
}

function resetForm() {
  form.value = blankForm()
}

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await apiGet("/learning/tasks")
  } catch (e) {
    ElMessage.error(e.message || "任务加载失败")
  } finally {
    loading.value = false
  }
}

async function createTask() {
  if (!form.value.title.trim()) return ElMessage.warning("请填写任务名称")
  saving.value = true
  try {
    const task = await apiPost("/learning/tasks", { ...form.value, title: form.value.title.trim(), kp_id: form.value.kp_id || null })
    tasks.value.unshift(task)
    dialogVisible.value = false
    ElMessage.success("任务已创建")
  } catch (e) {
    ElMessage.error(e.message || "创建失败")
  } finally {
    saving.value = false
  }
}

function openCompletion(task) {
  completingTask.value = task
  completion.value = { minutes: 20, reflection: "", quiz_score: null }
  completionVisible.value = true
}

async function completeTask() {
  if (!completion.value.reflection.trim() || completion.value.reflection.trim().length < 10) return ElMessage.warning("请写下至少 10 个字的学习复盘")
  completing.value = true
  try {
    const updated = await apiPost(`/learning/tasks/${completingTask.value.id}/complete`, completion.value)
    Object.assign(completingTask.value, updated)
    completionVisible.value = false
    ElMessage.success("复盘已保存，任务完成")
  } catch (e) {
    ElMessage.error(e.message || "提交失败")
  } finally {
    completing.value = false
  }
}

async function removeTask(task) {
  try {
    await ElMessageBox.confirm(`确定删除“${task.title}”吗？`, "删除任务", { type: "warning" })
    await apiDelete(`/learning/tasks/${task.id}`)
    tasks.value = tasks.value.filter(t => t.id !== task.id)
    ElMessage.success("已删除")
  } catch (e) {
    if (e !== "cancel" && e !== "close") ElMessage.error(e.message || "删除失败")
  }
}

onMounted(async () => {
  await Promise.all([
    loadTasks(),
    apiGet("/learning/knowledge-points").then(data => knowledgePoints.value = data).catch(() => {}),
  ])
})
</script>

<style scoped>
.tasks-page { max-width:1000px; margin:0 auto; }
.page-header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:20px; }
.eyebrow { color:var(--accent-primary); font-size:11px; font-weight:700; letter-spacing:1.2px; margin:0 0 4px; }
.page-header h3 { margin:0 0 6px; font-size:22px; }
.page-desc { margin:0; color:var(--text-secondary); font-size:14px; }
.summary-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:20px; }
.summary-card { padding:16px 18px; border:1px solid var(--border-color); border-radius:var(--radius-lg); background:var(--surface-card); color:var(--text-secondary); font-size:13px; }
.summary-value { display:block; color:var(--text-primary); font-size:26px; line-height:1.15; font-weight:700; margin-bottom:5px; }
.task-toolbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.task-list { min-height:150px; }
.task-card { display:flex; align-items:flex-start; gap:13px; padding:17px; margin-bottom:10px; background:var(--surface-card); border:1px solid var(--border-color); border-radius:var(--radius-lg); transition:.2s; }
.task-card:hover { border-color:var(--accent-primary); box-shadow:var(--shadow-sm); }
.task-card.done { opacity:.65; }
.task-main { flex:1; min-width:0; }
.task-title-row { display:flex; gap:10px; align-items:center; }
.task-title-row h4 { font-size:15px; margin:0; }
.done h4 { text-decoration:line-through; }
.task-main p { margin:6px 0; color:var(--text-secondary); font-size:13px; line-height:1.55; white-space:pre-wrap; }
.task-meta { display:flex; flex-wrap:wrap; gap:12px; color:var(--text-tertiary); font-size:12px; }
.overdue { color:var(--error); }
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.completion-tip { margin:0 0 14px; color:var(--text-secondary); font-size:13px; line-height:1.6; }
@media(max-width:640px) {
  .page-header { flex-direction:column; }
  .summary-grid { gap:8px; }
  .summary-card { padding:14px 12px; }
  .form-grid { grid-template-columns:1fr; }
  .task-card { padding:14px; }
  .task-title-row { align-items:flex-start; flex-direction:column; gap:6px; }
}
</style>
