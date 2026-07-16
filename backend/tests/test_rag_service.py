import tempfile
import unittest
import uuid
from pathlib import Path

from app.services import rag_service


class HybridRagServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = rag_service.KB_ROOT
        rag_service.KB_ROOT = Path(self.tmp.name)
        rag_service._kb_cache.clear()
        self.user_id = uuid.uuid4().bytes
        self.kb = rag_service.KnowledgeBase(self.user_id)
        self.kb._upsert_chroma_chunks = lambda chunks: None
        self.kb._delete_chroma_doc = lambda doc_id: None
        self.kb._collection = lambda: type("EmptyCollection", (), {"count": lambda self: 0})()

    def tearDown(self):
        self.kb.clear()
        rag_service._kb_cache.clear()
        rag_service.KB_ROOT = self.old_root
        self.tmp.cleanup()

    def test_chinese_query_retrieves_relevant_document(self):
        self.kb.add_document(
            "rl",
            "强化学习是一类通过奖励信号优化决策策略的方法。"
            "智能体在环境中执行动作，并根据回报更新策略。"
            "Q-learning 是经典的无模型强化学习算法。",
            {"title": "强化学习入门", "category": "AI"},
        )
        self.kb.add_document(
            "sql",
            "MySQL 索引用于提升查询性能，常见结构包括 B+ 树索引。",
            {"title": "MySQL 索引", "category": "Database"},
        )

        hits = self.kb.search("智能体如何通过奖励学习策略", top_k=2)

        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["doc_id"], "rl")
        self.assertGreater(hits[0]["score"], 0)
        self.assertGreater(hits[0]["semantic_score"], 0)

    def test_english_fuzzy_query_uses_ngram_similarity(self):
        self.kb.add_document(
            "transformer",
            "Transformer models use self-attention to model long-range dependencies.",
            {"title": "Transformer Architecture"},
        )
        self.kb.add_document(
            "docker",
            "Docker images are built from layered filesystem instructions.",
            {"title": "Docker Basics"},
        )

        hits = self.kb.search("self attention dependency model", top_k=1)

        self.assertEqual(hits[0]["doc_id"], "transformer")
        self.assertGreater(hits[0]["bm25_score"] + hits[0]["semantic_score"], 0)

    def test_neighbor_expansion_and_context_format(self):
        content = "\n".join(
            [
                "第一节：学习路径从基础语法开始。",
                "第二节：函数、模块和异常处理需要配套练习。",
                "第三节：项目实战用于巩固综合能力。",
            ]
        )
        self.kb.CHUNK_SIZE = 30
        self.kb.CHUNK_OVERLAP = 0
        self.kb.add_document("python-path", content, {"title": "Python 学习路径"})

        hits = self.kb.search("异常处理配套练习", top_k=1)
        context = rag_service.format_retrieval_context(hits, max_chars=1200)

        self.assertEqual(hits[0]["doc_id"], "python-path")
        self.assertIn("expanded_chunk_ids", hits[0])
        self.assertIn("Python 学习路径", context)
        self.assertIn("Knowledge Base Context", context)


if __name__ == "__main__":
    unittest.main()
