# 스피드랙 사내 앱 — 외부 환경에서 만든 앱의 Supabase 데이터 이관 가이드

> **이 문서의 용도**: Replit, Lovable, 개인 PC 등에서 만들어 쓰던 앱을 GitHub repo로 옮겼을 때,
> 그 앱의 데이터가 **지금 어디에 어떻게 쌓이고 있는지 분석**하고, 이를 **앱 담당 부서의 사내
> Supabase 프로젝트로 옮기는 설계·실행·검증**까지 한 번에 진행할 수 있도록 쓴 가이드입니다.
> 이 파일 하나를 AI(Claude Code 등)에 읽히면 대상 앱의 스택에 맞춰 바로 진행할 수 있게 구성했습니다.
>
> **범위**: 데이터 저장소(DB·파일·키-값 저장소)의 이관만 다룹니다. 로그인은
> `supabaseauthloginguide.md`, 스키마 변경 절차는 `CLAUDE.md` 2번이 원본이며 이 문서는 그 둘을
> 전제로 합니다. 이관 중 그 두 문서와 충돌하는 내용이 있으면 그 문서가 우선입니다.
>
> **작성**: 경영지원파트. 진행 중 막히면 코드나 이 문서를 임의로 고치지 말고 경영지원파트
> (박종서, 조민기)에게 먼저 문의하세요.

---

## 0. 한 줄 요약

**분석 → 설계 → 실행 → 검증** 4단계로 진행한다. 먼저 앱이 데이터를 어디에 쓰는지(Replit DB,
SQLite, JSON 파일, Lovable의 Supabase 등) 코드로 확인하고, **앱 담당 부서의 Supabase 프로젝트**(§1-1)
안의 **앱 전용 스키마**로 옮기는 설계를 세운 뒤, 마이그레이션 PR 절차로 스키마를 만들고 코드·환경변수를
바꿔 배포하고, **새 데이터가 그 프로젝트에만 쌓이는지** 확인하는 것으로 끝난다.

가장 흔한 실패는 네 가지다. ① 코드는 바꿨는데 배포 플랫폼 환경변수를 안 넣어서 옛 저장소에 계속
쌓임, ② 스키마 변경을 git에 남기지 않아 "고아 마이그레이션"이 됨, ③ 옛 환경의 비밀값이
코드에 그대로 딸려 들어옴, ④ **부서 프로젝트를 확인하지 않고 로그인용 `ai_data_hub`에 데이터 스키마를
만듦**. 이 문서의 검증 단계(§5)는 이 네 가지를 잡기 위한 것이다.

## 1. 조직 공통 전제 (바꾸지 말 것)

| 항목 | 값 |
|---|---|
| 인증(로그인) | **항상** `ai_data_hub` (ref `qtzlhedrlrulxxerueky`). 부서와 무관. `supabaseauthloginguide.md` §1 |
| 데이터 목적지 | **앱 담당 부서의 Supabase 프로젝트** — §1-1 표에서 고른다. 경영지원 앱만 인증 프로젝트와 같다 |
| 앱 데이터 위치 | 목적지 프로젝트 안의 **앱 전용 스키마** (예: `slam`, `ms_flo`). `public`에 새 테이블을 만들지 않는다 |
| RLS | 예외 없이 켠다. 권한 구분이 없는 앱도 마찬가지 (`supabaseauthloginguide.md` §8) |
| 브라우저 키 | publishable key(`sb_publishable_…`)만. **`service_role` 키·DB 비밀번호는 브라우저와 저장소에 절대 넣지 않는다** |
| 스키마·데이터 변경 | `CLAUDE.md` 2번. **`ai_data_hub`(A)**: 바로 실행하지 않는다. `speedrack-co/MS_supabase_schema`에 마이그레이션 파일 → PR → **merge(이 순간 창구 ②가 자동 적용)**. **부서 프로젝트(B)**: `apply_migration`으로 바로 적용 → 실행한 SQL을 앱 repo `supabase/applied/`에 `[DB]` PR로 기록 |
| 비밀값 | 코드·설정 파일(`.replit`, `vercel.json` 등)에 하드코딩 금지. 이미 커밋된 값을 발견하면 지우는 것으로 끝나지 않고 **재발급** (`CLAUDE.md` 3번) |
| 새 스키마 API 노출 | supabase-js에서 `.schema('앱스키마')`로 접근하려면 대시보드 Settings → API → **Exposed schemas**에 추가되어 있어야 한다. 프로젝트 설정이라 Developer 권한으로는 안 되므로 경영지원파트에 요청 |

읽기 전용 SELECT는 절차 없이 바로 실행해도 된다. 분석 단계에서 자유롭게 써도 되는 이유다.

### 1-1. 부서별 데이터 프로젝트 (인증 프로젝트와 다르다)

Supabase 조직이 **부서 단위로 분리**되어 있다. 로그인은 전 부서가 `ai_data_hub` 하나를 쓰지만,
**앱 데이터는 앱 담당 부서의 프로젝트**에 둔다.

| 담당 부서 | 데이터 프로젝트 ref | 인증 프로젝트와 | 클라이언트 |
|---|---|---|---|
| 경영지원 (MS) | `qtzlhedrlrulxxerueky` (`ai_data_hub`) | 같음 | 1개 |
| 물류 (LG) | `xjmeqendyeaptelgxlzg` | 다름 | 2개 (인증용 + 데이터용) |
| 생산 (PD) | `sphlalnqitoplsdpewmp` | 다름 | 2개 |
| 그 외 (PUBLIC) | `ylosliafngprakeyyvwz` | 다름 | 2개 |

프로젝트 URL은 `https://<ref>.supabase.co`, publishable key는 각 프로젝트 대시보드의 Settings → API Keys에서
확인한다(값은 배포 플랫폼 환경변수에만). 표에 없는 부서·프로젝트는 경영지원파트에 확인한다.

**AI가 자동으로 알 수 없는 부분이다.** AI 세션에 연결된 Supabase MCP는 **그 연결이 허가된 조직의
프로젝트만** 보여준다(예: 경영지원 담당자 세션에서는 `ai_data_hub`만 보인다). `list_projects`에 하나만
나온다고 그게 목적지라고 판단하지 말고, **§3-0의 첫 질문으로 담당 부서를 먼저 묻고 이 표에서 ref를
고른다.** 목적지 프로젝트가 MCP에 안 보이면 그 부서 담당자에게 ref·key를 받거나 MCP 연결을 바꿔야 한다.

**인증 프로젝트 ≠ 데이터 프로젝트인 앱(경영지원 외 전부)은 `supabaseauthloginguide.md` §4-1의 경고가
그대로 적용된다.** `ai_data_hub`가 발급한 로그인 JWT는 다른 프로젝트의 RLS에서 인정되지 않는다 —
데이터 프로젝트 입장에서 그 요청은 `anon`이고 `auth.uid()`는 비어 있다. 이 문서 §3-1-1의 선택지 A/B/C 중
무엇으로 갈지 **설계 전에 경영지원파트와 정한다**(§3-1-1). "로그인했으니 데이터도 보호된다"고 가정하고
`user_id = auth.uid()` 정책을 만들면 아무도 못 읽거나, 반대로 anon 정책을 열다가 전부 공개되는 사고가 난다.

---

## 2. 1단계 — 분석: 지금 데이터가 어디에 어떻게 쌓이는가

**코드를 고치기 전에 반드시 이 단계를 끝내고 §2-6의 분석 결과표를 채운다.** 결과표가 비어 있으면
설계도 검증도 할 수 없다.

### 2-0. 출처별로 먼저 찾아볼 흔적

이관 출처에 따라 데이터가 숨어 있는 자리가 다르다. 아래 표의 파일·패키지·환경변수가 있는지부터
확인한다.

#### Replit

| 흔적 | 의미 |
|---|---|
| `.replit`, `replit.nix`, `replit.md` | Replit에서 만든 앱. `.replit`의 `[deployment]`·`[env]` 블록에 비밀값이 들어 있는지 확인 |
| `@replit/database` 패키지, `REPLIT_DB_URL` | **Replit Database (키-값 저장소)**. Replit 밖에서는 접근 불가 → 반드시 Replit 안에서 export해야 한다 |
| `DATABASE_URL`, `PGHOST`/`PGUSER`/`PGPASSWORD`/`PGDATABASE` | **Replit PostgreSQL** (Neon 기반). Replit Secrets에만 값이 있고 코드에는 이름만 있는 게 정상 |
| `drizzle.config.ts`, `shared/schema.ts`, `server/storage.ts`, `server/db.ts` | Replit Agent가 만든 전형적 구조. Drizzle ORM + zod 스키마. **`storage.ts`의 `MemStorage`가 쓰이고 있으면 데이터는 메모리에만 있고 재시작 시 사라진다** — 실은 "쌓이고 있지 않은" 상태 |
| `@replit/object-storage` | Replit Object Storage. 파일·이미지가 여기 있으면 Supabase Storage로 별도 이관 |
| `server/replitAuth.ts`, `openid-client`, `REPL_ID`, `ISSUER_URL` | Replit Auth. 이관 후 동작하지 않으므로 `supabaseauthloginguide.md`로 교체 |
| `.upm/`, `package-lock.json`의 `replit` 항목 | Replit 도구 흔적. 이관과 무관하나 정리 대상 |

#### Lovable

| 흔적 | 의미 |
|---|---|
| `src/integrations/supabase/client.ts`, `src/integrations/supabase/types.ts` | Lovable이 자동 생성한 Supabase 클라이언트. **URL과 publishable key가 하드코딩**되어 있고, 이 URL이 가리키는 프로젝트가 "지금 데이터가 쌓이는 곳"이다 |
| `supabase/migrations/*.sql`, `supabase/config.toml` | Lovable이 적용해 온 마이그레이션 이력. 테이블 구조를 파악하는 1차 자료. 전부 `public` 스키마 기준이다 |
| `supabase/functions/` | Edge Function. 있다면 이관 시 함께 옮겨야 한다 |
| `.env`에 `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` / `VITE_SUPABASE_PROJECT_ID` | Lovable Cloud 프로젝트 식별자. 이 값이 `qtzlhedrlrulxxerueky`가 아니면 **다른 Supabase 프로젝트에 데이터가 있다** |
| `supabase.auth.signUp`, `/auth` 라우트 | Lovable이 만든 self-signup 로그인. 조직 규칙상 제거하고 `supabaseauthloginguide.md`로 교체 |

Lovable 앱은 "이미 Supabase를 쓰니 이관이 필요 없다"고 생각하기 쉽지만, **Lovable Cloud가 관리하는
별도 프로젝트**에 데이터가 있는 경우가 대부분이다. 그 프로젝트는 Lovable 구독·계정에 묶여 있어
회사 자산으로 관리되지 않으므로 담당 부서의 프로젝트(§1-1)로 옮기는 것이 원칙이다.

#### 개인 PC (로컬 개발)

| 흔적 | 의미 |
|---|---|
| `*.db`, `*.sqlite`, `*.sqlite3` 파일, `better-sqlite3`/`sqlite3`/`sql.js` 패키지, Python `sqlite3`, Prisma `provider = "sqlite"` | **SQLite**. 파일 자체가 데이터베이스이므로 그 파일이 repo에 커밋됐는지, 누구 PC에 있는지부터 확인 |
| `localhost:5432`, `localhost:3306`, `pg`/`mysql2`/`psycopg2`/`SQLAlchemy` | 로컬 Postgres/MySQL. 그 PC가 꺼지면 앱도 멈추는 구조 |
| `fs.writeFile`, `fs.appendFile`, `JSON.parse(fs.readFileSync(...))`, `open(..., 'w')`, `json.dump`, `pandas.to_csv` | **JSON/CSV 파일 저장**. `data/`, `db.json`, `*.csv` 같은 파일이 저장소 역할 |
| `localStorage`, `sessionStorage`, `IndexedDB`, `Dexie` | **브라우저에만 저장**. 서버에는 아무것도 없고 사용자 PC마다 다른 데이터를 갖고 있다. "쌓이고 있다"고 착각하기 가장 쉬운 유형 |
| `googleapis`/`gspread`, 스프레드시트 ID | Google Sheets를 DB처럼 사용. 시트 소유자 계정에 종속 |
| `openpyxl`, `xlsx` 패키지로 파일에 append | Excel 파일 저장. 동시 쓰기 시 깨짐 |
| `streamlit`, `st.session_state` | Streamlit 앱. session_state는 새로고침 시 사라지므로 진짜 저장소가 따로 있는지 확인 |

### 2-1. 코드에서 저장 지점 찾기 (명령)

repo 루트에서 아래를 실행해 저장·접속 코드를 한 번에 모은다. 결과를 §2-6 표의 "코드 위치" 열에
옮겨 적는다.

```bash
# 1) 어떤 저장소 라이브러리를 쓰는가
grep -rn -E "better-sqlite3|sqlite3|sql\.js|@replit/database|@replit/object-storage|drizzle-orm|prisma|@prisma/client|knex|typeorm|sequelize|mongoose|pg\b|mysql2|@supabase/supabase-js|supabase-py|firebase|googleapis|gspread" \
  package.json requirements.txt pyproject.toml 2>/dev/null

# 2) 접속 문자열과 환경변수 이름
grep -rn -E "DATABASE_URL|REPLIT_DB_URL|PGHOST|PGPASSWORD|SUPABASE_URL|SUPABASE_KEY|SUPABASE_ANON|PUBLISHABLE_KEY|SERVICE_ROLE|localhost:(5432|3306|27017)|\.supabase\.co|neon\.tech|postgres(ql)?://" \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.py" --include="*.env*" --include="*.toml" --include=".replit" --include="*.json" -r . \
  | grep -v node_modules

# 3) 파일 저장 지점
grep -rn -E "writeFile|appendFile|createWriteStream|readFileSync\(.*\.json|to_csv|to_excel|json\.dump|open\(.*['\"]w|['\"]a['\"]\)" \
  --include="*.ts" --include="*.js" --include="*.py" -r . | grep -v node_modules

# 4) 브라우저 저장소
grep -rn -E "localStorage|sessionStorage|indexedDB|Dexie" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" -r src app 2>/dev/null

# 5) 데이터 파일이 repo에 커밋되어 있는가
git ls-files | grep -E "\.(db|sqlite|sqlite3|json|csv|xlsx)$" | grep -v -E "package(-lock)?\.json|tsconfig|\.eslintrc|components\.json"

# 6) 비밀값이 코드·이력에 남아 있는가 (§2-4)
grep -rn -E "sb_secret_|service_role|eyJhbGciOi|postgres(ql)?://[^:]+:[^@]+@|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35}" -r . | grep -v node_modules
git log -p --all -S "service_role" --oneline | head -50
git log -p --all -S "postgres://" --oneline | head -50
```

Python 앱이면 `--include="*.py"`가 들어간 명령만으로도 충분하다. Streamlit이면 `st.connection`,
`st.secrets`도 같이 찾는다.

### 2-2. 저장 흐름 추적

찾은 저장 지점마다 **"사용자가 어떤 동작을 하면 → 어떤 코드가 → 어디에 → 무엇을 쓰는가"** 를
한 줄로 적는다. 화면·API 단위로 정리하면 빠진 저장 지점이 드러난다.

```
[예시]
- 주문 등록 버튼 → server/routes.ts POST /api/orders → storage.createOrder() → Replit Postgres orders 테이블
- 사진 첨부      → server/routes.ts POST /api/upload  → objectStorage.upload()  → Replit Object Storage
- 즐겨찾기 토글  → src/hooks/useFavorites.ts          → localStorage['favorites'] → 사용자 브라우저 (서버 없음)
- 설정 저장      → src/lib/settings.ts                → fs.writeFile('data/settings.json') → 서버 로컬 파일
```

Replit Agent 구조(`server/storage.ts`)는 `IStorage` 인터페이스 하나를 통해 모든 저장이 지나가므로
이 파일의 메서드 목록이 곧 엔티티 목록이다. 단, **`export const storage = new MemStorage()`** 로
되어 있으면 지금까지의 데이터는 어디에도 남아 있지 않다는 뜻이다. 이관할 "기존 데이터"가 없고
구조만 옮기면 되는 경우이므로 담당자에게 그 사실을 먼저 알린다.

### 2-3. 실제 데이터 확인 (규모·상태)

구조를 알았으면 실데이터를 직접 본다. 옮길 것이 있는지, 얼마나 되는지, 상태가 어떤지 파악한다.

| 출처 | 확인 방법 |
|---|---|
| Replit PostgreSQL | Replit 워크스페이스의 Database 탭 또는 Shell에서 `psql $DATABASE_URL -c "\dt"` 후 테이블별 `select count(*)`. Replit 밖에서는 접속이 막혀 있을 수 있다 |
| Replit Database (키-값) | Replit Shell에서 `curl "$REPLIT_DB_URL?prefix="` 로 키 목록. 키 전체를 JSON으로 덤프하는 스크립트를 Replit 안에서 실행 |
| Lovable Supabase | 해당 프로젝트 대시보드 → Table Editor. 또는 `client.ts`의 URL·key로 `supabase-js`에서 `select('*', { count: 'exact', head: true })`. RLS 때문에 anon으로는 안 보일 수 있으니 대시보드가 확실 |
| SQLite | `sqlite3 파일.db ".tables"` → `select count(*) from 각테이블` → `.schema` |
| JSON/CSV 파일 | 파일 크기, 레코드 수(`jq length`, `wc -l`), 최근 수정 시각. **여러 PC에 서로 다른 버전이 있을 수 있으니 어느 파일이 정본인지 담당자에게 확인** |
| localStorage | 정본이 없다. 사용자 수만큼 사본이 있다. 옮길 데이터가 있다면 사용자별로 export 기능을 만들어 받거나, 포기한다 |
| Google Sheets | 시트 자체가 export 가능(CSV). 행 수·시트 수·수식 여부 확인 |

여기서 확인할 것: 테이블(엔티티)별 건수, 가장 오래된/최근 레코드 시각, NULL이 많은 컬럼, 자유 텍스트로
저장된 날짜·숫자, 사용자 식별 방법(이메일? 이름? Replit user id?), 첨부 파일 유무.

### 2-4. 비밀값 점검

§2-1의 6번 명령 결과를 본다. 아래 중 하나라도 해당하면 **이관 작업을 진행하기 전에 담당자에게
알리고 키 재발급을 요청한다.** 조용히 파일에서만 지우지 않는다(`CLAUDE.md` 3번).

- `.replit`, `vercel.json`, `*.config.ts`, `client.ts` 등에 값이 직접 적혀 있다
- `.env`가 `.gitignore`에 없어서 커밋되어 있다
- git 이력(`git log -p`)에서 접속 문자열이나 `service_role` 키가 나온다
- Lovable의 `client.ts`에 하드코딩된 값은 **publishable key라면 공개 가능**하므로 재발급 대상이 아니다.
  다만 그 프로젝트의 `service_role`이나 DB 비밀번호가 Edge Function 코드 등에 있으면 재발급 대상

### 2-5. 앱 형태 판별 (① 브라우저 직접 / ② 자체 서버)

`supabaseauthloginguide.md` §2(1번 앱 형태)와 같은 판별이다. 이관 후 코드 접근 방식(§3-4)이 여기서 갈린다.

- **① 브라우저가 저장소를 직접 부른다** — 정적 SPA + Supabase(Lovable 전형), 또는 localStorage 앱
- **② 자체 서버(Express, FastAPI, Flask, Next.js API Route 등)가 저장소에 붙는다** — Replit Agent 전형,
  SQLite/로컬 Postgres 앱 전형

②형태는 이관 후에도 서버가 DB 접속 권한을 갖게 되므로, 로그인 화면과 별개로 **API 보호
(`supabaseauthloginguide.md` §7)** 가 이관 범위에 반드시 포함된다.

### 2-6. 분석 결과표 (이 표를 채워야 다음 단계로 간다)

```markdown
## 데이터 현황 분석 — <앱 이름> (<날짜>)

- 이관 출처: Replit / Lovable / 개인 PC (택1, 복수면 모두)
- 담당 부서 → 데이터 목적지 프로젝트: (예: 물류 → `xjmeqendyeaptelgxlzg`, §1-1 표)
- 앱 형태: ① 브라우저 직접 / ② 자체 서버 (프레임워크: )
- 배포 예정 플랫폼: Vercel / Netlify / Cloudflare Pages / Replit Deployments / 기타

| # | 저장소 유형 | 위치(URL/파일/서비스) | 엔티티(테이블/키/파일) | 건수 | 코드 위치 | 실데이터 | 이관 필요 |
|---|---|---|---|---|---|---|---|
| 1 | Replit Postgres | Replit Secrets DATABASE_URL | orders, order_items, customers | 1,240 / 3,870 / 96 | server/storage.ts, shared/schema.ts | 있음 (2026-03~) | 예 |
| 2 | Replit Object Storage | bucket: uploads | 첨부 이미지 | 312개 | server/routes.ts:88 | 있음 | 예 → Supabase Storage |
| 3 | localStorage | 사용자 브라우저 | favorites | 불명 | src/hooks/useFavorites.ts | 사용자별 | 아니오 (포기, 기능은 테이블로 재구현) |
| 4 | JSON 파일 | data/settings.json (repo 커밋됨) | 앱 설정 | 1 | src/lib/settings.ts | 있음 | 예 (수동 재입력) |

- 사용자 식별 방식: (예: Replit Auth의 sub / 이메일 문자열 / 없음)
- 비밀값 점검 결과: (예: .replit에 DATABASE_URL 하드코딩 → 담당자 통보, 재발급 요청함)
- 특이사항: (예: MemStorage 사용 중이라 기존 데이터 없음 / 날짜가 문자열 'YYYY.MM.DD'로 저장됨)
```

이 표는 PR 본문이나 repo의 `docs/` 아래에 남긴다. 검증(§5)에서 이 표의 건수와 비교한다.

---

## 3. 2단계 — 설계: 어디로, 어떤 구조로 옮길 것인가

### 3-0. 사용자에게 먼저 물어볼 것

AI가 임의로 정하면 안 되는 항목이다. 구현 전에 답을 받는다.

0. **이 앱의 담당 부서는 어디인가?** → §1-1 표에서 데이터 목적지 프로젝트가 정해진다. 경영지원이 아니면
   인증 프로젝트와 데이터 프로젝트가 달라지므로 클라이언트 2개 구성(§3-4)과 데이터 보호 방식(§3-1-1)까지
   같이 정해야 한다. **이 답 없이는 아래 어느 것도 시작하지 않는다.**
1. **기존 데이터를 옮겨야 하는가, 구조만 새로 만들면 되는가?** (테스트 데이터뿐이면 후자)
2. **앱 전용 스키마 이름은 무엇으로 할까?** (기존 관례: 소문자, 앱 이름 기반. 예 `slam`, `ms_flo`)
3. **권한 모델** — `supabaseauthloginguide.md` §8의 질문 4개 (전 직원 공용? 본인 것만? 관리자 구분?)
4. **배포 플랫폼은 어디인가?** 환경변수 등록 위치가 달라진다(§3-5)
5. **다른 사내 앱과 공유할 데이터가 있는가?** 있으면 그 앱의 스키마를 참조할지, 뷰를 둘지 경영지원파트와 상의.
   다른 부서 프로젝트에 있는 데이터는 같은 DB가 아니므로 조인이 안 된다 — 복제·동기화가 필요하면 별도 설계
6. **전환 시 앱을 잠시 멈춰도 되는가?** 멈출 수 없으면 병행 기간과 최종 동기화 시점을 정해야 한다(§4-4)
7. **옛 환경(Replit 배포, Lovable 프로젝트)은 언제 내리는가?** 검증 완료 전에는 내리지 않는다

### 3-1. 목적지 구조

- 스키마: **목적지 프로젝트**(§1-1) 안의 `<앱스키마>`. 테이블은 전부 이 스키마 아래에 둔다.
- 테이블명: 소문자 snake_case. 출처의 이름을 그대로 써도 되지만 Lovable의 `public.` 접두사는 뗀다.
- 모든 테이블에 공통으로:
  - `id` — `uuid default gen_random_uuid()` 또는 `bigint generated always as identity`. 출처가 정수 id면
    정수를 유지하는 편이 데이터 이관이 쉽다(외래키 매핑을 안 해도 됨).
  - `created_at timestamptz default now()`, `updated_at timestamptz default now()` (+ 갱신 트리거)
  - 사용자 참조가 있으면 `user_id uuid` — **정본 키는 `ai_data_hub`의 `auth.users.id`**. 목적지가
    `ai_data_hub`면 `references auth.users(id)`를 걸 수 있지만, **다른 부서 프로젝트면 그 DB에 `auth.users`가
    다른 것(그 프로젝트 자체의 auth)이므로 외래키를 걸지 않고 UUID만 저장**한다
- RLS: 모든 테이블 `enable row level security` + 권한 모델에 맞는 정책. 정책 없이 RLS만 켜면
  아무도 못 읽으니 최소한 `authenticated`용 정책은 넣는다.
- 권한(grant): 새 스키마는 기본적으로 API 롤에 열려 있지 않다. 아래를 마이그레이션에 포함한다.

```sql
grant usage on schema <앱스키마> to anon, authenticated, service_role;
grant all on all tables in schema <앱스키마> to authenticated, service_role;
grant all on all sequences in schema <앱스키마> to authenticated, service_role;
alter default privileges in schema <앱스키마> grant all on tables to authenticated, service_role;
alter default privileges in schema <앱스키마> grant all on sequences to authenticated, service_role;
-- anon 에게는 읽기가 정말 필요한 테이블에만 개별 grant
```

그리고 §1의 **Exposed schemas 등록**을 요청한다(목적지 프로젝트의 관리자에게). 등록 전에는 supabase-js의
`.schema('<앱스키마>')` 호출이 `PGRST106` 류 에러로 실패한다.

#### 3-1-1. 인증 프로젝트 ≠ 데이터 프로젝트일 때의 데이터 보호 (경영지원 외 부서 전부)

§1-1에서 말했듯 `ai_data_hub` 로그인 JWT는 물류·생산·PUBLIC 프로젝트의 RLS에서 `anon`으로 취급된다.
따라서 **RLS 정책에 `auth.uid()`·`authenticated` 롤을 쓰는 설계는 이 앱들에서 그대로 동작하지 않는다.**
`supabaseauthloginguide.md` §4-1·§4-2를 참고해 아래 선택지 중에서 경영지원파트와 정한다:

| 선택지 | 내용 | 이 가이드에서의 결과 |
|---|---|---|
| A | 데이터도 `ai_data_hub`에 둔다 | 부서 분리 원칙과 충돌. **경영지원파트가 명시적으로 허용한 경우에만** |
| B | **토큰 교환** — 서버 함수가 `ai_data_hub` 토큰을 검증한 뒤 데이터 프로젝트용 토큰을 새로 서명해 준다(`supabaseauthloginguide.md` §4-2) | 2026-09 OS_scm 에서 동작 확인. 데이터 프로젝트의 RLS 를 `authenticated` 기준으로 다시 써야 하고, 그 프로젝트의 레거시 JWT 비밀값(HS256)에 의존한다. 브라우저가 데이터 프로젝트를 직접 부르는 ①형태를 유지하고 싶을 때 |
| C | 로그인은 화면 게이트로만 쓰고, 데이터 프로젝트 접근은 **자체 서버(②형태)** 가 담당 | **현실적인 기본값.** 서버가 `supabaseauthloginguide.md` §7로 `ai_data_hub` 토큰을 검증한 뒤, 데이터 프로젝트에는 서버 전용 자격(데이터 프로젝트의 `service_role` 또는 pooler 접속)으로 붙는다. 브라우저에는 데이터 프로젝트 키를 **주지 않는다**. 사용자별 권한은 서버 코드에서 판정 |

C를 고르면: 데이터 프로젝트 테이블의 RLS는 여전히 켜되(anon 차단 목적), 실제 접근 제어는 서버가 한다.
①형태(브라우저 직접) 앱을 경영지원 외 부서 프로젝트로 이관하려면 **②형태로 바꾸는 작업이 이관 범위에
들어간다** — 이 점을 §3-0에서 사용자에게 먼저 알린다. 어느 선택지든 **AI가 임의로 정하지 않는다.**

### 3-2. 출처별 스키마 매핑

| 출처 | 매핑 방법 |
|---|---|
| Replit PostgreSQL (Drizzle) | 이미 Postgres이므로 구조 대부분 그대로. `shared/schema.ts`의 `pgTable` 정의를 SQL로 옮기거나 `drizzle-kit generate`로 SQL을 뽑아 스키마 접두사를 붙인다. `serial` → `generated always as identity` 권장. Replit Auth의 `users`/`sessions` 테이블은 **옮기지 않는다** (Supabase Auth로 대체) |
| Replit Database (키-값) | 키 패턴을 분석해 테이블로 정규화한다. `user:123:orders` 같은 접두사 구조면 `orders(user_ref, ...)`. 값이 JSON이면 컬럼으로 풀되, 구조가 제각각인 부분만 `jsonb` 컬럼에 남긴다 |
| Lovable Supabase | `supabase/migrations/*.sql`을 순서대로 읽어 최종 구조를 만들고, `public.` → `<앱스키마>.`로 바꾼다. Lovable이 만든 `profiles` 테이블과 `handle_new_user` 트리거는 **조직 관례(`user_metadata` 우선)와 충돌하므로 제거**하고 필요하면 §4-3의 미러 테이블 패턴으로 대체. Lovable의 RLS 정책은 대부분 `auth.uid() = user_id` 형태라 **목적지가 `ai_data_hub`일 때만** 재사용 가능. 다른 부서 프로젝트면 §3-1-1의 선택지에 따라 다시 설계 |
| SQLite | 타입이 느슨하므로 실데이터를 보고 정한다. `INTEGER` → `bigint`/`boolean`(0/1이면), `TEXT`로 저장된 날짜 → `date`/`timestamptz`(형식 확인 후), `REAL` → `numeric`. `AUTOINCREMENT` → identity. 외래키가 선언만 되고 실제로 안 맞는 행이 흔하니 §5-1에서 검사 |
| JSON/CSV 파일 | 파일 하나 = 테이블 하나가 기본. 배열 안에 배열이 있으면 자식 테이블로 분리. 파일에 없던 `id`·`created_at`을 적재 시 부여 |
| localStorage | 데이터 이관은 보통 포기하고 **기능을 테이블로 재구현**한다(`user_id = auth.uid()` 소유자 모델). 꼭 옮겨야 하면 앱에 "내 데이터 내보내기 → 업로드" 기능을 임시로 넣는다 |
| Google Sheets | 시트 = 테이블. 헤더 행을 컬럼명(snake_case)으로, 수식 셀은 값으로 고정해 CSV로 뽑는다 |

사용자 식별 컬럼은 특히 주의한다. 출처에서 이메일 문자열이나 Replit `sub`로 사람을 구분했다면,
이관 시 `auth.users`의 UUID로 매핑해야 한다. 매핑표(옛 식별자 → `auth.users.id`)는 이메일 기준으로
`select id, email from auth.users`를 읽어 만들고, 매핑 안 되는 사람(퇴사자 등)은 어떻게 할지 담당자에게
묻는다(NULL 허용 / 별도 "레거시 사용자" 컬럼에 원문 보존 등).

### 3-3. 파일·첨부 데이터

Replit Object Storage, 로컬 `uploads/` 폴더, Lovable Storage 버킷의 파일은 **Supabase Storage**로
옮긴다. 버킷 이름은 `<앱스키마>-<용도>` (예 `slam-attachments`), private 버킷 + RLS 정책이 기본.
DB 테이블에는 파일 경로만 저장한다. 버킷 생성과 정책도 DB 변경이므로 §4-1 절차에 포함한다
(`storage.buckets` insert + `storage.objects` 정책).

### 3-4. 코드 접근 방식

| 앱 형태 | 권장 방식 | 비고 |
|---|---|---|
| ① 브라우저 직접 | `@supabase/supabase-js` + publishable key + `.schema('<앱스키마>')`. 데이터 보호는 전적으로 RLS | 가장 단순. 로그인(`supabaseauthloginguide.md`)과 같은 클라이언트를 쓴다 |
| ② 자체 서버 (Node) | 서버에서도 `supabase-js`를 쓰되, **요청의 Authorization 헤더로 받은 사용자 토큰을 그대로 넘겨** RLS가 사용자 기준으로 걸리게 한다 | `supabaseauthloginguide.md` §7의 `requireAuth`와 결합. `service_role`은 배치·관리 작업에만, 서버 env에만 |
| ② 자체 서버 (Drizzle/Prisma/SQLAlchemy 유지) | Supabase의 **Session pooler** 접속 문자열(`…pooler.supabase.com:5432`)을 `DATABASE_URL`로. ORM 설정에 `schema: '<앱스키마>'` 지정 | 이 접속은 RLS를 우회하는 `postgres` 권한이므로 **DB 비밀번호는 service_role과 동급의 비밀값**. 서버 env에만 두고 로그인 가이드 §7 API 보호 필수. 서버리스(Vercel Functions 등)면 Transaction pooler(6543) + `prepare: false` |
| ② Python | `supabase-py` (publishable key + 사용자 토큰 전달) 또는 SQLAlchemy + pooler | 위와 같은 원칙 |

위 표는 **인증 프로젝트 = 데이터 프로젝트(경영지원 앱)** 기준이다. 경영지원 외 부서 앱은 §3-1-1에서
정한 선택지에 따라 달라진다. C(기본값)라면:

```ts
// server/supabase.ts — 인증은 ai_data_hub, 데이터는 부서 프로젝트
import { createClient } from "@supabase/supabase-js";
const need = (k: string) => { const v = process.env[k]; if (!v) throw new Error(`${k} 환경변수가 설정되지 않았습니다.`); return v; };

// 데이터 프로젝트 — 서버 전용 자격. 브라우저로 절대 내보내지 않는다
export const dataClient = createClient(need("DATA_SUPABASE_URL"), need("DATA_SUPABASE_SERVICE_ROLE_KEY"), {
  db: { schema: "<앱스키마>" },
  auth: { persistSession: false, autoRefreshToken: false },
});
// 인증 검증은 supabaseauthloginguide.md §7 의 requireAuth(JWKS, AUTH_SUPABASE_URL) 그대로
```

브라우저 쪽은 로그인용 `authClient`(`ai_data_hub`, publishable key) **하나만** 갖고, 데이터는 전부 자체 API를
거친다. 두 클라이언트를 브라우저에 같이 두는 구성(로그인 가이드 §4-1의 `authClient`/`dataClient` 예시)은
B(토큰 교환, 로그인 가이드 §4-2)를 채택했을 때만 의미가 있다.

Replit Agent 구조(`IStorage`)는 `DatabaseStorage` 구현을 Supabase용으로 하나 더 만들고
`export const storage = new SupabaseStorage()`로 바꾸는 방식이 변경 범위를 가장 좁힌다.
Lovable 구조는 `client.ts`의 하드코딩 값을 env로 바꾸고 `.schema()`를 붙이는 것이 핵심이다.

### 3-5. 환경변수 재정립

옛 환경의 변수 이름을 그대로 쓰지 말고 아래 표로 **정리한 뒤** `.env.example`을 그에 맞게 고친다.
값은 절대 적지 않는다.

| 옛 환경 변수 | 새 변수 (프레임워크 접두사 포함) | 위치 | 비고 |
|---|---|---|---|
| `DATABASE_URL` (Replit Postgres/Neon) | `DATABASE_URL` (Supabase pooler) | 서버 env만 | ②-ORM 유지 시. 브라우저 번들에 들어가면 안 되므로 `VITE_`/`NEXT_PUBLIC_` 접두사 금지 |
| `REPLIT_DB_URL` | (삭제) | — | 테이블로 대체 |
| `PGHOST`/`PGUSER`/… | (삭제) | — | `DATABASE_URL` 하나로 통합 |
| Lovable `VITE_SUPABASE_URL`/`VITE_SUPABASE_PUBLISHABLE_KEY` | 경영지원 앱: 같은 이름 유지, 값만 `ai_data_hub`로. 그 외 부서: 이 변수는 **인증용**(`ai_data_hub`)이 되고 데이터용은 아래 `DATA_*`로 분리 | 배포 플랫폼 + 로컬 `.env.local` | `VITE_SUPABASE_PROJECT_ID`는 삭제 |
| (없음, 하드코딩) | `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` (Vite), `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` (Next.js) — 인증 프로젝트 `ai_data_hub` | 배포 플랫폼 | 이 템플릿의 `.env.example` 기본값은 Next.js 이름이다. Vite/CRA면 접두사를 바꾼다 |
| (없음) — 경영지원 외 부서 | `DATA_SUPABASE_URL`, `DATA_SUPABASE_SERVICE_ROLE_KEY` (C) 또는 `DATABASE_URL` (pooler) | **서버 env만** | 데이터 프로젝트(§1-1) 자격. 브라우저 접두사 절대 금지. B 채택 시에만 `VITE_DATA_SUPABASE_URL`/`VITE_DATA_SUPABASE_PUBLISHABLE_KEY`를 브라우저에 준다 |
| (없음) | `SUPABASE_SERVICE_ROLE_KEY` | **서버 env만, 정말 필요할 때만** | 배치·관리 작업 전용. 브라우저 접두사 절대 금지. 어느 프로젝트의 키인지 이름에 드러나게(`DATA_…`/`AUTH_…`) |
| `REPL_ID`, `ISSUER_URL`, `SESSION_SECRET` (Replit Auth) | (삭제) | — | Supabase Auth로 대체 |

등록 위치와 재배포 방법은 `supabaseauthloginguide.md` §3의 배포 사이트 표를 따른다. 정적 SPA는
**환경변수 등록 후 재배포해야 반영**된다.

옛 환경의 Secrets(Replit Secrets 탭, Lovable 프로젝트 설정)는 검증 완료 후 삭제한다. 삭제 전에
옛 환경이 아직 필요한지(§4-4 병행 기간) 확인한다.

---

## 4. 3단계 — 실행

### 4-1. 스키마 적용과 기록 (`CLAUDE.md` 2번 절차)

목적지에 따라 순서가 반대다. 어느 쪽이든 **실행한 SQL이 git에 남는 것**으로 끝난다.

**A. 목적지가 `ai_data_hub` (경영지원 앱) — PR 먼저, merge가 곧 적용**

1. `speedrack-co/MS_supabase_schema`를 `access="push"`로 세션에 추가하고 클론
2. 새 브랜치에서 `supabase/migrations/YYYYMMDDHHMMSS_create_<앱스키마>_schema.sql` 작성. 파일 머리 주석에
   **대상 프로젝트 ref**를 적는다(어느 프로젝트에 적용할 SQL인지 나중에 헷갈리지 않게)
3. commit → push → PR. **여기까지 DB는 건드리지 않는다**
4. 담당자 merge — **이 순간 창구 ②가 자동으로 `db push`** 한다. 그 뒤에 `apply_migration`을 또 실행하지
   마라(이미 적용된 것을 재실행해 파일 없는 고아 버전이 생긴다)
5. 적용 후 워크플로 run 성공 여부와 `supabase_migrations.schema_migrations` 반영을 확인.
   `db push`는 파일명을 그대로 버전으로 쓰므로 파일명 정정 커밋은 필요 없다(어긋난 경우에만 재라벨링)

**B. 목적지가 부서 프로젝트 (물류·생산·그 외) — 바로 적용, 적용한 SQL을 앱 repo에 기록**

1. 적용 직전에 MCP가 가리키는 프로젝트 ref가 목적지(§1-1)와 같은지 확인한다(`get_project`)
2. `apply_migration`으로 적용한다(이름 예: `create_<앱스키마>_schema`). 사전 승인 단계는 없다
3. `list_migrations`로 채번된 버전을 확인한다
4. 실행한 SQL을 **그대로** 앱 repo의 `supabase/applied/<버전>_<이름>.sql`에 저장한다. 맨 위에 대상 프로젝트
   ref 주석만 덧붙인다
5. 새 브랜치 → commit → push → PR. 제목 `[DB] <설명>`, 라벨 `supabase-migration`. merge는 기록 확정일 뿐
   DB에는 이미 반영돼 있으므로 "DB 적용" 단계를 따로 두지 않는다. 같은 SQL을 다시 실행하지 마라
6. Exposed schemas 등록처럼 **Developer 권한으로 안 되는 프로젝트 설정**은 경영지원파트에 요청한다

마이그레이션 파일 골격:

```sql
-- <앱 이름> 데이터 이관: 스키마 생성
-- 대상 프로젝트: <ref> (<부서>, §1-1)
-- 출처: Replit PostgreSQL (2026-03~), 분석 결과표는 <앱 repo>/docs/migration-analysis.md 참고

create schema if not exists <앱스키마>;

create table <앱스키마>.orders (
  id          bigint generated always as identity primary key,
  legacy_id   integer,                         -- 출처의 원래 id (검증·추적용, 이관 완료 후 삭제 가능)
  user_id     uuid references auth.users(id),
  legacy_user text,                            -- 매핑 안 된 옛 식별자 보존
  status      text not null default 'draft',
  amount      numeric(14,2),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index on <앱스키마>.orders (user_id);
create index on <앱스키마>.orders (created_at);

-- updated_at 자동 갱신
create or replace function <앱스키마>.set_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
create trigger trg_orders_updated before update on <앱스키마>.orders
  for each row execute function <앱스키마>.set_updated_at();

-- RLS (권한 모델은 §3-0에서 받은 답대로)
alter table <앱스키마>.orders enable row level security;
create policy "orders_select_authenticated" on <앱스키마>.orders
  for select to authenticated using (true);
create policy "orders_write_owner" on <앱스키마>.orders
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- 권한
grant usage on schema <앱스키마> to anon, authenticated, service_role;
grant all on all tables in schema <앱스키마> to authenticated, service_role;
grant all on all sequences in schema <앱스키마> to authenticated, service_role;
alter default privileges in schema <앱스키마> grant all on tables to authenticated, service_role;
alter default privileges in schema <앱스키마> grant all on sequences to authenticated, service_role;
```

`legacy_id`/`legacy_user` 같은 이관 추적 컬럼은 §5-1 검증에 쓰고, 검증이 끝난 뒤 별도 마이그레이션으로
지운다.

### 4-2. 코드 변경

원칙: **저장 지점(§2-2에서 찾은 곳)만 바꾸고 화면·비즈니스 로직은 건드리지 않는다.** 이관 PR에
기능 개선을 섞으면 검증에서 문제가 생겼을 때 원인을 못 가른다.

**①형태 / Lovable** — `src/integrations/supabase/client.ts`:

```ts
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
if (!url || !key) throw new Error("VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY 가 설정되지 않았습니다.");

export const supabase = createClient(url, key, {
  db: { schema: "<앱스키마>" },          // 모든 쿼리가 앱 스키마를 기본으로 보게
  auth: { storageKey: "sb-<앱이름>-auth", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});
```

`db.schema` 옵션을 쓰면 기존 `supabase.from('orders')` 호출을 고치지 않아도 된다. `types.ts`는
`supabase gen types typescript --schema <앱스키마>`로 다시 뽑는다. 이 예시는 목적지가 `ai_data_hub`(경영지원 앱)일
때다 — 다른 부서 프로젝트면 §3-1-1의 C대로 브라우저 클라이언트는 로그인 전용이 되고 데이터 호출은 자체 API로 옮긴다.

**②형태 / Replit Agent 구조** — `server/storage.ts`에 Supabase 구현 추가:

```ts
// server/supabase.ts
import { createClient } from "@supabase/supabase-js";
const url = process.env.SUPABASE_URL!;
const key = process.env.SUPABASE_PUBLISHABLE_KEY!;

// 요청마다 사용자 토큰을 실어 RLS가 그 사용자 기준으로 동작하게 한다
export function supabaseForRequest(accessToken: string) {
  return createClient(url, key, {
    db: { schema: "<앱스키마>" },
    global: { headers: { Authorization: `Bearer ${accessToken}` } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
```

```ts
// server/storage.ts — 기존 IStorage 는 그대로, 구현만 교체
export class SupabaseStorage implements IStorage {
  constructor(private sb: SupabaseClient) {}
  async createOrder(input: InsertOrder): Promise<Order> {
    const { data, error } = await this.sb.from("orders").insert(input).select().single();
    if (error) throw error;
    return data;
  }
  // ... 나머지 메서드
}
```

라우트에서는 `supabaseauthloginguide.md` §7의 `requireAuth`가 검증한 토큰으로
`supabaseForRequest(token)`을 만들어 `new SupabaseStorage(sb)`에 넘긴다. `MemStorage`는 삭제한다
(남겨두면 나중에 누군가 다시 켠다).

**②형태 / Drizzle·Prisma 유지** — `DATABASE_URL`만 Supabase pooler로 바꾸고 스키마를 지정한다:

```ts
// drizzle.config.ts
export default { schema: "./shared/schema.ts", out: "./drizzle", dialect: "postgresql",
  dbCredentials: { url: process.env.DATABASE_URL! }, schemaFilter: ["<앱스키마>"] };
// shared/schema.ts
export const app = pgSchema("<앱스키마>");
export const orders = app.table("orders", { ... });
```

```prisma
// schema.prisma
datasource db { provider = "postgresql"; url = env("DATABASE_URL"); directUrl = env("DIRECT_URL"); schemas = ["<앱스키마>"] }
generator client { provider = "prisma-client-js"; previewFeatures = ["multiSchema"] }
```

이 방식은 **DDL 생성(`drizzle-kit push`, `prisma migrate deploy`)을 앱 repo에서 실행하지 않는다.**
DDL은 §4-1 절차로만 적용하고, ORM은 이미 만들어진 테이블을 읽고 쓰기만 한다. ORM의
마이그레이션 명령을 CI나 시작 스크립트에 넣지 말 것.

**SQLite / JSON 파일 (Python 포함)** — 저장 함수 단위로 교체한다. Python이면:

```python
from supabase import create_client
import os
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_PUBLISHABLE_KEY"])
sb.postgrest.schema("<앱스키마>")
sb.table("orders").insert({...}).execute()
```

파일 저장 코드(`fs.writeFile`, `json.dump`)는 남기지 말고 지운다. "혹시 몰라" 두 곳에 동시에 쓰는 코드는
검증(§5-2)을 무의미하게 만든다.

### 4-3. 기존 데이터 적재

**적재 순서**: 부모 테이블 → 자식 테이블. 사용자 매핑표(§3-2)를 먼저 준비한다.

**export**

| 출처 | 명령 |
|---|---|
| Replit Postgres | Replit Shell에서 `pg_dump --data-only --column-inserts --no-owner "$DATABASE_URL" -t 테이블 > dump.sql`, 또는 `psql "$DATABASE_URL" -c "\copy 테이블 to '테이블.csv' csv header"` |
| Replit Database | Replit Shell에서 Node 스크립트로 `db.list()` → `db.get(key)` 전부 JSON 파일로 |
| Lovable Supabase | 대시보드 Table Editor → 각 테이블 → Export CSV. DB 비밀번호를 알면 `pg_dump --schema=public --data-only` |
| SQLite | `sqlite3 파일.db -header -csv "select * from 테이블" > 테이블.csv` |
| JSON/CSV | 그대로. JSON은 `jq`로 평탄화해 CSV로 |
| Google Sheets | 파일 → 다운로드 → CSV (시트별) |

export 파일은 **repo에 커밋하지 않는다.** 개인정보·업무 데이터가 들어 있으므로 작업 PC나 세션의
임시 디렉터리에만 두고 적재 후 삭제한다.

**변환**: CSV를 §3-2 매핑에 맞게 고친다(컬럼명, 날짜 형식, boolean, 사용자 UUID 매핑, `legacy_id` 채우기).
행 수를 변환 전후로 세어 둔다.

**적재** — 공유 프로덕션 DB에 INSERT하는 것이므로 `CLAUDE.md` 2번 절차 안에서 한다:

- **소량(수백 건 이하)**: `insert` 문을 담은 데이터 마이그레이션(`seed_<앱스키마>_from_replit`).
  A는 파일로 PR → merge 시 적용(창구 ②), B는 `apply_migration`으로 적용 → `supabase/applied/`에 기록 PR
- **대량**: 담당자가 Supabase 대시보드 Table Editor → Import data from CSV로 직접 넣거나,
  담당자 승인 아래 `psql "<pooler 접속 문자열>" -c "\copy <앱스키마>.테이블 from '테이블.csv' csv header"`.
  이 경우에도 "어떤 파일을 언제 어디에 넣었는지"를 마이그레이션 PR(빈 SQL + 주석)이나 PR 본문에 기록해
  이력을 남긴다
- identity 컬럼에 옛 id를 그대로 넣어야 하면 `overriding system value`를 쓰고, 적재 후
  `select setval(pg_get_serial_sequence('<앱스키마>.orders','id'), (select max(id) from <앱스키마>.orders))`
  로 시퀀스를 맞춘다. 이걸 빠뜨리면 이관 후 첫 INSERT가 PK 충돌로 실패한다

**파일 적재**: Supabase Storage에는 대시보드 업로드나 `supabase-js`의 `storage.from(bucket).upload()`
스크립트로 넣고, DB의 경로 컬럼을 새 경로로 UPDATE한다(이 UPDATE도 데이터 마이그레이션 PR).

### 4-4. 전환 순서

앱을 멈출 수 있으면 아래 순서로 한 번에 한다. 멈출 수 없으면 1~4를 먼저 하고, 코드 배포 직전에
증분(마지막 export 이후 생긴 데이터)만 한 번 더 export·적재한다.

1. 옛 환경에 "이관 중, 입력 중단" 공지 (또는 읽기 전용 전환)
2. 최종 export → 변환 → 건수 기록
3. 적재 (§4-3) → 시퀀스 보정
4. §5-1 적재 검증
5. 배포 플랫폼에 환경변수 등록 (§3-5) → 코드 배포
6. §5-2 신규 데이터 검증, §5-3 보안 검증
7. 옛 환경을 **읽기 전용으로 최소 1~2주 유지** (검증에서 놓친 데이터 대조용)
8. 문제 없으면 옛 환경 폐기, 옛 Secrets 삭제, `legacy_*` 컬럼 제거 마이그레이션

---

## 5. 4단계 — 검증: 옮겨졌는가, 그리고 새로 쌓이는가

검증은 두 가지를 따로 본다. **(a) 옛 데이터가 빠짐없이 들어왔는가**, **(b) 이제부터 생기는 데이터가
Supabase에만 쌓이는가.** (b)를 빠뜨리면 이관이 끝난 줄 알았는데 옛 저장소에 계속 쌓이는 사고가 난다.

### 5-1. 적재 검증 (옛 데이터)

읽기 전용 SELECT이므로 절차 없이 바로 실행한다.

```sql
-- 1) 건수: §2-6 분석표의 건수와 일치해야 한다
select 'orders' t, count(*) from <앱스키마>.orders
union all select 'order_items', count(*) from <앱스키마>.order_items;

-- 2) 기간: 가장 오래된/최근 레코드가 출처와 같은가
select min(created_at), max(created_at) from <앱스키마>.orders;

-- 3) 사용자 매핑 누락
select count(*) filter (where user_id is null) as unmapped, count(*) as total from <앱스키마>.orders;

-- 4) 외래키 고아 (출처가 SQLite/JSON이면 반드시)
select count(*) from <앱스키마>.order_items i
 left join <앱스키마>.orders o on o.id = i.order_id where o.id is null;

-- 5) 시퀀스가 max(id) 이후를 가리키는가
select last_value from <앱스키마>.orders_id_seq;  -- >= max(id) 여야 한다

-- 6) 합계·샘플 대조: 금액 합, 상태별 건수 등 출처에서 같은 집계를 내서 비교
select status, count(*), sum(amount) from <앱스키마>.orders group by status order by 1;
```

여기에 더해 **무작위 표본 10~20건**을 옛 저장소와 화면에서 눈으로 대조한다(날짜 시차, 인코딩 깨짐,
소수점 잘림은 집계로는 안 잡힌다). 한국어가 `???`로 보이면 CSV 인코딩(EUC-KR ↔ UTF-8) 문제다.

### 5-2. 신규 데이터 검증 (이제부터 쌓이는가) — 가장 중요

배포된 앱에서 실제로 조작하고 DB를 본다.

1. **배포본**(로컬 아님)에서 로그인 → 저장이 일어나는 동작을 종류별로 1건씩 수행 (등록·수정·삭제·첨부)
2. 즉시 확인:
   ```sql
   select * from <앱스키마>.orders order by created_at desc limit 5;
   ```
   방금 만든 행이 보이고 `user_id`가 로그인한 계정의 `auth.users.id`와 같아야 한다.
3. **옛 저장소에는 안 쌓이는지** 확인 — Replit Postgres·Lovable 프로젝트·로컬 파일의 건수가 그대로인지.
   여기가 늘었으면 어딘가 옛 저장 코드가 살아 있거나 환경변수가 옛 값이다.
4. 수정 동작 후 `updated_at`이 바뀌는지, 삭제 후 행이 사라지는지(또는 soft delete 컬럼이 바뀌는지)
5. Supabase 로그로 실제 요청이 도착했는지 확인 — 대시보드 Logs → API, 또는 MCP `query_logs`
   (service: `postgrest`)에서 `<앱스키마>` 테이블로의 INSERT 요청이 배포 도메인에서 들어오는지
6. 첨부 파일: Storage 버킷에 객체가 생기고 DB 경로 컬럼이 그 객체를 가리키는지
7. 다른 사용자 계정으로 같은 동작 → 권한 모델대로 보이거나 막히는지 (RLS 실동작)

배포 후 **1주일 뒤** 다시 본다:

```sql
select date_trunc('day', created_at) d, count(*) from <앱스키마>.orders
 where created_at > now() - interval '7 days' group by 1 order by 1;
```

매일 건수가 붙고 있으면 정상. 배포 당일 이후 0이면 환경변수 미반영이나 사용자들이 옛 URL로
접속 중일 가능성이 크다.

### 5-3. 보안 검증

```sql
-- RLS가 꺼진 테이블이 있는가 (0건이어야 한다)
select schemaname, tablename from pg_tables
 where schemaname = '<앱스키마>' and not rowsecurity;

-- 정책이 하나도 없는 테이블 (RLS만 켜고 정책이 없으면 아무도 못 읽는다 → 의도인지 확인)
select t.tablename from pg_tables t
 left join pg_policies p on p.schemaname = t.schemaname and p.tablename = t.tablename
 where t.schemaname = '<앱스키마>' group by t.tablename having count(p.policyname) = 0;
```

```bash
# 로그인 없이(anon) 읽기·쓰기가 막히는지 — publishable key만으로 호출
curl -s "https://<데이터 프로젝트 ref>.supabase.co/rest/v1/orders?select=*" \
  -H "apikey: <데이터 프로젝트 publishable key>" -H "Accept-Profile: <앱스키마>"
# 기대: [] 또는 401/permission denied. 데이터가 내려오면 anon 정책이 과하게 열린 것

curl -s -X POST "https://<데이터 프로젝트 ref>.supabase.co/rest/v1/orders" \
  -H "apikey: <데이터 프로젝트 publishable key>" -H "Content-Profile: <앱스키마>" -H "Content-Type: application/json" \
  -d '{"status":"test"}'
# 기대: 401 또는 42501 (permission denied). 201이면 위험

# ②형태: 자체 API를 토큰 없이 호출 → 401 (supabaseauthloginguide.md §7)
curl -s -X POST https://<배포도메인>/api/orders -H "Content-Type: application/json" -d '{}'

# 배포된 번들에 비밀값이 섞여 들어갔는지 (①형태 정적 SPA)
curl -s https://<배포도메인>/assets/index-*.js | grep -c -E "sb_secret_|service_role|postgres://"
# 기대: 0

# repo에 비밀값이 남았는지 (§2-1의 6번 다시)
```

MCP `get_advisors` (type: `security`)로 새 스키마에 대한 경고(RLS 미적용, SECURITY DEFINER 뷰 등)가
없는지 마지막으로 본다.

### 5-4. 환경변수·설정 검증

- `.env.example`의 변수 이름 == 코드가 읽는 이름 == 배포 플랫폼에 등록된 이름. 세 곳을 나란히 놓고
  대조한다. 접두사(`VITE_`/`NEXT_PUBLIC_`) 하나가 다르면 배포본에서 `undefined`가 된다
- 배포 플랫폼의 Production / Preview 환경 모두에 등록됐는가
- 옛 변수(`REPLIT_DB_URL`, `PGHOST`, Lovable `VITE_SUPABASE_PROJECT_ID` 등)가 코드에서 완전히 사라졌는가
  (`grep -rn` 결과 0건)
- `.replit`, `vercel.json`, `netlify.toml`에 값이 남아 있지 않은가
- `CLAUDE.md` 상단 「이 앱에 대해」의 "DB (Supabase 프로젝트 / 스키마)" 항목과 README의 "DB" 항목을 새 값으로 채웠는가

### 5-5. 이관 완료 기록

검증이 끝나면 아래를 남긴다.

- 앱 repo: `docs/migration-analysis.md`(§2-6 표) + 검증 결과(건수 대조표, 검증 일자, 검증한 사람)
- 스키마·데이터 변경 SQL: A는 `speedrack-co/MS_supabase_schema`, B는 앱 repo `supabase/applied/` (`[DB]` PR)
- Notion 「레포 인덱스」와 `CLAUDE.md` 「이 앱에 대해」: DB 위치를 `<프로젝트 ref 또는 이름> / <앱스키마>`로 갱신
- 옛 환경 폐기 예정일과 담당자

---

## 6. 출처별 함정 (실제로 자주 걸리는 것)

1. **Replit `MemStorage`** — 코드에 Drizzle 스키마와 `DatabaseStorage`가 있어도 `storage = new MemStorage()`면
   지금까지 데이터는 없다. "왜 옛 데이터가 없냐"는 문의가 오기 전에 분석 단계에서 먼저 알린다.
2. **Replit Database는 Replit 밖에서 못 읽는다** — `REPLIT_DB_URL`은 워크스페이스 안에서만 유효. export는
   반드시 Replit Shell에서. Replit 계정이 사라지면 데이터도 사라지므로 서두른다.
3. **Replit Postgres(Neon)는 idle 시 중지된다** — 첫 접속이 느리거나 실패할 수 있다. 재시도한다.
4. **Lovable의 `profiles` + `handle_new_user` 트리거** — `auth.users`에 걸린 트리거를 `ai_data_hub`로 그대로
   가져오면 **다른 앱의 로그인에까지 영향**을 준다. 공유 DB의 `auth.users`에 트리거를 거는 건 경영지원파트와
   협의 후에만.
5. **Lovable의 self-signup** — 조직은 계정을 앱에서 만들지 않는다. `signUp` 코드는 제거.
6. **Lovable `types.ts`가 `public` 기준** — 스키마를 옮기면 타입이 안 맞아 빌드가 깨진다. `--schema`로 재생성.
7. **SQLite 날짜** — `'2026-03-05 14:00'`, `'2026.03.05'`, epoch ms가 한 컬럼에 섞여 있는 경우가 흔하다.
   변환 전에 `select distinct length(col)`, 정규식으로 형식 분포부터 본다.
8. **SQLite boolean** — 0/1, 'true'/'false', 'Y'/'N'이 섞인다. 명시적으로 매핑한다.
9. **CSV 인코딩** — Excel로 저장한 CSV는 EUC-KR(CP949)일 수 있다. `iconv -f cp949 -t utf-8` 후 적재.
10. **localStorage 앱은 "서버 데이터"가 처음부터 없다** — 이관이 아니라 신규 구축이다. 사용자에게 그렇게 설명한다.
11. **identity 시퀀스 미보정** — 옛 id를 그대로 넣고 시퀀스를 안 맞추면 이관 후 첫 등록이 PK 충돌.
12. **Exposed schemas 미등록** — 코드·env 다 맞는데 `PGRST106`/"schema must be one of" 에러면 이것.
13. **`db.schema` 옵션 없이 `.from('테이블')`** — `public.테이블`을 찾아 404. 클라이언트 생성 시 스키마 지정.
14. **ORM의 자동 마이그레이션** — `drizzle-kit push`, `prisma db push`, `synchronize: true`(TypeORM)가 시작
    스크립트에 남아 있으면 배포 때마다 공유 프로덕션 DB에 DDL을 날린다. 반드시 제거.
15. **정적 SPA 환경변수는 빌드 타임** — 등록만 하고 재배포 안 하면 옛 값(또는 undefined)으로 계속 동작.
16. **두 곳에 동시에 쓰는 과도기 코드** — 안전해 보이지만 §5-2 검증을 무력화하고, 나중에 어느 쪽이 정본인지
    아무도 모르게 된다. 전환은 한 번에.
17. **부서 프로젝트 확인 없이 `ai_data_hub`에 스키마 생성** — MCP에 `ai_data_hub`만 보여서, 또는 로그인 가이드가
    `ai_data_hub`를 말해서 데이터도 거기 두는 실수. 물류·생산·PUBLIC 앱의 데이터는 §1-1의 부서 프로젝트로.
18. **`ai_data_hub` 로그인 JWT로 부서 프로젝트 RLS를 통과하려는 설계** — 안 된다(§1-1, §3-1-1). `auth.uid()`
    기반 정책을 만들었는데 "로그인했는데 아무것도 안 보인다"면 이것. 데이터 프로젝트에서 그 요청은 `anon`이다.
19. **부서 프로젝트 `service_role`을 브라우저 변수에** — C 구성에서 데이터 프로젝트 자격은 서버 env에만.
    `VITE_`/`NEXT_PUBLIC_` 접두사가 붙은 순간 번들에 실려 공개된다.

---

## 7. 완료 체크리스트

작업을 "완료"로 보고하기 전에 전부 체크한다.

**분석**
- [ ] 담당 부서 확인 → §1-1 표에서 데이터 목적지 프로젝트 ref 확정
- [ ] §2-6 분석 결과표 작성 (저장소별 위치·엔티티·건수·코드 위치)
- [ ] 앱 형태(①/②) 판별
- [ ] 비밀값 점검 완료. 발견 시 담당자 통보·재발급 요청함
- [ ] 사용자 식별 방식과 `auth.users` 매핑 방법 확정

**설계**
- [ ] §3-0 질문 8개(0~7)에 대한 답 확보
- [ ] 경영지원 외 부서면 §3-1-1의 데이터 보호 선택지(A/B/C) 경영지원파트와 확정. C면 ②형태 전환 포함
- [ ] 앱 스키마 이름, 테이블 구조, RLS 정책, grant 확정
- [ ] 환경변수 표(§3-5) 작성, `.env.example` 갱신
- [ ] Exposed schemas 등록 요청함

**실행**
- [ ] §4-1대로 스키마 적용·기록. A: `MS_supabase_schema` PR → merge(=적용) → 워크플로 run 성공 +
      `schema_migrations` 반영 확인. B: 프로젝트 ref 확인 → `apply_migration` → 실행한 SQL을 앱 repo에
      `[DB]` PR(라벨 `supabase-migration`)로 기록. 파일 머리에 대상 프로젝트 ref 명시
- [ ] 코드에서 옛 저장 경로 제거, Supabase 경로로 교체. ORM 자동 마이그레이션 제거
- [ ] ②형태면 API 보호(§2-6) 구현
- [ ] 기존 데이터 export → 변환 → 적재(승인 절차 안에서) → 시퀀스 보정
- [ ] 배포 플랫폼 환경변수 등록 → 재배포

**검증**
- [ ] §5-1 건수·기간·매핑·고아·집계 대조, 표본 육안 대조
- [ ] §5-2 배포본에서 실제 동작 → 새 행 확인, 옛 저장소 건수 불변 확인, 로그 확인
- [ ] §5-3 RLS 전 테이블 적용, anon curl 차단, 번들·repo에 비밀값 없음, advisors 경고 없음
- [ ] §5-4 변수 이름 3곳 일치, 옛 변수 0건
- [ ] 1주 후 일별 건수 추이 확인
- [ ] §5-5 기록 (docs, Notion 인덱스, CLAUDE.md 「이 앱에 대해」)
- [ ] 옛 환경 읽기 전용 유지 후 폐기 일정 확정

---

## 8. AI에게 (이 파일을 읽고 진행할 때)

0. **담당 부서를 가장 먼저 물어라.** 그 답으로 §1-1 표에서 데이터 목적지 프로젝트를 정한다. `list_projects`에
   `ai_data_hub`만 보인다고 그게 목적지라고 판단하지 마라 — 그건 이 세션의 MCP가 경영지원 조직에만 붙어
   있다는 뜻일 뿐이다. 경영지원 외 부서면 인증·데이터 프로젝트가 다르다는 것과 그 결과(§3-1-1)를 사용자에게
   먼저 설명하라.
1. **§2 분석을 먼저 끝내고 §2-6 표를 사용자에게 보여준 뒤에** 설계로 넘어가라. 표 없이 코드부터 고치지 마라.
2. `MemStorage`·localStorage처럼 "실은 쌓이고 있지 않은" 경우를 발견하면 그 사실을 가장 먼저 보고하라.
3. 비밀값을 발견하면 지우지 말고 위치를 보고하라. 값 자체를 대화나 PR 본문에 옮겨 적지 마라.
4. §3-0의 질문에 답을 받기 전에 스키마 이름·권한 모델을 정하지 마라.
5. DDL·INSERT는 `CLAUDE.md` 2번 절차(§4-1)대로 하라. 목적지가 `ai_data_hub`면 **절대 바로 실행하지 말고**
   `MS_supabase_schema`에 PR을 올려 merge를 기다려라 — merge 순간 창구 ②가 자동 적용하므로, 그 뒤에
   `apply_migration`을 또 실행하면 고아 버전이 생긴다. 목적지가 부서 프로젝트면 `apply_migration`으로 바로
   적용하고, 실행한 SQL을 그대로 앱 repo에 `[DB]` PR로 남겨라 — 기록 PR까지 올려야 완료다.
   읽기 전용 SELECT(분석·검증)는 바로 실행해도 된다.
6. 코드 변경은 저장 지점만. 기능 개선을 섞지 마라. 옛 저장 코드는 남기지 말고 지워라.
7. ②형태면 `supabaseauthloginguide.md` §7 API 보호를 이 작업의 필수 범위로 포함하라.
   DB 비밀번호·`service_role`은 서버 env에만, 브라우저 접두사 변수에는 절대 넣지 마라.
8. export 파일과 데이터 CSV는 repo에 커밋하지 마라.
9. 검증은 §5-1(옛 데이터)과 §5-2(새 데이터)를 **둘 다** 하고, 결과(건수 대조표, curl 결과)를 보고에 포함하라.
   "코드를 바꿨다"는 완료가 아니다. **배포본에서 만든 행이 목적지 프로젝트(§1-1)의 앱 스키마에 들어가고
   옛 저장소에는 안 들어가는 것을 확인한 시점**이 완료다.
10. 완료 보고 전에 §7 체크리스트를 스스로 대조하고, 못 한 항목은 이유와 함께 명시하라.
