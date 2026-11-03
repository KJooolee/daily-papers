#!/usr/bin/env python3
"""HF Daily Papers 헬퍼 (Claude Code 루틴용). 선별·번역·발송은 Claude가 맡는다.

  python3 digest.py fetch [N]   미확인 논문 중 upvote 상위 N개(기본 15)를 JSON으로 출력
  python3 digest.py mark ID...  해당 논문을 확인 처리
  python3 digest.py reset       확인 기록 초기화(주말용)
"""
import json, sys, urllib.request
from pathlib import Path

SEEN = Path(__file__).with_name("seen_papers.json")
API = "https://huggingface.co/api/daily_papers?limit=100"


def load():
    try:
        return set(json.loads(SEEN.read_text(encoding="utf-8")).get("ids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save(ids):
    SEEN.write_text(json.dumps({"ids": sorted(ids)}, ensure_ascii=False, indent=2), encoding="utf-8")


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
else:
    sys.exit(__doc__)
