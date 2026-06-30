# overrides.csv 暫定エントリ（要・公式サイトでの直接再確認）

下記は Web 検索で公式情報源（実施団体の公式サイト）から得た値を **暫定** で
`data/overrides.csv` に登録したもの。確認時点で実行環境から公式ページの直接取得
（WebFetch）が 403 でブロックされていたため、検索エンジン経由の要約に基づく。
**公開運用前に各 official_url を直接開いて値を再確認すること**（特に受験料・実施日程）。

確認日: 2026-06-30

| slug | 資格 | 再確認の要点 | 公式URL |
|---|---|---|---|
| c-1612 | 下水道管理技術認定(処理施設) | 受験手数料・システム利用料・実施日 | https://www.jswa.go.jp/kentei/ |
| c-4338 | 3級ブライダルコーディネート技能士 | 学科/実技の手数料・実施時期 | https://www.bia.or.jp/kentei2019-3/ |
| c-3714 | 診療情報管理士 | 受験料・受験資格・試験日 | https://www.hospital.or.jp/ |
| c-2505 | ファイナンシャルプランナー(CFP/AFP) | 課目別受験料・受験資格の最新要件 | https://www.jafp.or.jp/aim/cfp/cfp_exam/ |
| c-3630 | 簿記実務検定1級(全商) | 部門別受験料(情報源で1,300/1,600円と相違)・実施日 | https://zensho.or.jp/examination/bookkeeping/ |
| c-3631 | 簿記実務検定2級(全商) | 受験料・試験科目・実施日 | https://zensho.or.jp/examination/bookkeeping/ |
| c-3632 | 簿記実務検定3級(全商) | 受験料・試験科目・実施日 | https://zensho.or.jp/examination/bookkeeping/ |

備考:
- 受験料は年度で改定されるため、確証が持てないものは `fee` を空欄にして
  「公式で確認」を促す方針（全商簿記の各料金・FPの課目別料金など）。
- 直接取得が可能な環境では `tools/seed_worklist.py` の手順で再確認し、
  値を確定のうえ本ファイルの該当行を削除する。
