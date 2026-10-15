# CLAUDE.md

> 이 파일의 공통 규칙은 경영지원파트 박종서가 작성했습니다. 규칙 때문에 작업이
> 막히거나 이해가 안 되면 코드나 이 파일을 임의로 고치지 말고 먼저 경영지원파트
> (박종서, 조민기)에게 문의하세요.

`speedrack-co/repo-template`에서 복사된 공통 규칙입니다. 아래 「이 앱에 대해」만
앱에 맞게 채우고, 그 뒤 공통 규칙은 앱마다 다시 쓰거나 지우지 않습니다.

## 이 앱에 대해

- 하는 일:
- 담당자:
- 배포:
- DB — **2번 절차가 여기서 갈립니다. 비워두지 마세요.**
  - Supabase 조직(org):
  - 프로젝트 이름 / ref:
  - 스키마:
  - DB 변경 기록 위치: (`ai_data_hub`면 `MS_supabase_schema`, 부서 프로젝트면 이 repo의 `supabase/applied/`)

---

## 1. main에 직접 커밋·푸시하지 않습니다

조직이 GitHub Free 플랜이라 **private repo에는 브랜치 보호(Rulesets / branch
protection)가 걸리지 않습니다.** 설정 화면에서 규칙을 만들어도 "won't be enforced"
경고와 함께 무시됩니다. 즉 `git push origin main`이 아무 저항 없이 성공합니다.
막아주는 장치가 없으니 규칙으로 지킵니다.

- 작업은 항상 새 브랜치에서 하고, 변경은 PR로 올립니다.
- **머지는 담당자가 합니다.** AI는 PR을 올리는 데까지만 하고 스스로 머지하지 않습니다.
- `--force` 푸시, 브랜치 삭제, 이력 재작성 금지. 되돌릴 수 없습니다.
- 유일한 예외: 파일명↔실제 적용 버전이 어긋났을 때의 재라벨링 커밋 (아래 2번 A-5 참고
  — 창구 ②로 적용하면 어긋나지 않으므로 실제로 쓸 일이 거의 없습니다).

## 2. Supabase 스키마 변경 시 필수 절차

**먼저 이 앱의 데이터가 어느 Supabase 프로젝트에 있는지 확인하세요.**
Supabase 조직이 **부서 단위로 분리**돼 있어서, 로그인은 전 부서가 `ai_data_hub` 하나를
쓰지만 **앱 데이터는 담당 부서의 프로젝트**에 들어갑니다. 부서별 ref 표는
`migration-guide.md` §1-1 이 원본입니다.

| 담당 부서 | 데이터 프로젝트 | 절차 |
|---|---|---|
| 경영지원 (MS) | `ai_data_hub` (`qtzlhedrlrulxxerueky`) | 아래 **A** — PR 먼저, merge가 곧 적용 |
| 물류 (LG) · 생산 (PD) · 그 외 (PUBLIC) | 부서별 프로젝트 (§1-1 표) | 아래 **B** — 바로 적용, 적용한 SQL을 이 repo에 PR로 기록 |

⚠ **`list_projects`에 하나만 나온다고 그게 목적지라고 판단하지 마세요.** 세션에 연결된
Supabase MCP는 **연결이 허가된 조직의 프로젝트만** 보여줍니다. 경영지원 담당자 세션에서는
`ai_data_hub`만 보이는 게 정상이고, 그걸 "프로젝트가 하나뿐"으로 읽으면 다른 부서 앱에
엉뚱한 절차를 적용하게 됩니다. 담당 부서를 먼저 확인하고 §1-1 표에서 ref를 고르세요.

### 어느 DB를 쓰든 공통

- 대상은 구조 변경(테이블/뷰/컬럼/인덱스/트리거/함수/RLS/권한)과 기존 운영 데이터 수정
  (INSERT/UPDATE/DELETE)입니다.
- 모든 변경은 **실행한 SQL 그대로 git에 남깁니다.** DB에만 있고 git에 없는 변경은
  "고아"가 되어, 나중에 누가 왜 바꿨는지 아무도 모르게 됩니다.
- **읽기 전용 SELECT/집계 쿼리는 이 절차 없이 바로 실행 가능합니다.**
- **Supabase Developer 권한으로 안 되는 설정은 경영지원파트에 문의합니다.** Exposed
  schemas 등록(Settings → API), Auth·API 설정 같은 프로젝트 설정 변경이 여기에 해당합니다.
  SQL로 우회하지 마세요.

### A. 데이터가 `ai_data_hub`에 있는 앱 (경영지원 담당 앱)

**`apply_migration`/`execute_sql`로 DDL·데이터 변경을 직접 실행하지 않습니다.**
원본 절차는 `speedrack-co/MS_supabase_schema`의 `CONVENTIONS.md`
("0. 스키마/데이터 변경 프로세스")와 `speedrack-supabase-migration` skill입니다 —
아래는 요약이니 실제 작업 전 원본을 확인하세요.

1. `speedrack-co/MS_supabase_schema`를 `access="push"`로 세션에 추가하고 클론
2. 새 브랜치에서 마이그레이션 파일 작성(`supabase/migrations/YYYYMMDDHHMMSS_설명.sql`)
   → commit → push → PR 오픈. **이 시점까지 실제 DB는 손대지 않습니다.**
3. 담당자가 merge — **이 순간 DB에 적용됩니다.** `main`에 `supabase/migrations/**`가
   들어가면 「마이그레이션 접수 (창구 ②)」 워크플로가 자동으로 `supabase db push`를
   실행합니다(2026-08-11부터). merge 버튼이 곧 적용 승인입니다.
4. merge 후 할 일은 **적용 결과 확인**입니다 — 창구 ② run이 성공했는지,
   `supabase_migrations.schema_migrations`에 반영됐는지. "DB 적용해줘"라고 요청받으면
   먼저 **이미 적용됐는지 확인**하고, 창구 ②가 실패했을 때만 Actions에서 그 워크플로를
   `confirm: apply`로 재실행합니다.
5. `db push`는 **파일명을 그대로 버전으로 씁니다** — 파일명↔실제 버전이 어긋나지 않으므로
   `git mv` 정정 커밋은 필요 없습니다. (어긋난 경우에만 재라벨링하며, 내용 변경이 아니라
   재라벨링이므로 PR 없이 main에 직접 커밋해도 됩니다 — 1번의 유일한 예외. 이 커밋에는
   파일명 변경 외 다른 수정을 포함하지 않습니다.)

**우리 스키마만 건드리는데 왜 이렇게까지 하나** — 격리 단위가 스키마가 아니라
**프로젝트**이기 때문입니다. `ai_data_hub` 한 프로젝트에 부서·앱별 스키마가 28개
들어 있고(`ms_foreignflow`·`ms_safety_app`·`ms_flo`·`teamcost`·`data_access` 등,
2026-09-21 실측), 마이그레이션 대장(`supabase_migrations.schema_migrations`)은
**프로젝트당 하나**라 그 안의 모두가 공유합니다. 내 스키마에만 손대도 대장은
공유라서, 여기서 낸 사고가 **다음에 배포하는 다른 부서를 막습니다.**
실제로 4번 그랬습니다.

### B. 데이터가 부서 프로젝트에 있는 앱 (물류·생산·그 외)

창구 ②와 `MS_supabase_schema`는 `ai_data_hub` 전용입니다. 부서 프로젝트는 **사전 승인
없이 AI가 MCP로 바로 적용하고, 적용한 SQL을 이 앱 repo에 PR로 기록**합니다. 전사 도입
단계라 진입장벽을 낮추려고 승인 단계를 두지 않았습니다 — 문제가 생기면 그때 승인 지점을
추가합니다.

1. **목적지 확인** — 「이 앱에 대해」의 프로젝트 ref와 MCP가 가리키는 프로젝트가 같은지
   `get_project`로 확인합니다. 세션의 MCP는 **각자 개인 Supabase 계정**(부서 조직에
   Developer로 초대된 계정)으로 붙습니다. 목적지가 안 보이면 그 계정의 조직 초대 상태를
   확인하세요. 안 보인다고 없는 게 아닙니다.
2. **적용** — `apply_migration`으로 실행합니다(이름은 snake_case 설명). `execute_sql`이
   아니라 `apply_migration`을 쓰는 이유: 프로젝트의 마이그레이션 대장
   (`supabase_migrations.schema_migrations`)에 버전이 남아서, 그 프로젝트를 쓰는 repo가
   여러 개여도 전체 변경 이력을 DB에서 한 번에 볼 수 있습니다.
3. **버전 확인** — `list_migrations`로 방금 채번된 버전(`YYYYMMDDHHMMSS`)을 확인합니다.
4. **기록** — 실행한 SQL을 **그대로** `supabase/applied/<버전>_<이름>.sql`에 저장합니다.
   파일 맨 위에 대상 프로젝트 ref와 한 줄 설명을 주석으로 덧붙이는 것 외에는 고치지
   않습니다. 기억으로 다시 쓰지 말고 실행한 문자열을 옮기세요.
5. **PR** — 새 브랜치에서 commit → push → PR. 제목은 `[DB] <설명>`, 라벨은
   `supabase-migration`, 본문에는 대상 프로젝트 ref · 바뀐 스키마/테이블 · 적용 버전을
   적습니다. 머지는 평소처럼 담당자가 합니다. 이 PR의 merge는 기록 확정일 뿐이고 DB에는
   2번에서 이미 반영돼 있습니다.

제목 접두사와 라벨은 여러 repo에 흩어진 DB 변경을 한 번에 모아 보기 위한 것입니다 —
`org:speedrack-co is:pr label:supabase-migration` (라벨이 빠졌으면 `"[DB]" in:title`).

- **"DB 적용해줘" 단계는 없습니다.** 2번에서 이미 적용됐습니다. 같은 SQL을 다시 실행하면
  같은 변경이 새 버전으로 한 번 더 채번됩니다.
- `supabase/applied/`는 **기록용**입니다. 이 폴더나 `supabase/migrations/`로
  `supabase db push`를 실행하지 마세요. 같은 프로젝트를 쓰는 다른 앱의 버전이 이 repo에
  없어서 충돌합니다.
- **다른 앱의 스키마는 건드리지 않습니다.** 부서 프로젝트 하나를 여러 앱이 같이 씁니다.
  내 앱 스키마 밖의 객체를 바꿔야 하면 그 앱 담당자와 먼저 얘기하세요.

### 고아 마이그레이션 — 왜 이 절차가 있는지

절차를 건너뛰고 DB에 직접 넣으면 "git에 없는 고아"가 되어 나중에 다른 세션이 우연히
발견해서 복구해야 합니다(`create_welfare_docs`, `ms_cost_analysis_base_layer`,
`create_ms_device_manager_schema` 등). B에서는 적용(2번)만 하고 기록 PR(4~5번)을
빠뜨리는 것이 고아입니다.

**이미 적용된 것을 `apply_migration`으로 한 번 더 실행하는 것도 같은 고아를 만듭니다** —
실행 시각으로 새 버전이 채번되는데 그 번호에 해당하는 파일이 레포에 없기 때문입니다
(창구 ② 자동화 이전 3회 — PR #49·#51·#52, 이후 2026-09-21 1회).

⚠ **(A) `MS_supabase_schema` CI의 고아 검출은 그물이 성깁니다. 안 걸렸다고 없는 게 아닙니다.**
마이그레이션 파일을 건드리는 PR이 올라올 때만 돌고(`on: pull_request` +
`paths: supabase/migrations/**`), 접속 secrets가 없으면 원격 대조를 건너뛴 채
초록불이 나며, main에 직접 푸시하면 검증을 통째로 지나갑니다. 그리고 빨간불을 받는 사람은
고아를 만든 사람이 아니라 **다음에 PR을 올린 남**입니다.

**작업을 완료로 표시하기 전에 위 절차를 끝냈는지 스스로 확인하세요.**

## 3. 비밀값

- API 키, 비밀번호, service_role key 등은 **절대 코드에 하드코딩하지 않습니다.**
  설정 파일(`.replit`, `vercel.json` 등)도 코드입니다.
- 실제 값은 배포 플랫폼(Vercel/Replit 등)의 Secrets/환경변수 기능에만 입력하고,
  어떤 변수가 필요한지는 `.env.example`에 **이름만** 남깁니다.
- **이미 커밋된 비밀값을 발견하면**, 파일에서 지우는 것만으로는 해결되지 않습니다.
  git 이력에 그대로 남기 때문에 반드시 해당 키를 재발급(rotate)해야 합니다.
  발견 즉시 담당자에게 알리고, 임의로 조용히 지우지 마세요.

## 4. 권한 구조 (참고)

왜 이런 규칙이 필요한지에 대한 배경입니다.

- 조직 기본 권한은 **No permission**입니다. repo는 **부서 Team 단위**로만 보입니다.
- 부서원은 자기 부서 repo에 **Write**까지 갖습니다. **Admin은 Owner만** 갖습니다
  (그래서 repo 삭제·이전·공개전환·외부인 초대는 Owner만 가능합니다).
- 부서원 전원이 Write를 갖지만, **담당자 지정은 GitHub 권한이 아니라 팀 내
  합의**입니다. 담당자가 아니면 Write 권한이 있어도 직접 push하지 말고,
  CONTRIBUTING.md에 따라 Issue로 남겨주세요.
- 열람만 필요한 사람은 부서 Team에 넣지 말고, 해당 repo에만 **외부
  collaborator(Read)** 로 초대합니다. 조직 멤버라도 마찬가지입니다 — Team에
  넣으면 그 부서의 다른 repo까지 다 보이게 됩니다.
- AI가 이 repo에서 할 수 있는 일의 상한은 **그 작업을 지시한 사람의 GitHub 권한**입니다.
  Read 권한만 있는 사람은 `@claude`를 불러도 수정이 거부됩니다.

## 5. 이 템플릿으로 새 repo를 만들었다면

- [ ] README와 위 「이 앱에 대해」 채우기
- [ ] 담당 부서 Team에 이 repo 접근 권한 부여 (Settings → Collaborators and teams)
- [ ] Claude App 접근 범위에 이 repo가 포함되는지 확인
      (Organization → Settings → GitHub Apps → Claude)
- [ ] Notion 「레포 인덱스」에 등록
- [ ] 로그인 기능이 필요한 앱이면 `supabaseauthloginguide.md` 확인 — 특히 §2(형태 판별)와,
      자체 서버가 있다면 §7(API 보호)은 필수
- [ ] Replit·Lovable·개인 PC에서 만들던 앱을 옮겨온 것이면 `migration-guide.md` 확인 —
      데이터가 지금 어디에 쌓이는지 분석 → 담당 부서 Supabase 프로젝트의 앱 스키마로 이관 → 검증까지

## 6. 로그인 기능이 필요하면

새 앱에 사내 계정 로그인을 붙일 때는 `supabaseauthloginguide.md`를 그대로 AI에게 읽혀서
구현하면 됩니다. 비밀번호 찾기·첫 로그인 설정·비밀번호 변경은 계정 센터(`speedrack-co/MS_account`)가
하므로 앱에 만들지 않습니다(최신본: https://ms-account.vercel.app/app-guide.md).

**다만 이 앱이 자체 서버(Express 등)를 갖고 그 서버가 DB에 붙는 구조라면,
로그인 화면만으로는 부족합니다** — 그 문서의 §2에서 형태를 먼저 판별하고, 해당되면 §7의
API 보호(서버 쪽 토큰 검증)까지 반드시 구현해야 합니다. 로그인 화면만 만들고 이 부분을
빠뜨려서 로그인 없이도 데이터를 읽고 쓸 수 있었던 실제 사고가 있었습니다(2026-09,
PD_MSDS-Management).
