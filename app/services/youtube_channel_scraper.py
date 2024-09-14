import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi


class YoutubeScraper:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.video_ids = []

    def get_video_ids(self, limit: int = 20):
        videos = scrapetube.get_channel(channel_id=self.channel_id)
        cnt = 0
        for video in videos:
            self.video_ids.append(video["videoId"])
            cnt += 1
            if cnt >= limit:
                break
        return self.video_ids

    def __get_video_transcript_util(self, video_id: str):
        try:
            raw_transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcript = " ".join([t["text"] for t in raw_transcript])
            return transcript
        except Exception as e:
            print(f"Could not get transcript for video {video_id}: {str(e)}")
            return None  # Handle the error as needed

    def get_video_transcript(self, video_id: str = None):
        if video_id is not None:
            return self.__get_video_transcript_util(video_id)
        transcripts = {}
        for v_id in self.video_ids:
            transcript = self.__get_video_transcript_util(v_id)
            transcripts[v_id] = transcript
        return transcripts
