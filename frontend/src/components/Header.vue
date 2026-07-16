<template>
  <div class="chat-header">
    <Transition name="slide-fade">
      <button class="toggle-sidebar-btn" @click="handleToggle" v-if="collapsed">
        <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
          <path d="M896 853.333333H128v-85.333333h768v85.333333z m42.666667-490.666666l-196.096 196.096-60.330667-60.330667L818.005333 362.666667 682.24 226.901333l60.330667-60.330666L938.666667 362.666667zM512 554.666667H128v-85.333334h384v85.333334z m0-298.666667H128V170.666667h384v85.333333z"/>
        </svg>
      </button>
    </Transition>
    <div class="header-content">
      <div v-if="!isEditing" class="title-display">
        <h2>{{ title }}</h2>
      </div>
      <div v-else class="title-edit">
        <input
          v-model="editTitle"
          @blur="saveTitle"
          @keyup.enter="saveTitle"
          @keyup.esc="cancelEdit"
          ref="inputRef"
          type="text"
          class="title-input"
        />
      </div>
      <button class="edit-btn" @click="startEdit" v-show="!isEditing">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M18.5 2.50001C18.8978 2.10219 19.4374 1.87869 20 1.87869C20.5626 1.87869 21.1022 2.10219 21.5 2.50001C21.8978 2.89784 22.1213 3.4374 22.1213 4.00001C22.1213 4.56262 21.8978 5.10219 21.5 5.50001L12 15L8 16L9 12L18.5 2.50001Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>

      <!-- 灵动岛：AI 运行状态 -->
      <Transition name="island-flip" mode="out-in">
        <div
          v-if="showIsland"
          class="dynamic-island"
          :key="islandKey"
        >
          <div class="island-content">
            <span v-if="showLoading" class="island-spinner">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-opacity="0.25"/>
                <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
              </svg>
            </span>
            <span class="island-text">{{ islandText }}</span>
          </div>
        </div>
      </Transition>

      <!-- 模型选择器 -->
      <div class="model-selector-wrapper">
        <button class="model-selector-btn" @click.stop="toggleDropdown">
          <span class="model-selector-label">{{ currentModelName }}</span>
          <svg class="model-selector-arrow" :class="{ open: showDropdown }" viewBox="0 0 24 24" fill="none">
            <path d="M6 9L12 15L18 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <Transition name="dropdown-fade">
          <div class="model-dropdown" v-if="showDropdown">
            <div
              v-for="model in availableModels"
              :key="model.id"
              :class="['model-dropdown-item', { active: model.id === selectedModel }]"
              @click="selectModel(model)"
            >
              <div class="model-dropdown-item-content">
                <span class="model-name">{{ model.name }}</span>
                <span class="model-provider">{{ model.provider }}</span>
              </div>
              <svg v-if="model.id === selectedModel" class="model-check" viewBox="0 0 24 24" fill="none">
                <path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
        </Transition>
      </div>

      <button class="theme-toggle-btn" @click="toggleTheme" :title="isDark ? '切换到亮色主题' : '切换到深色主题'">
        <svg v-if="!isDark" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M12 1V3M12 21V23M4.22 4.22L5.64 5.64M18.36 18.36L19.78 19.78M1 12H3M21 12H23M4.22 19.78L5.64 18.36M18.36 5.64L19.78 4.22" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    
      <!-- 画像按钮 -->
      <button class="profile-header-btn" @click="emit('openProfile')" title="查看 / 编辑用户画像">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button></div>
  </div>
</template>

<script setup>
import { ref, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { useTheme } from '@/composables/useTheme'

const props = defineProps({
  collapsed: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '新对话'
  },
  availableModels: {
    type: Array,
    default: () => []
  },
  selectedModel: {
    type: String,
    default: ''
  },
  agentEnabled: {
    type: Boolean,
    default: false
  },
  isStreaming: {
    type: Boolean,
    default: false
  },
  agentStatus: {
    type: Object,
    default: null
  },
  toolStatus: {
    type: Object,
    default: null
  },
  conversationId: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['toggle', 'update:title', 'update:selectedModel', 'update:agentEnabled', 'openProfile'])

const { isDark, toggleTheme } = useTheme()

const isEditing = ref(false)
const editTitle = ref('')
const inputRef = ref(null)
const showDropdown = ref(false)

const currentModelName = computed(() => {
  const model = props.availableModels.find(m => m.id === props.selectedModel)
  return model ? model.name : '选择模型'
})

const showIsland = computed(() => props.isStreaming)
const islandKey = computed(() => (props.isStreaming ? props.conversationId : 'none'))
const showLoading = computed(() => {
  if (props.toolStatus && props.toolStatus.status === 'running') return true
  if (props.agentStatus && props.agentStatus.status !== 'done') return true
  return props.isStreaming
})
const islandText = computed(() => {
  if (props.agentStatus && props.agentStatus.status !== 'done') {
    return props.agentStatus.message || '正在处理...'
  }
  return '正在回复...'
})

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function closeDropdown(e) {
  if (!e || !e.target.closest('.model-selector-wrapper')) {
    showDropdown.value = false
  }
}

function selectModel(model) {
  emit('update:selectedModel', model.id)
  showDropdown.value = false
}

// Click outside handler
onMounted(() => {
  document.addEventListener('click', closeDropdown)
})

onUnmounted(() => {
  document.removeEventListener('click', closeDropdown)
})

function handleToggle() {
  emit('toggle')
}

function startEdit() {
  editTitle.value = props.title
  isEditing.value = true
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
      inputRef.value.select()
    }
  })
}

function saveTitle() {
  if (editTitle.value.trim()) {
    emit('update:title', editTitle.value.trim())
  }
  isEditing.value = false
}

function cancelEdit() {
  isEditing.value = false
}
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: var(--bg-glass);
  backdrop-filter: var(--blur-glass);
  -webkit-backdrop-filter: var(--blur-glass);
  border-bottom: 1px solid var(--border-color);
  min-height: 56px;
  position: relative;
  z-index: 10;
}

.toggle-sidebar-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  color: var(--text-secondary);
}

.toggle-sidebar-btn:hover {
  background: rgba(102, 126, 234, 0.1);
}

.toggle-sidebar-btn svg {
  width: 20px;
  height: 20px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.title-display {
  display: flex;
  align-items: center;
}

.title-display h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 400px;
  letter-spacing: -0.2px;
}

.title-edit {
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 400px;
}

.title-input {
  width: 100%;
  padding: 8px 12px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  border: 2px solid var(--accent-primary);
  border-radius: 6px;
  outline: none;
  background: var(--bg-secondary);
}

.title-input:focus {
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.edit-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 8px;
  color: var(--text-secondary);
}

.edit-btn:hover {
  background: rgba(102, 126, 234, 0.1);
}

.edit-btn svg {
  width: 18px;
  height: 18px;
}

.model-selector-wrapper {
  position: relative;
  margin-left: auto;
  margin-right: 8px;
}

.model-selector-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  transition: all var(--transition-fast);
  white-space: nowrap;
}
.model-selector-btn:hover {
  background: var(--bg-hover);
  border-color: var(--accent-primary);
}

.model-selector-btn:hover {
  border-color: var(--accent-primary);
  background: var(--bg-hover);
}

.model-selector-label {
  font-size: 14px;
  color: var(--text-primary);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-selector-arrow {
  width: 16px;
  height: 16px;
  color: var(--text-tertiary);
  transition: transform 0.2s;
}

.model-selector-arrow.open {
  transform: rotate(180deg);
}

.model-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 220px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  z-index: 9999;
  animation: dropdown-in 0.2s ease;
}
@keyframes dropdown-in {
  from { opacity: 0; transform: translateY(-8px) scale(0.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.model-dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.model-dropdown-item:hover {
  background: var(--bg-hover);
}

.model-dropdown-item.active {
  background: rgba(255, 126, 95, 0.1);
}

.model-dropdown-item-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.model-dropdown-item .model-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.model-dropdown-item .model-provider {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

.model-dropdown-item .model-check {
  width: 18px;
  height: 18px;
  color: var(--accent-primary);
}

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: all 0.2s ease;
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.theme-toggle-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.theme-toggle-btn:hover {
  background: rgba(102, 126, 234, 0.1);
}

.theme-toggle-btn svg {
  width: 20px;
  height: 20px;
}

.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}

.slide-fade-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.slide-fade-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}


/* Profile header button */
.profile-header-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 8px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  margin-left: 4px;
}

.profile-header-btn:hover {
  background: rgba(102, 126, 234, 0.1);
  color: var(--accent-primary);
}

.profile-header-btn svg {
  width: 20px;
  height: 20px;
}

/* ========== Dynamic Island（灵动岛）========== */
.header-content {
  position: relative;
  perspective: 1200px;
}

.dynamic-island {
  position: absolute;
  left: 50%;
  top: 8px;
  transform: translateX(-50%);
  min-width: 140px;
  max-width: 340px;
  padding: 8px 18px;
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.32) 0%,
    rgba(255, 255, 255, 0.14) 100%
  );
  color: #1a1a1a;
  border: 1px solid rgba(255, 255, 255, 0.42);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1),
              inset 0 1px 0 rgba(255, 255, 255, 0.55),
              inset 0 -1px 0 rgba(0, 0, 0, 0.02);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  line-height: 1.4;
  z-index: 100;
  pointer-events: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dark .dynamic-island {
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.16) 0%,
    rgba(255, 255, 255, 0.07) 100%
  );
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35),
              inset 0 1px 0 rgba(255, 255, 255, 0.25),
              inset 0 -1px 0 rgba(0, 0, 0, 0.05);
}

.island-content {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  overflow: hidden;
}

.island-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.island-spinner {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  animation: island-spin 0.85s linear infinite;
}

.island-spinner svg {
  width: 100%;
  height: 100%;
}

@keyframes island-spin {
  to { transform: rotate(360deg); }
}

/* 翻转动画：切换正在运行的会话时像卡片一样翻转 */
.island-flip-enter-active,
.island-flip-leave-active {
  transition: transform 0.45s cubic-bezier(0.34, 1.56, 0.64, 1),
              opacity 0.35s ease;
  transform-origin: center center;
}

.island-flip-enter-from {
  opacity: 0;
  transform: translateX(-50%) rotateY(90deg) scale(0.82);
}

.island-flip-leave-to {
  opacity: 0;
  transform: translateX(-50%) rotateY(-90deg) scale(0.82);
}

.island-flip-enter-to,
.island-flip-leave-from {
  opacity: 1;
  transform: translateX(-50%) rotateY(0deg) scale(1);
}
</style>
