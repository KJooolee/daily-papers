# HF Daily Papers → 유통/물류 다이제스트 + 연구 동향 아카이브 (Claude Code 루틴)

평일 아침 HuggingFace Daily Papers upvote 상위 15개(신규)를 Claude가 직접 읽고,
1. 유통·물류 자동화/효율화와 연관된 논문만 **한국어 abstract 번역 + 시사점**으로 Slack `#proj-ai-papers`에 올리고,
2. 검토한 15편 **전부**를 분야·문제·기법으로 분류해 `archive/papers.jsonl`에 누적합니다.

Anthropic API 키·SMTP·GitHub Actions 불필요.

## 구성
- `digest.py` : 표준 라이브러리 헬퍼. `fetch [N]` / `mark ID...` / `reset` / `append`(stdin JSONL, vocab 검증)
- `seen_papers.json` : 중복 방지용 확인 기록 (매주 월요일 초기화)
- `archive/papers.jsonl` : 장기 아카이브 (초기화 없음). 한 줄에 논문 하나
  `{date, id, title, upvotes, field, problems, methods, relevant}`
- `archive/vocab.json` : 분류 어휘 — 분야(닫힌 목록), 문제·기법(세부 + 상위군 2단), 별칭, 규칙, 후보, 변경 이력
- 루틴 프롬프트 : Claude Code 스케줄 작업(daily-papers-digest)에 저장됨

## 동작 (평일 08:55 KST)
- **월** : `reset` 후 이어서 평소처럼 처리 (아카이브는 초기화하지 않음)
- **월~금** : `fetch` → vocab 읽기 → 15편 분류 → 연관 논문 선별·Slack 발송 → `mark` + `append` → 커밋/푸시

## 동향 집계 기준
- 월별·3개월 이동 추세 : 분야, 문제 상위군(7), 기법 상위군(8)
- 세부 문제·기법 : 분기 누적 (분기 누적 5편 미만은 병합 후보 표시, 병합은 사용자 확인 후)
- HF Daily 상위 논문은 표본이므로 "HF Daily에서 주목받는 흐름"으로 해석
- 시드(2026-07-17~11-03)는 과거 메일의 **연관 논문 106편만** 포함(relevant=true).
  이후는 15편 전부라 표본 기준이 다르므로, 경계 전후 비교는 `relevant=true`끼리 한다.

## 커스터마이징
- 관심 주제·검토 개수·발송 형식 : 스케줄 작업의 프롬프트 수정
- 분류 어휘 : `archive/vocab.json` 수정 (changelog에 기록)
- 기록 수동 초기화 : `python3 digest.py reset` 후 커밋
