# 資格マスター / shikaku-master

日本の資格を「探せる・絞れる・比べられる」資格データベース・メディア。
厚生労働省 ハローワークの「免許・資格コード一覧（小分類）」を正本シードに、
CSV → Python ジェネレータ → 静的HTML を生成する量産型サイト。

公開サイト: https://shikaku-master.jp/

- 検索・分野/区分での絞り込み・**受験料/合格率での並び替え**・**比較（最大4件）**
- 受験料・試験形式・受験資格・合格率・実施団体・公式URLを**公式の一次情報**に基づき掲載（約1,050件）
- SEO対応（メタ説明・OGP・canonical・sitemap.xml・robots.txt・パンくずJSON-LD）
- データ方針と出典は `data/SOURCES.md`、整合性検査は `python3 tools/validate.py`

## 構成

```
data/
  sources/hellowork_license_list.tsv   # 正本シード（ハローワーク全1078件・原文ママ）
  certifications.csv                    # 資格カタログ本体（分類済みデータ）
  extra_certs.csv                       # ハローワーク一覧に無い主要資格の追加シード（生成AIパスポート・英検下位級等）
tools/
  build_seed.py                         # TSV → certifications.csv（NFKC正規化・分類）
  classify_rules.py                     # 大分類(21) / 国家・公的・民間 の判定ルール
  build_pages.py                        # certifications.csv → site/（静的サイト）
site/                                   # 生成物（トップ＋詳細1008ページ＋検索JSON）
```

## ビルド

```bash
python3 tools/build_seed.py     # data/certifications.csv を生成
python3 tools/build_pages.py    # site/ を生成
```

## ローカル確認

```bash
cd site && python3 -m http.server 8000   # http://localhost:8000
```

## データの考え方（3層ソース戦略）

1. **シード（網羅）**: ハローワーク コード一覧 … 資格名＋カテゴリの抜け漏れない骨格
2. **充実**: 職業情報提供サイト job tag 等で受験資格・関連職業を補完
3. **検証（事実値）**: 各資格の実施団体 **公式サイト** で受験料・合格率・日程・公式URLを確認

数値・制度は必ず公式の一次情報で確認すること（`type_confidence` / `type_reason` / `source_checked_at` 列で管理）。

### 合格率の補完パイプライン（`tools/pass_rate_pipeline.py`）

合格率（`pass_rate`）は公開ページの多くで未入力。GSC の検索意図でも上位のため、
**出典URL＋確認日を必須にした証跡付き**で安全に穴埋めするワークフローを用意している。
憶測値の混入は apply 側の検証で機械的に却下される。

```bash
# 1) 穴埋めリストを書き出す（GSC表示回数の多い順に並ぶ）
python3 tools/pass_rate_pipeline.py export      # → data/worklist_pass_rate.csv

# 2) worklist の pass_rate / source_url / checked_at を公式一次情報で記入

# 3) 検証して正本 data/overrides.csv に反映（証跡は data/pass_rate_sources.csv へ）
python3 tools/pass_rate_pipeline.py apply --dry-run   # まず検証だけ
python3 tools/pass_rate_pipeline.py apply             # 反映
python3 tools/build_seed.py && python3 tools/validate.py && python3 tools/build_pages.py
```

- 記入行は `source_url`（出典）と `checked_at`（`YYYY-MM-DD`）が両方必須。欠けると却下。
- `pass_rate` は `%` か「非公表」を含まない値を却下（形式チェック）。
- 空欄行は既存値を消さない。既登録は既定でスキップ（`--overwrite` で上書き）。
- GSC のページ別表示回数は `data/gsc_page_impressions.json` を優先度付けに使用。

## 分類の現状

- 大分類: 21 分野
- 区分: 国家 614 / 公的 58 / 民間 43 / 要確認 297 / 海外 6（バケット・重複除く）
- 「要確認」は出典で公的・民間の判断が割れるもの。一次情報での精査待ち。

## ライセンス / 出典

資格名・分類コードの出典: 厚生労働省 ハローワーク 免許・資格コード一覧。
本リポジトリは学習・メディア目的のプロトタイプ。
