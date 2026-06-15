# HF Daily Papers → 유통/물류 다이제스트 (GitHub Actions + SMTP)

매일 아침 8시(KST), HuggingFace Daily Papers의 upvote 상위 10개를 Claude가 읽고
유통·물류 자동화/효율화와 연관된 LLM·Agent 논문만 골라 **한국어 abstract 번역 + 시사점**을
본인 이메일로 보내줍니다. 서버를 항상 켜둘 필요 없이 GitHub의 무료 스케줄러로 돌아갑니다.

## 파일 구성
```
hf-digest/
├── digest.py                    # 핵심 스크립트 (fetch → 중복제외 → Claude 필터 → 메일 → 기록)
├── seen_papers.json             # 이미 확인한 논문 ID 기록 (자동 갱신/커밋됨)
├── .github/workflows/daily.yml  # 평일 다이제스트 + 주말 리셋 스케줄
└── email_preview.html           # 메일 모양 미리보기
```

## 동작 방식
- **평일(월~금) 08:00 KST**: 상위 10개 중 `seen_papers.json`에 없는 신규 논문만 검토 →
  연관 논문 메일 발송 → 검토한 논문 ID를 기록에 추가하고 저장소에 자동 커밋.
  신규 논문이 없거나 연관 논문이 없으면 그 사실대로 처리(빈 날은 메일 없음).
- **주말(토 09:00 KST)**: `seen_papers.json`을 비워 기록을 초기화. 다음 주 월요일부터
  지난주 본 논문도 다시 후보가 됩니다. 주말에는 다이제스트 메일이 가지 않습니다.

> "이미 본 논문 제외"가 작동하려면 GitHub Actions가 `seen_papers.json`을 커밋해야 하므로,
> 워크플로에 `permissions: contents: write`가 포함되어 있습니다. 별도 설정은 필요 없습니다.

## 셋업 (10분)

### 1. GitHub 저장소 만들기
- github.com에서 새 **private** 저장소 생성 (예: `hf-digest`)
- 이 폴더의 파일들을 그대로 올립니다. (웹 업로드 또는 git push)

### 2. SMTP 정보 준비
Gmail을 쓴다면:
- Google 계정 → 보안 → 2단계 인증 켜기 → **앱 비밀번호** 발급 (16자리)
- SMTP_HOST = `smtp.gmail.com`, SMTP_PORT = `587`
- SMTP_USER = 본인 Gmail 주소, SMTP_PASS = 발급받은 앱 비밀번호

> 일반 Gmail 비밀번호가 아니라 **앱 비밀번호**여야 합니다.
> 네이버는 smtp.naver.com / 포트 587, 회사 메일은 IT팀에 SMTP 정보를 문의하세요.

### 3. Anthropic API 키
- console.anthropic.com → API Keys에서 키 발급

### 4. GitHub Secrets 등록
저장소 → Settings → Secrets and variables → Actions → **New repository secret** 로
아래 6개를 등록합니다:

| 이름 | 값 |
|------|-----|
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `SMTP_HOST` | smtp.gmail.com |
| `SMTP_PORT` | 587 |
| `SMTP_USER` | 보내는 이메일 주소 |
| `SMTP_PASS` | 앱 비밀번호 |
| `MAIL_TO` | 받을 이메일 주소 (본인) |

### 5. 테스트
저장소 → **Actions** 탭 → "HF Daily Papers Digest" → **Run workflow** 버튼으로
지금 바로 한 번 수동 실행해 메일이 오는지 확인하세요.

이후로는 매일 08:00 KST에 자동 실행됩니다.

## 커스터마이징
- **관심 주제 변경**: `digest.py`의 `INTEREST_PROFILE` 텍스트만 고치면 됩니다.
- **검토 논문 수 변경**: `daily.yml`의 `TOP_N` 값 변경 (기본 10).
- **실행 시각 변경**: `daily.yml`의 cron 값 변경. KST = UTC+9이므로
  원하는 KST 시각에서 9시간을 뺀 값을 UTC로 적습니다.
  (평일 08:00 KST → `0 23 * * 0-4`, 주말 리셋 토 09:00 KST → `0 0 * * 6`)
- **기록 수동 초기화**: Actions 탭 → Run workflow → mode에 `reset` 입력.
- **테스트 실행**: Actions 탭 → Run workflow → mode `digest` (기본값)로 즉시 1회 발송 확인.

## 비용
- GitHub Actions: 하루 1회 실행은 무료 한도 내 (private도 월 2,000분 무료).
- Anthropic API: 하루 abstract 10개 처리 ≈ 호출 1회. 매우 적은 토큰만 사용.

## 참고
HuggingFace API는 인증 없이 호출되며, 가끔 봇 차단(403)이 날 수 있습니다.
지속적으로 막히면 `digest.py`의 요청 헤더에 HF 토큰을 추가하는 방식으로 보완할 수 있습니다.
