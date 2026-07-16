<template>
  <AppLayout>
    <div class="chat-page">
      <aside class="conversation-panel">
        <button class="new-chat" :disabled="locked || isCreatingConversation" @click="newConversation">
          <span>+</span>
          <span>{{ isCreatingConversation ? "创建中..." : "新对话" }}</span>
        </button>

        <div class="panel-label">最近对话</div>
        <div class="conversation-list">
          <button
            v-for="c in conversations"
            :key="c.id"
            class="conversation-item"
            :class="{ active: c.id === currentId }"
            :disabled="locked && c.id !== currentId"
            @click="switchConv(c.id)"
          >
            <span class="conversation-title">{{ c.title || "未命名对话" }}</span>
            <span class="conversation-time">{{ formatTime(c.updated_at || c.created_at) }}</span>
          </button>
          <div v-if="!conversations.length" class="empty-list">暂无对话</div>
        </div>
      </aside>

      <section class="chat-main">
        <div ref="msgRef" class="message-scroll">
          <div v-if="!visibleMessages.length" class="welcome">
            <div class="welcome-mark">XBots</div>
            <h1>今天想学什么？</h1>
            <p>可以直接提问、让它解释概念、生成练习，或帮你拆解一段不理解的内容。</p>
            <div class="prompt-grid">
              <button v-for="s in suggests" :key="s" @click="send(s)">{{ s }}</button>
            </div>
          </div>

          <div
            v-for="(m, mi) in visibleMessages"
            :key="m.localId || m.id || mi"
            class="message-row"
            :class="m.role"
          >
            <div class="message-card">
              <div v-if="m.role === 'assistant' && m.transcript?.length" class="steps-card">
                <button class="steps-head" @click="toggleSteps(m, mi)">
                  <span>Steps</span>
                  <span>{{ m.transcript.length }} 步 · {{ expandedSteps.includes(stepKey(m, mi)) ? "收起" : "展开" }}</span>
                </button>
                <div
                  v-if="expandedSteps.includes(stepKey(m, mi))"
                  :ref="(el) => setStepsBodyRef(stepKey(m, mi), el)"
                  class="steps-body"
                >
                  <div v-for="(s, si) in m.transcript" :key="si" class="step-line" :class="`step-${s.kind}`">
                    <div class="step-index">{{ si + 1 }}</div>
                    <div class="step-content">
                      <div v-if="stepTransition(s, si, m.transcript)" class="step-transition">
                        {{ stepTransition(s, si, m.transcript) }}
                      </div>
                      <div class="step-title-row">
                        <span class="step-title">{{ stepLabel(s) }}</span>
                        <span v-if="stepBadge(s)" class="step-badge" :class="`step-badge-${s.kind}`">
                          {{ stepBadge(s) }}
                        </span>
                      </div>
                      <div class="step-summary">{{ stepSummary(s) }}</div>
                      <div v-if="stepDetail(s)" class="step-detail">
                        <pre>{{ stepDetail(s) }}</pre>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="m.role === 'assistant' && m.humanReview" class="human-review-card">
                <div class="human-review-copy">
                  <strong>{{ m.humanReview.title || "需要你的确认" }}</strong>
                  <p>{{ m.humanReview.message || "这一步可能产生外部影响，请确认是否继续。" }}</p>
                  <small v-if="m.humanReview.action">准备执行：{{ m.humanReview.action }}</small>
                </div>
                <div class="human-review-actions">
                  <button
                    class="review-cancel"
                    :disabled="m.humanReview.status === 'submitting'"
                    @click="resumeHumanReview(m, false)"
                  >取消</button>
                  <button
                    class="review-approve"
                    :disabled="m.humanReview.status === 'submitting'"
                    @click="resumeHumanReview(m, true)"
                  >继续执行</button>
                </div>
              </div>

              <div v-if="m.role === 'user'" class="user-bubble">{{ m.content }}</div>
              <div v-else class="assistant-content">
                <MarkdownRenderer v-if="m.content" :content="m.content" />
                <div v-else-if="m.isStreaming" class="streaming-dots"><span></span><span></span><span></span></div>
                <div v-if="m.evidenceRefs?.length" class="evidence-card">
                  <button class="evidence-head" @click="toggleEvidence(m, mi)">
                    <span>参考来源</span>
                    <span>{{ m.evidenceRefs.length }} 条 · {{ expandedEvidence.includes(evidenceKey(m, mi)) ? "收起" : "展开" }}</span>
                  </button>
                  <div v-if="expandedEvidence.includes(evidenceKey(m, mi))" class="evidence-list">
                    <div v-for="ref in m.evidenceRefs" :key="`${ref.doc_id}-${ref.chunk_id}-${ref.index}`" class="evidence-item">
                      <div class="evidence-title">
                        <button class="evidence-link" @click="openEvidence(ref)">
                          {{ ref.index }}. {{ evidenceTitle(ref) }}
                        </button>
                        <span v-if="formatScore(ref.score, ref)" class="evidence-score">{{ formatScore(ref.score, ref) }}</span>
                      </div>
                      <p v-if="ref.snippet">{{ ref.snippet }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form class="composer" @submit.prevent="send(input)">
          <textarea
            v-model="input"
            :disabled="isStreaming"
            placeholder="输入你的问题..."
            rows="1"
            @keydown.enter.exact.prevent="send(input)"
            @input="resizeInput"
            ref="inputRef"
          ></textarea>
          <button
            v-if="isStreaming"
            type="button"
            class="stop-generation"
            :disabled="isStopping"
            @click="stopGeneration"
          >{{ isStopping ? "正在暂停" : "暂停" }}</button>
          <button v-else type="submit" :disabled="!input.trim()">发送</button>
        </form>
      </section>
    </div>

    <div v-if="evidenceModal.open" class="source-modal" @click.self="closeEvidence">
      <article class="source-dialog">
        <header class="source-head">
          <div>
            <p>参考原文</p>
            <h3>{{ evidenceModal.data?.title || evidenceTitle(evidenceModal.ref) }}</h3>
          </div>
          <button class="source-close" @click="closeEvidence">×</button>
        </header>
        <div v-if="evidenceModal.loading" class="source-state">正在加载原文...</div>
        <div v-else-if="evidenceModal.error" class="source-state error">{{ evidenceModal.error }}</div>
        <div v-else class="source-body">
          <a
            v-if="evidenceModal.data?.source_url"
            class="source-external"
            :href="evidenceModal.data.source_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            打开原网页
          </a>
          <section
            v-for="chunk in evidenceModal.data?.chunks || []"
            :key="chunk.chunk_id"
            class="source-chunk"
            :class="{ active: chunk.active }"
          >
            <div class="source-chunk-label">片段 {{ chunk.chunk_id }}</div>
            <p>{{ chunk.content }}</p>
          </section>
        </div>
      </article>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from "vue"
import { useRoute } from "vue-router"
import AppLayout from "../components/AppLayout.vue"
import MarkdownRenderer from "../components/MarkdownRenderer.vue"
import { apiDelete, apiGet, apiPost, getToken } from "../utils/api"

const route = useRoute()
const msgRef = ref(null)
const inputRef = ref(null)
const conversations = ref([])
const currentId = ref(null)
const input = ref(route.query.q || "")
const isStreaming = ref(false)
const isStopping = ref(false)
const isCreatingConversation = ref(false)
const msgCache = reactive({})
const expandedSteps = ref([])
const expandedEvidence = ref([])
const evidenceModal = reactive({
  open: false,
  loading: false,
  error: "",
  ref: null,
  data: null,
})
const stepsBodyRefs = new Map()
const agentMode = ref(true)
const locked = computed(() => isStreaming.value)
const visibleMessages = computed(() => {
  const slot = msgCache[currentId.value] || []
  return dedupeFinalMessages(dedupeRestoredUsers(slot))
    .filter((m) => m.role !== "assistant" || m.content || m.transcript?.length || m.isStreaming || m.humanReview)
})
const STREAM_LOCK_KEY = "xbots.chat.activeStream"
const STREAM_LOCK_TTL = 10 * 60 * 1000
let restorePollTimer = null
let pageUnloading = false
let suppressAutoScrollUntil = 0
let pendingConversationPromise = null

const suggests = [
  "用例子解释快速排序",
  "帮我制定一周 Python 学习计划",
  "出 5 道机器学习基础练习",
  "把递归讲得更容易理解",
]

onMounted(async () => {
  window.addEventListener("pagehide", markPageUnloading)
  const pendingLock = readStreamLock()
  const requestedConversationId = route.query.conversation_id || pendingLock?.conversationId || currentId.value
  await refreshConversations(requestedConversationId, { scroll: !pendingLock })
  await restoreStreamLock()
  if (!currentId.value) await newConversation()
  if (route.query.q && input.value) setTimeout(() => send(input.value), 300)
})

onUnmounted(() => {
  window.removeEventListener("pagehide", markPageUnloading)
  stopRestorePolling()
})

function initSlot(id) {
  if (!msgCache[id]) msgCache[id] = []
  return msgCache[id]
}

function getCurrentSlot() {
  return initSlot(currentId.value)
}

async function refreshConversations(selectId = currentId.value, options = {}) {
  const { scroll = true } = options
  try {
    const convs = (await apiGet("/conversations")) || []
    conversations.value = convs
    if (selectId && convs.some((c) => c.id === selectId)) {
      currentId.value = selectId
    } else if (convs.length) {
      currentId.value = convs[0].id
    }
    if (currentId.value) await loadMsgs(currentId.value, { scroll })
  } catch {
    conversations.value = []
  }
}

async function newConversation() {
  if (locked.value) return currentId.value
  if (pendingConversationPromise) return pendingConversationPromise

  isCreatingConversation.value = true
  pendingConversationPromise = (async () => {
  try {
    const c = await apiPost("/conversations", { title: "新对话" })
    conversations.value = [c, ...conversations.value.filter((item) => item.id !== c.id)]
    currentId.value = c.id
    msgCache[c.id] = []
    resetConversationUiState()
    input.value = ""
    await scrollToBottom()
    return c.id
  } catch {
    currentId.value = currentId.value || `local-${Date.now()}`
    msgCache[currentId.value] = msgCache[currentId.value] || []
    return currentId.value
  } finally {
    isCreatingConversation.value = false
    pendingConversationPromise = null
  }
  })()

  return pendingConversationPromise
}

async function loadMsgs(id, options = {}) {
  const { scroll = true } = options
  if (!id) return
  try {
    const ms = (await apiGet(`/conversations/${id}/messages`)) || []
    const slot = initSlot(id)
    slot.splice(0, slot.length, ...ms.map(normalizeMessage))
    const lock = readStreamLock()
    if (lock?.conversationId === id && lock.humanReview && !hasFinalAssistantForLock(slot, lock)) {
      ensurePendingAssistant(lock)
    } else if (!lock || lock.conversationId !== id) {
      await restoreHumanReviewFromBackend(id)
    }
    if (scroll) await scrollToBottom()
  } catch {
    initSlot(id)
  }
}

async function restoreHumanReviewFromBackend(conversationId) {
  try {
    const pending = await apiGet(`/conversations/${conversationId}/human-review`)
    if (pending?.status !== "waiting") return
    const lock = {
      conversationId,
      userContent: pending.user_input || "",
      assistantLocalId: `human-review-${conversationId}`,
      assistantContent: "",
      transcript: normalizeTranscript(pending.transcript || []),
      humanReview: { ...(pending.review || {}), status: "waiting" },
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    writeStreamLock(lock)
    ensurePendingAssistant(lock)
  } catch {}
}

async function switchConv(id) {
  if (!id || id === currentId.value || locked.value) return
  currentId.value = id
  resetConversationUiState()
  await loadMsgs(id)
}

async function delConv(id) {
  if (locked.value) return
  try {
    await apiDelete(`/conversations/${id}`)
    delete msgCache[id]
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (currentId.value === id) {
      currentId.value = conversations.value[0]?.id || null
      resetConversationUiState()
      if (currentId.value) await loadMsgs(currentId.value)
      else await newConversation()
    }
  } catch {}
}

async function send(text) {
  const t = (text || "").trim()
  if (!t || isStreaming.value) return
  if (!currentId.value) await newConversation()
  if (!currentId.value) return

  input.value = ""
  isStopping.value = false
  resizeInput()
  const conversationId = currentId.value
  const slot = initSlot(conversationId)
  const assistant = {
    localId: `assistant-${Date.now()}`,
    role: "assistant",
    content: "",
    transcript: [],
    evidenceRefs: [],
    pendingEvidenceRefs: [],
    isStreaming: true,
  }

  slot.push({ localId: `user-${Date.now()}`, role: "user", content: t })
  slot.push(assistant)
  const assistantIndex = slot.length - 1
  isStreaming.value = true
  writeStreamLock({
    conversationId,
    userContent: t,
    assistantLocalId: assistant.localId,
    assistantContent: "",
    transcript: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  })
  touchConversation(conversationId, t)
  await scrollToBottom()

  try {
    const res = await fetch(`/api/v1/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ content: t, enable_agent: agentMode.value }),
    })

    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let doneByEvent = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        const raw = line.slice(6).trim()
        if (!raw) continue
        if (raw === "[DONE]") {
          doneByEvent = true
          break
        }
        handleStreamEvent(slot, assistantIndex, raw, conversationId, t)
      }

      await scrollToBottom()
      if (doneByEvent) break
    }
  } catch (e) {
    slot[assistantIndex].content = `请求失败：${e.message || "网络异常"}`
  } finally {
    slot[assistantIndex].isStreaming = false
    isStreaming.value = false
    isStopping.value = false
    const keepLocal = slot[assistantIndex].humanReview?.status === "waiting" || slot[assistantIndex].isPaused
    if (keepLocal) {
      persistAssistantSnapshot(conversationId, t, slot[assistantIndex])
    } else {
      await refreshConversations(conversationId)
      if (!pageUnloading) clearStreamLock(conversationId)
    }
    await scrollToBottom()
  }
}

function handleStreamEvent(slot, assistantIndex, raw, conversationId, userContent) {
  try {
    const d = JSON.parse(raw)
    const assistant = slot[assistantIndex]
    if (!assistant) return

    if (d.type === "assistant_chunk" && d.content) {
      assistant.content += d.content
      persistAssistantSnapshot(conversationId, userContent, assistant)
      return
    }
    if (d.type === "finish") {
      publishAssistantEvidence(assistant)
      persistAssistantSnapshot(conversationId, userContent, assistant)
      return
    }
    if (d.type === "title_update" && d.data?.title) {
      touchConversation(d.data.conversation_id || conversationId, d.data.title)
      return
    }
    if (d.type === "human_required") {
      assistant.humanReview = { ...(d.data || {}), status: "waiting" }
      assistant.isStreaming = false
      isStreaming.value = false
      persistAssistantSnapshot(conversationId, userContent, assistant)
      return
    }
    if (d.type === "interrupted") {
      assistant.isPaused = true
      assistant.isStreaming = false
      isStreaming.value = false
      isStopping.value = false
      assistant.transcript.push({
        kind: "thinking",
        data: { content: "执行已暂停，可以补充要求后继续。", status: "paused" },
        content: "执行已暂停，可以补充要求后继续。",
      })
      persistAssistantSnapshot(conversationId, userContent, assistant)
      return
    }
    if (["thinking", "action", "observation", "reflection"].includes(d.type)) {
      updateAssistantProcessMeta(assistant, d.data || {})
      assistant.transcript.push({
        kind: d.type,
        data: d.data || {},
        content: formatStepPayload(d),
      })
      const key = stepKeyForMessage(assistant)
      if (key && !expandedSteps.value.includes(key)) expandedSteps.value.push(key)
      persistAssistantSnapshot(conversationId, userContent, assistant)
      if (key) scrollStepsToBottom(key)
    }
  } catch {}
}

async function stopGeneration() {
  if (!isStreaming.value || !currentId.value || isStopping.value) return
  isStopping.value = true
  try {
    await apiPost(`/conversations/${currentId.value}/interrupt`, {})
  } catch {
    isStopping.value = false
  }
}

async function resumeHumanReview(assistant, approved) {
  if (!assistant?.humanReview || isStreaming.value || !currentId.value) return
  const conversationId = currentId.value
  const slot = initSlot(conversationId)
  const assistantIndex = slot.indexOf(assistant)
  if (assistantIndex < 0) return

  const review = { ...assistant.humanReview }
  assistant.humanReview.status = "submitting"
  assistant.isStreaming = true
  isStreaming.value = true
  persistAssistantSnapshot(conversationId, readStreamLock()?.userContent || "", assistant)

  try {
    const res = await fetch(`/api/v1/conversations/${conversationId}/human-review`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ approved, feedback: "" }),
    })
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

    assistant.humanReview = null
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let complete = false
    while (!complete) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        const raw = line.slice(6).trim()
        if (!raw) continue
        if (raw === "[DONE]") {
          complete = true
          break
        }
        handleStreamEvent(slot, assistantIndex, raw, conversationId, readStreamLock()?.userContent || "")
      }
      await scrollToBottom()
    }

    assistant.isStreaming = false
    isStreaming.value = false
    await refreshConversations(conversationId)
    clearStreamLock(conversationId)
  } catch (error) {
    assistant.humanReview = { ...review, status: "waiting" }
    assistant.isStreaming = false
    isStreaming.value = false
    persistAssistantSnapshot(conversationId, readStreamLock()?.userContent || "", assistant)
  }
  await scrollToBottom()
}

function markPageUnloading() {
  pageUnloading = true
}

function readStreamLock() {
  try {
    const raw = localStorage.getItem(STREAM_LOCK_KEY)
    if (!raw) return null
    const lock = JSON.parse(raw)
    if (!lock?.conversationId || Date.now() - Number(lock.updatedAt || lock.createdAt || 0) > STREAM_LOCK_TTL) {
      localStorage.removeItem(STREAM_LOCK_KEY)
      return null
    }
    lock.transcript = normalizeTranscript(lock.transcript || [])
    if (lock.humanReview?.status === "submitting") lock.humanReview.status = "waiting"
    return lock
  } catch {
    localStorage.removeItem(STREAM_LOCK_KEY)
    return null
  }
}

function writeStreamLock(lock) {
  try {
    localStorage.setItem(STREAM_LOCK_KEY, JSON.stringify(lock))
  } catch {}
}

function clearStreamLock(conversationId = null) {
  try {
    const lock = readStreamLock()
    if (!lock) return
    if (!conversationId || lock.conversationId === conversationId) {
      localStorage.removeItem(STREAM_LOCK_KEY)
    }
  } catch {}
}

function persistAssistantSnapshot(conversationId, userContent, assistant) {
  const old = readStreamLock()
  writeStreamLock({
    conversationId,
    userContent,
    assistantLocalId: assistant.localId,
    assistantContent: assistant.content || "",
    transcript: normalizeTranscript(assistant.transcript || []),
    evidenceRefs: normalizeEvidenceRefs(assistant.evidenceRefs || []),
    pendingEvidenceRefs: normalizeEvidenceRefs(assistant.pendingEvidenceRefs || []),
    multiAgent: assistant.multiAgent || null,
    humanReview: assistant.humanReview || null,
    isPaused: Boolean(assistant.isPaused),
    createdAt: old?.createdAt || Date.now(),
    updatedAt: Date.now(),
  })
}

async function restoreStreamLock() {
  const lock = readStreamLock()
  if (!lock) return
  if (conversations.value.length && !conversations.value.some((c) => c.id === lock.conversationId)) {
    clearStreamLock(lock.conversationId)
    return
  }

  currentId.value = lock.conversationId
  await loadMsgs(lock.conversationId, { scroll: false })
  const slot = initSlot(lock.conversationId)
  if (hasFinalAssistantForLock(slot, lock)) {
    clearStreamLock(lock.conversationId)
    return
  }

  if (lock.humanReview) {
    isStreaming.value = false
    ensurePendingAssistant(lock)
    return
  }
  isStreaming.value = true
  ensurePendingAssistant(lock, { resetAssistant: true })
  reconnectStream(lock)
}

function ensurePendingAssistant(lock, options = {}) {
  const { resetAssistant = false } = options
  const slot = initSlot(lock.conversationId)
  pruneDuplicateRestoredUsers(slot, lock.userContent)
  const hasUser = slot.some((m) => (
    m.role === "user"
    && normalizeText(m.content) === normalizeText(lock.userContent)
  ))
  if (!hasUser) {
    slot.push({
      localId: `restored-user-${lock.conversationId}`,
      role: "user",
      content: lock.userContent || "",
    })
  }

  const existing = slot.find((m) => m.localId === lock.assistantLocalId)
  if (existing) {
    existing.isStreaming = !lock.humanReview
    existing.humanReview = lock.humanReview || existing.humanReview || null
    existing.isPaused = Boolean(lock.isPaused || existing.isPaused)
    if (resetAssistant) {
      existing.content = ""
      existing.transcript = []
      existing.evidenceRefs = []
      existing.pendingEvidenceRefs = []
    } else {
      existing.evidenceRefs = []
      existing.pendingEvidenceRefs = normalizeEvidenceRefs(
        lock.pendingEvidenceRefs?.length
          ? lock.pendingEvidenceRefs
          : (lock.evidenceRefs || lock.multiAgent?.evidence_refs || [])
      )
    }
    return existing
  } else {
    const assistant = {
      localId: lock.assistantLocalId || `restored-assistant-${Date.now()}`,
      role: "assistant",
      content: resetAssistant ? "" : (lock.assistantContent || ""),
      transcript: resetAssistant ? [] : normalizeTranscript(lock.transcript || []),
      evidenceRefs: [],
      pendingEvidenceRefs: resetAssistant ? [] : normalizeEvidenceRefs(
        lock.pendingEvidenceRefs?.length
          ? lock.pendingEvidenceRefs
          : (lock.evidenceRefs || lock.multiAgent?.evidence_refs || [])
      ),
      multiAgent: resetAssistant ? null : (lock.multiAgent || null),
      humanReview: lock.humanReview || null,
      isPaused: Boolean(lock.isPaused),
      isStreaming: !lock.humanReview,
    }
    slot.push(assistant)
    const key = stepKeyForMessage(assistant)
    if (assistant.transcript.length && key && !expandedSteps.value.includes(key)) {
      expandedSteps.value.push(key)
    }
    return assistant
  }
}

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim()
}

function pruneDuplicateRestoredUsers(slot, userContent) {
  const normalized = normalizeText(userContent)
  const hasPersistedUser = slot.some((m) => (
    m.role === "user"
    && m.id
    && normalizeText(m.content) === normalized
  ))
  if (!hasPersistedUser) return
  for (let i = slot.length - 1; i >= 0; i -= 1) {
    const m = slot[i]
    if (
      m.role === "user"
      && !m.id
      && String(m.localId || "").startsWith("restored-user-")
      && normalizeText(m.content) === normalized
    ) {
      slot.splice(i, 1)
    }
  }
}

function dedupeRestoredUsers(slot) {
  const persistedUserContent = new Set(
    slot
      .filter((m) => m.role === "user" && m.id)
      .map((m) => normalizeText(m.content))
  )
  return slot.filter((m) => {
    if (
      m.role === "user"
      && !m.id
      && String(m.localId || "").startsWith("restored-user-")
      && persistedUserContent.has(normalizeText(m.content))
    ) {
      return false
    }
    return true
  })
}

function dedupeFinalMessages(slot) {
  const output = []
  for (const message of slot) {
    const prev = output[output.length - 1]
    if (
      prev
      && message.role === "user"
      && prev.role === "user"
      && normalizeText(prev.content) === normalizeText(message.content)
    ) {
      if (!prev.id && message.id) output[output.length - 1] = message
      continue
    }

    if (
      prev
      && message.role === "assistant"
      && prev.role === "assistant"
      && !prev.isStreaming
      && !message.isStreaming
    ) {
      const sameContent = normalizeText(prev.content) === normalizeText(message.content)
      const bothFinal = prev.id && message.id
      if (sameContent || bothFinal) {
        output[output.length - 1] = preferRicherAssistant(prev, message)
        continue
      }
    }

    output.push(message)
  }
  return output
}

function preferRicherAssistant(a, b) {
  const aSteps = a.transcript?.length || 0
  const bSteps = b.transcript?.length || 0
  if (bSteps > aSteps) return b
  if (aSteps > bSteps) return a
  const aStepScore = transcriptCompleteness(a.transcript)
  const bStepScore = transcriptCompleteness(b.transcript)
  if (bStepScore > aStepScore) return b
  if (aStepScore > bStepScore) return a
  return String(b.content || "").length >= String(a.content || "").length ? b : a
}

function transcriptCompleteness(transcript = []) {
  return normalizeTranscript(transcript).reduce((score, step) => {
    const data = stepData(step)
    if (step.kind === "action" && data.tool) score += 3
    if (step.kind === "action" && data.params) score += 2
    if (step.kind === "observation" && (data.formatted || data.raw || data.result || data.content)) score += 2
    if (step.kind === "reflection" && (data.overall || data.content)) score += 2
    if (step.content) score += 1
    return score
  }, 0)
}

function hasFinalAssistantForLock(slot, lock) {
  const userIndex = findLastIndex(slot, (m) => m.role === "user" && m.content === lock.userContent)
  if (userIndex < 0) return false
  return slot.slice(userIndex + 1).some((m) => (
    m.role === "assistant"
    && !m.isStreaming
    && !!m.id
    && !!String(m.content || "").trim()
  ))
}

function findLastIndex(items, predicate) {
  for (let i = items.length - 1; i >= 0; i -= 1) {
    if (predicate(items[i], i)) return i
  }
  return -1
}

async function reconnectStream(lock) {
  const slot = initSlot(lock.conversationId)
  const assistant = ensurePendingAssistant(lock)
  const assistantIndex = slot.indexOf(assistant)
  if (assistantIndex < 0) {
    startRestorePolling(lock)
    return
  }

  try {
    const res = await fetch(`/api/v1/conversations/${lock.conversationId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({
        content: lock.userContent || "",
        enable_agent: true,
        reconnect: true,
      }),
    })

    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let doneByEvent = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        const raw = line.slice(6).trim()
        if (!raw) continue
        if (raw === "[DONE]") {
          doneByEvent = true
          break
        }
        handleStreamEvent(slot, assistantIndex, raw, lock.conversationId, lock.userContent || "")
      }

      await scrollToBottom()
      if (doneByEvent) break
    }

    slot[assistantIndex].isStreaming = false
    isStreaming.value = false
    await refreshConversations(lock.conversationId)
    clearStreamLock(lock.conversationId)
    await scrollToBottom()
  } catch {
    isStreaming.value = true
    ensurePendingAssistant(lock)
    startRestorePolling(lock)
  }
}

function startRestorePolling(lock) {
  stopRestorePolling()
  restorePollTimer = window.setInterval(async () => {
    const latestLock = readStreamLock()
    if (!latestLock || latestLock.conversationId !== lock.conversationId) {
      stopRestorePolling()
      return
    }
    let latestMessages = []
    try {
      const ms = (await apiGet(`/conversations/${latestLock.conversationId}/messages`)) || []
      latestMessages = ms.map(normalizeMessage)
    } catch {
      latestMessages = []
    }

    if (hasFinalAssistantForLock(latestMessages, latestLock)) {
      const slot = initSlot(latestLock.conversationId)
      slot.splice(0, slot.length, ...latestMessages)
      isStreaming.value = false
      clearStreamLock(latestLock.conversationId)
      stopRestorePolling()
      await refreshConversations(latestLock.conversationId)
      await scrollToBottom()
      return
    }

    // Keep the restored local snapshot stable while the backend is still running.
    // Replacing the message list here would collapse/scroll the Steps panel every poll.
    isStreaming.value = true
    ensurePendingAssistant(latestLock)
  }, 2000)
}

function stopRestorePolling() {
  if (restorePollTimer) {
    window.clearInterval(restorePollTimer)
    restorePollTimer = null
  }
}

function normalizeMessage(m) {
  const metadata = m.metadata || m.msg_metadata || {}
  const multiAgent = metadata.multi_agent || m.multiAgent || null
  const evidenceRefs = normalizeEvidenceRefs(m.evidenceRefs || metadata.evidence_refs || multiAgent?.evidence_refs || [])
  return {
    ...m,
    transcript: normalizeTranscript(m.transcript || metadata.transcript || []),
    runMeta: metadata.run_meta || null,
    multiAgent,
    evidenceRefs,
    isStreaming: false,
  }
}

function normalizeEvidenceRefs(refs) {
  if (!Array.isArray(refs)) return []
  return refs
    .filter((ref) => ref && typeof ref === "object")
    .map((ref, index) => ({
      index: Number(ref.index || index + 1),
      title: ref.title || ref.doc_id || "参考资料",
      doc_id: ref.doc_id || "",
      chunk_id: ref.chunk_id ?? "",
      score: ref.score,
      snippet: ref.snippet || "",
      category: ref.category || "",
      source_url: ref.source_url || ref.url || "",
    }))
}

function updateAssistantProcessMeta(assistant, data = {}) {
  if (!assistant) return
  const next = { ...(assistant.multiAgent || {}) }
  if (Array.isArray(data.evidence_refs)) {
    assistant.pendingEvidenceRefs = normalizeEvidenceRefs(data.evidence_refs)
    next.evidence_refs = assistant.pendingEvidenceRefs
  }
  if (Array.isArray(data.rule_hits)) next.rule_hits = data.rule_hits
  if (data.agent === "judge" || data.risk_level || data.confidence) {
    next.judge = data
  }
  if (Object.keys(next).length) assistant.multiAgent = next
}

function publishAssistantEvidence(assistant) {
  if (!assistant) return
  const pending = normalizeEvidenceRefs(assistant.pendingEvidenceRefs || [])
  const refs = pending.length
    ? pending
    : normalizeEvidenceRefs(assistant.multiAgent?.evidence_refs || [])
  assistant.evidenceRefs = refs
  assistant.pendingEvidenceRefs = []
  if (assistant.multiAgent) assistant.multiAgent.evidence_refs = refs
}

function normalizeTranscript(transcript) {
  if (!Array.isArray(transcript)) return []
  return transcript.map((step) => {
    if (!step || typeof step !== "object") return step
    const data = step.data && typeof step.data === "object"
      ? step.data
      : Object.fromEntries(
          Object.entries(step).filter(([key]) => !["kind", "content", "data"].includes(key))
        )
    return {
      ...step,
      data,
      content: step.content || formatStoredStepPayload(step.kind, data),
    }
  })
}

function formatStoredStepPayload(kind, data = {}) {
  if (kind === "action") {
    const params = data.params ? ` ${JSON.stringify(data.params, null, 2)}` : ""
    return `${data.tool || "tool"}${params}`
  }
  if (kind === "observation") {
    const value = data.raw || data.result || data.content || data.formatted || ""
    return typeof value === "string" ? value : JSON.stringify(value, null, 2)
  }
  return data.content || ""
}

function touchConversation(id, title) {
  const index = conversations.value.findIndex((c) => c.id === id)
  if (index < 0) return
  const c = { ...conversations.value[index] }
  if (!c.title || c.title === "新对话") c.title = title.slice(0, 28)
  c.updated_at = new Date().toISOString()
  conversations.value.splice(index, 1)
  conversations.value.unshift(c)
}

function formatStepPayload(d) {
  const data = d.data || {}
  if (d.type === "action") {
    const tool = d.data?.tool || "工具"
    const params = data.params ? ` ${JSON.stringify(data.params, null, 2)}` : ""
    return `${tool}${params}`
  }
  if (d.type === "observation") {
    const value = data.raw || data.result || data.content || data.formatted || ""
    return typeof value === "string" ? value : JSON.stringify(value, null, 2)
  }
  return data.content || d.content || ""
}

const intentLabels = {
  capability: "能力咨询",
  live_info: "实时查询",
  research: "深度调研",
  smalltalk: "日常对话",
  coding: "代码任务",
  explanation: "概念讲解",
  learning: "学习任务",
  general: "普通问答",
}

const levelLabels = {
  low: "低风险",
  medium: "需注意",
  high: "高风险",
}

const toolLabels = {
  datetime: "查询时间",
  web_search: "搜索互联网",
  url_fetch: "阅读网页",
  code_exec: "运行代码",
  knowledge_search: "检索学习资料",
  file_read: "读取文件",
  file_write: "写入文件",
  calculator: "计算",
}

function toolLabel(tool) {
  return toolLabels[tool] || tool || "工具"
}

function stepLabel(step) {
  const kind = typeof step === "string" ? step : step?.kind
  const data = typeof step === "string" ? {} : stepData(step)
  if (kind === "action" && data.tool) return `${data.agent_name || "生成 Agent"} · 工具调用`
  if (kind === "observation" && data.tool) return `${data.agent_name || "生成 Agent"} · 工具结果`
  if (data.agent_name) return data.agent_name
  if (data.agent === "diagnosis") return "任务识别 Agent"
  if (data.agent === "retrieval") return "检索 Agent"
  if (data.agent === "generation") return "生成 Agent"
  if (data.agent === "review") return "审核 Agent"
  if (data.agent === "judge") return "裁判 Agent"
  if (data.agent === "rules") return "规则校验"
  if (data.agent === "human_gate") return "人工确认"
  return {
    thinking: "思考",
    action: "调用工具",
    observation: "读取结果",
    reflection: "反思检查",
  }[kind] || "步骤"
}

function stepContent(step) {
  if (step.content) return String(step.content)
  const data = stepData(step)
  if (step.kind === "action") {
    return `${data.tool || "tool"}${data.params ? ` ${JSON.stringify(data.params, null, 2)}` : ""}`
  }
  if (step.kind === "observation") {
    const value = data.raw || data.result || data.content || data.formatted || data
    return typeof value === "string" ? value : JSON.stringify(value, null, 2)
  }
  return typeof data === "string" ? data : JSON.stringify(data, null, 2)
}

function stepData(step) {
  if (!step || typeof step !== "object") return {}
  if (step.data && typeof step.data === "object") return step.data
  return Object.fromEntries(
    Object.entries(step).filter(([key]) => !["kind", "content", "data"].includes(key))
  )
}

function prettyJson(value) {
  if (value === undefined || value === null || value === "") return ""
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function shortText(value, max = 180) {
  const text = String(value || "").replace(/\s+/g, " ").trim()
  return text.length > max ? `${text.slice(0, max)}...` : text
}

function stepTransition(step, index = 0, transcript = []) {
  const data = stepData(step)
  if (data.transition) return shortText(data.transition, 180)

  const previous = index > 0 ? stepData(transcript[index - 1]) : {}
  if (step.kind === "action") {
    const tool = toolLabel(data.tool)
    if (previous.overall === "FAIL" || previous.overall === "CHECK") {
      return `检查发现还需要补充信息，接下来使用${tool}进行修正。`
    }
    if (index > 0) return `基于上一项结果，接下来使用${tool}继续完成任务。`
    return `为获得回答所需的信息，接下来使用${tool}。`
  }

  if (step.kind === "observation" && data.tool) return ""
  return {
    diagnosis: "先识别问题类型和目标，再确定本轮处理路径。",
    retrieval: "任务范围已经明确，接下来查找与问题直接相关的资料。",
    rules: "资料策略已经确定，接下来检查回答边界和来源要求。",
    human_gate: "规则检查发现需要确认，接下来由你决定是否继续。",
    generation: previous.tool
      ? "工具结果已经返回，接下来组织信息并判断是否需要继续验证。"
      : "任务信息已经准备，接下来组织回答并判断是否需要工具。",
    review: "回答草稿已经形成，接下来检查事实依据和完整性。",
    judge: "回答已经完成，最后核对可信度和风险。",
  }[data.agent] || ""
}

function stepBadge(step) {
  const data = stepData(step)
  if (data.agent === "diagnosis") return data.intent_label || intentLabels[data.intent] || data.intent || ""
  if (data.agent === "retrieval") return Array.isArray(data.evidence_refs) ? `${data.evidence_refs.length} 条` : "ok"
  if (data.agent === "rules") return data.success === false ? "需注意" : "通过"
  if (data.agent === "human_gate") return data.requires_human ? "待确认" : "通过"
  if (data.agent === "judge") return levelLabels[data.risk_level] || data.risk_level || ""
  if (step.kind === "action") return data.auto ? "自动" : "执行"
  if (step.kind === "observation") return data.success === false ? "失败" : "完成"
  if (step.kind === "reflection") {
    return {
      PASS: "通过",
      FAIL: "修正",
      MEMORY: "历史经验",
      POLICY: "响应策略",
      CHECK: "需注意",
    }[data.overall] || data.overall || ""
  }
  return ""
}

function stepSummary(step) {
  const data = stepData(step)
  if (step.kind === "action") {
    const params = data.params || {}
    const target = params.query || params.focus || params.path || params.operation || params.lang || ""
    return `${toolLabel(data.tool)}${target ? `：${shortText(target, 100)}` : ""}`
  }
  if (step.kind === "observation") {
    if (Array.isArray(data.evidence_refs)) {
      if (!data.evidence_refs.length) return shortText(data.formatted || "本轮没有需要展示的参考资料")
      const names = data.evidence_refs.slice(0, 3).map(evidenceTitle).join("、")
      return `找到 ${data.evidence_refs.length} 条参考来源：${names}`
    }
    if (Array.isArray(data.rule_hits)) {
      const passed = data.rule_hits.filter((hit) => hit.passed).length
      return `完成 ${data.rule_hits.length} 项回答检查，${passed} 项通过`
    }
    if (data.success === false) {
      return shortText(data.formatted || data.error || data.content || "工具执行失败", 220)
    }
    if (data.tool === "datetime" && data.raw?.datetime) {
      return `当前时间：${data.raw.datetime}（${data.raw.timezone || "本地时区"}）`
    }
    if (data.tool === "web_search" && Array.isArray(data.raw?.results)) {
      const names = data.raw.results.slice(0, 3).map((item) => item.title).filter(Boolean).join("、")
      return `找到 ${data.raw.results.length} 条网页结果${names ? `：${names}` : ""}`
    }
    if (data.tool === "url_fetch") {
      return shortText(data.formatted || "已读取并提炼网页内容", 220)
    }
    return shortText(data.formatted || data.content || data.result || data.raw || "已读取工具结果")
  }
  if (step.kind === "reflection") {
    if (data.agent === "judge") {
      const verdict = data.overall === "PASS" ? "最终检查通过" : data.overall === "CHECK" ? "最终检查发现注意项" : "最终检查未通过"
      return `${verdict}：${data.content || data.proposed_action || "已完成回答检查"}`
    }
    if (data.overall === "MEMORY") return "已读取过往反思，用于调整本轮执行策略"
    if (data.overall === "POLICY") return data.content || "已选择本轮响应策略"
    const verdict = data.overall === "PASS" ? "通过" : data.overall === "FAIL" ? "需要修正" : data.overall === "CHECK" ? "需要注意" : data.overall || "已检查"
    return shortText(`${verdict}：${data.content || step.content || "已完成反思检查"}`, 220)
  }
  return shortText(step.content || data.content || "")
}

function stepDetail(step) {
  const data = stepData(step)
  if (step.kind === "action") return prettyJson(data.params)
  if (step.kind === "observation") {
    if (Array.isArray(data.evidence_refs)) {
      return data.evidence_refs.map((ref) => {
        const formattedScore = formatScore(ref.score, ref)
        const score = formattedScore ? ` · ${formattedScore}` : ""
        const snippet = ref.snippet ? `\n${ref.snippet}` : ""
        return `${ref.index || ""}. ${evidenceTitle(ref)}${score}${snippet}`
      }).join("\n\n")
    }
    if (Array.isArray(data.rule_hits)) {
      return data.rule_hits.map((hit) => {
        const status = hit.passed ? "PASS" : "CHECK"
        return `${status} ${hit.name || hit.rule_id}: ${hit.message || ""}`
      }).join("\n")
    }
    if (data.success === false) {
      return prettyJson(data.raw || data.result || data.formatted || data.error || step.content || "")
    }
    if (data.tool === "web_search" && Array.isArray(data.raw?.results)) {
      return data.raw.results.slice(0, 5).map((item, index) => (
        `${index + 1}. ${item.title || "网页结果"}${item.url ? `\n${item.url}` : ""}`
      )).join("\n\n")
    }
    if (data.tool === "datetime" && data.raw?.datetime) {
      return `时间：${data.raw.datetime}\n时区：${data.raw.timezone || ""}`
    }
    if (data.tool === "url_fetch") return String(data.formatted || "")
    const raw = data.raw || data.result
    if (raw) return prettyJson(raw)
    const text = data.formatted || data.content || step.content || ""
    return String(text).length > 220 ? String(text) : ""
  }
  if (step.kind === "reflection") {
    const lines = []
    if (data.action_plan) lines.push(`下一步：${data.action_plan}`)
    if (data.strategy_hint) lines.push(`可复用经验：${data.strategy_hint}`)
    if (data.scores) {
      const labels = {
        factual_grounding: "事实依据",
        verification_depth: "验证充分度",
        completeness: "完整性",
        directness: "直接性",
      }
      const scores = Object.entries(data.scores)
        .map(([key, value]) => `${labels[key] || key}：${Math.round(Number(value) * 100)}%`)
        .join("\n")
      lines.push(scores)
    }
    return lines.join("\n")
  }
  const text = stepContent(step)
  return String(text).length > 220 ? String(text) : ""
}

function stepKey(message, index = 0) {
  return `steps-${message?.localId || message?.id || index}`
}

function stepKeyForMessage(assistant) {
  const index = visibleMessages.value.indexOf(assistant)
  return index >= 0 ? stepKey(assistant, index) : ""
}

function setStepsBodyRef(key, el) {
  if (!key) return
  if (el) stepsBodyRefs.set(key, el)
  else stepsBodyRefs.delete(key)
}

function scrollStepsToBottom(key) {
  nextTick(() => {
    const el = stepsBodyRefs.get(key)
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

function toggleSteps(message, index) {
  suppressAutoScrollUntil = Date.now() + 2500
  const key = stepKey(message, index)
  const i = expandedSteps.value.indexOf(key)
  if (i >= 0) expandedSteps.value.splice(i, 1)
  else {
    expandedSteps.value.push(key)
    scrollStepsToBottom(key)
  }
}

function evidenceKey(message, index = 0) {
  const conv = currentId.value || "no-conv"
  const refSig = (message?.evidenceRefs || [])
    .map((ref) => `${ref.doc_id || ""}:${ref.chunk_id ?? ""}:${ref.index || ""}`)
    .join("|")
  const stable = message?.id || message?.localId || refSig || index
  return `evidence-${conv}-${stable}`
}

function toggleEvidence(message, index) {
  const key = evidenceKey(message, index)
  const i = expandedEvidence.value.indexOf(key)
  if (i >= 0) expandedEvidence.value.splice(i, 1)
  else expandedEvidence.value.push(key)
}

function evidenceTitle(ref) {
  return ref?.title || ref?.doc_id || "参考资料"
}

async function openEvidence(ref) {
  if ((!ref?.doc_id || String(ref.doc_id).startsWith("course:") || String(ref.doc_id).startsWith("web:")) && ref?.source_url) {
    window.open(ref.source_url, "_blank", "noopener,noreferrer")
    return
  }
  if (String(ref?.doc_id || "").startsWith("course:") || String(ref?.doc_id || "").startsWith("web:")) {
    evidenceModal.open = true
    evidenceModal.loading = false
    evidenceModal.error = ""
    evidenceModal.ref = ref
    evidenceModal.data = {
      title: evidenceTitle(ref),
      content: ref.snippet || "暂无可展示的原文片段",
      source_url: ref.source_url || "",
    }
    return
  }
  evidenceModal.open = true
  evidenceModal.loading = true
  evidenceModal.error = ""
  evidenceModal.ref = ref
  evidenceModal.data = null
  try {
    const docId = encodeURIComponent(ref.doc_id || "")
    const chunkId = encodeURIComponent(ref.chunk_id ?? 0)
    evidenceModal.data = await apiGet(`/knowledge-base/documents/${docId}/chunks/${chunkId}?neighbors=1`)
  } catch (error) {
    evidenceModal.error = error?.message || "原文加载失败"
  } finally {
    evidenceModal.loading = false
  }
}

function closeEvidence() {
  evidenceModal.open = false
  evidenceModal.loading = false
  evidenceModal.error = ""
  evidenceModal.ref = null
  evidenceModal.data = null
}

function resetConversationUiState() {
  expandedEvidence.value = []
  closeEvidence()
}

function formatScore(score, ref = null) {
  // Ranking heuristics and web-provider scores are not calibrated probabilities.
  const docId = String(ref?.doc_id || "")
  if (docId.startsWith("course:") || docId.startsWith("web:")) return ""
  const value = Number(score)
  if (!Number.isFinite(value)) return ""
  return `相关度 ${Math.round(value * 100)}%`
}

function formatTime(value) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })
}

function resizeInput() {
  nextTick(() => {
    const el = inputRef.value
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  })
}

async function scrollToBottom() {
  if (Date.now() < suppressAutoScrollUntil) return
  await nextTick()
  const el = msgRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}
</script>

<style scoped>
.chat-page {
  height: calc(100vh - 96px);
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
}

.conversation-panel {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  border-radius: 18px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.new-chat {
  width: 100%;
  height: 42px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--text-primary);
  color: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 650;
}

.new-chat:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.new-chat span:first-child {
  font-size: 20px;
  line-height: 1;
}

.panel-label {
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  margin: 18px 8px 8px;
}

.conversation-list {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

.conversation-item {
  width: 100%;
  border: 0;
  background: transparent;
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
  cursor: pointer;
  color: var(--text-primary);
}

.conversation-item:hover,
.conversation-item.active {
  background: var(--bg-hover);
}

.conversation-item:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.conversation-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.conversation-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.empty-list {
  color: var(--text-tertiary);
  padding: 24px 8px;
  text-align: center;
  font-size: 13px;
}

.chat-main {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 18px;
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.message-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 32px 24px 20px;
  scroll-behavior: smooth;
}

.human-review-card {
  margin: 10px 0 14px;
  padding: 16px;
  border: 1px solid #d8dee8;
  border-left: 3px solid #2f6f5e;
  border-radius: 12px;
  background: #fbfcfc;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.human-review-copy strong {
  color: var(--text-primary);
  font-size: 14px;
}

.human-review-copy p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.human-review-copy small {
  display: block;
  margin-top: 8px;
  color: var(--text-tertiary);
}

.human-review-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.human-review-actions button {
  border-radius: 9px;
  padding: 8px 13px;
  cursor: pointer;
  font-weight: 650;
}

.human-review-actions button:disabled {
  opacity: 0.55;
  cursor: wait;
}

.review-cancel {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.review-approve {
  border: 1px solid #2f6f5e;
  background: #2f6f5e;
  color: #fff;
}

.welcome {
  max-width: 720px;
  margin: 13vh auto 0;
  text-align: center;
}

.welcome-mark {
  width: 68px;
  height: 68px;
  border-radius: 22px;
  margin: 0 auto 20px;
  display: grid;
  place-items: center;
  background: var(--text-primary);
  color: var(--bg-secondary);
  font-weight: 800;
  letter-spacing: -0.04em;
}

.welcome h1 {
  font-size: clamp(28px, 5vw, 44px);
  line-height: 1.1;
  letter-spacing: -0.04em;
  margin-bottom: 12px;
}

.welcome p {
  color: var(--text-secondary);
  margin: 0 auto 28px;
  max-width: 560px;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.prompt-grid button {
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  color: var(--text-primary);
  border-radius: 14px;
  padding: 13px 14px;
  text-align: left;
  cursor: pointer;
}

.prompt-grid button:hover {
  border-color: var(--border-hover);
  background: var(--bg-hover);
}

.message-row {
  max-width: 920px;
  margin: 0 auto 26px;
  display: flex;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-card {
  width: min(100%, 860px);
}

.message-row.user .message-card {
  width: auto;
  max-width: min(680px, 78%);
}

.user-bubble {
  background: var(--text-primary);
  color: var(--bg-secondary);
  border-radius: 20px 20px 4px 20px;
  padding: 12px 16px;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

.assistant-content {
  color: var(--text-primary);
  line-height: 1.8;
}

.evidence-card {
  margin-top: 14px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-primary);
  overflow: hidden;
}

.evidence-head {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
}

.evidence-head span:first-child {
  color: var(--text-primary);
  font-weight: 700;
}

.evidence-list {
  border-top: 1px solid var(--border-color);
  padding: 4px 12px 10px;
}

.evidence-item {
  padding: 10px 0;
}

.evidence-item + .evidence-item {
  border-top: 1px solid var(--border-color);
}

.evidence-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.evidence-link {
  border: 0;
  background: transparent;
  color: var(--text-primary);
  padding: 0;
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.evidence-link:hover {
  color: var(--accent-primary);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.evidence-score {
  flex: none;
  color: var(--text-tertiary);
  font-weight: 500;
}

.evidence-item p {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.source-modal {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.28);
  backdrop-filter: blur(6px);
}

.source-dialog {
  width: min(760px, 100%);
  max-height: min(78vh, 760px);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: var(--bg-primary);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.source-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border-color);
}

.source-head p {
  margin: 0 0 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.source-head h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
  line-height: 1.35;
}

.source-close {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-color);
  border-radius: 50%;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
}

.source-body {
  padding: 16px 20px 20px;
  overflow: auto;
}

.source-state {
  padding: 42px 20px;
  color: var(--text-secondary);
  text-align: center;
}

.source-state.error {
  color: var(--danger-color, #b91c1c);
}

.source-external {
  display: inline-flex;
  margin-bottom: 14px;
  color: var(--accent-primary);
  font-weight: 700;
  text-decoration: none;
}

.source-external:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.source-chunk {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 12px 14px;
  background: var(--bg-secondary);
}

.source-chunk + .source-chunk {
  margin-top: 10px;
}

.source-chunk.active {
  border-color: color-mix(in srgb, var(--accent-primary) 45%, var(--border-color));
  background: color-mix(in srgb, var(--accent-primary) 6%, var(--bg-secondary));
}

.source-chunk-label {
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 6px;
}

.source-chunk p {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.steps-card {
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  border-radius: 14px;
  margin-bottom: 14px;
  overflow: hidden;
}

.steps-head {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
}

.steps-head span:first-child {
  color: var(--text-primary);
  font-weight: 700;
}

.steps-body {
  border-top: 1px solid var(--border-color);
  padding: 8px 12px 12px;
  max-height: 520px;
  overflow: auto;
}

.step-line {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 10px;
  padding: 11px 0;
  position: relative;
}

.step-line + .step-line::before {
  content: "";
  position: absolute;
  left: 12px;
  top: -8px;
  width: 1px;
  height: 16px;
  background: var(--border-color);
}

.step-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 700;
}

.step-reflection {
  border-radius: 12px;
  background: color-mix(in srgb, var(--accent-primary) 7%, transparent);
  margin: 4px 0;
  padding: 12px 10px;
}

.step-reflection .step-index {
  background: var(--accent-primary);
  color: var(--bg-primary);
}

.step-reflection .step-title {
  color: var(--accent-primary);
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 24px;
}

.step-transition {
  margin: 0 0 5px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.55;
  word-break: break-word;
}

.step-title {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.step-badge {
  border: 1px solid var(--border-color);
  border-radius: 999px;
  color: var(--text-tertiary);
  background: var(--bg-secondary);
  padding: 1px 7px;
  font-size: 11px;
  line-height: 18px;
  text-transform: uppercase;
}

.step-badge-observation,
.step-badge-reflection {
  color: var(--accent-primary);
  border-color: color-mix(in srgb, var(--accent-primary) 35%, var(--border-color));
}

.step-summary {
  color: var(--text-secondary);
  margin-top: 3px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.step-detail {
  margin-top: 7px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-secondary);
  padding: 8px 10px;
}

.step-detail pre {
  margin: 0;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  font: 12px/1.6 "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

.streaming-dots {
  display: inline-flex;
  gap: 6px;
  padding: 10px 0;
}

.streaming-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: pulse 1s infinite ease-in-out;
}

.streaming-dots span:nth-child(2) { animation-delay: 0.15s; }
.streaming-dots span:nth-child(3) { animation-delay: 0.3s; }

@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-3px); }
}

.composer {
  margin: 0 auto 18px;
  width: min(920px, calc(100% - 32px));
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: var(--bg-primary);
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 10px;
  box-shadow: var(--shadow-sm);
}

.composer textarea {
  flex: 1;
  resize: none;
  min-height: 28px;
  max-height: 160px;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  line-height: 1.7;
  padding: 4px 6px;
}

.composer textarea::placeholder {
  color: var(--text-tertiary);
}

.composer button {
  border: 0;
  border-radius: 14px;
  background: var(--text-primary);
  color: var(--bg-secondary);
  padding: 9px 16px;
  cursor: pointer;
  font-weight: 700;
}

.composer button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.composer .stop-generation {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

@media (max-width: 920px) {
  .chat-page {
    grid-template-columns: 1fr;
    height: auto;
    min-height: calc(100vh - 92px);
  }

  .conversation-panel {
    display: none;
  }

  .chat-main {
    min-height: calc(100vh - 92px);
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }

  .message-row.user .message-card {
    max-width: 88%;
  }
}
</style>
