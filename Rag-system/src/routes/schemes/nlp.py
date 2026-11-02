from pydantic import BaseModel
from typing import Optional,List

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0    

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 20
    file_id: Optional[str] = None



class RAGEvalRequest(BaseModel):
    question: str
    answer: str
    contexts: List[str]
