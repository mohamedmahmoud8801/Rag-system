from enum import Enum


class RouterIntentEnum(Enum):

    RAG = "rag"
    SQL = "sql"

    KNOWLEDGE_QA = "knowledge_qa"
    KNOWLEDGE_SUMMARY = "knowledge_summary"
    KNOWLEDGE_KEY_POINTS = "knowledge_key_points"
    KNOWLEDGE_NOTES = "knowledge_notes"
    KNOWLEDGE_FLASHCARDS = "knowledge_flashcards"
    KNOWLEDGE_QUIZ = "knowledge_quiz"
