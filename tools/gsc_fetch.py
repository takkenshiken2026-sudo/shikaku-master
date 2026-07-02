#!/usr/bin/env python3
"""Google Search Console (Search Analytics API) からデータを取得して
data/gsc/ に CSV 保存する。取得は無料。認証はサービスアカウント（無料）。

出力（既定の日付範囲は「終了 = 3日前 / 開始 = 終了の28日前」。GSC はデータ確定に
2〜3日かかるため、直近を避ける）:
  data/gsc/gsc_pages_<start>_<end>.csv        … dimensions=page
  data/gsc/gsc_queries_<start>_<end>.csv      … dimensions=query
  data/gsc/gsc_page_query_<start>_<end>.csv   … dimensions=page,query

いずれも列は page/query/clicks/impressions/ctr/position（CTR は 0〜1 の割合）。
取得後は tools/gsc_analyze.py でレポート化できる。

--- 事前準備（すべて無料）-------------------------------------------------
1. Google Cloud で新規プロジェクト → 「Google Search Console API」を有効化。
2. サービスアカウントを作成し、JSON 鍵をダウンロード（この鍵は絶対にコミット
   しない。data/gsc/ は .gitignore 済み。鍵は環境変数で渡す）。
3. Search Console のプロパティ設定 → ユーザーと権限 → サービスアカウントの
   メールアドレス（xxx@xxx.iam.gserviceaccount.com）を「制限付き」で追加。
4. 依存をインストール: pip install -r tools/requirements-gsc.txt
5. 認証情報とプロパティを環境変数で指定して実行:
     export GSC_CREDENTIALS_FILE=/path/to/service-account.json
     export GSC_PROPERTY='sc-domain:shikaku-master.jp'   # or 'https://shikaku-master.jp/'
     python3 tools/gsc_fetch.py
   （GitHub Actions では鍵 JSON を Secret に入れ、GSC_CREDENTIALS_JSON で渡す）

使い方:
  python3 tools/gsc_fetch.py
  python3 tools/gsc_fetch.py --start 2026-06-01 --end 2026-06-28
  python3 tools/gsc_fetch.py --property 'https://shikaku-master.jp/' --days 90
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GSC_DIR = ROOT / "data" / "gsc"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
ROW_LIMIT = 25000  # API の 1 リクエスト上限


def load_credentials():
    """サービスアカウント認証情報を返す。
    GSC_CREDENTIALS_JSON（JSON 文字列）優先、無ければ GSC_CREDENTIALS_FILE（パス）。
    """
    try:
        from google.oauth2 import service_account
    except ImportError:
        sys.exit("google-auth が未インストールです。\n"
                 "  pip install -r tools/requirements-gsc.txt")

    raw = os.environ.get("GSC_CREDENTIALS_JSON")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES)

    path = os.environ.get("GSC_CREDENTIALS_FILE")
    if path and Path(path).exists():
        return service_account.Credentials.from_service_account_file(
            path, scopes=SCOPES)

    sys.exit("認証情報がありません。GSC_CREDENTIALS_JSON か GSC_CREDENTIALS_FILE を"
             "設定してください（tools/gsc_fetch.py の冒頭コメント参照）。")


def build_service(creds):
    try:
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("google-api-python-client が未インストールです。\n"
                 "  pip install -r tools/requirements-gsc.txt")
    # cache_discovery=False で file_cache の警告を回避
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def query_all(service, site_url, start, end, dimensions):
    """指定ディメンションで全行をページングして取得する。"""
    rows = []
    start_row = 0
    while True:
        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions,
            "rowLimit": ROW_LIMIT,
            "startRow": start_row,
            "dataState": "final",
        }
        resp = service.searchanalytics().query(
            siteUrl=site_url, body=body).execute()
        batch = resp.get("rows", [])
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            break
        start_row += ROW_LIMIT
    return rows


def write_csv(path, dimensions, rows):
    header = list(dimensions) + ["clicks", "impressions", "ctr", "position"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            keys = r.get("keys", [])
            w.writerow(list(keys) + [
                int(r.get("clicks", 0)),
                int(r.get("impressions", 0)),
                r.get("ctr", 0.0),
                r.get("position", 0.0),
            ])


def default_dates(days):
    end = dt.date.today() - dt.timedelta(days=3)   # データ確定待ち
    start = end - dt.timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def main():
    ap = argparse.ArgumentParser(description="GSC データ取得")
    ap.add_argument("--property", default=os.environ.get("GSC_PROPERTY"),
                    help="対象プロパティ。例 'sc-domain:shikaku-master.jp' "
                         "または 'https://shikaku-master.jp/'")
    ap.add_argument("--days", type=int, default=28,
                    help="取得日数（--start/--end 未指定時に使用。既定28）")
    ap.add_argument("--start", help="開始日 YYYY-MM-DD")
    ap.add_argument("--end", help="終了日 YYYY-MM-DD")
    args = ap.parse_args()

    site_url = args.property
    if not site_url:
        sys.exit("プロパティ未指定です。--property か環境変数 GSC_PROPERTY を"
                 "設定してください。")

    if args.start and args.end:
        start, end = args.start, args.end
    else:
        start, end = default_dates(args.days)

    creds = load_credentials()
    service = build_service(creds)

    GSC_DIR.mkdir(parents=True, exist_ok=True)
    tag = f"{start}_{end}"
    jobs = [
        (["page"], GSC_DIR / f"gsc_pages_{tag}.csv"),
        (["query"], GSC_DIR / f"gsc_queries_{tag}.csv"),
        (["page", "query"], GSC_DIR / f"gsc_page_query_{tag}.csv"),
    ]

    print(f"プロパティ: {site_url}")
    print(f"期間: {start} 〜 {end}\n")
    for dims, path in jobs:
        try:
            rows = query_all(service, site_url, start, end, dims)
        except Exception as e:  # noqa: BLE001 — API エラーは分かりやすく表示
            sys.exit(f"取得失敗（dimensions={dims}）: {e}\n"
                     f"プロパティ名・サービスアカウントの権限付与を確認してください。")
        write_csv(path, dims, rows)
        print(f"  {'+'.join(dims):16s} {len(rows):>6,} 行 → {path.name}")

    print(f"\n完了。分析: python3 tools/gsc_analyze.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
