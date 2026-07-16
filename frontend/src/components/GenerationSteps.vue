<template>
  <div class="generation"><p class="eyebrow">AGENT WORKING</p><h2>正在准备题集</h2><p>题目会基于当前学习内容生成并保存，完成前不会重复创建。</p><ol><li v-for="(step,index) in steps" :key="step.name" :class="{active:index===activeStep,done:index<activeStep||done}"><span>{{ index<activeStep||done?'✓':index+1 }}</span><div><strong>{{ step.name }}</strong><small>{{ step.detail }}</small></div></li></ol></div>
</template>
<script setup>
defineProps({ activeStep:{type:Number,default:0}, done:{type:Boolean,default:false} })
const steps=[{name:'资料整理',detail:'提取本章关键概念与学习范围。'},{name:'出题 Agent',detail:'生成符合章节范围的选择题。'},{name:'题目校验',detail:'检查选项、答案与解析是否完整。'},{name:'保存题集',detail:'保存后可随时继续作答。'}]
</script>
<style scoped>
.eyebrow{margin:0;color:var(--accent-primary);font-size:11px;font-weight:800;letter-spacing:1.1px}.generation h2{margin:7px 0}.generation>p:not(.eyebrow){color:var(--text-secondary);line-height:1.65}.generation ol{display:grid;gap:12px;padding:0;margin:22px 0 0;list-style:none}.generation li{display:flex;gap:10px;opacity:.45}.generation li.active,.generation li.done{opacity:1}.generation li span{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:var(--bg-tertiary);font-size:12px}.generation li.active span,.generation li.done span{background:var(--accent-primary);color:#fff}.generation strong,.generation small{display:block}.generation small{margin-top:3px;color:var(--text-tertiary)}
</style>
