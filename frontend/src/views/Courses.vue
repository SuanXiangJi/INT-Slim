<template>
  <AppLayout>
    <section class="course-home" v-loading="loading">
      <header class="hero">
        <div>
          <p class="eyebrow">CURRICULUM</p>
          <h1>选择一个学习方向</h1>
          <p>每个方向按章节学习。读完章节并通过 10 题测验后，下一章才会解锁。</p>
        </div>
        <el-button type="primary" @click="$router.push('/code-practice')">进入代码实训</el-button>
      </header>
      <div class="stats">
        <article><strong>{{ overview.course_count || 0 }}</strong><span>学习方向</span></article>
        <article><strong>{{ overview.chapter_count || 0 }}</strong><span>可学习章节</span></article>
      </div>
      <div class="course-grid">
        <button v-for="course in courses" :key="course.key" class="course-card" @click="$router.push(`/courses/${course.key}`)">
          <div class="course-top"><span>{{ course.title.slice(0, 1) }}</span><small>{{ course.chapter_count }} 章</small></div>
          <h2>{{ course.title }}</h2>
          <p>{{ course.passed_count ? `已通过 ${course.passed_count} 章，可继续学习` : '从第一章开始，逐章完成学习与测验' }}</p>
          <el-progress :percentage="Math.round((course.passed_count || 0) * 100 / Math.max(course.chapter_count, 1))" :show-text="false" :stroke-width="5" />
        </button>
      </div>
      <el-empty v-if="!loading && !courses.length" description="公共课程资料还没有准备好" />
    </section>
  </AppLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/AppLayout.vue'
import { apiGet } from '../utils/api'
const loading = ref(false), courses = ref([]), overview = ref({})
async function load() { loading.value = true; try { const data = await apiGet('/learning/curriculum'); courses.value = data.courses || []; overview.value = data.overview || {} } catch (error) { ElMessage.error(error.message || '课程目录加载失败') } finally { loading.value = false } }
onMounted(load)
</script>

<style scoped>
.course-home{max-width:1120px;margin:0 auto}.hero{display:flex;justify-content:space-between;gap:24px;align-items:center;padding:28px 30px;border:1px solid var(--border-color);border-radius:20px;background:linear-gradient(120deg,var(--surface-card),var(--accent-soft));}.eyebrow{margin:0 0 7px;color:var(--accent-primary);font-size:11px;font-weight:800;letter-spacing:1.3px}.hero h1{margin:0 0 8px;font-size:28px;color:var(--text-primary)}.hero p{margin:0;max-width:620px;color:var(--text-secondary);line-height:1.7}.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:16px 0}.stats article{padding:15px 18px;border:1px solid var(--border-color);border-radius:14px;background:var(--surface-card)}.stats strong,.stats span{display:block}.stats strong{font-size:25px}.stats span{margin-top:4px;color:var(--text-tertiary);font-size:13px}.course-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.course-card{min-height:185px;padding:18px;border:1px solid var(--border-color);border-radius:16px;background:var(--surface-card);text-align:left;color:var(--text-primary);cursor:pointer;transition:.18s}.course-card:hover{transform:translateY(-2px);border-color:var(--accent-primary);box-shadow:var(--shadow-sm)}.course-top{display:flex;justify-content:space-between;align-items:center}.course-top span{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;color:var(--accent-primary);background:var(--accent-soft);font-weight:800}.course-top small{color:var(--text-tertiary)}.course-card h2{margin:18px 0 6px;font-size:18px}.course-card p{min-height:42px;margin:0 0 14px;color:var(--text-secondary);font-size:13px;line-height:1.6}@media(max-width:820px){.course-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:580px){.hero{align-items:flex-start;flex-direction:column}.course-grid{grid-template-columns:1fr}}
</style>
