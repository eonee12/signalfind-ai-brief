"""Telegram -> existing Google Sheet. Requires TG_API_ID, TG_API_HASH, TG_SESSION, GOOGLE_SERVICE_ACCOUNT_JSON."""
import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials
from telethon import TelegramClient
from telethon.sessions import StringSession

SHEET_ID = "14iQm3E7eykZmyirVc-s9X73xGT_J676vEsto8GDmtZM"
TAB = "Telegram_Global_21D"
CHANNELS = """insidertracking itechkorea mstaryun maddingStock BeOn_BeClear bornlupin merITz_tech Ibks_innovation_research skitteam huhjae IThardwareDisplay KISemicon eqmirae HanaResearchTelecom meritz_research HI_GS SmallCap energy_youn DBsecTech eugene2team aetherjapanresearch""".split()
KST = ZoneInfo("Asia/Seoul")
START = datetime(2026, 11, 5, tzinfo=KST).astimezone(timezone.utc)
KEYWORDS = re.compile(r"실적|매출|영업이익|가이던스|반도체|AI|수주|투자|주가|증시|금리|환율|관세|수출|earnings|guidance|revenue|semiconductor|FDA|SEC|NASDAQ|NYSE|KOSPI|KOSDAQ|\$[A-Z]{2,5}", re.I)
TICKERS = re.compile(r"\$([A-Z]{1,5})\b")
HEADERS = ["market","collected_at_kst","source","post_time","tickers","sector_theme","category","summary","sentiment","importance","verification","source_url","expires_at_kst"]

async def main():
    credentials = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    ws = gspread.authorize(credentials).open_by_key(SHEET_ID).worksheet(TAB)
    existing = ws.get_all_values()
    if not existing or existing[0][:13] != HEADERS:
        raise RuntimeError("Sheet header mismatch; refusing to write")
    seen = {row[11].strip() for row in existing[1:] if len(row) > 11 and row[11].strip()}
    now = datetime.now(KST)
    rows = []
    failures = []
    async with TelegramClient(StringSession(os.environ["TG_SESSION"]),
                              int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as client:
        for channel in CHANNELS:
            count = 0
            try:
                async for msg in client.iter_messages(channel, limit=None):
                    if not msg.date:
                        continue
                    posted = msg.date.astimezone(timezone.utc)
                    if posted < START:
                        break
                    url = f"https://t.me/{channel}/{msg.id}"
                    if url in seen:
                        continue
                    body = (msg.raw_text or "").strip()
                    if not body or not KEYWORDS.search(body):
                        continue
                    local = posted.astimezone(KST)
                    summary = " ".join(body.split())[:1000]
                    tickers = ",".join(dict.fromkeys(TICKERS.findall(body)))
                    market = "US" if tickers or re.search(r"NASDAQ|NYSE|미국|\bFED\b", body, re.I) else "KR"
                    rows.append([market, now.strftime("%Y-%m-%d %H:%M:%S"),
                                 channel, local.strftime("%Y-%m-%d %H:%M:%S"),
                                 tickers, "", "TELEGRAM", summary,
                                 "중립", "C", "원문 게시시각 확인; 사실관계 별도 검증 필요",
                                 url, (local + timedelta(days=21)).strftime("%Y-%m-%d %H:%M:%S")])
                    seen.add(url)
                    count += 1
                print(f"{channel}: {count} candidates")
            except Exception as exc:
                failures.append(f"{channel}: {type(exc).__name__}: {exc}")
    if failures:
        print("CHANNEL FAILURES:", *failures, sep="\n")
        raise RuntimeError("Incomplete channel collection; no rows written")
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
    print(f"APPENDED={len(rows)}; duplicates excluded; old rows untouched")

if __name__ == "__main__":
    asyncio.run(main())
