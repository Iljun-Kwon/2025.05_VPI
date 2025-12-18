# youtube_video_collector.py

import os
import isodate
from datetime import datetime, timezone
from typing import List, Dict
from youtube.api_key import build_youtube_with_fallback


from supabase import create_client, Client

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
VIDEO_CUTOFF_UTC = datetime(2025, 12, 16, 15, 0, tzinfo=timezone.utc)

def _parse_yt_published_at_utc(published_at: str) -> datetime:
    return datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(timezone.utc)

def fetch_videos_from_channel(channel_id: str) -> List[Dict]:
    youtube = build_youtube_with_fallback()

    # Step 1: upload playlist ID 얻기
    channel_response = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    if channel_response.get("items"):
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    else:
        print(f"[❌] 채널 정보를 찾을 수 없습니다: {channel_id}")
        return []

    # Step 2: 영상 50개 가져오기
    playlist_response = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_playlist_id,
        maxResults=50
    ).execute()

    items = playlist_response.get("items", [])
    if not items:
        return []

    # ✅ Filter by publishedAt using UTC cutoff
    # Uploads playlist is newest -> oldest, so we can "break" once older than cutoff.
    filtered_video_ids: List[str] = []
    for item in items:
        published_at = item.get("snippet", {}).get("publishedAt")
        if not published_at:
            continue

        published_dt_utc = _parse_yt_published_at_utc(published_at)
        if published_dt_utc < VIDEO_CUTOFF_UTC:
            break  # stop early (older videos beyond this are also older)

        vid = item.get("contentDetails", {}).get("videoId")
        if vid:
            filtered_video_ids.append(vid)

    if not filtered_video_ids:
        return []

    # Step 3: video statistics 포함된 video 상세 정보 얻기
    videos_response = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(filtered_video_ids)
    ).execute()

    return videos_response.get("items", [])

def parse_duration_to_seconds(duration_str: str) -> int:
    """ISO 8601 duration → 초 단위 정수 변환"""
    try:
        duration = isodate.parse_duration(duration_str)
        return int(duration.total_seconds())
    except Exception:
        return 0

def store_videos_and_snapshots(channel_id: str, videos: List[Dict], collected_at_utc: str):
    video_records = []
    snapshot_records = []

    for video in videos:
        vid = video["id"]
        snippet = video["snippet"]
        stats = video.get("statistics", {})
        content_details = video.get("contentDetails", {})
        
        # 1. 영상 길이(duration)를 ISO 8601 문자열 -> 초 단위 정수(int)로 변환
        duration_str = content_details.get("duration", "")
        duration_seconds = parse_duration_to_seconds(duration_str)
        
        # 2. 카테고리 ID를 문자열 -> 정수(int)로 변환
        category_id_str = snippet.get("categoryId")
        category_id = int(category_id_str) if category_id_str and category_id_str.isdigit() else None
        
        video_records.append({
            "video_id": vid,
            "channel_id": channel_id,
            "title": snippet.get("title"),
            "published_at": snippet.get("publishedAt"),
            "video_length": duration_seconds, 
            "category_id": category_id,       
            "is_short": duration_seconds <= 140,  # 140초 이하이면 Shorts
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url")
        })

        snapshot_records.append({
            "video_id": vid,
            "collected_at": collected_at_utc,
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0))
        })
        
    return video_records, snapshot_records
    
   
