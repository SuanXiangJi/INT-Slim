<template>
  <Transition name="profile-fade">
    <div v-if="open" class="profile-overlay" @click.self="$emit('close')">
      <div class="profile-panel">
        <header class="profile-header">
          <div class="profile-title">
            <span class="profile-avatar">{{ initials }}</span>
            <div>
              <h2>用户画像</h2>
              <p class="profile-subtitle">persona for personalising responses</p>
            </div>
          </div>
          <button class="close-btn" @click="$emit('close')" aria-label="关闭">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </button>
        </header>

        <div v-if="loading && !profile" class="profile-loading">
          <span>加载中...</span>
        </div>

        <div v-else-if="profile" class="profile-body">
          <!-- Section: identity -->
          <section class="profile-section">
            <h3>身份 / Identity</h3>
            <div class="form-grid">
              <label class="form-field">
                <span>显示名称</span>
                <input
                  v-model="editable.display_name"
                  type="text"
                  maxlength="64"
                  placeholder="希望被如何称呼"
                />
              </label>
              <label class="form-field">
                <span>职业</span>
                <input
                  v-model="editable.profession"
                  type="text"
                  maxlength="128"
                  placeholder="例如 后端工程师 / 学生"
                />
              </label>
              <label class="form-field">
                <span>所在地区</span>
                <input
                  v-model="editable.location"
                  type="text"
                  maxlength="128"
                  placeholder="例如 上海 / 北京"
                />
              </label>
              <label class="form-field">
                <span>首选语言</span>
                <select v-model="editable.language_preference">
                  <option value="zh-CN">中文 (zh-CN)</option>
                  <option value="en-US">English (en-US)</option>
                  <option value="mixed">中英混合 (mixed)</option>
                </select>
              </label>
            </div>
          </section>

          <!-- Section: interests -->
          <section class="profile-section">
            <div class="section-header">
              <h3>兴趣 / Interests</h3>
              <span class="hint">回车添加</span>
            </div>
            <div class="tag-input">
              <span v-for="(tag, idx) in editable.interests" :key="`int-${idx}`" class="tag">
                {{ tag }}
                <button @click="removeAt(editable.interests, idx)" aria-label="删除">×</button>
              </span>
              <input
                v-model="newInterest"
                @keydown.enter.prevent="addInterest"
                placeholder="+ 添加兴趣"
              />
            </div>
          </section>

          <!-- Section: expertise -->
          <section class="profile-section">
            <div class="section-header">
              <h3>专长 / Expertise</h3>
              <span class="hint">{{ editable.expertise_pairs.length }} 项</span>
            </div>
            <div class="tag-input">
              <span
                v-for="(item, idx) in editable.expertise_pairs"
                :key="`exp-${idx}`"
                class="tag tag-expertise"
                :data-level="item.level"
              >
                {{ item.area }}
                <select
                  class="level-picker"
                  :value="item.level"
                  @change="setExpertiseLevel(idx, $event.target.value)"
                >
                  <option value="beginner">beginner</option>
                  <option value="intermediate">intermediate</option>
                  <option value="advanced">advanced</option>
                </select>
                <button @click="removeExpertise(idx)" aria-label="删除">×</button>
              </span>
              <div class="add-expertise">
                <input v-model="newExpertise" placeholder="领域" @keydown.enter.prevent="addExpertise" />
                <button @click="addExpertise">+ 添加</button>
              </div>
            </div>
          </section>

          <!-- Section: preferences -->
          <section class="profile-section">
            <h3>风格偏好 / Style preferences</h3>
            <div class="kv-list">
              <div v-for="(item, idx) in editable.preferences_pairs" :key="`pref-${idx}`" class="kv-row">
                <input v-model="item.key" placeholder="key" />
                <span class="kv-sep">=</span>
                <input v-model="item.value" placeholder="value" />
                <button @click="removeAt(editable.preferences_pairs, idx)">×</button>
              </div>
              <button class="add-kv" @click="editable.preferences_pairs.push({ key: '', value: '' })">+ 添加偏好</button>
            </div>
          </section>

          <!-- Section: portrait -->
          <section class="profile-section">
            <div class="section-header">
              <h3>AI 总结 / Portrait</h3>
              <span class="hint">{{ profile.analyzed_msg_count }} messages analysed</span>
            </div>
            <p class="portrait-text" :class="{ empty: !profile.portrait_summary }">
              {{ profile.portrait_summary || '尚未生成 - 点击下方"重新分析"由 LLM 推断。' }}
            </p>
          </section>

          <!-- Status footer -->
          <div class="profile-meta">
            <span>最后分析: {{ profile.last_analyzed_at || '—' }}</span>
            <span>自动更新: <strong>{{ profile.auto_update_enabled ? '开' : '关' }}</strong></span>
          </div>
        </div>

        <!-- Footer / actions -->
        <footer v-if="profile" class="profile-footer">
          <div class="footer-left">
            <button class="ghost-btn" :disabled="busy" @click="onReset">重置</button>
            <label class="toggle-row">
              <input type="checkbox" v-model="editable.auto_update_enabled" />
              <span>对话后自动分析</span>
            </label>
          </div>
          <div class="footer-right">
            <button class="ghost-btn" :disabled="busy" @click="onAnalyze">
              {{ busy.analyze ? '分析中...' : '重新分析' }}
            </button>
            <button class="primary-btn" :disabled="busy.save" @click="onSave">
              {{ busy.save ? '保存中...' : '保存' }}
            </button>
          </div>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getMyProfile,
  updateMyProfile,
  analyzeMyProfile,
  resetMyProfile,
} from '@/utils/api'

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'updated'])

const loading = ref(false)
const busy = reactive({ save: false, analyze: false })
const profile = ref(null)
const newInterest = ref('')
const newExpertise = ref('')

const editable = reactive({
  display_name: '',
  profession: '',
  location: '',
  language_preference: 'zh-CN',
  interests: [],
  expertise_pairs: [],   // [{area, level}]
  preferences_pairs: [], // [{key, value}]
  auto_update_enabled: true,
})

const initials = computed(() => {
  const s = (profile.value?.display_name || profile.value?.user_id || '?').trim()
  if (!s) return '?'
  // First character; for CJK take first, for Latin first letter
  return s[0].toUpperCase()
})

// ── Load / unload ──
watch(
  () => props.open,
  (val) => { if (val) load() }
)

async function load() {
  loading.value = true
  try {
    const data = await getMyProfile(false)
    applyToEditable(data)
  } catch (e) {
    ElMessage.error('加载画像失败: ' + (e.message || e))
  } finally {
    loading.value = false
  }
}

function applyToEditable(data) {
  profile.value = data
  editable.display_name = data.display_name || ''
  editable.profession = data.profession || ''
  editable.location = data.location || ''
  editable.language_preference = data.language_preference || 'zh-CN'
  editable.interests = Array.isArray(data.interests) ? [...data.interests] : []
  editable.expertise_pairs = Object.entries(data.expertise || {}).map(([area, level]) => ({
    area, level,
  }))
  editable.preferences_pairs = Object.entries(data.preferences || {}).map(([key, value]) => ({
    key, value: typeof value === 'object' ? JSON.stringify(value) : String(value),
  }))
  editable.auto_update_enabled = data.auto_update_enabled !== false
}

// ── Tag helpers ──
function addInterest() {
  const v = newInterest.value.trim()
  if (!v) return
  if (!editable.interests.includes(v)) {
    editable.interests.push(v)
  }
  newInterest.value = ''
}

function addExpertise() {
  const v = newExpertise.value.trim()
  if (!v) return
  if (!editable.expertise_pairs.find(e => e.area === v)) {
    editable.expertise_pairs.push({ area: v, level: 'intermediate' })
  }
  newExpertise.value = ''
}

function removeAt(arr, idx) {
  arr.splice(idx, 1)
}

function removeExpertise(idx) {
  editable.expertise_pairs.splice(idx, 1)
}

function setExpertiseLevel(idx, level) {
  editable.expertise_pairs[idx].level = level
}

// ── Actions ──
function buildPatch() {
  const expertise = {}
  for (const { area, level } of editable.expertise_pairs) {
    if (area) expertise[area] = level
  }
  const preferences = {}
  for (const { key, value } of editable.preferences_pairs) {
    const k = (key || '').trim()
    if (!k) continue
    preferences[k] = value
  }
  return {
    display_name: editable.display_name || null,
    profession: editable.profession || null,
    location: editable.location || null,
    language_preference: editable.language_preference,
    interests: editable.interests,
    expertise,
    preferences,
    auto_update_enabled: editable.auto_update_enabled,
  }
}

async function onSave() {
  busy.save = true
  try {
    const data = await updateMyProfile(buildPatch())
    applyToEditable(data)
    ElMessage.success('画像已保存')
    emit('updated', data)
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || e))
  } finally {
    busy.save = false
  }
}

async function onAnalyze() {
  busy.analyze = true
  try {
    const data = await analyzeMyProfile({ force: true, message_count: 20 })
    applyToEditable(data)
    ElMessage.success('已重新分析')
    emit('updated', data)
  } catch (e) {
    ElMessage.error('分析失败: ' + (e.message || e))
  } finally {
    busy.analyze = false
  }
}

async function onReset() {
  try {
    await resetMyProfile()
    await load()
    ElMessage.success('画像已重置')
    emit('updated', profile.value)
  } catch (e) {
    ElMessage.error('重置失败: ' + (e.message || e))
  }
}
</script>

<style scoped>
.profile-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: flex-end;
  z-index: 2000;
}

.profile-panel {
  position: fixed;
  top: 60px;
  right: 0;
  bottom: 0;
  width: 420px;
  max-width: 90vw;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  z-index: 200;
  overflow: hidden;
}

.profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 22px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-glass);
  backdrop-filter: var(--blur-glass);
  -webkit-backdrop-filter: var(--blur-glass);
}

.profile-title {
  display: flex;
  align-items: center;
  gap: 14px;
}

.profile-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--accent-gradient);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
}

.profile-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.profile-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.close-btn svg {
  width: 18px;
  height: 18px;
}

.profile-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}

.profile-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 22px;
}

.profile-section {
  margin-bottom: 24px;
}
.profile-section h3 {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 12px;
}

.profile-section h3 {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-tertiary);
  margin: 0 0 10px;
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.section-header h3 {
  margin: 0;
}

.hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-field > span {
  font-size: 12px;
  color: var(--text-secondary);
}

.form-field input,
.form-field select {
  padding: 8px 12px;
  border: 1.5px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all var(--transition-fast);
}
.form-field input:focus,
.form-field select:focus {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.08);
}

.form-field input:focus,
.form-field select:focus {
  border-color: var(--accent-primary);
}

.tag-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding: 8px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-tertiary);
  min-height: 38px;
}

.tag-input > input {
  flex: 1;
  min-width: 100px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: rgba(255, 126, 95, 0.12);
  color: var(--accent-primary);
  border-radius: 12px;
  font-size: 12px;
}

.tag-expertise {
  background: rgba(102, 126, 234, 0.12);
  color: #667eea;
}

.tag-expertise[data-level="advanced"] {
  background: rgba(76, 175, 80, 0.15);
  color: #2e7d32;
}
.tag-expertise[data-level="intermediate"] {
  background: rgba(33, 150, 243, 0.15);
  color: #1565c0;
}
.tag-expertise[data-level="beginner"] {
  background: rgba(158, 158, 158, 0.18);
  color: #616161;
}

.tag button {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 0 0 4px;
  color: inherit;
  opacity: 0.6;
}

.tag button:hover {
  opacity: 1;
}

.level-picker {
  border: none;
  background: transparent;
  font-size: 11px;
  color: inherit;
  cursor: pointer;
}

.add-expertise {
  display: flex;
  gap: 4px;
  align-items: center;
  flex: 1;
  min-width: 180px;
}

.add-expertise input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.add-expertise button {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border-radius: 4px;
  padding: 3px 8px;
  cursor: pointer;
  font-size: 11px;
}

.add-expertise button:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.kv-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kv-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr auto;
  gap: 6px;
  align-items: center;
}

.kv-row input {
  padding: 6px 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-size: 12px;
  outline: none;
}

.kv-row button {
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: 14px;
}

.kv-sep {
  color: var(--text-tertiary);
  font-size: 12px;
}

.add-kv {
  align-self: flex-start;
  border: 1px dashed var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 11px;
}

.add-kv:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
}

.portrait-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  padding: 10px 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  border-left: 3px solid var(--accent-primary);
  margin: 0;
  white-space: pre-wrap;
}

.portrait-text.empty {
  color: var(--text-tertiary);
  border-left-color: var(--border-color);
  font-style: italic;
}

.profile-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 8px 0 4px;
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}

.profile-footer {
  padding: 14px 22px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.footer-left,
.footer-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.primary-btn,
.ghost-btn {
  border-radius: 6px;
  padding: 7px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid var(--border-color);
}

.primary-btn {
  background: var(--accent-gradient);
  color: #fff;
  border-color: transparent;
}

.primary-btn:hover:not(:disabled) {
  filter: brightness(1.05);
}

.primary-btn:disabled,
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ghost-btn {
  background: transparent;
  color: var(--text-secondary);
}

.ghost-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* Transition */
.profile-fade-enter-active,
.profile-fade-leave-active {
  transition: opacity 0.2s ease;
}

.profile-fade-enter-active .profile-panel,
.profile-fade-leave-active .profile-panel {
  position: fixed;
  top: 60px;
  right: 0;
  bottom: 0;
  width: 420px;
  max-width: 90vw;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  z-index: 200;
  overflow: hidden;
}

.profile-fade-enter-from,
.profile-fade-leave-to {
  opacity: 0;
}

.profile-fade-enter-from .profile-panel,
.profile-fade-leave-to .profile-panel {
  position: fixed;
  top: 60px;
  right: 0;
  bottom: 0;
  width: 420px;
  max-width: 90vw;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  z-index: 200;
  overflow: hidden;
}
</style>
