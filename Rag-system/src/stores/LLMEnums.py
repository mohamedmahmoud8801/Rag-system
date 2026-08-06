from enum import Enum

class LLMEnums (Enum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    COHERE = "COHERE"
    HUGGINGFACE = "HUGGINGFACE"


class OpenAIEnums (Enum):
    system = "system",
    USER = "user",
    ASSISTANT = "assistant",