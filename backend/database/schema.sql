/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `agent_configs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_configs` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `default_model` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `sandbox_path` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_agent_configs_user_id` (`user_id`),
  CONSTRAINT `agent_configs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `agent_reflections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_reflections` (
  `entry_id` varchar(36) COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` binary(16) NOT NULL,
  `conversation_id` varchar(36) COLLATE utf8mb4_general_ci NOT NULL,
  `entry_data` json NOT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`entry_id`),
  KEY `ix_agent_reflections_conversation_id` (`conversation_id`),
  KEY `ix_agent_reflections_user_id` (`user_id`),
  KEY `idx_reflection_user_conversation` (`user_id`,`conversation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `agent_runtime_states`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_runtime_states` (
  `conversation_id` varchar(36) COLLATE utf8mb4_general_ci NOT NULL,
  `status` varchar(32) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `state_data` json NOT NULL,
  `updated_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`conversation_id`),
  KEY `ix_agent_runtime_states_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `agent_skills`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_skills` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `skill_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_agent_skills_skill_id` (`skill_id`),
  KEY `ix_agent_skills_user_id` (`user_id`),
  CONSTRAINT `agent_skills_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `agent_skills_ibfk_2` FOREIGN KEY (`skill_id`) REFERENCES `skills` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `agent_tools`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_tools` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `tool_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `enabled` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_agent_tools_user_id` (`user_id`),
  KEY `ix_agent_tools_tool_id` (`tool_id`),
  CONSTRAINT `agent_tools_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `agent_tools_ibfk_2` FOREIGN KEY (`tool_id`) REFERENCES `tools` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `assessment_submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `assessment_submissions` (
  `id` binary(16) NOT NULL,
  `assessment_id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `answers` json NOT NULL,
  `result` json NOT NULL,
  `score` float NOT NULL,
  `passed` int NOT NULL,
  `submitted_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `assessment_id` (`assessment_id`),
  KEY `idx_assessment_submission_user` (`user_id`,`assessment_id`),
  CONSTRAINT `assessment_submissions_ibfk_1` FOREIGN KEY (`assessment_id`) REFERENCES `learning_assessments` (`id`) ON DELETE CASCADE,
  CONSTRAINT `assessment_submissions_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `auth_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_tokens` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `token_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` binary(16) NOT NULL,
  `token_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'access_token',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `expires_at` datetime NOT NULL,
  `is_revoked` tinyint(1) NOT NULL DEFAULT '0',
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_agent` text COLLATE utf8mb4_unicode_ci,
  `device_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token_hash` (`token_hash`),
  KEY `idx_auth_tokens_user_id` (`user_id`),
  KEY `idx_auth_tokens_expires_at` (`expires_at`),
  CONSTRAINT `auth_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=714 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `candidate_rankings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `candidate_rankings` (
  `id` binary(16) NOT NULL,
  `content_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `rank_score` float NOT NULL,
  `risk_info` json DEFAULT NULL,
  `is_selected` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_candidate_rankings_content_id` (`content_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `chapter_progress`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chapter_progress` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `course_key` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `chapter_doc_id` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `status` enum('not_started','reading','ready_for_quiz','passed') COLLATE utf8mb4_general_ci NOT NULL,
  `started_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `assistant_conversation_id` binary(16) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_chapter_progress_user_chapter` (`user_id`,`chapter_doc_id`),
  KEY `idx_chapter_progress_user_course` (`user_id`,`course_key`),
  CONSTRAINT `chapter_progress_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `code_submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `code_submissions` (
  `id` binary(16) NOT NULL,
  `assessment_id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `language` enum('python','c','cpp','java') COLLATE utf8mb4_general_ci NOT NULL,
  `mode` enum('acm','leetcode') COLLATE utf8mb4_general_ci NOT NULL,
  `code` text COLLATE utf8mb4_general_ci NOT NULL,
  `score` float NOT NULL,
  `passed` int NOT NULL,
  `verdict` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `feedback` json DEFAULT NULL,
  `submitted_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `assessment_id` (`assessment_id`),
  KEY `idx_code_submission_user` (`user_id`,`assessment_id`),
  CONSTRAINT `code_submissions_ibfk_1` FOREIGN KEY (`assessment_id`) REFERENCES `learning_assessments` (`id`) ON DELETE CASCADE,
  CONSTRAINT `code_submissions_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `content_assemblies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `content_assemblies` (
  `id` binary(16) NOT NULL,
  `plan_id` binary(16) DEFAULT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `template_type` enum('lecture','practice','quiz','summary','example') COLLATE utf8mb4_general_ci NOT NULL,
  `title` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `content_data` json NOT NULL,
  `status` enum('draft','review','published','rejected') COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_ca_plan_status` (`plan_id`,`status`),
  KEY `ix_content_assemblies_plan_id` (`plan_id`),
  KEY `ix_content_assemblies_kp_id` (`kp_id`),
  CONSTRAINT `content_assemblies_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `learning_plans` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `conversations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversations` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'New Chat',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`) USING BTREE,
  KEY `idx_conversations_user_id` (`user_id`) USING BTREE,
  KEY `idx_conversations_updated_at` (`updated_at` DESC) USING BTREE,
  CONSTRAINT `fk_conversations_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `courses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `courses` (
  `id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `summary` text COLLATE utf8mb4_general_ci,
  `page_count` int NOT NULL,
  `category` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `source` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_courses_name` (`name`),
  KEY `idx_course_category` (`category`),
  KEY `ix_courses_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `exam_attempts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `exam_attempts` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `exam_id` binary(16) NOT NULL,
  `answers` json NOT NULL,
  `score` float NOT NULL,
  `total` int NOT NULL,
  `submitted_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_exam_attempts_user_id` (`user_id`),
  KEY `ix_exam_attempts_exam_id` (`exam_id`),
  CONSTRAINT `exam_attempts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `exam_attempts_ibfk_2` FOREIGN KEY (`exam_id`) REFERENCES `exams` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `exam_questions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `exam_questions` (
  `id` binary(16) NOT NULL,
  `exam_id` binary(16) NOT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `question_type` enum('choice','fill_blank','short_answer','code','true_false') COLLATE utf8mb4_general_ci NOT NULL,
  `question_data` json NOT NULL,
  `difficulty` float NOT NULL,
  `sort_order` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_eq_exam_order` (`exam_id`,`sort_order`),
  KEY `ix_exam_questions_exam_id` (`exam_id`),
  KEY `ix_exam_questions_kp_id` (`kp_id`),
  CONSTRAINT `exam_questions_ibfk_1` FOREIGN KEY (`exam_id`) REFERENCES `exams` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `exams`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `exams` (
  `id` binary(16) NOT NULL,
  `plan_id` binary(16) DEFAULT NULL,
  `title` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_exams_plan_id` (`plan_id`),
  CONSTRAINT `exams_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `learning_plans` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `knowledge_chunks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_chunks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` binary(16) NOT NULL,
  `doc_id` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `chunk_id` int NOT NULL,
  `content` text COLLATE utf8mb4_general_ci NOT NULL,
  `chunk_metadata` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_kc_user_doc_chunk` (`user_id`,`doc_id`,`chunk_id`),
  KEY `ix_knowledge_chunks_user_id` (`user_id`),
  KEY `idx_kc_user_doc` (`user_id`,`doc_id`)
) ENGINE=InnoDB AUTO_INCREMENT=90107 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `knowledge_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_documents` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` binary(16) NOT NULL,
  `doc_id` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `title` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `category` varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `source_type` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `content_length` int NOT NULL,
  `chunk_count` int NOT NULL,
  `doc_metadata` json DEFAULT NULL,
  `added_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_kd_user_doc` (`user_id`,`doc_id`),
  KEY `ix_knowledge_documents_category` (`category`),
  KEY `ix_knowledge_documents_user_id` (`user_id`),
  KEY `idx_kd_user_category` (`user_id`,`category`),
  KEY `idx_kd_user_title` (`user_id`,`title`)
) ENGINE=InnoDB AUTO_INCREMENT=20802 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `knowledge_points`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_points` (
  `id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `category` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `difficulty` float NOT NULL,
  `tags` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_kp_category` (`category`),
  KEY `ix_knowledge_points_name` (`name`),
  KEY `ix_knowledge_points_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `kp_prerequisites`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `kp_prerequisites` (
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `prerequisite_kp_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`kp_id`,`prerequisite_kp_id`),
  KEY `ix_kp_prerequisites_prerequisite_kp_id` (`prerequisite_kp_id`),
  KEY `ix_kp_prerequisites_kp_id` (`kp_id`),
  CONSTRAINT `kp_prerequisites_ibfk_1` FOREIGN KEY (`kp_id`) REFERENCES `knowledge_points` (`id`) ON DELETE CASCADE,
  CONSTRAINT `kp_prerequisites_ibfk_2` FOREIGN KEY (`prerequisite_kp_id`) REFERENCES `knowledge_points` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learner_cognitive_load`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learner_cognitive_load` (
  `id` binary(16) NOT NULL,
  `learner_id` binary(16) NOT NULL,
  `current_load` float NOT NULL,
  `threshold` float NOT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `learner_id` (`learner_id`),
  CONSTRAINT `learner_cognitive_load_ibfk_1` FOREIGN KEY (`learner_id`) REFERENCES `learners` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learner_errors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learner_errors` (
  `id` binary(16) NOT NULL,
  `learner_id` binary(16) NOT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '知识点ID(逻辑引用)',
  `error_type` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `count` float NOT NULL,
  `last_occurrence` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_le_learner_type` (`learner_id`,`error_type`),
  KEY `ix_learner_errors_learner_id` (`learner_id`),
  KEY `ix_learner_errors_kp_id` (`kp_id`),
  CONSTRAINT `learner_errors_ibfk_1` FOREIGN KEY (`learner_id`) REFERENCES `learners` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learner_mastery`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learner_mastery` (
  `id` binary(16) NOT NULL,
  `learner_id` binary(16) NOT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL COMMENT '知识点ID(逻辑引用)',
  `level` float NOT NULL,
  `confidence` float NOT NULL,
  `last_assessed` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_learner_mastery_kp_id` (`kp_id`),
  KEY `ix_learner_mastery_learner_id` (`learner_id`),
  CONSTRAINT `learner_mastery_ibfk_1` FOREIGN KEY (`learner_id`) REFERENCES `learners` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learners`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learners` (
  `id` binary(16) NOT NULL,
  `name` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `grade` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `language` varchar(16) COLLATE utf8mb4_general_ci NOT NULL,
  `goals` json DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_learners_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learning_assessments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learning_assessments` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `course_key` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `chapter_doc_id` varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `exam_id` binary(16) DEFAULT NULL,
  `assessment_type` enum('chapter_quiz','course_exam','code_practice') COLLATE utf8mb4_general_ci NOT NULL,
  `status` enum('active','submitted','passed','failed') COLLATE utf8mb4_general_ci NOT NULL,
  `passing_score` float NOT NULL,
  `question_count` int NOT NULL,
  `blueprint` json DEFAULT NULL,
  `generated_at` datetime DEFAULT (now()),
  `submitted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `exam_id` (`exam_id`),
  KEY `idx_learning_assessment_user_scope` (`user_id`,`course_key`,`chapter_doc_id`,`assessment_type`,`status`),
  CONSTRAINT `learning_assessments_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `learning_assessments_ibfk_2` FOREIGN KEY (`exam_id`) REFERENCES `exams` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learning_mistakes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learning_mistakes` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `source_type` enum('quiz','code') COLLATE utf8mb4_general_ci NOT NULL,
  `assessment_id` binary(16) NOT NULL,
  `question_key` varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `title` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `prompt` text COLLATE utf8mb4_general_ci NOT NULL,
  `user_answer` text COLLATE utf8mb4_general_ci,
  `correct_answer` text COLLATE utf8mb4_general_ci,
  `explanation` text COLLATE utf8mb4_general_ci,
  `status` enum('open','reviewed') COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `assessment_id` (`assessment_id`),
  KEY `idx_learning_mistake_user_source` (`user_id`,`source_type`,`status`),
  CONSTRAINT `learning_mistakes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `learning_mistakes_ibfk_2` FOREIGN KEY (`assessment_id`) REFERENCES `learning_assessments` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learning_plans`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learning_plans` (
  `id` binary(16) NOT NULL,
  `learner_id` binary(16) NOT NULL,
  `goal` text COLLATE utf8mb4_general_ci,
  `status` enum('draft','active','completed','paused') COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_lp_learner_status` (`learner_id`,`status`),
  KEY `ix_learning_plans_learner_id` (`learner_id`),
  CONSTRAINT `learning_plans_ibfk_1` FOREIGN KEY (`learner_id`) REFERENCES `learners` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `learning_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `learning_tasks` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `title` varchar(160) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `task_type` varchar(32) COLLATE utf8mb4_general_ci NOT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `due_date` datetime DEFAULT NULL,
  `status` enum('todo','done') COLLATE utf8mb4_general_ci NOT NULL,
  `completed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_learning_tasks_status` (`status`),
  KEY `ix_learning_tasks_user_id` (`user_id`),
  KEY `ix_learning_tasks_due_date` (`due_date`),
  KEY `ix_learning_tasks_kp_id` (`kp_id`),
  KEY `idx_learning_task_user_status` (`user_id`,`status`),
  CONSTRAINT `learning_tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `messages` (
  `id` binary(16) NOT NULL,
  `conversation_id` binary(16) NOT NULL,
  `role` enum('user','assistant','tool','system') COLLATE utf8mb4_general_ci NOT NULL,
  `content` text COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `msg_metadata` json DEFAULT NULL COMMENT 'e.g., tool_calls, model_name, token_usage',
  `is_favored` tinyint(1) unsigned zerofill NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_messages_conversation_id` (`conversation_id`),
  KEY `idx_messages_conversation_id` (`conversation_id`),
  KEY `idx_messages_created_at` (`created_at`),
  CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `plan_knowledge_points`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `plan_knowledge_points` (
  `id` binary(16) NOT NULL,
  `plan_id` binary(16) NOT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `sort_order` int NOT NULL,
  `status` enum('pending','learning','completed','skipped') COLLATE utf8mb4_general_ci NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_plan_knowledge_points_plan_id` (`plan_id`),
  KEY `idx_pkp_plan_order` (`plan_id`,`sort_order`),
  KEY `ix_plan_knowledge_points_kp_id` (`kp_id`),
  CONSTRAINT `plan_knowledge_points_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `learning_plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `projects` (
  `id` binary(16) NOT NULL,
  `owner_id` binary(16) NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `owner_id` (`owner_id`),
  CONSTRAINT `projects_ibfk_1` FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `quality_reviews`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `quality_reviews` (
  `id` binary(16) NOT NULL,
  `content_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL COMMENT '内容ID(逻辑引用)',
  `reviewer_type` enum('auto','expert','peer') COLLATE utf8mb4_general_ci NOT NULL,
  `status` enum('pending','approved','rejected','needs_revision') COLLATE utf8mb4_general_ci NOT NULL,
  `risk_level` enum('low','medium','high') COLLATE utf8mb4_general_ci NOT NULL,
  `review_summary` text COLLATE utf8mb4_general_ci,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_qr_content` (`content_id`),
  KEY `ix_quality_reviews_content_id` (`content_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `review_defects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `review_defects` (
  `id` binary(16) NOT NULL,
  `review_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL COMMENT '审核ID(逻辑引用)',
  `defect_type` enum('factual','normative','adaptability','clarity') COLLATE utf8mb4_general_ci NOT NULL,
  `severity` enum('critical','major','minor') COLLATE utf8mb4_general_ci NOT NULL,
  `location` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `suggestion` text COLLATE utf8mb4_general_ci,
  PRIMARY KEY (`id`),
  KEY `ix_review_defects_review_id` (`review_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `skills`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `skills` (
  `id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `parameters_schema` json DEFAULT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `study_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `study_events` (
  `id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `user_id` binary(16) NOT NULL,
  `kp_id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `studied_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_study_events_kp_id` (`kp_id`),
  KEY `idx_study_user_kp` (`user_id`,`kp_id`),
  KEY `ix_study_events_user_id` (`user_id`),
  CONSTRAINT `study_events_ibfk_1` FOREIGN KEY (`kp_id`) REFERENCES `knowledge_points` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `tools`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tools` (
  `id` varchar(64) COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_general_ci NOT NULL,
  `description` text COLLATE utf8mb4_general_ci,
  `parameters_schema` json DEFAULT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_profiles` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `display_name` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `profession` varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `location` varchar(128) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `language_preference` varchar(16) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `interests` json DEFAULT NULL,
  `expertise` json DEFAULT NULL,
  `preferences` json DEFAULT NULL,
  `topic_history` json DEFAULT NULL,
  `portrait_summary` text COLLATE utf8mb4_general_ci,
  `portrait_updated_at` datetime DEFAULT NULL,
  `auto_update_enabled` tinyint(1) NOT NULL,
  `analyzed_msg_count` bigint NOT NULL,
  `last_analyzed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  `updated_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_user_profiles_user_id` (`user_id`),
  KEY `idx_user_profiles_user_id` (`user_id`),
  CONSTRAINT `user_profiles_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` binary(16) NOT NULL,
  `email` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `nickname` varchar(64) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `verification_codes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `verification_codes` (
  `id` binary(16) NOT NULL,
  `user_id` binary(16) DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb4_general_ci NOT NULL,
  `code` char(6) COLLATE utf8mb4_general_ci NOT NULL,
  `purpose` enum('register','login','reset_password') COLLATE utf8mb4_general_ci NOT NULL,
  `is_used` tinyint(1) DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` timestamp NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_email_purpose` (`email`,`purpose`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_expires_at` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

