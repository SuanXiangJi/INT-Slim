<template>
  <div class="app-container">
    <h2>Element Plus 动态高度输入框演示</h2>
    
    <div class="controls">
      <label>
        手动调整高度: <span>{{ manualHeight }}px</span>
      </label>
      <input 
        type="range" 
        v-model.number="manualHeight" 
        min="84" 
        max="300" 
        step="1"
        class="height-slider"
      />
    </div>
    
    <h3>1. 手动调整高度</h3>
    <ElementTextarea
      v-model="message"
      placeholder="试着输入超过3行，再超过8行..."
      :manual-height="manualHeight"
    />
    
    <p>当前输入内容长度: {{ message.length }}</p>
    
    <div class="divider"></div>
    
    <h3>2. 根据文本行数动态调整高度</h3>
    <ElementTextarea
      v-model="autoMessage"
      placeholder="输入多行文本，高度会自动调整..."
      :manual-height="dynamicHeight"
    />
    
    <p>当前输入内容长度: {{ autoMessage.length }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import ElementTextarea from '@/components/ElementTextarea.vue';

const message = ref('');
const manualHeight = ref(84);
const autoMessage = ref('');

const dynamicHeight = computed(() => {
  const lineHeight = 28;
  const padding = 48;
  const lines = Math.max(1, autoMessage.value.split('\n').length);
  const height = lines * lineHeight + padding;
  return Math.min(height, 400);
});
</script>

<style scoped>
.app-container {
  width: 500px;
  margin: 50px auto;
}

h2 {
  color: var(--text-primary);
  margin-bottom: 20px;
}

h3 {
  color: var(--text-primary);
  margin-bottom: 15px;
  font-size: 18px;
}

.controls {
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 8px;
}

.controls label {
  display: block;
  margin-bottom: 10px;
  font-weight: 500;
  color: #333;
}

.controls span {
  color: #409eff;
  font-weight: bold;
}

.height-slider {
  width: 100%;
  height: 8px;
  cursor: pointer;
}

.divider {
  height: 2px;
  background: #e0e0e0;
  margin: 30px 0;
}

p {
  color: var(--text-secondary);
  margin-top: 20px;
}
</style>
