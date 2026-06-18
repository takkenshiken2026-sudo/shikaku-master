# 資格カタログ（仮）/ shikaku-catalog

日本の資格を「探せる・絞れる・比べられる」資格データベース・メディア。
厚生労働省 ハローワークの「免許・資格コード一覧（小分類）」を正本シードに、
CSV → Python ジェネレータ → 静的HTML を生成する量産型サイト。

## 構成

```
data/
  sources/hellowork_license_list.tsv   # 正本シード（ハローワーク全1078件・原文ママ）
  certifications.csv                    # 資格カタログ本体（分類済みデータ）
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

## 分類の現状

- 大分類: 21 分野
- 区分: 国家 614 / 公的 58 / 民間 43 / 要確認 297 / 海外 6（バケット・重複除く）
- 「要確認」は出典で公的・民間の判断が割れるもの。一次情報での精査待ち。

## ライセンス / 出典

資格名・分類コードの出典: 厚生労働省 ハローワーク 免許・資格コード一覧。
本リポジトリは学習・メディア目的のプロトタイプ。
