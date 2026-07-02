# 資格カタログ / shikaku-master

日本の資格を「探せる・絞れる・比べられる」資格データベース・メディア。
厚生労働省 ハローワークの「免許・資格コード一覧（小分類）」を正本シードに、
CSV → Python ジェネレータ → 静的HTML を生成する量産型サイト。

公開サイト: https://shikaku-master.jp/

- 検索・分野/区分での絞り込み・**受験料/合格率での並び替え**・**比較（最大4件）**
- 受験料・試験形式・受験資格・合格率・実施団体・公式URLを**公式の一次情報**に基づき掲載（約862件）
- SEO対応（メタ説明・OGP・canonical・sitemap.xml・robots.txt・パンくずJSON-LD）
- データ方針と出典は `data/SOURCES.md`、整合性検査は `python3 tools/validate.py`

## 構成

```
data/
  sources/hellowork_license_list.tsv   # 正本シード（ハローワーク全1078件・原文ママ）
  certifications.csv                    # 資格カタログ本体（分類済みデータ）
tools/
  build_seed.py                         # TSV → certifications.csv（NFKC正規化・分類）
  classify_rules.py                     # 大分類(21) / 国家・公的・民間 の判定ルール
  build_pages.py                        # certifications.csv → site/（静的サイト）
  gsc_fetch.py                          # Search Console API → data/gsc/ CSV（無料）
  gsc_analyze.py                        # GSC CSV → SEO分析レポート（標準ライブラリのみ）
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

## SEO 分析（Search Console）

Search Console のデータを取り込んで SEO 改善候補を抽出できる（取得・分析とも無料）。

```bash
# 手軽: GSC管理画面からエクスポートしたCSVを data/gsc/ に置いて分析するだけ
python3 tools/gsc_analyze.py

# 自動: サービスアカウントでAPIから取得 → 分析
export GSC_CREDENTIALS_FILE=/path/to/service-account.json
export GSC_PROPERTY='sc-domain:shikaku-master.jp'
python3 tools/gsc_fetch.py && python3 tools/gsc_analyze.py
```

`data/gsc/report.md` に、資格ページ単位の集計・ストライキングディスタンス
（あと一歩で上位化）・低CTR（機会損失）・クエリ分析が出力される。
GitHub Actions（`.github/workflows/gsc.yml`）で定期実行も可能。
セットアップ詳細は `data/gsc/README.md`。

## データの考え方（3層ソース戦略）

1. **シード（網羅）**: ハローワーク コード一覧 … 資格名＋カテゴリの抜け漏れない骨格
2. **充実**: 職業情報提供サイト job tag 等で受験資格・関連職業を補完
3. **検証（事実値）**: 各資格の実施団体 **公式サイト** で受験料・合格率・日程・公式URLを確認

数値・制度は必ず公式の一次情報で確認すること（`type_confidence` / `type_reason` / `source_checked_at` 列で管理）。

## 分類の現状

- 大分類: 21 分野
- 区分: 国家 614 / 公的 58 / 民間 43 / 要確認 297 / 海外 6（バケット・重複除く）
- 「要確認」は出典で公的・民間の判断が割れるもの。一次情報での精査待ち。

## ライセンス / 出典

資格名・分類コードの出典: 厚生労働省 ハローワーク 免許・資格コード一覧。
本リポジトリは学習・メディア目的のプロトタイプ。
