# HF Daily Papers → 유통/물류 다이제스트 (Claude Code 루틴)

매일 아침 HuggingFace Daily Papers upvote 상위 15개(신규만)를 Claude가 직접 읽고,
유통·물류 자동화/효율화와 연관된 LLM·Agent 논문만 골라 **한국어 abstract 번역 + 시사점**을
Slack `#proj-ai-papers`에 올립니다. Anthropic API 키·SMTP·GitHub Actions 불필요.

## 구성
- `digest.py` : 표준 라이브러리 헬퍼. `fetch [N]` / `mark ID...` / `reset`
- `seen_papers.json` : 이미 확인한 논문 ID (루틴이 커밋)
- 루틴 프롬프트 : Claude Code 스케줄 태스크(daily-papers-digest)에 저장됨

## 동작 (매일 07:42 KST)
- **월~금** : `fetch` → Claude가 관심 프로필로 선별·번역 → Slack 발송 → `mark` → 커밋/푸시.
  신규 논문이 없거나 연관 논문이 없으면 한 줄 안내만 발송.
- **토** : `reset`으로 확인 기록 초기화 (메시지 없음). **일** : 아무것도 안 함.

## 커스터마이징
- 관심 주제·검토 개수·발송 형식 : 스케줄 태스크의 프롬프트 수정
- 기록 수동 초기화 : `python3 digest.py reset` 후 커밋
