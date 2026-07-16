import { createRouter, createWebHistory } from "vue-router"
import Login from "../views/Login.vue"
import Dashboard from "../views/Dashboard.vue"
import Courses from "../views/Courses.vue"
import Chat from "../views/Chat.vue"
import LearningPath from "../views/LearningPath.vue"
import LearningDiagnosis from "../views/LearningDiagnosis.vue"
import LearningReport from "../views/LearningReport.vue"
import Tasks from "../views/Tasks.vue"
import Mistakes from "../views/Mistakes.vue"
import StudySession from "../views/StudySession.vue"
import Curriculum from "../views/Curriculum.vue"
import CodePractice from "../views/CodePractice.vue"
import Assessment from "../views/Assessment.vue"
import LearningReader from "../views/LearningReader.vue"
import { isLoggedIn, getCurrentUser, removeToken } from "../utils/api"

const routes = [
  { path: "/", name: "Login", component: Login, meta: { requiresAuth: false } },
  { path: "/dashboard", component: Dashboard, meta: { requiresAuth: true, layout: "app" } },
  { path: "/courses", component: Courses, meta: { requiresAuth: true, layout: "app" } },
  { path: "/courses/:courseKey", component: Curriculum, meta: { requiresAuth: true, layout: "app" } },
  { path: "/courses/:courseKey/read/:docId", component: LearningReader, meta: { requiresAuth: true, layout: "app" } },
  { path: "/code-practice", component: CodePractice, meta: { requiresAuth: true, layout: "app" } },
  { path: "/assessments/:assessmentId", component: Assessment, meta: { requiresAuth: true, layout: "app" } },
  { path: "/chat", component: Chat, meta: { requiresAuth: true, layout: "app" } },
  { path: "/path", component: LearningPath, meta: { requiresAuth: true, layout: "app" } },
  { path: "/diagnosis", component: LearningDiagnosis, meta: { requiresAuth: true, layout: "app" } },
  { path: "/mistakes", component: Mistakes, meta: { requiresAuth: true, layout: "app" } },
  { path: "/reports", component: LearningReport, meta: { requiresAuth: true, layout: "app" } },
  { path: "/tasks", component: Tasks, meta: { requiresAuth: true, layout: "app" } },
  { path: "/study/:taskId", component: StudySession, meta: { requiresAuth: true, layout: "app" } },
  { path: "/:pathMatch(.*)*", redirect: "/" }
]

const router = createRouter({ history: createWebHistory("/app/"), routes })

router.beforeEach(async (to, from, next) => {
  if (to.path === "/" && isLoggedIn()) {
    try { await getCurrentUser(); next("/dashboard"); return }
    catch { removeToken() }
  }
  if (to.meta.requiresAuth) {
    if (isLoggedIn()) {
      try { await getCurrentUser(); next() }
      catch { removeToken(); next("/") }
    } else { next("/") }
  } else { next() }
})

export default router
