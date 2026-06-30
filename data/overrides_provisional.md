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
| c-3534 | 日本語検定6級 | 受験料・実施日 | https://www.nihongokentei.jp/exam/ |
| c-3536 | 日本語検定7級 | 受験料・実施日 | https://www.nihongokentei.jp/exam/ |
| c-3206 | 不動産コンサルティング技能登録 | 受験料・受験資格・実施日 | https://www.retpc.jp/rcm/exam/ |
| c-7309 | コンクリート技士・主任技士 | 部門別受験料・受験資格年数 | https://www.jci-net.or.jp/j/exam/gishi/ |
| c-3884 | 検索技術者検定3級 | 受験料・試験方式 | https://www.infosta.or.jp/kensaku-kentei/ |
| c-3883 | 検索技術者検定2級 | 受験料(税別)・試験方式 | https://www.infosta.or.jp/kensaku-kentei_pro/ |
| c-3882 | 検索技術者検定1級 | 受験料(税別)・一次/二次の方式 | https://www.infosta.or.jp/examination/kensaku-kentei-1/ |
| c-4325 | 葬祭ディレクター1級 | 受験料・受験資格・実施日 | https://www.sousai-director.jp/ |
| c-4326 | 葬祭ディレクター2級 | 受験料・受験資格・実施日 | https://www.sousai-director.jp/ |
| c-4410〜4412 | 惣菜管理士1〜3級 | 会員区分別の受験料・実施日 | https://www.nsouzai-kyoukai.or.jp/training/rmm/ |
| c-5119〜5121 | 非破壊試験技術者レベル1〜3 | 方法別受験料・受験資格の詳細 | https://www.jsndi.jp/qualification/ |
| c-5504〜5505 | 溶接管理技術者1〜2級 | 筆記/口述の受験料・経験年数区分 | https://www.jwes.or.jp/qualifications/we/ |
| c-6617〜6620 | トレース技能検定1〜4級 | 受験料・実施日 | https://chuoko-center.or.jp/trace.html |
| c-6902 | 採石業務管理者 | 都道府県別の受験料・実施日 | https://www.meti.go.jp/information/license/c_text18.html |
| c-6903 | 砂利採取業務主任者 | 都道府県別の受験料・実施日 | https://www.meti.go.jp/information/license/c_text19.html |
| c-7034 | 解体工事施工技士 | 受験料・受験資格年数・実施日 | https://www.zenkaikouren.or.jp/engineer/about-test/ |
| c-5812 | 自転車安全整備士 | 科目免除別の受験料・実施日 | https://www.tmt.or.jp/safety/index5.html |
| c-7032 | 基礎施工士 | 受験料・受験資格年数・実施日 | https://www.kisokyo.or.jp/activity/index/1 |
| c-6810 | CATV技術者 | 科目別の受講・受験料・等級 | https://www.shikaku.catv.or.jp/ |
| c-6811 | 配電制御システム検査技士 | 学科/実技の受験料・実施日 | https://jsia.or.jp/kensa/ |
| c-4110 | 衣料管理士1〜2級 | 認定校・取得要件の詳細 | http://www.jasta1.or.jp/qualification/qualification-ta.html |
| c-4109 | 中古自動車査定士 | 受験料・研修費・実施日 | http://www.jaai.or.jp/ginoukentei.html |
| c-6120 | パターンメーキング技術検定 | 級別受験料・実施日 | https://www.fashion-edu.jp/pm/ |
| c-6621〜6624 | レタリング技能検定1〜4級 | 受験料・実施日 | https://lettering-kentei.com/ |

備考:
- 受験料は年度で改定されるため、確証が持てないものは `fee` を空欄にして
  「公式で確認」を促す方針（全商簿記の各料金・FPの課目別料金など）。
- 直接取得が可能な環境では `tools/seed_worklist.py` の手順で再確認し、
  値を確定のうえ本ファイルの該当行を削除する。
