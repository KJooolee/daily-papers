#!/usr/bin/env python3
"""HF Daily Papers 헬퍼 (Claude Code 루틴용). 선별·번역·발송은 Claude가 맡는다.

  python3 digest.py fetch [N]   미확인 논문 중 upvote 상위 N개(기본 15)를 JSON으로 출력
  python3 digest.py mark ID...  해당 논문을 확인 처리
  python3 digest.py reset       확인 기록 초기화(월요일 시작 시)
  python3 digest.py append      stdin의 JSONL(논문당 한 줄)을 archive/papers.jsonl에 추가.
                                라벨은 archive/vocab.json으로 검증하며, 하나라도 틀리면 아무것도 쓰지 않는다.
                                입력: {"id","title","upvotes","field","problems","methods","relevant"} (date 생략 시 오늘 KST)
  python3 digest.py missing     확인 기록에는 있는데 아카이브에 없는 논문을 fetch와 같은 형식의 JSON으로 출력
"""
import json, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEEN = Path(__file__).with_name("seen_papers.json")
ARCHIVE = Path(__file__).with_name("archive")
API = "https://huggingface.co/api/daily_papers?limit=100"


def load():
    try:
        return set(json.loads(SEEN.read_text(encoding="utf-8")).get("ids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save(ids):
    SEEN.write_text(json.dumps({"ids": sorted(ids)}, ensure_ascii=False, indent=2), encoding="utf-8")


def archived():
    t = (ARCHIVE / "papers.jsonl").read_text(encoding="utf-8")
    return {json.loads(l)["id"] for l in t.splitlines() if l.strip()}


cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]

if cmd == "fetch":
    seen = load()
    req = urllib.request.Request(API, headers={"User-Agent": "hf-digest/1.0"})
    items = json.load(urllib.request.urlopen(req, timeout=60))
    out = []
    for it in items:
        p = it.get("paper", it)
        pid, title = p.get("id", ""), (p.get("title") or "").strip()
        abstract = (p.get("summary") or p.get("abstract") or "").strip()
        if pid and title and abstract and pid not in seen:
            out.append({"id": pid, "title": title, "abstract": abstract,
                        "upvotes": p.get("upvotes", it.get("upvotes", 0)) or 0,
                        "url": f"https://huggingface.co/papers/{pid}"})
    out.sort(key=lambda x: x["upvotes"], reverse=True)
    print(json.dumps(out[: int(args[0]) if args else 15], ensure_ascii=False, indent=1))
elif cmd == "mark":
    save(load() | set(args))
elif cmd == "reset":
    save(set())
elif cmd == "append":
    v = json.loads((ARCHIVE / "vocab.json").read_text(encoding="utf-8"))
    F, P, M = ({x["name"] for x in v[k]} for k in ("fields", "problems", "methods"))
    path = ARCHIVE / "papers.jsonl"
    have = archived()
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    rows, errs = [], []
    for l in sys.stdin.read().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        ps, ms = r.get("problems", []), r.get("methods", [])
        bad = [k for k, ok in (("field", r.get("field") in F),
                               ("problems", 1 <= len(ps) <= 2 and set(ps) <= P),
                               ("methods", 1 <= len(ms) <= 3 and set(ms) <= M)) if not ok]
        if bad:
            errs.append(f"{r.get('id')}: {bad}")
        elif r["id"] not in have:
            have.add(r["id"])
            rows.append({"date": r.get("date", today), "id": r["id"], "title": r["title"],
                         "upvotes": r.get("upvotes", 0), "field": r["field"], "problems": ps,
                         "methods": ms, "relevant": bool(r.get("relevant"))})
    if errs:
        sys.exit("vocab.json에 없는 라벨 또는 개수 오류 — vocab을 먼저 갱신하세요:\n" + "\n".join(errs))
    with path.open("a", encoding="utf-8") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)
    print(f"appended {len(rows)}")
elif cmd == "missing":
    out = []
    for pid in sorted(load() - archived()):
        req = urllib.request.Request(f"https://huggingface.co/api/papers/{pid}", headers={"User-Agent": "hf-digest/1.0"})
        try:
            p = json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            print(f"skip {pid}: {e}", file=sys.stderr)
            continue
        out.append({"id": pid, "title": (p.get("title") or "").strip(), "abstract": (p.get("summary") or "").strip(),
                    "upvotes": p.get("upvotes", 0) or 0, "url": f"https://huggingface.co/papers/{pid}"})
    print(json.dumps(out, ensure_ascii=False, indent=1))
else:
    sys.exit(__doc__)
