import os
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from dotenv import load_dotenv
import re
from tqdm import tqdm  # ✅ tqdm 추가

# .env 로드
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("환경 변수 SUPABASE_URL 또는 SUPABASE_SERVICE_KEY가 없습니다.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

KST = timezone(timedelta(hours=9))
_MICRO_RE = re.compile(r"(\.\d{1,6})(\d*)")

# 페이징 처리 설정
BATCH_SIZE = 1000

def _normalize_iso_fraction(s: str) -> str:
    if "." not in s:
        return s
    # Keep first 1~6 digits; ignore extra
    return _MICRO_RE.sub(lambda m: m.group(1)[:7], s)

def _parse_iso_to_utc(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None

    dt_str = dt_str.strip().replace("Z", "+00:00")
    dt_str = _normalize_iso_fraction(dt_str)

    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)

def backfill_collected_at_kst():
    updated_total = 0
    offset = 0
    batch_num = 0

    while True:
        # Pull a page
        resp = (
            supabase.table("video_snapshots")
            .select("id,collected_at")
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )

        rows: List[Dict] = resp.data or []
        if not rows:
            break

        batch_num += 1
        updates: List[Dict] = []

        for row in tqdm(rows, desc=f"Batch {batch_num}", unit="row"):
            snapshot_id = row.get("id")
            collected_at_str = row.get("collected_at")

            if not snapshot_id or not collected_at_str:
                continue

            utc_dt = _parse_iso_to_utc(collected_at_str)
            if utc_dt is None:
                continue

            kst_dt = utc_dt.astimezone(KST).isoformat()

            updates.append({
                "id": snapshot_id,
                "collected_at_kst": kst_dt
            })

        # ✅ ONE request per batch
        if updates:
            supabase.table("video_snapshots").upsert(updates, on_conflict=["id"]).execute()
            updated_total += len(updates)

        offset += BATCH_SIZE

    print(f"[✅] Backfill done. Updated rows: {updated_total}")

if __name__ == "__main__":
    backfill_collected_at_kst()
