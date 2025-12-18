# channels_test 테입르에서 channel_id 리스트를 가져와서
# 유튜브 API로 채널 정보와 영상을 수집하고, Supabase에 저장하는 코드입니다.
from youtube.channel_initializer import fetch_channel_admin_list, initialize_channels_from_admins
from youtube.youtube_channel_collector import get_channel_ids_from_supabase, fetch_and_store_channel_data
from youtube.youtube_video_collector import fetch_videos_from_channel, store_videos_and_snapshots
from supabase import create_client, Client
import os
from datetime import datetime, timezone

# Supabase 설정
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

if __name__ == "__main__":
    RUN_COLLECTED_AT = datetime.now(timezone.utc).isoformat()

    admins = fetch_channel_admin_list()
    initialize_channels_from_admins(admins)
    
    # 채널 ID 리스트를 Supabase에서 가져옵니다.
    test_channel_ids = get_channel_ids_from_supabase()

    # 각 채널 ID에 대해 채널 정보를 수집하고 Supabase에 저장합니다.
    fetch_and_store_channel_data(test_channel_ids, RUN_COLLECTED_AT)
    
    # 각 채널 ID에 대해 영상을 수집하고 Supabase에 저장합니다.
    for channel_id in test_channel_ids:
        videos = fetch_videos_from_channel(channel_id)
        video_records, snapshot_records = store_videos_and_snapshots(channel_id, videos, RUN_COLLECTED_AT)

        if not video_records:
            continue

        try:
            # 영상 업서트
            supabase.table("videos").upsert(video_records, on_conflict=["video_id"]).execute()

            # snapshot 저장
            supabase.table("video_snapshots").insert(snapshot_records).execute()

        except Exception as e:
            print(f"[❌] 채널 수집 실패 (건너뜀): {channel_id}")
            print(f"[ERROR] {e}")
            continue  # 👉 다음 채널로 넘어가기