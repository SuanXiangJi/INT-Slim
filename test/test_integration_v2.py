
"""Comprehensive Integration Tests for all 6 services + Agent Graph."""
import asyncio, json, sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("PYTHONPATH", os.path.join(os.path.dirname(__file__), "..", "backend"))
PASS = 0; FAIL = 0
def report(name, passed):
    global PASS, FAIL
    if passed:
        PASS += 1; print(f"  [PASS] {name}")
    else:
        FAIL += 1; print(f"  [FAIL] {name}")

async def test_rule_engine():
    from app.services.rule_engine import get_rule_engine
    e = get_rule_engine()
    r = e.list_rules()
    report("Rule count: 5", len(r) == 5)

    r = await e.evaluate_all(cognitive_load=0.9, load_threshold=0.8, plan_difficulty=0.7)
    l = [x for x in r if x.rule_id == "load_ok"][0]
    report("load_ok: overloaded fails", not l.passed)

    r = await e.evaluate_all(cognitive_load=0.1, load_threshold=0.8, plan_difficulty=0.2)
    l = [x for x in r if x.rule_id == "load_ok"][0]
    report("load_ok: low load passes", l.passed)

    r = await e.evaluate_all(target_kp="kp3", prerequisites=["kp1", "kp2"], mastery={"kp1": {"level": 0.1}, "kp2": {"level": 0.2}})
    p = [x for x in r if x.rule_id == "prereq_covered"][0]
    report("prereq_covered: uncovered fails", not p.passed)

    r = await e.evaluate_all(target_kp="kp3", prerequisites=["kp1"], mastery={"kp1": {"level": 0.8}})
    p = [x for x in r if x.rule_id == "prereq_covered"][0]
    report("prereq_covered: covered passes", p.passed)

    r = await e.evaluate_all(content={"title": "t", "sections": [{"body": "x"}]})
    e2 = [x for x in r if x.rule_id == "evidence_required"][0]
    report("evidence_required: missing fails", not e2.passed)

    r = await e.evaluate_all(content={"title": "t", "evidence_map": [{"claim": "x", "source": "d", "confidence": "high"}]})
    e2 = [x for x in r if x.rule_id == "evidence_required"][0]
    report("evidence_required: present passes", e2.passed)

    r = await e.evaluate_all(content={"sections": [{"heading": "Intro", "body": "test"}]})
    s = [x for x in r if x.rule_id == "has_structure"][0]
    report("has_structure: passes with sections", s.passed)

async def test_kg_rag():
    from app.services.kg_rag_service import get_kg_rag_service
    kg = get_kg_rag_service()
    kg.graph.add_node("kp1", "Python Basics", "Programming", "vars loops", 0.3)
    kg.graph.add_node("kp2", "Python OOP", "Programming", "classes", 0.6)
    kg.graph.add_node("kp3", "Python Advanced", "Programming", "decorators", 0.8)
    kg.graph.add_edge("kp1", "kp2", "prerequisite")
    kg.graph.add_edge("kp2", "kp3", "prerequisite")
    p = kg.graph.get_prerequisites("kp3")
    report("KG prereqs for kp3", p == ["kp2"])
    pa = kg.graph.find_path("kp3")
    report("KG find_path length", len(pa) >= 2)
    n = kg.graph.get_next_skills("kp1")
    report("KG next from kp1", "kp2" in n)
    kg.tfidf.add_document("d1", "Python basics tutorial", {"course": "Py101", "title": "Intro"})
    kg.tfidf.add_document("d2", "Advanced decorators and generators", {"course": "Py Pro", "title": "Adv"})
    kg.tfidf.build()
    s = kg.tfidf.search("python", 3)
    report("TF-IDF search returns results", len(s) > 0)
    s2 = kg.tfidf.search("decorators", 3)
    hd = any("decorator" in kg.tfidf.documents[i]["text"].lower() for i, sc in s2)
    report("TF-IDF finds decorators", hd)
    d = kg.graph.to_dict()
    report("KG to_dict", len(d["nodes"]) == 3 and len(d["edges"]) == 2)

def test_cognitive_diagnosis():
    from app.services.cognitive_diagnosis import get_diagnosis_service
    d = get_diagnosis_service()
    d1 = d.diagnose("kp1", "Basics", 0, 0)
    report("New learner mastery 0-1", 0 < d1.mastery_prob < 1)
    d2 = d.diagnose("kp1", "Basics", 8, 10)
    report("Good learner mastery > 0.5", d2.mastery_prob > 0.5)
    d3 = d.diagnose("kp1", "Basics", 1, 10)
    report("Poor learner struggles", d3.struggling)
    nr, nd = d.estimate_elo_change(1500, 1500, True)
    report("Elo correct increases rating", nr > 1500)
    nr2, nd2 = d.estimate_elo_change(1500, 1500, False)
    report("Elo wrong decreases rating", nr2 < 1500)
    r = d.apply_forgetting_curve(0.8, 30)
    report("Forgetting decays after 30d", r < 0.8 and r > 0.1)
    r2 = d.apply_forgetting_curve(0.8, 0)
    report("Forgetting no decay at 0d", abs(r2 - 0.8) < 0.01)
    report("Review low=1d", d.estimate_next_review_days(0.2) == 1)
    report("Review high=14d", d.estimate_next_review_days(0.9) == 14)
    df = d.diagnose("kp1", "Py", 8, 10, last_practiced_days=30, current_level=0.8, current_confidence=0.7)
    report("Detects forgotten after 30d", df.forgotten)

def test_evidence_tracker():
    from app.services.evidence_tracker import get_evidence_tracker
    t = get_evidence_tracker()
    t.start_tracking("c1", "Python Tutorial")
    c1 = t.add_claim("Python dynamic", "kb_document", "d1", "Guide", "high")
    c2 = t.add_claim("Python OOP", "kb_document", "d2", "OOP", "medium")
    c3 = t.add_claim("AI replaces all", "llm_generated", "", "", "low")
    report("3 claims added", c1 and c2 and c3)
    t.verify_claim(c1, "auto")
    t.verify_claim(c2, "manual")
    r = t.generate_report("c1")
    report("Report total=3", r.total_claims == 3)
    report("Report verified=2", r.verified_claims == 2)
    report("Report unverified=1", r.unverified_claims == 1)
    r2 = t.track_content({"title": "Advanced", "sections": [{"body": "decors [source:Pro]"}]},
        [{"claim": "decors", "source": "d3", "source_name": "Pro", "confidence": "high", "verified": True}], "c2")
    report("Track from evidence works", r2.total_claims >= 1)
    report("Report has content_id", r2.content_id == "c2")
    report("Report has content_title", r2.content_title == "Advanced")

def test_path_planner():
    from app.services.path_planner import get_path_planner
    p = get_path_planner()
    kps = [{"id": "kp1", "name": "Basics", "difficulty": 0.3, "category": "Prog"},
        {"id": "kp2", "name": "DS", "difficulty": 0.5, "category": "Prog"},
        {"id": "kp3", "name": "OOP", "difficulty": 0.6, "category": "Prog"},
        {"id": "kp4", "name": "Advanced", "difficulty": 0.8, "category": "Prog"}]
    pm = {"kp2": ["kp1"], "kp3": ["kp2"], "kp4": ["kp3", "kp1"]}
    m = {"kp1": {"level": 0.8}, "kp2": {"level": 0.3}, "kp3": {"level": 0.1}}
    path = p.plan(goal="Master Python", available_kps=kps, prerequisite_map=pm, learner_mastery=m, cognitive_load=0.3, focus_areas=["Python"])
    report("Plan has nodes", len(path.nodes) > 0)
    report("Plan hours > 0", path.total_hours > 0)
    report("Plan has schedule", bool(path.weekly_schedule))
    if len(path.nodes) >= 2:
        correct = True
        for i, node in enumerate(path.nodes):
            if node.kp_id in pm:
                for prereq in pm[node.kp_id]:
                    pi = next((j for j, n in enumerate(path.nodes) if n.kp_id == prereq), -1)
                    if pi >= 0 and pi > i: correct = False
        report("Plan topological order", correct)
    sn = p._topological_sort({"kp1", "kp2", "kp3", "kp4"}, pm, {k["id"]: k for k in kps})
    no = [n[0] for n in sn]
    report("Topo sort kp1 first", no[0] == "kp1")
    report("Topo sort all present", len(no) == 4)
    nk = p.recommend_next_kp(path, m)
    report("Recommend next exists", nk is not None)
    path2 = p.plan(goal="Scratch", available_kps=kps, prerequisite_map=pm, learner_mastery={}, cognitive_load=0.0)
    report("Empty learner path works", len(path2.nodes) > 0)
    path3 = p.plan(goal="All", available_kps=kps, prerequisite_map=pm, learner_mastery=m, cognitive_load=0.9, load_threshold=0.8)
    report("Overloaded path works", path3.total_hours > 0)

async def test_agent_graph():
    import os
    if not os.environ.get("MYSQL_HOST"):
        os.environ["MYSQL_HOST"] = "localhost"
        os.environ["MYSQL_PORT"] = "3306"
        os.environ["MYSQL_USER"] = "root"
        os.environ["MYSQL_PASSWORD"] = "MYSQL"
        os.environ["MYSQL_DATABASE"] = "xbots_v2"
        os.environ["MYSQL_CHARSET"] = "utf8mb4"
    from app.agents.base import GraphState
    from app.services.agent_graph import get_agent_graph
    g = get_agent_graph()
    d = g.describe()
    report("Graph 6 agents", len(d["agents"]) == 6)
    report("Graph 6 pipeline", len(d["pipeline"]) == 6)
    report("Graph pipeline matches agents", set(d["pipeline"]) == set(d["agents"].keys()))
    for aid in ["diagnosis", "task", "retrieval", "generation", "review", "judge"]:
        a = g.get_agent(aid)
        report(f"Agent {aid} registered", a is not None and bool(a.name))
        if a: report(f"Agent {aid} has description", bool(a.description))
    s = GraphState(user_id="test", user_input="Learn Python")
    report("GraphState creation", s.user_input == "Learn Python")
    sd = s.to_dict()
    report("GraphState to_dict", isinstance(sd, dict))

async def main():
    print("=" * 60)
    print("COMPREHENSIVE INTEGRATION TESTS")
    print("=" * 60)
    tests = [("Rule Engine", test_rule_engine()), ("KG + RAG", test_kg_rag()),
        ("Cognitive Diagnosis", asyncio.to_thread(test_cognitive_diagnosis)),
        ("Evidence Tracker", asyncio.to_thread(test_evidence_tracker)),
        ("Path Planner", asyncio.to_thread(test_path_planner)),
        ("Agent Graph", test_agent_graph())]
    for name, coro in tests:
        print(f"\n--- {name} ---")
        try:
            if asyncio.iscoroutine(coro): await coro
            else: await coro
        except Exception as e:
            traceback.print_exc(); print(f"  [ERROR] {name}: {e}")
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"RESULTS: {PASS}/{total} PASSED, {FAIL}/{total} FAILED")
    print(f"{'=' * 60}")
if __name__ == "__main__": asyncio.run(main())
