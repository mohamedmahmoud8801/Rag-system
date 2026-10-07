from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class VideoInterface(ABC):

    @abstractmethod
    async def get_video_metadata(
        self,
        video_url: str
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_transcript(
        self,
        video_url: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_video(
        self,
        video_url: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        pass