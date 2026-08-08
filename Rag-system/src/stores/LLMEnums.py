from enum import Enum

class LLMEnums (Enum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    COHERE = "COHERE"
    HUGGINGFACE = "HUGGINGFACE"


class OpenAIEnums (Enum):
    SYSTEM = "system",
    USER = "user",
    ASSISTANT = "assistant",


class CohereEnums (Enum):
    SYSTEM = "SYSTEM",
    USER = "USER",
    ASSISTANT = "CHATBOT",
    DOCUMENT = "search_document"
    QUERY = "search_query"    


class DocumentTypeEnums (Enum):
    DOCUMENT = "document",
    QUERY = "query",