# 整備対象の公式統計URL一覧（合格率・受験者数の出典候補）

合格率または受験者数が空欄の資格について、**実施団体ごとに公式の統計／受験データページ**を
まとめたもの。フェッチ許可（ネットワークポリシー）やデータ提供の優先順位付けに使う。
件数は「pass_rate または applicants が空欄かつ official_url を持つ」エントリ数（2026-06-20 時点）。

凡例: ✅=公式統計が存在し取得すれば埋まる ／ ⛔=合格率の概念なし（空欄が正しい） ／ ❓=非公表の可能性

---

## A. 優先度高（公式統計あり・件数多い）✅

| 件数 | 実施団体 | ドメイン | 公式統計ページ（要確認含む） |
|---|---|---|---|
| 273 | 中央職業能力開発協会（技能検定） | javada.or.jp | 厚労省「技能検定の実施状況」 https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/ginoukentei/index.html ／ JAVADA https://www.javada.or.jp/ |
| 13 | 全国経理教育協会（所得税法・法人税法・簿記等） | zenkei.or.jp | https://www.zenkei.or.jp/exam/result （試験結果・合格率） |
| 12 | 日本技術士会（技術士 各部門） | engineer.or.jp | 第二次統計PDF https://www.engineer.or.jp/c_topics/001/attached/attach_1013_2.pdf ／ 第一次統計PDF https://www.engineer.or.jp/c_topics/001/attached/attach_1012_2.pdf |
| 12 | 安全衛生技術試験協会（エックス線・ボイラー溶接士・作業主任者試験等） | exam.or.jp | 受験者数・合格者数 https://www.exam.or.jp/exmpdf/aggregate.htm |
| 11 | 日本無線協会（無線従事者国家試験） | nichimu.or.jp | 国家試験実施状況 https://www.nichimu.or.jp/kshiken/ ／ 総務省 電波利用統計 |
| 9 | 日本情報処理検定協会（情報処理技能検定 ほか） | goukaku.ne.jp | https://www.goukaku.ne.jp/ |
| 9 | 日本語検定委員会（日本語検定） | nihongokentei.jp | 結果データ https://www.nihongokentei.jp/about/data.html |
| 8 | IPA（情報処理技術者・情報処理安全確保支援士） | ipa.go.jp | 統計資料 https://www.ipa.go.jp/shiken/reports/index.html |
| 8 | 日本書写技能検定協会（毛筆・硬筆書写技能検定） | nihon-shosha.or.jp | https://www.nihon-shosha.or.jp/ |
| 13 | 日本自動車整備振興会連合会（自動車整備士） | jaspa.or.jp | 登録試験 実施状況 https://www.jaspa.or.jp/ |
| 13 | 厚生労働省（保健師・助産師・臨床検査技師等 医療系国家試験） | mhlw.go.jp | 国家試験合格発表 https://www.mhlw.go.jp/kouseiroudoushou/shikaku_shiken/ |
| 13 | 国土交通省（航空整備士・操縦士等） | mlit.go.jp | 航空従事者試験 https://www.mlit.go.jp/koku/ |
| 11 | サーティファイ（C言語・Java・Access等 認定試験） | sikaku.gr.jp | https://www.sikaku.gr.jp/ ※合格率を公表しているか要確認 |
| 6 | 日本商工会議所（残り：日商ビジネス英語＝スコア制⛔ ほか） | kentei.ne.jp | https://www.kentei.ne.jp/ |
| 6 | 医療秘書教育全国協議会（医療秘書技能検定） | medical-secretary.jp | https://www.medical-secretary.jp/ |
| 4 | 金融財政事情研究会（FP技能士・金融系） | kinzai.or.jp | 試験結果 https://www.kinzai.or.jp/ginou/result |
| 4 | 消防試験研究センター（危険物・消防設備士） | shoubo-shiken.or.jp | 試験実施状況 https://www.shoubo-shiken.or.jp/result/ |
| 4 | 気象業務支援センター（気象予報士） | jstc.jma.or.jp | 試験結果 https://www.jmbsc.or.jp/jp/examination/examination.html |

## B. 合格率の概念なし＝空欄が正しい ⛔（フェッチ不要）

| 件数 | 区分 | ドメイン | 備考 |
|---|---|---|---|
| 38 | 中央労働災害防止協会 ほか（作業主任者の多く） | jisha.or.jp | **技能講習修了**で付与（試験合格率なし） |
| 19 | 警視庁（運転免許の種別） | keishicho.metro.tokyo.lg.jp | 受験＝技能・適性試験。種別合格率は概念が異なる（警察庁「運転免許統計」に総計あり） |
| 13 | 文部科学省（司書・学芸員・教員認定 等） | mext.go.jp | **講習・課程修了／任用資格**中心（試験合格率なし） |
| 3 | IIBC（TOEIC）/ 各スコア制 | iibc-global.org | **スコア制**＝合否なし（既に「該当なし」表記） |

## C. 非公表の可能性が高い ❓

| 件数 | 実施団体 | ドメイン | 備考 |
|---|---|---|---|
| 10 | 日本珠算連盟（珠算 段位・各級） | shuzan.jp | 合格率・受験者数とも**非公表**（調査済み） |
| 13 | 日本電卓技能検定協会（電卓技能検定） | dentaku.or.jp | 公表有無を要確認 |
| 14 | 警備員特別講習事業センター（警備業務検定） | csst.jp | 講習修了ルートあり／検定試験合格率は公表有無を要確認 |
| 7 | 高圧ガス保安協会（高圧ガス・冷凍機械等） | khk.or.jp | 試験結果 https://www.khk.or.jp/ で公表あり（要確認） |

---

## 使い方

1. **フェッチ許可をいただく場合**: 上表 A の各ドメインを許可いただければ、公式統計を取得し
   「合格率＝合格者数÷受験者数」の内部検算を通したうえで一括整備します。
2. **データ提供の場合**: A の各統計ページのPDF/コピペをいただければ、それを一次情報として整備します。
3. B・C は方針上、空欄維持が正しい（または非公表）ため対象外です。

※本ファイルは整備管理用のメモ。確定値は `data/overrides.csv`・`data/exam_details.csv` に格納し、
方針は `data/SOURCES.md` に記載する。
