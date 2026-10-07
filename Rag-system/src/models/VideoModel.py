from typing import Any, Dict, List, Optional

from stores.video.VideoInterface import VideoInterface


class VideoModel:

    def __init__(
        self,
        provider: VideoInterface
    ):
        self.provider = provider

    @classmethod
    async def create_instance(
        cls,
        provider: VideoInterface
    ):

        instance = cls(
            provider=provider
        )

        return instance

    async def get_video_metadata(
        self,
        video_url: str
    ) -> Dict[str, Any]:

        return await self.provider.get_video_metadata(
            video_url=video_url
        )

    async def get_transcript(
        self,
        video_url: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        return await self.provider.get_transcript(
            video_url=video_url,
            language=language
        )

    async def get_video(
        self,
        video_url: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:

        return await self.provider.get_video(
            video_url=video_url,
            language=language
        )