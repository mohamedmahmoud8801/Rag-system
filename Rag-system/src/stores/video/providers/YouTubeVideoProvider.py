import re

from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

from stores.video.VideoInterface import VideoInterface


class YouTubeVideoProvider(VideoInterface):

    def __init__(self):
        self.transcript_api = YouTubeTranscriptApi()

    def extract_video_id(self, video_url: str) -> str:

        if not video_url:
            raise ValueError("Video URL is required.")

        parsed_url = urlparse(video_url)

        if parsed_url.hostname in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
        }:

            query = parse_qs(parsed_url.query)

            video_id = query.get("v")

            if video_id:
                return video_id[0]

            match = re.search(
                r"/shorts/([^/?]+)",
                parsed_url.path
            )

            if match:
                return match.group(1)

            match = re.search(
                r"/embed/([^/?]+)",
                parsed_url.path
            )

            if match:
                return match.group(1)

        if parsed_url.hostname == "youtu.be":

            video_id = parsed_url.path.strip("/").split("/")[0]

            if video_id:
                return video_id

        raise ValueError(
            "Invalid YouTube URL. Could not extract video ID."
        )

    async def get_video_metadata(
        self,
        video_url: str
    ) -> Dict[str, Any]:

        video_id = self.extract_video_id(video_url)

        return {
            "video_id": video_id,
            "video_url": video_url,
            "source_type": "youtube",
        }

    async def get_transcript(
        self,
        video_url: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:

        video_id = self.extract_video_id(video_url)

        try:

            if language:

                transcript = self.transcript_api.fetch(
                    video_id,
                    languages=[language]
                )

            else:

                transcript_list = self.transcript_api.list(
                    video_id
                )

                transcript = None

                for item in transcript_list:

                    if not item.is_generated:
                        transcript = item.fetch()
                        break

                if transcript is None:

                    for item in transcript_list:
                        transcript = item.fetch()
                        break

                if transcript is None:
                    raise ValueError(
                        "No transcript available for this video."
                    )

            result = []

            for item in transcript:

                text = item.text.strip()

                if not text:
                    continue

                start_time = float(item.start)
                duration = float(item.duration)

                result.append({
                    "text": text,
                    "start_time": start_time,
                    "end_time": start_time + duration,
                })

            if not result:
                raise ValueError(
                    "Transcript was found but contains no usable text."
                )

            return result

        except Exception as e:

            raise RuntimeError(
                f"Failed to retrieve YouTube transcript: {str(e)}"
            ) from e

    async def get_video(
        self,
        video_url: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:

        metadata = await self.get_video_metadata(
            video_url
        )

        transcript = await self.get_transcript(
            video_url,
            language
        )

        metadata["transcript"] = transcript

        metadata["transcript_segments"] = len(
            transcript
        )

        if transcript:

            metadata["duration"] = max(
                item["end_time"]
                for item in transcript
            )

        return metadata