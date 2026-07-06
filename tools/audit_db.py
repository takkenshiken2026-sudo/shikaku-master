#!/usr/bin/env python3
"""DB全体の正確性・整合性・表記の監査（読み取り専用）。"""
import csv, re, unicodedata
from collections import Counter

files = {
    'certifications': 'data/certifications.csv',
    'overrides': 'data/overrides.csv',
    'exam_details': 'data/exam_details.csv',
    'careers': 'data/careers.csv',
    'descriptions': 'data/descriptions.csv',
    'study_time': 'data/study_time.csv',
}
data = {k: list(csv.DictReader(open(v, encoding='utf-8'))) for k, v in files.items()}
issues = []
def add(cat, slug, detail): issues.append((cat, slug, detail))

REPLACEMENT = '�'
def has_control(s):
    for ch in s:
        o = ord(ch)
        if ch == REPLACEMENT:
            return True
        if o < 32 and ch not in '\t':
            return True
    return False

# 1) 文字化け・制御文字
for fname, rows in data.items():
    for r in rows:
        for col, val in r.items():
            if val and has_control(val):
                add('文字化け/制御文字', r.get('slug', '?'), f"{fname}.{col}")

# 2) 合格率: %範囲・内訳整合
for r in data['certifications']:
    pr = r['pass_rate']
    if not pr:
        continue
    for pct in re.findall(r'(\d+(?:\.\d+)?)\s*%', pr):
        if float(pct) > 100:
            add('合格率>100%', r['slug'], pr)
    m = re.search(r'受験\s*([\d,]+).{0,4}?合格\s*([\d,]+)', pr)
    if m:
        ju = int(m.group(1).replace(',', '')); go = int(m.group(2).replace(',', ''))
        if ju:
            calc = round(100 * go / ju, 1)
            mp = re.search(r'(\d+(?:\.\d+)?)\s*%', pr)
            if mp and abs(float(mp.group(1)) - calc) > 0.6:
                add('合格率と内訳の不一致', r['slug'], f"{pr} → 実計算{calc}%")

# 3) 年度ラベルの妥当性
for r in data['certifications']:
    for col in ['pass_rate', 'fee']:
        v = r[col]
        for y in re.findall(r'令和(\d+)年', v):
            if int(y) > 8:
                add('年度ラベル異常(令和>8)', r['slug'], f"{col}:{v}")
        for y in re.findall(r'平成(\d+)年', v):
            if int(y) > 31:
                add('年度ラベル異常(平成)', r['slug'], f"{col}:{v}")

# 4) URL形式
for r in data['certifications']:
    u = r['official_url']
    if u and not re.match(r'https?://', u):
        add('URL形式不正', r['slug'], u)

# 5) 前後空白
for fname, rows in data.items():
    for r in rows:
        for col, val in r.items():
            if val and val != val.strip():
                add('前後に空白', r.get('slug', '?'), f"{fname}.{col}")

# 6) slug整合
certslugs = {r['slug'] for r in data['certifications']}
for fname in ['overrides', 'exam_details', 'careers', 'descriptions', 'study_time']:
    for r in data[fname]:
        if r['slug'] and r['slug'] not in certslugs:
            add('slug不在', r['slug'], fname)

# 7) 受験料: 円表記なのに数字なし等の軽い検査
for r in data['certifications']:
    fee = r['fee']
    if fee and '円' in fee and not re.search(r'\d', fee):
        add('受験料: 円表記だが数字なし', r['slug'], fee)

# 8) 重複slug
seen = {}
for i, r in enumerate(data['certifications']):
    s = r['slug']
    if s in seen:
        add('slug重複', s, f"L{seen[s]}とL{i}")
    seen[s] = i

# 9) よくある誤字（簡易辞書）
typo_pat = {
    '試驗': '試験', '資挌': '資格', '免許状': None, '合格立': '合格率',
    '受験料金': None, '実施団体団体': '重複', '従免': None,
}
for r in data['certifications']:
    for col in ['name', 'authority', 'eligibility', 'exam_format', 'fee', 'frequency']:
        v = r[col]
        for bad in ['試驗', '資挌', '合格立', '団体団体', '試験験', '受験験']:
            if bad in v:
                add('誤字候補', r['slug'], f"{col}:{bad} in {v[:30]}")
for r in data['descriptions']:
    for bad in ['試驗', '資挌', '合格立', '団体団体', '試験験', '受験験', 'をを', 'のの', 'ですです']:
        if bad in r.get('description', ''):
            add('誤字候補(解説)', r['slug'], bad)

c = Counter(i[0] for i in issues)
print("=== 自動監査カテゴリ別 ===")
for k, v in c.most_common():
    print(f"  {k}: {v}件")
print(f"\n総検出: {len(issues)}件\n")
print("=== 詳細（最大60件）===")
for cat, slug, det in issues[:60]:
    print(f"  [{cat}] {slug} | {det}")
