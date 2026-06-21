#!/usr/bin/env python3
"""データ鮮度の運用支援ツール.

ファクトチェックの照合履歴(data/factcheck_log.csv)と本体(data/certifications.csv)を
突き合わせ、再照合が必要な資格を抽出する。バッチ照合のワークフローを繰り返し回すための補助。

使い方:
  python3 tools/recheck.py status
      照合カバレッジ・type分布・確信度分布・flagged/要確認の件数を表示。

  python3 tools/recheck.py stale [--months N] [--limit M]
      source_checked_at が N か月以上前(既定12)の資格を古い順に一覧。

  python3 tools/recheck.py export --out FILE [--category CAT] [--months N]
                                  [--flagged] [--yokakunin] [--confidence LV] [--limit M]
      再照合対象を JSON(配列)で書き出す。サブエージェントへの入力に使う。
      フィルタは AND 条件。--flagged は factcheck_log で result=flagged のもの、
      --yokakunin は type=要確認、--confidence は type_confidence(low/medium/high)。
"""
import csv, json, argparse, datetime, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERT = os.path.join(ROOT, "data", "certifications.csv")
LOG = os.path.join(ROOT, "data", "factcheck_log.csv")
COLS = ["slug", "name", "type", "authority", "official_url",
        "eligibility", "pass_rate", "fee", "frequency"]
TODAY = datetime.date(2026, 6, 21)


def load_index():
    rows = list(csv.DictReader(open(CERT, encoding="utf-8")))
    return [r for r in rows
            if r["is_bucket"] == "0" and r["is_duplicate"] == "0"
            and r["scope"] == "domestic"]


def load_log():
    if not os.path.exists(LOG):
        return {}
    out = {}
    for r in csv.DictReader(open(LOG, encoding="utf-8")):
        out[r["slug"]] = r  # 最後の記録が最新
    return out


def parse_date(s):
    s = (s or "").strip()
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def cmd_status(_):
    idx = load_index()
    log = load_log()
    from collections import Counter
    n = len(idx)
    print(f"index対象: {n} 件")
    print(f"照合ログ: {len(log)} 件 ({len(log)*100//max(n,1)}% カバー)")
    print("type分布     :", dict(Counter(r["type"] for r in idx)))
    print("確信度分布   :", dict(Counter(r.get("type_confidence", "") for r in idx)))
    res = Counter(r["result"] for r in log.values())
    print("ログ結果内訳 :", dict(res))
    print("flagged(要再確認):",
          [s for s, r in log.items() if r["result"] == "flagged"])
    empties = {f: sum(1 for r in idx if not (r.get(f) or "").strip())
               for f in COLS[3:]}
    print("空欄フィールド:", empties)


def cmd_stale(args):
    idx = load_index()
    dated = []
    for r in idx:
        d = parse_date(r.get("source_checked_at"))
        dated.append((d, r))
    cutoff = TODAY - datetime.timedelta(days=int(args.months * 30.4))
    stale = [(d, r) for d, r in dated if d is None or d < cutoff]
    stale.sort(key=lambda x: (x[0] or datetime.date.min))
    print(f"再照合候補(>{args.months}か月 または 日付なし): {len(stale)} 件")
    for d, r in stale[:args.limit]:
        print(f"  {r['slug']}  {d or '日付なし'}  {r['name'][:32]}")


def cmd_export(args):
    idx = load_index()
    log = load_log()
    cutoff = TODAY - datetime.timedelta(days=int(args.months * 30.4)) if args.months else None
    sel = []
    for r in idx:
        if args.category and r["major_category"] != args.category:
            continue
        if args.yokakunin and r["type"] != "要確認":
            continue
        if args.confidence and r.get("type_confidence") != args.confidence:
            continue
        if args.flagged:
            lr = log.get(r["slug"])
            if not (lr and lr["result"] == "flagged"):
                continue
        if cutoff:
            d = parse_date(r.get("source_checked_at"))
            if d and d >= cutoff:
                continue
        sel.append({k: r.get(k, "") for k in COLS})
    if args.limit:
        sel = sel[:args.limit]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sel, f, ensure_ascii=False, indent=1)
    print(f"{len(sel)} 件を {args.out} に書き出し")


def main():
    p = argparse.ArgumentParser(description="データ鮮度の運用支援ツール")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    s = sub.add_parser("stale")
    s.add_argument("--months", type=float, default=12)
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_stale)
    e = sub.add_parser("export")
    e.add_argument("--out", required=True)
    e.add_argument("--category")
    e.add_argument("--months", type=float, default=0)
    e.add_argument("--flagged", action="store_true")
    e.add_argument("--yokakunin", action="store_true")
    e.add_argument("--confidence", choices=["low", "medium", "high"])
    e.add_argument("--limit", type=int, default=0)
    e.set_defaults(func=cmd_export)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
