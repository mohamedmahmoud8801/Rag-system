from pydantic import BaseModel
from typing import Optional

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0    

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 20
    file_id: Optional[str] = None # 👈 ضيف السطر ده