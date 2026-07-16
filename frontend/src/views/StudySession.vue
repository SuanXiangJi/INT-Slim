<template>
  <AppLayout>
    <section class="study-page" v-loading="loading">
      <header class="study-head">
        <div>
          <p class="eyebrow">IMMERSIVE STUDY</p>
          <h3>{{ task?.title || "学习计划" }}</h3>
          <p>{{ task?.task_type || "guided" }} · {{ cards.length }} 张学习卡片</p>
        </div>
        <div class="head-actions">
          <el-button @click="$router.push('/courses')">返回工作台</el-button>
          <el-button type="primary" @click="$router.push('/tasks')">查看任务</el-button>
        </div>
      </header>

      <main class="reader-panel" @mouseup="captureSelection">
        <div class="reader-progress">
          <span>第 {{ activeIndex + 1 }} / {{ cards.length || 1 }} 张</span>
          <el-progress :percentage="progress" :stroke-width="6" />
        </div>

        <article v-if="activeCard" class="study-card">
          <span class="card-kicker">{{ activeCard.kicker }}</span>
          <h4>{{ activeCard.title }}</h4>
          <div class="card-body">
            <p v-for="(line, index) in activeCard.lines" :key="index">{{ line }}</p>
          </div>
          <div class="checkpoint">
            <strong>检查点</strong>
            <p>{{ activeCard.checkpoint }}</p>
          </div>
        </article>

        <div class="reader-nav">
          <el-button :disabled="activeIndex === 0" @click="activeIndex--">上一张</el-button>
          <el-button type="primary" :disabled="activeIndex >= cards.length - 1" @click="activeIndex++">下一张</el-button>
        </div>
      </main>

      <button class="agent-fab" :class="{ active: agentOpen }" @click="agentOpen = !agentOpen">
        <span>伴学</span>
        <small v-if="selectedText">已选中内容</small>
        <small v-else>选中文本后提问</small>
      </button>

      <transition name="agent-pop">
        <aside v-if="agentOpen" class="agent-popover">
          <div class="agent-head">
            <div>
              <p class="eyebrow">STUDY AGENT</p>
              <h4>伴学解释</h4>
            </div>
            <button class="agent-close" @click="agentOpen = false">收起</button>
          </div>

          <div class="selection-box">
            <span>当前选区</span>
            <p>{{ selectedText || "在学习卡片中选中不理解的句子或概念，再让伴学解释。" }}</p>
          </div>

          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            maxlength="600"
            show-word-limit
            placeholder="例如：这句话和前面的概念有什么关系？"
          />
          <el-button class="ask-btn" type="primary" :loading="asking" :disabled="!selectedText.trim()" @click="askAgent">
            解释选中内容
          </el-button>

          <div v-if="agentAnswer" class="answer-card">
            <div class="answer-meta">
              <strong>{{ agentAnswer.used_llm ? "伴学解释" : "资料解释" }}</strong>
              <span>{{ agentAnswer.evidence_refs?.length || 0 }} 条参考</span>
            </div>
            <p class="answer-text">{{ sanitizeStudyCopy(agentAnswer.answer) }}</p>
          </div>

          <details v-if="agentAnswer?.evidence_refs?.length" class="reference-mini">
            <summary>查看参考资料</summary>
            <article v-for="ev in agentAnswer.evidence_refs" :key="`${ev.doc_id}-${ev.chunk_id}`">
              <strong>{{ ev.title }}</strong>
              <small>相关度 {{ Number(ev.score || 0).toFixed(3) }}</small>
              <p>{{ ev.snippet }}</p>
            </article>
          </details>
        </aside>
      </transition>
    </section>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import { ElMessage } from "element-plus"
import AppLayout from "../components/AppLayout.vue"
import { apiGet, apiPost } from "../utils/api"

const route = useRoute()
const task = ref(null)
const cards = ref([])
const activeIndex = ref(0)
const selectedText = ref("")
const question = ref("")
const agentAnswer = ref(null)
const loading = ref(false)
const asking = ref(false)
const agentOpen = ref(false)

const activeCard = computed(() => cards.value[activeIndex.value])
const progress = computed(() => cards.value.length ? Math.round(((activeIndex.value + 1) / cards.value.length) * 100) : 0)

function sanitizeStudyCopy(text) {
  return String(text || "")
    .replace(/RAG\s*证据/g, "参考资料")
    .replace(/RAG/g, "资料辅助")
    .replace(/证据片段/g, "资料片段")
    .replace(/可追溯证据/g, "参考资料")
    .replace(/检索证据/g, "整理资料")
    .replace(/训练计划/g, "学习安排")
    .replace(/证据/g, "资料")
}

function splitCards(taskData) {
  const raw = sanitizeStudyCopy([taskData.description || "", taskData.title || ""].join("\n")).trim()
  const sections = raw
    .split(/\n(?=(目标|参考资料|相关资料|学习安排|完成要求|学习完成记录)[：:])/)
    .map(part => part.trim())
    .filter(Boolean)

  const normalized = sections.length ? sections : raw.split(/\n{2,}/).filter(Boolean)
  return normalized.map((section, index) => {
    const lines = section.split("\n").map(line => line.trim()).filter(Boolean)
    const first = lines[0] || `学习卡片 ${index + 1}`
    return {
      kicker: index === 0 ? "START" : `CARD ${index + 1}`,
      title: first.replace(/[：:].*$/, ""),
      lines: lines.length > 1 ? lines.slice(1) : [first],
      checkpoint: buildCheckpoint(first, lines.join(" ")),
    }
  })
}

function buildCheckpoint(title, text) {
  const body = title + text
  if (/参考资料|相关资料|资料片段/.test(body)) return "这段资料能帮你理解哪个关键问题？请用一句话说明。"
  if (/学习安排|计划/.test(body)) return "你现在能说出下一步要做什么吗？"
  if (/完成要求|复盘/.test(body)) return "学习结束后，请写下一个仍然不确定的问题。"
  return "把这张卡片的核心意思用自己的话复述一遍。"
}

function captureSelection() {
  const text = window.getSelection()?.toString()?.trim() || ""
  if (text.length >= 2) {
    selectedText.value = text.slice(0, 1000)
    agentOpen.value = true
  }
}

async function askAgent() {
  if (!selectedText.value.trim()) return
  asking.value = true
  try {
    agentAnswer.value = await apiPost(`/learning/tasks/${route.params.taskId}/study-assist`, {
      selected_text: selectedText.value,
      question: question.value.trim() || undefined,
      context: activeCard.value ? [activeCard.value.title, ...activeCard.value.lines].join("\n") : "",
      use_llm: true,
    })
  } catch (error) {
    ElMessage.error(error.message || "伴学暂时不可用")
  } finally {
    asking.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    task.value = await apiGet(`/learning/tasks/${route.params.taskId}`)
    cards.value = splitCards(task.value)
  } catch (error) {
    ElMessage.error(error.message || "学习计划加载失败")
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.study-page { max-width:1320px; margin:0 auto; }
.study-head { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:16px; padding:18px 20px; border:1px solid var(--border-color); border-radius:var(--radius-lg); background:var(--surface-card); box-shadow:var(--shadow-xs); }
.eyebrow { margin:0 0 5px; color:var(--accent-primary); font-size:10px; font-weight:800; letter-spacing:1.2px; }
.study-head h3 { margin:0 0 6px; font-size:22px; color:var(--text-primary); }
.study-head p:not(.eyebrow) { margin:0; color:var(--text-secondary); font-size:13px; }
.head-actions { display:flex; gap:8px; }
.reader-panel { min-height:calc(100vh - 210px); padding:20px; border:1px solid var(--border-color); border-radius:var(--radius-lg); background:var(--surface-card); box-shadow:var(--shadow-xs); }
.reader-progress { display:grid; grid-template-columns:120px 1fr; gap:12px; align-items:center; color:var(--text-tertiary); font-size:12px; margin-bottom:16px; }
.study-card { max-width:860px; min-height:460px; margin:0 auto; padding:42px 48px; border:1px solid var(--border-color); border-radius:var(--radius-lg); background:var(--surface-raised); box-shadow:var(--shadow-sm); }
.card-kicker { color:var(--accent-primary); font-size:11px; font-weight:800; letter-spacing:1.4px; }
.study-card h4 { margin:8px 0 20px; font-size:25px; line-height:1.35; color:var(--text-primary); }
.card-body { display:grid; gap:13px; color:var(--text-primary); font-size:16px; line-height:1.9; }
.checkpoint { margin-top:26px; padding:14px; border-left:3px solid var(--accent-primary); background:var(--accent-soft); border-radius:var(--radius-md); }
.checkpoint strong { display:block; margin-bottom:6px; font-size:13px; color:var(--text-primary); }
.checkpoint p { margin:0; color:var(--text-secondary); font-size:13px; line-height:1.6; }
.reader-nav { display:flex; justify-content:center; gap:10px; margin-top:16px; }
.agent-fab { position:fixed; right:26px; bottom:24px; z-index:80; display:grid; gap:2px; min-width:124px; padding:13px 16px; border:1px solid var(--border-color); border-radius:999px; color:#fff; background:var(--accent-gradient); box-shadow:var(--shadow-lg); cursor:pointer; text-align:left; }
.agent-fab span { font-size:14px; font-weight:800; line-height:1.1; }
.agent-fab small { font-size:11px; opacity:.86; }
.agent-fab.active { transform:translateY(-2px); box-shadow:var(--shadow-xl); }
.agent-popover { position:fixed; right:24px; bottom:92px; z-index:90; display:grid; gap:12px; width:min(420px, calc(100vw - 32px)); max-height:min(680px, calc(100vh - 126px)); overflow:auto; padding:15px; border:1px solid var(--border-color); border-radius:var(--radius-xl); background:var(--surface-card); box-shadow:var(--shadow-xl); }
.agent-pop-enter-active, .agent-pop-leave-active { transition:opacity .18s ease, transform .18s ease; }
.agent-pop-enter-from, .agent-pop-leave-to { opacity:0; transform:translateY(10px) scale(.98); }
.agent-head, .answer-meta { display:flex; justify-content:space-between; align-items:center; gap:10px; }
.agent-head h4 { margin:0; color:var(--text-primary); }
.agent-close { border:1px solid var(--border-color); border-radius:999px; padding:6px 10px; color:var(--text-secondary); background:var(--surface-raised); cursor:pointer; }
.agent-close:hover { color:var(--text-primary); border-color:var(--border-hover); }
.selection-box, .answer-card, .reference-mini article { border:1px solid var(--border-color); border-radius:var(--radius-md); background:var(--surface-raised); }
.selection-box { padding:12px; }
.selection-box span { color:var(--accent-primary); font-size:12px; font-weight:700; }
.selection-box p { margin:7px 0 0; color:var(--text-secondary); font-size:13px; line-height:1.6; max-height:120px; overflow:auto; }
.ask-btn { width:100%; }
.answer-card { padding:13px; }
.answer-meta strong { font-size:13px; color:var(--text-primary); }
.answer-meta span { color:var(--text-tertiary); font-size:12px; }
.answer-text { margin:10px 0 0; color:var(--text-primary); white-space:pre-wrap; line-height:1.65; font-size:13px; }
.reference-mini { display:grid; gap:8px; max-height:300px; overflow:auto; }
.reference-mini summary { cursor:pointer; color:var(--text-secondary); font-size:13px; font-weight:700; }
.reference-mini article { padding:10px; }
.reference-mini strong { display:block; font-size:12px; color:var(--text-primary); }
.reference-mini small { display:block; margin-top:4px; color:var(--accent-primary); font-size:11px; }
.reference-mini p { margin:6px 0 0; color:var(--text-secondary); font-size:12px; line-height:1.55; }
@media (max-width:640px) {
  .study-head { flex-direction:column; }
  .reader-progress { grid-template-columns:1fr; }
  .study-card { padding:24px 20px; }
  .agent-fab { right:16px; bottom:16px; }
  .agent-popover { right:12px; bottom:80px; }
}
</style>
