from abc import ABC,abstractmethod
import os
import re
import httpx


class VideoProvider(ABC):
    @abstractmethod
    async def search_exercise_video(self,exercise_name: str,limit: int=3) -> list[dict]: ...


class MockVideoProvider(VideoProvider):
    """No fabricated links. Tests may inject explicit fixtures."""
    def __init__(self,fixtures: list[dict] | None=None):
        self.fixtures=fixtures or []

    async def search_exercise_video(self,exercise_name: str,limit: int=3) -> list[dict]:
        return self.fixtures[:limit]


class YouTubeVideoProvider(VideoProvider):
    async def search_exercise_video(self,exercise_name: str,limit: int=3) -> list[dict]:
        key=os.getenv("YOUTUBE_API_KEY")
        if not key: raise ValueError("未配置视频检索服务")
        async with httpx.AsyncClient(timeout=8) as client:
            response=await client.get("https://www.googleapis.com/youtube/v3/search",params={
                "key":key,"part":"snippet","type":"video","q":exercise_name+" 标准动作 中文教学",
                "relevanceLanguage":"zh-Hans","maxResults":max(1,min(limit,3)),"safeSearch":"strict"})
            response.raise_for_status()
        videos=[]
        for item in response.json().get("items",[]):
            identifier=item.get("id",{}).get("videoId","")
            title=item.get("snippet",{}).get("title","")
            if re.fullmatch(r"[\w-]{11}",identifier) and re.search(r"[\u4e00-\u9fff]",title):
                videos.append({"title":title,"url":"https://www.youtube.com/watch?v="+identifier,
                               "thumbnail":None,"channel":item["snippet"].get("channelTitle"),"source":"youtube"})
        return videos
