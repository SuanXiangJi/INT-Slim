<template>
  <AppLayout>
    <section class="mistakes" v-loading="loading">
      <header><div><p class="eyebrow">MISTAKE BOOK</p><h1>错题本</h1><p>这里保留章节小测和代码实训中的错误答案、解析与评测反馈。</p></div><el-button @click="load">刷新</el-button></header>
      <el-tabs v-model="active"><el-tab-pane label="小测错题" name="quiz"/><el-tab-pane label="代码错题" name="code"/></el-tabs>
      <div class="mistake-list"><article v-for="item in filtered" :key="item.id" class="mistake"><div class="mistake-top"><el-tag :type="item.source==='code'?'warning':'primary'">{{ item.source==='code'?'代码实训':'章节小测' }}</el-tag><small>{{ dateText(item.created_at) }}</small></div><h2>{{ item.title }}</h2><p class="prompt">{{ item.prompt }}</p><template v-if="item.source==='quiz'"><div class="answer wrong">你的答案：{{ optionText(item.user_answer) || '未作答' }}</div><div class="answer right">正确答案：{{ optionText(item.correct_answer) }}</div></template><pre v-else>{{ item.user_answer }}</pre><div class="explanation"><strong>解析与建议</strong><p>{{ item.explanation || '请回到对应章节复习后重新尝试。' }}</p></div></article></div>
      <el-empty v-if="!loading && !filtered.length" :description="active==='quiz'?'暂无章节小测错题':'暂无代码实训错题'"/>
    </section>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import { apiGet } from '../utils/api'
const loading=ref(false),active=ref('quiz'),items=ref([])
const filtered=computed(()=>items.value.filter(x=>x.source===active.value))
function optionText(value){return value===undefined||value===null?'':String.fromCharCode(65+Number(value))}
function dateText(value){return value?new Date(value).toLocaleString('zh-CN'):'刚刚'}
async function load(){loading.value=true;try{const data=await apiGet('/learning/mistake-book');items.value=data.items||[]}catch(e){ElMessage.error(e.message||'错题本加载失败')}finally{loading.value=false}}
onMounted(load)
</script>

<style scoped>
.mistakes{max-width:980px;margin:0 auto}.mistakes header{display:flex;justify-content:space-between;align-items:start;gap:16px;margin-bottom:20px}.eyebrow{margin:0 0 5px;color:var(--accent-primary);font-size:11px;font-weight:800;letter-spacing:1.2px}.mistakes h1{margin:0 0 6px;font-size:27px}.mistakes header p{margin:0;color:var(--text-secondary)}.mistake-list{display:grid;gap:13px}.mistake{padding:18px 20px;border:1px solid var(--border-color);border-radius:15px;background:var(--surface-card)}.mistake-top{display:flex;justify-content:space-between}.mistake-top small{color:var(--text-tertiary)}.mistake h2{margin:13px 0 8px;font-size:16px}.prompt{margin:0 0 12px;line-height:1.7;color:var(--text-secondary)}.answer{padding:8px 10px;margin-top:7px;border-radius:8px;font-size:13px}.wrong{background:#fff3f2;color:#a3413b}.right{background:#eef9f1;color:#247246}.mistake pre{max-height:260px;overflow:auto;padding:12px;border-radius:9px;background:#101827;color:#e5edf8;font-size:12px;white-space:pre-wrap}.explanation{margin-top:14px;padding-top:12px;border-top:1px solid var(--border-color)}.explanation p{margin:5px 0 0;color:var(--text-secondary);line-height:1.65}.dark .wrong{background:#442321;color:#ffc6c0}.dark .right{background:#153a26;color:#c6f3d1}@media(max-width:600px){.mistakes header{flex-direction:column}}
</style>
