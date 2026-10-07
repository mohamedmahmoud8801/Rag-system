from stores.video.VideoEnums import VideoProviderEnum
from stores.video.providers.YouTubeVideoProvider import (
    YouTubeVideoProvider
)


class VideoProviderFactory:

    @staticmethod
    def create(provider: str):

        if not provider:
            raise ValueError(
                "Video provider is required."
            )

        provider = provider.lower().strip()

        if provider == VideoProviderEnum.YOUTUBE.value:
            return YouTubeVideoProvider()

        raise ValueError(
            f"Unsupported video provider: {provider}"
        )