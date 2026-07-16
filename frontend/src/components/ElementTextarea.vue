<template>
  <div class="textarea-wrapper">
    <el-input
      ref="inputRef"
      v-model="inputValue"
      type="textarea"
      :placeholder="placeholder"
      :rows="rows" 
      class="custom-textarea"
      @input="handleInput"
      @keydown="handleKeydown"
    ></el-input>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue';

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '请输入内容...'
  },
  manualHeight: {
    type: Number,
    default: null
  },
  autoHeight: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'keydown']);

const inputRef = ref(null);
const inputValue = ref(props.modelValue);

const rows = computed(() => {
  if (props.manualHeight !== null && props.manualHeight > 0) {
    return Math.max(1, Math.floor(props.manualHeight / 42));
  }
  return 1;
});

const handleInput = (value) => {
  emit('update:modelValue', value);
  if (props.autoHeight && inputRef.value) {
    nextTick(() => {
      const textarea = inputRef.value.$el?.querySelector('textarea');
      if (textarea) {
        const lineHeight = 28;
        const padding = 48;
        const lines = Math.max(1, value.split('\n').length);
        const newHeight = Math.min(lines * lineHeight + padding, 400);
        textarea.style.height = newHeight + 'px';
      }
    });
  }
};

const handleKeydown = (event) => {
  // 监听回车键事件，但不阻止默认行为（换行）
  emit('keydown', event);
};

watch(() => props.modelValue, (newVal) => {
  inputValue.value = newVal;
});

watch(() => props.manualHeight, (newHeight) => {
  if (newHeight !== null && inputRef.value) {
    nextTick(() => {
      const textarea = inputRef.value.$el?.querySelector('textarea');
      if (textarea) {
        textarea.style.height = newHeight + 'px';
        textarea.style.minHeight = newHeight + 'px';
        textarea.style.maxHeight = newHeight + 'px';
        textarea.style.overflowY = 'auto';
        // console.log('设置手动高度:', newHeight);
      }
    });
  }
}, { immediate: true, deep: true, flush: 'post' });
</script>

<style scoped>
.textarea-wrapper {
  width: auto;
  position: relative;
}

.custom-textarea {
  width: auto !important;
}

.custom-textarea :deep(.el-textarea__inner) {
  box-sizing: border-box;
  font-size: 18px;
  line-height: 28px;
  padding: 18px 28px 0 28px; /* 只保留顶部、左右padding，底部padding由外部容器处理 */
  border: none;
  border-radius: 0;
  background-color: transparent;
  resize: none;
  min-height: 64px; /* 最小高度：1行文字 + padding */
  max-height: 340px;
  overflow-y: auto;
  transition: all 0.3s ease;
  color: var(--text-primary, #333);
  box-shadow: none;
  outline: none;
}

/* 移除聚焦和悬停效果，因为边框和背景由外部容器处理 */
.custom-textarea :deep(.el-textarea__inner):hover,
.custom-textarea :deep(.el-textarea__inner):focus {
  border-color: transparent;
  box-shadow: none;
  background-color: transparent;
}

/* 移除textarea-wrapper的相对定位，因为定位由外部容器处理 */
.textarea-wrapper {
  width: 100%;
  position: static;
}

.custom-textarea :deep(.el-textarea__inner)::placeholder {
  color: var(--text-tertiary, #999);
  font-family: 黑体, SimHei, sans-serif;
  font-weight: bold;
  font-style: normal;
}

/* 添加滚动条样式 */
.custom-textarea :deep(.el-textarea__inner)::-webkit-scrollbar {
  width: 6px;
}

.custom-textarea :deep(.el-textarea__inner)::-webkit-scrollbar-track {
  background: transparent;
  margin: 0;
}

.custom-textarea :deep(.el-textarea__inner)::-webkit-scrollbar-thumb {
  background: rgba(71, 68, 68, 0.4); /* 淡白色，带有透明度 */
  border-radius: 20px;
  min-height: 40px;
}

.custom-textarea :deep(.el-textarea__inner)::-webkit-scrollbar-thumb:hover {
  background: rgba(92, 89, 89, 0.6); /* 淡白+淡淡的紫色混合效果 */
}
</style>
