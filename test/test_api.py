import requests, json, sys

BASE = "http://localhost:8000"

# 1. Login with form data (OAuth2)
r = requests.post(BASE + "/api/v1/auth/login", data={
    "username": "demo@example.com", "password": "change-me"
})
if r.status_code != 200:
    print(f"LOGIN FAILED: {r.status_code} {r.text}")
    sys.exit(1)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("1. Login OK")

# 2. List learners
r = requests.get(BASE + "/api/v1/learning/learners", headers=headers)
print(f"2. List learners: {r.status_code} -> {r.json()}")

# 3. Create a learner
r = requests.post(BASE + "/api/v1/learning/learners", headers=headers, json={
    "name": "测试学员张三", "grade": "大三", "goals": ["学Python", "学AI"]
})
assert r.status_code == 200, f"Create learner failed: {r.text}"
learner_id = r.json()["id"]
print(f"3. Create learner: OK id={learner_id}")

# 4-18: Continue...
for path in ["learners", "knowledge-points", "plans", "exams", "contents", "reviews", "candidates"]:
    r = requests.get(f"{BASE}/api/v1/learning/{path}", headers=headers)
    assert r.status_code == 200, f"GET {path} failed: {r.text}"
    print(f"  GET /{path}: OK")

# Test specific operations
# Mastery
r = requests.post(f"{BASE}/api/v1/learning/learners/{learner_id}/mastery",
    headers=headers, json={"kp_id": "python_101", "level": 0.7})
assert r.status_code == 200
print(f"  POST mastery: {r.json()['success']}")

# Errors
r = requests.post(f"{BASE}/api/v1/learning/learners/{learner_id}/errors",
    headers=headers, json={"error_type": "calculation", "kp_id": "python_101"})
assert r.status_code == 200
print(f"  POST error: {r.json()['success']}")

# Cognitive load
r = requests.post(f"{BASE}/api/v1/learning/learners/{learner_id}/cognitive-load",
    headers=headers, json={"load_value": 0.3})
assert r.status_code == 200
print(f"  POST load: {r.json()['success']}")

# Create KP
r = requests.post(BASE + "/api/v1/learning/knowledge-points", headers=headers, json={
    "name": "Python基础", "category": "编程", "difficulty": 0.3
})
assert r.status_code == 200
kp_id = r.json()["id"]
print(f"  POST KP: id={kp_id}")

# Plan
r = requests.post(BASE + "/api/v1/learning/plans", headers=headers, json={
    "learner_id": learner_id, "goal": "3个月精通Python"
})
assert r.status_code == 200
plan_id = r.json()["id"]
print(f"  POST plan: id={plan_id}")

# Exam
r = requests.post(BASE + "/api/v1/learning/exams", headers=headers, json={
    "title": "Python入门测试", "plan_id": plan_id
})
assert r.status_code == 200
exam_id = r.json()["id"]
print(f"  POST exam: id={exam_id}")

# Question
r = requests.post(f"{BASE}/api/v1/learning/exams/{exam_id}/questions",
    headers=headers, json={
        "kp_id": kp_id, "qtype": "choice",
        "question_data": {"question": "Python的关键字?", "options": ["A. int", "B. class", "C. both"], "answer": "C"}
    })
assert r.status_code == 200
print(f"  POST question: {r.json()['success']}")

# Content
r = requests.post(BASE + "/api/v1/learning/contents", headers=headers, json={
    "template_type": "lecture", "title": "Python入门讲义",
    "content_data": {"sections": [{"title": "变量", "body": "Python变量无需声明"}]},
    "plan_id": plan_id, "kp_id": kp_id
})
assert r.status_code == 200
content_id = r.json()["id"]
print(f"  POST content: id={content_id}")

# Review
r = requests.post(BASE + "/api/v1/learning/reviews", headers=headers, json={
    "content_id": content_id, "reviewer_type": "auto", "risk_level": "low"
})
assert r.status_code == 200
review_id = r.json()["id"]
print(f"  POST review: id={review_id}")

# Defect
r = requests.post(f"{BASE}/api/v1/learning/reviews/{review_id}/defects",
    headers=headers, json={
        "defect_type": "clarity", "severity": "minor",
        "description": "例子不够丰富", "suggestion": "增加更多代码示例"
    })
assert r.status_code == 200
print(f"  POST defect: {r.json()['success']}")

# Candidate
r = requests.post(BASE + "/api/v1/learning/candidates", headers=headers, json={
    "content_id": content_id, "rank_score": 0.85
})
assert r.status_code == 200
print(f"  POST candidate: {r.json()['success']}")

# Verify all data persisted
r = requests.get(BASE + "/api/v1/learning/learners", headers=headers)
learners = r.json()
print(f"\nVerify: {len(learners)} learner(s) in DB")
r = requests.get(BASE + "/api/v1/learning/knowledge-points", headers=headers)
print(f"Verify: {len(r.json())} knowledge point(s) in DB")
r = requests.get(BASE + "/api/v1/learning/plans", headers=headers)
print(f"Verify: {len(r.json()['data'])} plan(s) in DB")

print("\n=== ALL TESTS PASSED ===")
