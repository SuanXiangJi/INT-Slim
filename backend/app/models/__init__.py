from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Create database URL
DATABASE_URL = f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}?charset={settings.mysql_charset}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Import all models here to ensure they are registered with Base.metadata
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.models.auth_token import AuthToken
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.agent_config import AgentConfig
from app.models.tool import Tool
from app.models.agent_tool import AgentTool
from app.models.user_profile import UserProfile
from app.models.knowledge_base import KnowledgeDocument, KnowledgeChunk

# Agent extension models
from app.models.skill import Skill
from app.models.agent_skill import AgentSkill
from app.models.agent_runtime_state import AgentRuntimeState
from app.models.agent_reflection import AgentReflection
from app.models.project import Project

# Learning platform models
from app.models.learning.learner import Learner, LearnerMastery, LearnerError, LearnerCognitiveLoad
from app.models.learning.knowledge_point import KnowledgePoint, KpPrerequisite
from app.models.learning.plan import LearningPlan, PlanKnowledgePoint
from app.models.learning.exam import Exam, ExamQuestion
from app.models.learning.content import ContentAssembly
from app.models.learning.review import QualityReview, ReviewDefect
from app.models.learning.candidate import CandidateRanking
from app.models.learning.course import Course
from app.models.learning.task import LearningTask
from app.models.learning.exam_attempt import ExamAttempt
from app.models.learning.curriculum import ChapterProgress, LearningAssessment, AssessmentSubmission, CodeSubmission, LearningMistake


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
