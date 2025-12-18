# import os
# from dotenv import load_dotenv

# load_dotenv()

# API_KEYS = [
#     os.getenv('API_KEY_20'),
#     os.getenv('API_KEY_10')
# ]

# API_KEY = API_KEYS[1]

import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# 여러 키 불러오기
API_KEYS = [os.environ[k] for k in sorted(os.environ) if k.startswith('API_KEY_')]

def build_youtube_with_fallback(api_keys=API_KEYS):
    """
    여러 API 키 중 사용 가능한 키로 YouTube 객체를 생성 (자동 스위칭)
    """
    for key in api_keys:
        try:
            youtube = build('youtube', 'v3', developerKey=key)
            # 테스트 요청: 유효성 + quota 체크용
            youtube.channels().list(part='snippet', id='UC_x5XG1OV2P6uZZ5FSM9Ttw').execute()
            print(f"[✅] 사용 중인 API KEY: {key}")
            return youtube
        except HttpError as e:
            if 'quotaExceeded' in str(e):
                print(f"[❌] quotaExceeded: {key}")
                continue
            else:
                raise e
    raise RuntimeError("❌ 모든 API 키의 quota가 초과되었습니다.")