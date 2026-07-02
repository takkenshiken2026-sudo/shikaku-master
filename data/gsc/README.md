# GSC（Google Search Console）データの取得と分析

このディレクトリに Search Console のデータ（CSV）とレポート（`report.md`）を置く。
取得（`tools/gsc_fetch.py`）・分析（`tools/gsc_analyze.py`）ともに **無料** で完結する。

分析は 2 通りの入力に対応する。手軽さ優先なら A、全自動化なら B。

---

## A. 手動エクスポートを分析するだけ（認証不要・最も手軽）

1. [Search Console](https://search.google.com/search-console) を開く。
2. 「検索結果のパフォーマンス」→ 右上 **エクスポート** → CSV（ZIP）をダウンロード。
3. ZIP を展開し、`Queries.csv` `Pages.csv`（日本語なら同等の内容）を
   この `data/gsc/` に置く。
4. 分析を実行:

   ```bash
   python3 tools/gsc_analyze.py
   ```

   → `data/gsc/report.md` が生成される。

日本語/英語どちらのヘッダでも読める。CTR の `%` 表記も自動処理する。

---

## B. API で自動取得（サービスアカウント・無料）

### 1回だけの準備（すべて無料）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成。
2. 「API とサービス」→ ライブラリ →
   **Google Search Console API** を有効化。
3. 「認証情報」→ サービスアカウントを作成 → 鍵を追加（JSON）でダウンロード。
   - この JSON は**絶対にコミットしない**（`.gitignore` 済み）。
4. Search Console → 対象プロパティ → 設定 → **ユーザーと権限** →
   サービスアカウントのメール（`...@....iam.gserviceaccount.com`）を
   「制限付き」で追加。
5. 依存をインストール:

   ```bash
   pip install -r tools/requirements-gsc.txt
   ```

### 取得と分析

```bash
export GSC_CREDENTIALS_FILE=/path/to/service-account.json
export GSC_PROPERTY='sc-domain:shikaku-master.jp'   # or 'https://shikaku-master.jp/'

python3 tools/gsc_fetch.py       # data/gsc/ に CSV 保存（既定は直近28日）
python3 tools/gsc_analyze.py     # data/gsc/report.md を生成
```

日付範囲を変える:

```bash
python3 tools/gsc_fetch.py --days 90
python3 tools/gsc_fetch.py --start 2026-06-01 --end 2026-06-28
```

---

## C. GitHub Actions で完全自動化（無料）

`.github/workflows/gsc.yml` が用意済み（毎週月曜に実行 + 手動実行可）。
リポジトリの Settings → Secrets and variables → Actions に登録:

- `GSC_CREDENTIALS_JSON` … サービスアカウント鍵 JSON の中身をそのまま貼り付け
- `GSC_PROPERTY` … 例 `sc-domain:shikaku-master.jp`

実行されると `data/gsc/report.md` を更新してコミットし、artifact にも残す。

---

## レポートの内容

`report.md` には次が含まれる:

- **サマリ**: 合計クリック / 表示回数 / 平均 CTR / 平均掲載順位
- **資格ページ単位の集計**: URL を slug に変換し `certifications.csv` の資格名と
  紐づけて集計。クリック上位、および「表示は多いがクリックが少ない（伸びしろ）」
- **SEO 改善候補**
  - ストライキングディスタンス（掲載順位 5〜20 位・表示が多い＝あと一歩）
  - 低 CTR（上位表示なのにクリックが取れていない＝機会損失。想定クリック増つき）
- **クエリ分析**: クリック上位クエリ、資格名を含まない需要語（コンテンツ拡充のヒント）

しきい値や件数は調整可能:

```bash
python3 tools/gsc_analyze.py --min-impressions 30 --top 50
```
