import { apiGet, apiPost, getCurrentUser } from "./api"

/** Return a learner profile for the signed-in student, creating the first profile when needed. */
export async function ensureLearner() {
  const learners = await apiGet("/learning/learners")
  if (learners?.length) return learners[0]
  let name = "学员"
  try { name = (await getCurrentUser())?.nickname || (await getCurrentUser())?.email?.split("@")[0] || name } catch {}
  return apiPost("/learning/learners", { name, goals: ["持续提升学习掌握度"] })
}
