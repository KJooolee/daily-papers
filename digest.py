#!/usr/bin/env python3
"""
HuggingFace Daily Papers -> 유통/물류 자동화·효율화 관련 LLM/Agent 논문 필터링 다이제스트.

매일 GitHub Actions로 실행되어:
1. HF Daily Papers에서 upvote 상위 N개 논문을 가져오고
2. Claude(Anthropic API)로 유통/물류 자동화·효율화 연관성을 판단하고
3. 연관 논문만 abstract 한국어 번역 + 시사점을 작성해
4. SMTP로 본인 이메일에 발송한다.

환경변수 (GitHub Secrets로 주입):
  ANTHROPIC_API_KEY  : Anthropic API 키
  SMTP_HOST          : 예) smtp.gmail.com
  SMTP_PORT          : 예) 587
  SMTP_USER          : SMTP 로그인 계정 (보내는 주소)
  SMTP_PASS          : SMTP 비밀번호 / 앱 비밀번호
  MAIL_TO            : 받는 사람 이메일
  TOP_N              : (선택) 상위 몇 개를 검토할지. 기본 10
"""

import os
import sys
import json
import smtplib
import datetime
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

HF_API = "https://huggingface.co/api/daily_papers?limit=100"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-opus-4-8"

# --- 사용자가 원하면 이 키워드 프로필만 고쳐서 관심 주제를 바꿀 수 있습니다 ---
INTEREST_PROFILE = """유통(retail/distribution)과 물류(logistics/supply chain)의 자동화 및 효율화.
구체적으로는 다음과 관련된 LLM 또는 AI 에이전트(agent) 논문에 관심이 있다:
- 창고 자동화, 피킹/패킹, 재고 관리, 재고·수요 예측
- 라스트마일 배송, 경로/배차 최적화, 운송 스케줄링
- 공급망 의사결정, 발주/조달 자동화
- 멀티 에이전트 오케스트레이션, 도구 사용(tool-use) 에이전트, 워크플로 자동화
- 운영 효율화·비용 절감에 직접 응용 가능한 LLM 활용
순수 이론/비전/언어학 논문 등 물류·유통 응용과 거리가 먼 것은 제외한다."""


SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_papers.json")


def load_seen():
    """이미 확인한 논문 ID 집합을 불러온다. 파일이 없으면 빈 집합."""
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("ids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(ids):
    """확인한 논문 ID 집합을 파일에 저장한다."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"ids": sorted(ids)}, f, ensure_ascii=False, indent=2)


def reset_seen():
    """주말용: 확인 기록을 초기화한다."""
    save_seen(set())


def fetch_papers(top_n, seen=None):
    """HF Daily Papers를 upvote 내림차순으로 정렬해, 이미 본 것을 제외하고 상위 top_n개 반환."""
    seen = seen or set()
    req = urllib.request.Request(HF_API, headers={"User-Agent": "hf-digest/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    papers = []
    for item in data:
        paper = item.get("paper", item)
        title = paper.get("title", "").strip()
        abstract = (paper.get("summary") or paper.get("abstract") or "").strip()
        upvotes = paper.get("upvotes", item.get("upvotes", 0)) or 0
        pid = paper.get("id", "")
        url = f"https://huggingface.co/papers/{pid}" if pid else ""
        if title and abstract and pid and pid not in seen:
            papers.append({
                "id": pid,
                "title": title,
                "abstract": abstract,
                "upvotes": upvotes,
                "url": url,
            })

    papers.sort(key=lambda p: p["upvotes"], reverse=True)
    return papers[:top_n]


def call_claude(papers):
    """Claude에 상위 논문들을 보내 연관 논문 선별 + 번역 + 시사점을 JSON으로 받는다."""
    api_key = os.environ["ANTHROPIC_API_KEY"]

    numbered = "\n\n".join(
        f"[논문 {i+1}] (upvotes: {p['upvotes']})\n제목: {p['title']}\nURL: {p['url']}\nAbstract: {p['abstract']}"
        for i, p in enumerate(papers)
    )

    prompt = f"""너는 유통·물류 산업 종사자를 돕는 AI 리서치 애널리스트다.

[관심 프로필]
{INTEREST_PROFILE}

아래는 오늘 HuggingFace Daily Papers의 upvote 상위 논문들이다. 각 abstract을 읽고
관심 프로필과 연관이 있는 논문만 골라라. 연관성이 애매하면 제외한다(엄격하게 판단).

{numbered}

다음 JSON 형식으로만 응답하라. 마크다운 코드펜스나 다른 설명 없이 순수 JSON만 출력한다.
연관 논문이 하나도 없으면 "relevant" 배열을 빈 배열로 둔다.

{{
  "relevant": [
    {{
      "title": "원문 제목",
      "title_ko": "한국어 제목",
      "url": "논문 URL",
      "upvotes": 숫자,
      "abstract_ko": "abstract 전체의 자연스러운 한국어 번역",
      "implications": "유통/물류 자동화·효율화 관점에서의 시사점 2~3문장 (실무적으로 무엇에 쓸 수 있는지)"
    }}
  ],
  "skipped_reason": "제외된 논문들이 왜 관심사와 무관한지 1~2문장 요약"
}}"""

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    text = text.strip()
    # 혹시 모를 코드펜스 제거
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def build_html(parsed, total_reviewed, today):
    relevant = parsed.get("relevant", [])
    if not relevant:
        return f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:680px;margin:0 auto;color:#1a1a1a">
<h2 style="margin-bottom:4px">📄 HF Daily Papers · 유통/물류 다이제스트</h2>
<p style="color:#666;margin-top:0">{today} · 상위 {total_reviewed}개 검토</p>
<p style="background:#f5f5f5;padding:16px;border-radius:8px">오늘은 유통/물류 자동화·효율화와 연관된 논문이 없었습니다.</p>
<p style="color:#888;font-size:13px">{parsed.get('skipped_reason','')}</p>
</div>"""

    cards = []
    for p in relevant:
        cards.append(f"""
<div style="border:1px solid #e5e5e5;border-radius:10px;padding:18px;margin-bottom:16px">
  <div style="font-size:12px;color:#e8590c;font-weight:600;margin-bottom:6px">▲ {p.get('upvotes','?')} upvotes</div>
  <h3 style="margin:0 0 4px 0;font-size:17px">{p.get('title_ko','')}</h3>
  <div style="font-size:13px;color:#888;margin-bottom:12px">{p.get('title','')}</div>
  <div style="font-size:14px;line-height:1.6;margin-bottom:14px">{p.get('abstract_ko','')}</div>
  <div style="background:#f0f7ff;border-left:3px solid #1971c2;padding:10px 14px;border-radius:4px;font-size:14px;line-height:1.6">
    <strong style="color:#1971c2">💡 시사점</strong><br>{p.get('implications','')}
  </div>
  <div style="margin-top:10px"><a href="{p.get('url','')}" style="color:#1971c2;font-size:13px">원문 보기 →</a></div>
</div>""")

    return f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:680px;margin:0 auto;color:#1a1a1a">
<h2 style="margin-bottom:4px">📄 HF Daily Papers · 유통/물류 다이제스트</h2>
<p style="color:#666;margin-top:0">{today} · 상위 {total_reviewed}개 중 <strong>{len(relevant)}개</strong> 연관 논문</p>
{''.join(cards)}
<p style="color:#aaa;font-size:12px;border-top:1px solid #eee;padding-top:12px">자동 생성 · HuggingFace Daily Papers + Claude</p>
</div>"""


def send_mail(html, today):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    to_addr = os.environ["MAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[HF Papers] 유통/물류 다이제스트 · {today}"
    msg["From"] = formataddr(("HF Papers Digest", user))
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=60) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())


def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))  # KST 기준
    today = now.date().isoformat()
    weekday = now.weekday()  # 월=0 ... 토=5, 일=6
    top_n = int(os.environ.get("TOP_N", "10"))
    mode = os.environ.get("RUN_MODE", "digest")  # "digest"(평일) 또는 "reset"(주말)

    # 주말 리셋 모드: 확인 기록만 초기화하고 메일은 보내지 않는다.
    if mode == "reset":
        print("[reset] 주말 - 확인했던 논문 리스트를 초기화합니다.")
        reset_seen()
        print("Done (reset).")
        return

    # 안전장치: 평일 모드인데 실제로 주말이면 아무것도 하지 않는다.
    if weekday >= 5:
        print("주말이므로 다이제스트를 보내지 않습니다.")
        return

    seen = load_seen()
    print(f"[1/5] 기존 확인 논문 {len(seen)}개 로드.")

    print(f"[2/5] 상위 {top_n}개 신규 논문 가져오는 중...")
    papers = fetch_papers(top_n, seen=seen)
    if not papers:
        print("새 논문이 없습니다 (모두 이미 확인함). 메일을 보내지 않습니다.")
        return
    print(f"      신규 {len(papers)}개.")

    print("[3/5] Claude 필터링 & 번역 중...")
    parsed = call_claude(papers)
    print(f"      연관 논문 {len(parsed.get('relevant', []))}개.")

    print("[4/5] 메일 작성 중...")
    html = build_html(parsed, len(papers), today)
    send_mail(html, today)

    print("[5/5] 확인한 논문 기록 저장 중...")
    # 이번에 검토한 모든 논문(연관 여부 무관)을 확인 처리한다.
    seen.update(p["id"] for p in papers)
    save_seen(seen)
    print(f"Done. 누적 확인 논문 {len(seen)}개.")


if __name__ == "__main__":
    main()
