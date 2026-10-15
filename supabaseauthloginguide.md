# 스피드랙 사내 앱 — 로그인 · 계정 센터 연동 가이드

> **이 파일의 용도**: 사내 앱에 **사내 계정 로그인(Supabase Auth)** 과 **계정 센터(MS_account)** 를
> 붙일 때, 그 앱에서 일하는 AI(Claude Code 등)에게 이 파일 하나만 읽히면 되도록 쓴 실행 지침입니다.
> 새 앱에 처음 붙이는 경우와, 이미 자체 로그인·비밀번호 찾기가 있는 앱을 전환하는 경우를 모두 다룹니다.
>
> - 최신본: `https://ms-account.vercel.app/app-guide.md` (원본: `speedrack-co/MS_account` 의 `public/app-guide.md`)
> - `speedrack-co/repo-template` 의 `supabaseauthloginguide.md` 는 **이 파일의 사본**이다(2026-09-30 부터 — SLAM 기반 옛 가이드를 대체).
>   고칠 때는 이 파일을 고치고 사본을 똑같이 맞춘다.
>
> **사람이 할 일** — 둘 중 편한 방법으로 대상 앱의 Claude Code 에게 읽히면 됩니다. 저장소 권한은 필요 없습니다.
>
> - **파일로 전달**: 이 파일을 대상 앱 폴더에 넣거나 대화창에 첨부하고 `이 파일을 읽고 이 앱에 적용해줘.`
> - **주소로 전달**: `https://ms-account.vercel.app/app-guide.md 를 읽고 이 앱에 적용해줘.`
>
> 파일을 앱 폴더에 넣었다면 적용이 끝난 뒤 지워도 됩니다(최신본은 위 주소).

---

## 0. 한눈에 보기

| 누가 | 무엇을 |
|---|---|
| **앱** | 로그인(`signInWithPassword`) · 세션 유지 · 비활성 계정 차단 · 첫 로그인 강제 이동 · 계정 센터 링크 2개 · (자체 서버가 있으면) API 토큰 검증 |
| **계정 센터** (`MS_account`) | 비밀번호 찾기(다우오피스 알림으로 인증코드) · 처음 로그인 비밀번호 설정 · 비밀번호 변경 · 변경 기록 · 연결된 앱 관리 |
| **다우 동기화** (경영지원) | 전 직원 계정 생성 · 퇴사/비활성 처리 |

데이터가 **다른 Supabase 프로젝트**에 있는 앱은 로그인만으로 끝나지 않는다 — §4-1·§4-2 를 먼저 읽는다.

이 가이드는 **사내 계정 로그인**만 다룬다. 거래처(외부 업체) 등 다른 로그인이 필요하면 **앱이 자체 개발·운영**한다 — 지킬 것만 §8-1.

앱이 **만들지 않는 것**: 회원가입, 비밀번호 찾기 화면, 비밀번호 재설정 화면, 비밀번호 변경 폼,
`resetPasswordForEmail`, `PASSWORD_RECOVERY` 처리, Supabase Redirect URL 등록.

## 1. 바꾸면 안 되는 사실

| 항목 | 값 |
|---|---|
| 인증 프로젝트 | Supabase `ai_data_hub` (ref `qtzlhedrlrulxxerueky`), URL `https://qtzlhedrlrulxxerueky.supabase.co` — 여러 앱이 공유하는 **프로덕션** |
| 브라우저 키 | publishable key (`sb_publishable_…`). 공개 키지만 **값은 코드·저장소·문서에 적지 않고 배포 플랫폼 환경변수에만** 넣는다. 모르면 경영지원파트에 요청 |
| 절대 금지 | `service_role` / `sb_secret_…` 키를 브라우저 코드·번들·저장소에 넣는 것 |
| 계정 센터 주소 | 지금 `https://ms-account.vercel.app` → 2026-10 `https://account.speedrackms.kr` 이전 예정. **코드에 적지 말고 환경변수로** |
| 계정 | 이미 전 직원 계정이 있다. 로그인 ID 는 회사 이메일 |
| 비활성 | 다우 동기화가 `user_metadata.status = "STOP"` 과 `banned_until`(Supabase 차단)을 건다. 앱은 감지해서 막기만 한다. **실제로 막는 것은 `banned_until`** 이다 — `status` 는 본인이 고칠 수 있는 값이라 보조 신호로만 쓴다(§6-1) |
| 첫 로그인 강제 | `app_metadata.must_change_password === true` (**`user_metadata` 아님**) |
| 거래처(외부 업체) | **사내 로그인(`ai_data_hub`)에 계정을 만들지 않는다.** 사내 계정은 직원 권한을 받아 "로그인만 하면 누구나" 정책의 직원 데이터가 열린다. 거래처 로그인이 필요하면 앱이 자체 개발한다(§8-1) |
| 토큰 `role` | 직원은 대부분 `authenticated` 지만, 데이터 접근 승인을 받은 직원은 전용 롤(`gw_operator` 등)로 나간다. **`role === "authenticated"` 로 직원 여부를 판단하지 않는다** |

`user_metadata` 에는 `full_name` · `org_name` · `employee_number` · `status` 가 채워져 있다.
표시 이름은 `full_name → 이메일 앞부분` 순으로 쓴다(`user_metadata.name` 은 없다 — 구글 로그인 계정에만 붙는 값이다).
사용자 표시 정보는 `user_metadata` 를 먼저 쓴다. `public.MG_erp_user`(ERP 사용자)는 전 직원을 담고 있지 않아서,
표시 정보를 여기서만 읽으면 일부 사용자의 값이 빈다.

## 2. 시작 전에 AI 가 확인할 것 (추측 금지)

코드를 쓰기 전에 아래를 **코드로 확인**하고, 코드로 알 수 없는 것만 사용자에게 묻는다.

1. **앱 형태** — 로그인 뒤 데이터를 어떻게 읽고 쓰는가?
   - **① 브라우저 → Supabase 직접** (`supabase-js` 로 테이블 select/insert): RLS 가 데이터를 지킨다.
   - **② 브라우저 → 자체 서버(`/api/...`) → DB** (Express, Next.js API Route, Vercel Functions 등이
     `DATABASE_URL`·`service_role` 로 DB 접속): 서버 연결은 RLS 를 우회한다. **§7 API 보호가 필수** —
     빠뜨리면 로그인 화면은 장식이다(2026-09 PD_MSDS-Management 에서 인증 없는 DELETE API 가 열려 있던 실제 사고).
2. **앱 데이터 위치** — `ai_data_hub` 안인가, **다른 Supabase 프로젝트**인가, 다른 DB 인가?
   다른 Supabase 프로젝트면 로그인은 되는데 데이터가 안 보이는 상태가 된다 — **§4-2 를 먼저 읽는다.**
3. **배포 사이트** — Vercel / Netlify / Cloudflare Pages / Replit / 기타? (환경변수 안내에 필요)
4. **기존 인증** — 이미 로그인·비밀번호 찾기·회원가입이 있는가? 있으면 §9 전환 절차를 따른다.
5. **권한 모델** — 사용자에게 반드시 묻는다(§8). "관리자 = 경영지원파트" 는 기본값이 아니다.

## 3. 환경변수

값은 **배포 플랫폼 환경변수**와 로컬 `.env.local` 에만 넣고, `.env.example` 에는 이름만 남긴다.
아래 표는 Vite 기준이다. **브라우저로 내보내는 방법은 스택마다 다르니 먼저 확인한다.**

| 스택 | 브라우저용 이름 | 비고 |
|---|---|---|
| Vite | `VITE_…` | `import.meta.env` 로 읽는다 |
| Next.js | `NEXT_PUBLIC_…` | **`VITE_` 이름은 무시된다** — 이름을 바꿔 등록해야 한다 |
| CRA | `REACT_APP_…` | |
| 빌드 도구 없는 정적 앱(HTML 한 장 등) | 아무 이름이나 | 빌드 스크립트가 `process.env` 를 읽어 파일에 넣는다. OS_scm 은 `build.js` 가 `VITE_` 이름을 그대로 읽어 쓴다 |

이름을 정하기 전에 **배포 플랫폼에 이미 등록된 변수 이름을 확인한다.** 경영지원파트가 먼저 넣어 두는 경우가 있고,
이름이 안 맞으면 값이 비어서 "설정되지 않았습니다" 에러가 난다.

| 변수 | 값 | 비고 |
|---|---|---|
| `VITE_SUPABASE_URL` | `https://qtzlhedrlrulxxerueky.supabase.co` | 앱 데이터가 다른 프로젝트면 `VITE_AUTH_SUPABASE_URL` 로 구분(§4-1) |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_…` | 위와 같음 (`VITE_AUTH_SUPABASE_KEY`) — §4-1 |
| `VITE_ACCOUNT_CENTER_URL` | `https://ms-account.vercel.app` | 끝에 `/` 없이. 도메인 이전 때 이 값만 바꾸고 재배포 |
| `VITE_APP_URL` | (Vercel 앱은 **넣지 않는다** — 자동) | 비밀번호를 바꾼 뒤 돌아올 고정 주소. Vercel 은 빌드 때 `VERCEL_PROJECT_PRODUCTION_URL` 로 알려 주므로 §5-1 의 `vite.config` 한 줄이 채운다. Vercel 이 아니거나 회사 도메인을 따로 붙였으면 그 주소(`https://…`)를 넣는다 |
| `AUTH_SUPABASE_URL` | 위 URL 과 같음 | **②형태 서버 전용** (§7) — 프리픽스 없이 |

- 값이 없으면 **폴백 없이** 명확한 에러를 낸다. 하드코딩 폴백 금지.
- 정적 SPA 는 빌드 때 값이 구워지므로 **등록 후 재배포**해야 반영된다.

| 배포 사이트 | 등록 위치 | 재배포 |
|---|---|---|
| Vercel | Project → Settings → Environment Variables → 이름·값 입력, 적용 환경(Production / Preview) 선택 → Save | Deployments → 최신 배포 → ⋯ → Redeploy |
| Netlify | Site configuration → Environment variables → Add a variable | Deploys → Trigger deploy → Deploy site |
| Cloudflare Pages | Workers & Pages → 프로젝트 → Settings → Variables and Secrets (Production / Preview 각각) | Deployments → Retry deployment |
| Railway | 서비스 → Variables → New Variable | 변수 저장 시 자동 재배포(안 되면 Deployments → Redeploy) |
| 로컬 개발 | 프로젝트 루트 `.env.local` (`.gitignore` 에 들어 있는지 확인) | dev 서버 재시작 |

값이 안 들어가면 "설정되지 않았습니다"(이 가이드의 에러) 또는 "Invalid API key" 가 난다 — 배포본에서 로그인 1회로 확인한다.
- 서버 전용 값에 `VITE_`/`NEXT_PUBLIC_` 을 붙이지 않는다. Vite `envPrefix` 를 넓히지 않는다
  (`SUPABASE_` 같은 넓은 프리픽스는 서버 비밀값을 번들에 싣는다).

## 4. Supabase 클라이언트

```ts
// src/lib/supabase.ts
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
if (!url || !key) throw new Error("VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY 가 설정되지 않았습니다.");

export const supabase = createClient(url, key, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false, // 복구 링크를 쓰지 않는다. 구글 OAuth 를 같이 쓰는 앱만 true
  },
});
```

### 4-1. 앱 데이터가 다른 Supabase 프로젝트에 있을 때 — 클라이언트 2개

로그인은 **언제나 `ai_data_hub`** 가 한다. 앱 데이터가 다른 프로젝트에 있으면 클라이언트를 2개 두고
`storageKey` 를 반드시 나눈다(같은 origin 에서 기본 키를 공유하면 세션이 서로 덮어쓴다).

```ts
export const authClient = createClient(AUTH_URL, AUTH_KEY, {
  auth: { storageKey: "sb-<앱이름>-auth", persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
});
export const dataClient = createClient(DATA_URL, DATA_KEY, {
  auth: { persistSession: false, autoRefreshToken: false },
});
```

여기서 끝내면 **로그인은 되는데 데이터가 안 보이거나, 반대로 로그인 없이도 다 보이는** 상태가 된다.
`ai_data_hub` 가 발급한 토큰은 다른 프로젝트의 RLS 에서 인정되지 않기 때문이다 — 그쪽 입장에서 그 요청은
그냥 `anon` 이고 `auth.uid()` 는 비어 있다. 아래 셋 중 하나를 사용자와 **먼저** 정한다.

| 선택 | 언제 | 비용 |
|---|---|---|
| **A. 데이터를 `ai_data_hub` 앱 전용 스키마로 옮긴다** | 새 앱이거나 옮길 수 있는 앱 | 이관 작업 (`repo-template` 의 `migration-guide.md`). 이후 RLS·`auth.uid()` 가 그대로 동작 |
| **B. 토큰 교환** (§4-2) | 데이터 프로젝트를 유지해야 할 때 | 서버 함수 1개 + 데이터 프로젝트의 JWT 비밀값 관리 |
| **C. 로그인을 화면 게이트로만** | 공개돼도 되는 데이터일 때만 | 데이터 보호가 로그인과 무관해진다 — 민감한 데이터면 고르지 말 것 |

### 4-2. 토큰 교환 (B) — 데이터 프로젝트를 유지하는 방법

2026-09-20 OS_scm(해외영업 Speedrack-DB)에서 실제로 적용해 동작을 확인한 방식이다.
**데이터가 다른 Supabase 프로젝트에 있는 앱에만 해당한다.** `ai_data_hub` 를 쓰는 앱이 이걸 만들 이유는 없다.

```
브라우저: ai_data_hub 로 로그인 → access token 획득
   ↓ Authorization: Bearer <ai_data_hub 토큰>
서버 함수 /api/token: 토큰을 JWKS 로 검증 → 통과하면 데이터 프로젝트용 토큰을 새로 서명해 응답
   ↓
브라우저: 그 토큰으로 데이터 클라이언트를 세팅 → 데이터 프로젝트의 RLS 가 auth.uid()·email 을 인식
```

**서버 함수 규칙 (전부 필수)**

1. 순서를 지킨다: `ai_data_hub` 토큰 검증(JWKS, `issuer` 확인, `audience: "authenticated"`)
   → `user_metadata.status` 가 `ONLINE` 이 아니면 거부 → `app_metadata.must_change_password` 면 거부
   → **통과한 경우에만** 서명.
2. 서명하는 클레임은 **검증된 토큰에서 꺼낸 값만** 쓴다(`sub`, `email`). 클라이언트가 보낸 `role`·`sub`·`email` 은 절대 쓰지 않는다.
3. 발급 토큰은 `role: "authenticated"` 고정, 유효기간 10~15분, refresh token 없음.
   **`service_role` 은 어떤 경우에도 발급하지 않는다.**
4. 비밀값(데이터 프로젝트의 JWT secret)은 서버 런타임 환경변수로만 둔다. 로그·에러 메시지·응답에 실리지 않게 한다.
   브라우저 번들에 들어가는 이름(`VITE_`/`NEXT_PUBLIC_`)을 절대 쓰지 않는다.
5. 사용자당 호출 횟수 제한을 건다(예: 10분 30회).
6. **데이터 프로젝트의 RLS 를 이 토큰 기준으로 다시 쓴다** — 모든 정책을 `authenticated` 에게만 열고 `anon` 은 막는다.
   이걸 안 하면 로그인을 붙여도 보호 수준은 그대로다. 이 단계가 이 작업의 핵심이다.

**알아 둘 것**

- 이 방식은 데이터 프로젝트의 **레거시 JWT secret(HS256)** 에 의존한다. Supabase 가 새 키 체계로 넘어가면
  멈춘다(`ai_data_hub` 는 이미 레거시 키가 꺼져 있다). 앱의 `CLAUDE.md` 에 이 의존성을 적어 둔다.
- 비밀값은 **데이터 프로젝트 담당 부서가** Supabase 대시보드(Project Settings → JWT Keys)에서 꺼내
  경영지원파트에 사내 메신저로 전달한다. 채팅창·PR·코드에 붙이지 않는다. 등록은 경영지원파트가
  배포 플랫폼에서 하고, 전달한 메시지는 지운다. `revoked`/`disabled` 로 나오면 이 방식을 쓸 수 없으니 먼저 알린다.
- 병합·배포 순서: **환경변수 등록 → 병합 → 배포.** 먼저 배포하면 로그인은 되는데 교환 함수가 설정 없이 떠서 막힌다.
- 서버 함수를 만들 수 있는 앱이면, 토큰을 내주는 대신 **서버가 대신 데이터를 읽어 주는 방식(§7)** 이 더 안전하다.
  비밀값 자체가 필요 없기 때문이다. 다만 데이터 접근 코드를 전부 API 로 옮겨야 해서 작업량이 크다.

### 4-3. 서버에서 로그인·세션 갱신을 하면 — 앱 주소(Referer)를 붙인다

사내 앱 사용 현황(AccessHub `/apps`, 전사 레포 현황판)은 **로그인·세션 갱신 요청에 붙은 Referer(앱 주소)** 로
어느 앱인지 가른다. 브라우저에서 부르면 브라우저가 자동으로 붙이므로 할 일이 없다.
하지만 **서버 코드가 Supabase Auth 를 부르면 Referer 가 비어서**, 그 앱 이용자가 전부 「앱 미상 · 서버 로그인」으로
잡히고 현황판에서 앱이 사라진다(2026-10 실측: MS_FLO 이용자 24명, AccessHub middleware 세션 갱신).

해당하는 경우:

- 자체 서버(Express·Vercel 함수 등)가 `signInWithPassword` 를 대신 부르는 앱
- Next.js `@supabase/ssr` 의 `createServerClient`(middleware·서버 컴포넌트에서 세션 갱신)
- 그 밖에 서버에서 사용자 세션으로 `supabase.auth` 를 부르는 클라이언트

서버용 클라이언트를 만들 때 `global.headers` 에 앱의 **고정 운영 주소**를 넣는다.

```ts
// 서버 전용. 주소는 환경변수로 — 하드코딩 금지
const APP_URL = (process.env.APP_URL
  || (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "")
).replace(/\/+$/, "");
const appHeaders = APP_URL ? { Referer: `${APP_URL}/` } : {};

createClient(url, key, { global: { headers: appHeaders }, auth: { persistSession: false, autoRefreshToken: false } });
// Next.js: createServerClient(url, key, { global: { headers: appHeaders }, cookies: { … } });
```

- 주소는 이미 쓰는 변수가 있으면 그것을 쓴다(`PUBLIC_APP_URL`·`NEXT_PUBLIC_APP_URL` 등 — 이름을 새로 만들지 않는다).
  Vercel 앱은 `VERCEL_PROJECT_PRODUCTION_URL` 이 자동으로 들어온다.
- 값이 없으면 헤더를 붙이지 않는다 — 집계에서만 빠지고 로그인 동작은 같다.
- `service_role` 클라이언트(관리·배치용)에는 붙이지 않아도 된다 — 집계는 사람의 로그인·세션 갱신만 센다.
- 브라우저용 클라이언트에는 넣지 않는다(브라우저가 알아서 붙인다).
- 참조 구현: `MS_FLO` `artifacts/api-server/src/lib/supabase-auth.ts`(Express), `MS_accesshub` `lib/appReferer.js`(Next.js).

## 5. 계정 센터 연동 (핵심)

### 5-1. 링크 헬퍼

돌아올 주소는 **앱의 고정 주소**여야 한다. Vercel 의 배포별 주소(`ms-n0360xnum-speedrack-ms.vercel.app` 같은)로
접속했더라도 고정 주소(`ms-flo.vercel.app`)가 전달되게, 빌드 때 Vercel 이 주는 값을 쓴다. 따로 등록할 것은 없다.

```ts
// vite.config.ts — 파일 맨 위(defineConfig 보다 앞)에 추가
// Vercel 이 빌드 때 주는 프로젝트 고정 주소를 앱에 넘긴다. VITE_APP_URL 을 직접 넣었으면 그 값이 우선.
if (!process.env.VITE_APP_URL && process.env.VERCEL_PROJECT_PRODUCTION_URL) {
  process.env.VITE_APP_URL = `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
}
```

- Vercel 프로젝트 Settings → Environment Variables 의 **"Automatically expose System Environment Variables"** 가
  켜져 있어야 한다(기본값 켜짐).
- Next.js 는 `next.config` 의 `env: { NEXT_PUBLIC_APP_URL: … }` 로 같은 값을 넘긴다.
- 빌드 스크립트로 값을 넣는 앱(정적 HTML 등)은 그 스크립트에서 같은 순서로 정한다 —
  `process.env.VITE_APP_URL || (process.env.VERCEL_PROJECT_PRODUCTION_URL ? "https://" + process.env.VERCEL_PROJECT_PRODUCTION_URL : "")`.
- Vercel 이 아닌 곳(Replit 등)은 `VITE_APP_URL` 을 직접 넣는다. 안 넣으면 지금 접속한 주소를 보낸다.

```ts
// src/lib/accountCenter.ts
const CENTER = (import.meta.env.VITE_ACCOUNT_CENTER_URL ?? "").replace(/\/+$/, "");
if (!CENTER) throw new Error("VITE_ACCOUNT_CENTER_URL 이 설정되지 않았습니다.");
// 돌아올 주소는 고정 주소로. 배포별 임시 주소로 접속해도 계정 센터에는 고정 주소가 전달된다.
const APP = (import.meta.env.VITE_APP_URL ?? "").replace(/\/+$/, "");

/** 계정 센터 화면 주소. 비밀번호를 바꾼 뒤 [앱으로 돌아가기] 로 이 앱에 돌아온다. */
export function accountCenterUrl(path: "reset" | "change"): string {
  const back = `${APP || window.location.origin}/`;
  return `${CENTER}/${path}?return=${encodeURIComponent(back)}`;
}
```

| 화면 | 어디에 두나 | 주소 |
|---|---|---|
| 비밀번호 찾기 · 처음 로그인 | 로그인 화면 (비밀번호 입력칸 근처) | `accountCenterUrl("reset")` |
| 비밀번호 변경 | 내 정보 / 사용자 메뉴 | `accountCenterUrl("change")` |

```tsx
<a href={accountCenterUrl("reset")}>비밀번호를 잊으셨나요? · 처음 로그인</a>
<a href={accountCenterUrl("change")}>비밀번호 변경</a>
```

- 같은 탭 이동(`<a href>`)을 쓴다. 새 창으로 열 필요 없다.
- `return` 에는 **이 앱의 https 주소**만 넣는다. 계정 센터는 https 가 아니거나 허용되지 않은 주소면
  돌아가기 버튼 대신 "사용하던 앱으로 돌아가 로그인해 주세요" 문구만 보여 준다(로컬 `http://localhost` 도 마찬가지 — 정상).
- 고정 주소가 비면(위 설정 누락) 배포별 주소로 접속했을 때 계정 센터가 그 주소를 임시 주소로 보고
  돌아가기 버튼을 보여 주지 않는다. 구현 후 빌드 결과에 고정 주소가 들어갔는지 확인한다(§10).
- 경로까지 돌아오게 하고 싶으면 `window.location.origin + 원하는 경로` 를 넣어도 된다(쿼리·해시는 버려진다).

### 5-2. 돌아가기 허용 — 앱이 할 일 없음

계정 센터는 **허용된 앱**으로만 [앱으로 돌아가기] 버튼을 보여 준다(오픈 리다이렉트 방지).

- 직원이 이 앱에서 계정 센터로 가서 **실제로 비밀번호를 바꾸면**, 이 앱 주소가 계정 센터 관리 화면
  (`/admin` → 연결된 앱)에 **승인 대기**로 자동 등록된다. 경영지원파트가 [허용] 하면 즉시 적용된다(재배포 없음).
- `*.speedrackms.kr` 주소는 자동 허용이다.
- 배포 직후부터 버튼이 필요하면 경영지원파트에 **앱 고정 주소 미리 등록**을 부탁한다.
- Vercel 배포별 주소(`<앱>-<해시>-<팀>.vercel.app`)와 브랜치 미리보기 주소(`<앱>-git-<브랜치>-<팀>.vercel.app`)는
  자동 등록도 허용도 되지 않는다. 배포할 때마다 바뀌기 때문이다.
- 앱은 Supabase Redirect URL 을 등록하지 않는다(`resetPasswordForEmail` 을 쓰지 않으므로).

### 5-3. 비밀번호가 바뀐 뒤

- 계정 센터는 변경 후 **다른 기기·다른 앱의 로그인을 끊는다.** 앱은 따로 처리할 게 없다 — 토큰 갱신이
  실패하면 `onAuthStateChange` 가 `SIGNED_OUT` 을 보내고, 앱은 로그인 화면으로 간다. 사용자는 새 비밀번호로 로그인한다.
- 사번·다우 계정이 없는 계정(외국인 근로자, 거래처 등)은 인증코드를 받을 수 없다. 화면에는 보안상 똑같이
  "보냈습니다"가 뜬다. 이런 계정은 경영지원파트가 초기화한다 — 앱에 별도 경로를 만들지 않는다.

## 6. 세션 게이트 (로그인 흐름)

### 6-1. 규칙

앱 루트에서 **한 곳에서만** 세션을 구독하고, 아래 순서로 화면을 정한다.

```
확인 중        → 스플래시
세션 없음      → 로그인 화면
비활성 계정    → 로컬 로그아웃 + "비활성화된 계정입니다. 관리자에게 문의해 주세요."
변경 필요 계정 → 로컬 로그아웃 + 계정 센터 change 로 이동   (앱 화면을 한 번도 그리지 않는다)
그 외          → 앱 화면
```

- **비활성**: `user_metadata.status` 가 있고 `"ONLINE"` 이 아니면 비활성이다. 로그인 에러 `user_banned` 도 같은 문구로 매핑한다.
  두 출처(`status`, `banned_until`)는 실제로 어긋난 계정이 있으니 **둘 다** 본다.
- **무엇을 믿는가**: 믿는 값은 `banned_until` 이다 — 차단된 계정은 Supabase 가 로그인과 토큰 갱신 자체를 거부한다.
  `user_metadata.status` 는 **막는 쪽으로만 쓰는 보조 신호**다. `user_metadata` 는 본인 세션으로 고칠 수 있어서
  (`auth.updateUser({ data })`), `status` 가 `ONLINE` 이라는 것은 통과시킬 근거가 아니다.
  그래서 `status` 가 `ONLINE` 인지로 **권한을 주거나 다른 검사를 건너뛰지 않는다.** 퇴사자를 실제로 막는 일은 다우 동기화가
  `STOP` 과 함께 차단을 거는 데 달려 있다(경영지원파트 관리).
- **변경 필요**: `app_metadata.must_change_password === true`. 이동하기 **전에 반드시
  `signOut({ scope: "local" })`** 한다. 안 하면 계정 센터에서 바꾸고 돌아와도 브라우저에 남은 옛 토큰
  (플래그 true)이 다시 읽혀 **계정 센터로 되돌아가는 루프**가 생긴다.
- **같은 사용자 재발화 무시**: 탭 포커스 복귀 때 `onAuthStateChange` 가 다시 오므로, 사용자 id 가 같으면
  세션만 갱신하고 데이터 재로딩·스플래시를 하지 않는다.
- 로그인 성공 후 직접 리다이렉트하지 않는다 — 구독이 화면을 바꾼다.

### 6-2. 참조 구현 (React)

```tsx
// src/auth/AuthProvider.tsx
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import { accountCenterUrl } from "../lib/accountCenter";

export const INACTIVE_MESSAGE = "비활성화된 계정입니다. 관리자에게 문의해 주세요.";

export const isInactive = (u: User) => {
  const status = u.user_metadata?.status;
  const bannedUntil = (u as User & { banned_until?: string }).banned_until;
  return (!!status && status !== "ONLINE") || (!!bannedUntil && Date.parse(bannedUntil) > Date.now());
};
export const mustChangePassword = (u: User) => u.app_metadata?.must_change_password === true;
export const displayName = (u: User) => u.user_metadata?.full_name || u.email?.split("@")[0] || "";

type AuthState = { loading: boolean; session: Session | null; notice: string | null };
const Ctx = createContext<AuthState>({ loading: true, session: null, notice: null });
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ loading: true, session: null, notice: null });
  const lastUserId = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;

    const apply = async (session: Session | null) => {
      if (!alive) return;
      const user = session?.user;
      if (user && isInactive(user)) {
        await supabase.auth.signOut({ scope: "local" });
        lastUserId.current = null;
        return setState({ loading: false, session: null, notice: INACTIVE_MESSAGE });
      }
      if (user && mustChangePassword(user)) {
        await supabase.auth.signOut({ scope: "local" }); // 되돌이 루프 방지 (§6-1)
        window.location.replace(accountCenterUrl("change"));
        return; // 앱 화면을 그리지 않는다 — loading 유지
      }
      const uid = user?.id ?? null;
      const sameUser = uid !== null && uid === lastUserId.current;
      lastUserId.current = uid;
      // sameUser 면 세션(토큰)만 갱신하고, 데이터 재로딩 등은 사용자 전환 때만 한다.
      setState((prev) => ({ loading: false, session, notice: sameUser ? prev.notice : null }));
    };

    supabase.auth.getSession().then(({ data }) => apply(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      // 콜백 안에서 supabase 호출을 await 하면 교착될 수 있어 다음 틱으로 넘긴다.
      setTimeout(() => apply(session), 0);
    });
    return () => {
      alive = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}
```

```tsx
// src/App.tsx
export default function App() {
  const { loading, session, notice } = useAuth();
  if (loading) return <Splash />;
  if (!session) return <Login notice={notice} />;
  return <AppScreens />;
}
```

```tsx
// 로그인 폼 핵심
const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
if (error) setError(loginErrorMessage(error));
// 성공 시 아무것도 하지 않는다 — AuthProvider 가 화면을 바꾼다.

export function loginErrorMessage(error: { code?: string; message: string }): string {
  if (error.code === "user_banned" || /banned/i.test(error.message)) return INACTIVE_MESSAGE;
  if (error.code === "invalid_credentials" || /invalid login credentials/i.test(error.message))
    return "이메일 또는 비밀번호가 올바르지 않습니다.";
  if (error.code === "email_not_confirmed" || /email not confirmed/i.test(error.message))
    return "이메일 인증이 완료되지 않았습니다. 관리자에게 문의해 주세요.";
  if (error.code === "over_request_rate_limit" || /rate limit/i.test(error.message))
    return "시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.";
  return "로그인하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}
```

- 로그아웃: `supabase.auth.signOut()`.
- 디자인은 대상 앱의 기존 톤을 따른다. 이 문서의 문구·구조만 지키면 된다.
- 회원가입 링크는 두지 않는다. 로그인 화면 안내 예: "회사 이메일로 로그인하세요. 처음이면 [처음 로그인]에서 비밀번호를 정하세요."

### 6-3. 다른 스택

- **Vue/Svelte**: 같은 로직을 전역 스토어(Pinia / writable)에 두고 루트에서 게이트.
- **Next.js**: 브라우저 전용 코드는 클라이언트 컴포넌트에, 또는 `@supabase/ssr`(쿠키) 사용. 게이트 순서는 같다.
  서버 컴포넌트·미들웨어에서도 비활성·변경 필요를 확인한다.
- **정적 페이지**: CDN 으로 `@supabase/supabase-js` 를 불러 같은 API 사용, 섹션 show/hide 로 게이트.
- 어떤 스택이든 **비밀번호를 자체 서버로 보내지 않는다** — 로그인은 supabase-js 가 Supabase Auth 와 직접 한다.

## 7. (②형태 필수) 자체 서버 API 보호

브라우저는 모든 API 호출에 `Authorization: Bearer <session.access_token>` 을 붙이고,
서버는 **모든** 데이터 라우트 앞에서 토큰을 검증한다. `ai_data_hub` 공개키(JWKS)로 서명만 확인하므로
비밀키가 필요 없다.

```ts
// server/auth/requireAuth.ts (Express 예시 — 다른 프레임워크는 요청/응답 처리만 바꾼다)
import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";
import type { Request, Response, NextFunction } from "express";

const HUB = process.env.AUTH_SUPABASE_URL;
if (!HUB) throw new Error("AUTH_SUPABASE_URL 환경변수가 설정되지 않았습니다.");
const JWKS = createRemoteJWKSet(new URL(`${HUB}/auth/v1/.well-known/jwks.json`)); // 프로세스당 1회

export interface HubUser extends JWTPayload {
  email?: string;
  user_metadata?: { status?: string; full_name?: string; org_name?: string; [k: string]: unknown };
  app_metadata?: { must_change_password?: boolean; [k: string]: unknown };
}
declare module "express-serve-static-core" {
  interface Request { user?: HubUser }
}

export async function requireAuth(req: Request, res: Response, next: NextFunction) {
  const h = req.headers.authorization;
  const token = h?.startsWith("Bearer ") ? h.slice(7) : null;
  if (!token) return res.status(401).json({ error: "로그인이 필요합니다." });
  let user: HubUser;
  try {
    ({ payload: user } = await jwtVerify<HubUser>(token, JWKS, { issuer: `${HUB}/auth/v1`, audience: "authenticated" }));
  } catch {
    return res.status(401).json({ error: "유효하지 않은 로그인입니다." });
  }
  const status = user.user_metadata?.status;
  if (status && status !== "ONLINE") return res.status(403).json({ error: "비활성화된 계정입니다." });
  if (user.app_metadata?.must_change_password === true)
    return res.status(403).json({ error: "비밀번호를 먼저 변경해 주세요." });
  req.user = user;
  next();
}
```

```ts
app.use("/api", requireAuth);                       // 공개 API 가 없으면 한 번에
app.delete("/api/items/:id", requireAdmin, remove); // 쓰기·삭제는 권한 확인 추가(§8)
```

- `jose` 설치: `npm install jose`. **회사 계정 토큰을 확인하는 데는 비밀값이 필요 없다** — 공개키(JWKS)로 충분하다.
  `ai_data_hub` 의 JWT 비밀값을 달라고 요청하지 않는다(§12). 데이터가 **다른 Supabase 프로젝트**에 있어
  그쪽 토큰을 만들어야 하는 경우만 §4-2 의 예외다.
- 토큰 속 `user_metadata.status` 는 토큰 발급 시점 값이다(최대 1시간 지연). 즉시 차단이 중요한 앱은
  서버에서 `supabase.auth.getUser(token)` 으로 한 번 더 확인한다.
- 위 `status` 검사는 막는 쪽 보조 신호다(§6-1). `user_metadata` 는 본인이 고칠 수 있으므로 **`status`·부서·사번 등
  `user_metadata` 값으로 권한을 주지 않는다**(§8). 퇴사자 차단의 근거는 Supabase 차단(`banned_until`)이다.
- **확인**: 로그인 없이 `curl -X DELETE https://<배포주소>/api/items/1` → **401** 이어야 한다.

## 8. 권한 — 사용자에게 먼저 묻기

구현 전에 아래 4개를 묻고 답에 맞춰 설계한다.

1. 로그인한 직원이면 전부 봐도 되는가, 사람/부서마다 범위가 다른가?
2. 읽기와 쓰기 권한이 다른가? (예: 요청은 누구나, 승인·삭제는 담당 부서)
3. 특별 권한의 판정 기준은? (부서 / 직책 / 개별 명단)
4. 본인이 만든 데이터만 보이면 되는가? (`user_id = auth.uid()`)

- ①형태는 **RLS 로** 막는다. 권한 구분이 없어도 RLS 는 켜고 `authenticated` 에게만 연다.
- "경영지원파트만" 이면 기존 공용 함수 `public.is_admin_user()` 를 RLS 에서 재사용한다(새로 만들지 않는다).
  JWT 이메일로 `MG_erp_user` 를 찾아 부서가 경영지원파트면 true 다(`user_metadata.org_name` 과 다를 수 있다 — ERP 기준).
  기준이 다른 부서·직책·개별 명단이면 같은 형태의 **앱 전용 `security definer` 함수**를 만들어 RLS 에서 부른다.
- 화면의 버튼 숨김은 표시용일 뿐, 실제 차단은 RLS(①) 또는 서버 검증(②)이 한다.
- 권한 판정에 `user_metadata` 를 쓰지 않는다(사용자가 스스로 고칠 수 있다). `app_metadata` · DB 함수 · 서버 명단을 쓴다.
- **관리자 명단·기준의 실제 값은 AI 가 정하지 않는다.** 자리(환경변수 이름, 함수 뼈대)만 만들고 담당자가 채우게 한다.
- 테이블·RLS·함수 생성은 공유 프로덕션 DB 변경이다. **직접 실행하지 말고** `speedrack-co/MS_supabase_schema` 에
  마이그레이션 PR 을 올린다 → 사용자가 머지. **그 저장소는 머지하면 바로 운영 DB 에 적용된다**(자동 적용) — PR 본문 맨 위에 적는다.
- 앱 데이터는 `ai_data_hub` 의 **앱 전용 스키마**에 둔다(public 에 새 테이블 금지). 사용자 참조 컬럼은 `auth.uid()`.

### 8-1. 거래처(외부 업체) 로그인

이 가이드는 **사내 계정 로그인**만 다룬다. 거래처 등 외부 사용자 로그인이 필요하면 **앱이 자체 개발·운영**한다
(계정 센터·경영지원파트는 외부 계정을 만들거나 관리하지 않는다). 사용자가 요청하지 않았으면 만들지 않는다.
만든다면 아래는 지킨다.

- **사내 로그인(`ai_data_hub` Auth)에 외부 계정을 만들지 않는다** — `signUp`, 관리자 API `createUser`, 구글 로그인 모두.
  사내 계정은 직원 권한(`authenticated`)을 받아, "로그인만 하면 누구나" 정책의 직원 데이터가 외부인에게 열린다.
- 로그인 확인은 **서버에서** 한다(브라우저 코드만으로 막지 않는다). 외부 사용자는 DB 에 직접 붙지 않는다.
- 비밀번호는 원문으로 저장하지 않는다(bcrypt·argon2 등). 로그인 시도 횟수 제한과 세션 만료를 둔다.
- 1인 1계정. 공용 계정·공용 비밀번호(핀코드 로그인)를 만들지 않는다.
- 외부 사용자는 **자기 회사 데이터만** — 서버가 세션의 값으로 걸러서 준다. 클라이언트가 보낸 회사 값은 믿지 않는다.
- 거래가 끝나면 막을 방법(잠금·삭제)이 있어야 한다. 비밀번호 찾기에 계정 센터를 쓸 수 없다(사내 계정 전용).
- 사내 로그인과 같이 쓰면 두 세션을 구분하고, 서버 API 마다 "직원만 / 외부만 / 둘 다"를 명시해 확인한다.
- 이미 외부 로그인이 있는 앱은 **그대로 둔다.** 사내 로그인으로 옮기거나 합치지 않는다.

## 9. 이미 자체 인증이 있는 앱 전환

1. **찾아서 지운다**: `signUp`, `resetPasswordForEmail`, `PASSWORD_RECOVERY` 처리, 복구 링크 진입 화면
   (`ResetPassword` 류), 앱 안의 비밀번호 변경 폼(`updateUser({ password })`), 앱 자체의 임시 비밀번호·OTP 발송 코드.
   → 로그인 화면의 링크와 사용자 메뉴의 링크를 §5-1 로 바꾼다. 지운 라우트로 들어오면 로그인 화면으로 보낸다.
2. **하드코딩된 Supabase URL·키 폴백**을 지우고 §3 환경변수만 읽게 한다. 저장소에 `service_role`·`sb_secret_` 가
   커밋돼 있으면 **지우기 전에 사용자에게 알린다** — 이력에 남으므로 키 재발급이 필요하다.
3. `detectSessionInUrl` 을 `false` 로 (구글 OAuth 를 같이 쓰면 유지).
   이미 계정 센터 링크가 있는 앱은 돌아올 주소가 `window.location.origin` 뿐인지 확인하고 §5-1 의 고정 주소 설정을 더한다.
4. 비활성 차단·변경 필요 강제(§6)가 빠져 있으면 추가한다.
   앱에 거래처 로그인이 이미 있으면 그대로 두고 사내 로그인과 합치지 않는다(§8-1).
5. ②형태인데 §7 이 없으면 추가한다 — 이번 작업의 필수 범위다.
6. **자체 사용자 테이블**(앱 DB 의 users/password 컬럼 등)로 로그인하던 앱이면 전환 방식이 크다.
   바로 바꾸지 말고 계획을 사용자에게 먼저 보여 준다: 기존 사용자 ↔ `auth.users` 매칭(이메일), 앱 테이블의
   사용자 참조를 `auth.uid()` 로 옮기기, 비밀번호 컬럼 폐기. 비밀번호는 옮기지 않는다 — 직원은 계정 센터
   [처음 로그인]으로 새로 정한다.
7. 앱 쪽 Supabase Redirect URL 설정은 건드리지 않는다(다른 앱과 공유되는 설정이다).

## 10. 확인 시나리오

구현 후 배포본(또는 프리뷰)에서 확인하고 결과를 보고한다.

- [ ] 올바른 계정으로 로그인 → 앱 화면
- [ ] 틀린 비밀번호 → "이메일 또는 비밀번호가 올바르지 않습니다."
- [ ] 비활성 계정 → 전용 문구, 앱 화면 진입 안 됨 (테스트 계정은 사용자에게 요청 — 임의로 계정 상태를 바꾸지 않는다)
- [ ] 새로고침 → 로그인 유지 / 탭을 바꿨다 돌아옴 → 스플래시로 튕기지 않음
- [ ] 로그인 화면 [비밀번호 찾기] → 계정 센터 `/reset?return=<이 앱>` 으로 이동
- [ ] 메뉴 [비밀번호 변경] → 계정 센터 `/change?return=<이 앱>` 으로 이동
- [ ] Vercel 배포별 주소(`<앱>-<해시>-<팀>.vercel.app`)로 접속해도 위 링크의 `return` 이 **고정 주소**(`https://<앱>.vercel.app/`)인지
- [ ] 계정 센터에서 변경 → (허용된 앱이면) [앱으로 돌아가기] → 새 비밀번호로 로그인
- [ ] `must_change_password` 계정 → 앱 화면 없이 계정 센터 변경 화면, 바꾸고 돌아와 로그인 → 앱 화면 (루프 없음)
- [ ] 로그아웃
- [ ] (권한 구분 앱) 권한 없는 계정으로 쓰기 시도 → 거부
- [ ] (②형태) 토큰 없이 curl 로 쓰기 API → 401
- [ ] (§4-2 토큰 교환 앱) 로그인하지 않은 시크릿 창에서 앱을 열었을 때 데이터가 하나도 안 보임 — RLS 확인
- [ ] (§4-2 토큰 교환 앱) 토큰 없이 교환 함수 호출 → 401, 아무 문자열이나 넣어 호출 → 401
- [ ] 코드 어디에도 거래처 계정을 사내 로그인에 만드는 호출(`signUp`·`auth.admin.createUser`)이 없음
- [ ] (거래처 로그인이 있는 앱) 거래처 세션으로 직원용 API 호출 → 403, 다른 거래처의 데이터 요청 → 거부
- [ ] (서버에서 로그인·세션 갱신을 하는 앱, §4-3) 다음 날 AccessHub `/apps` 에 이 앱 주소로 잡힘 — 「앱 미상 · 서버 로그인」으로 잡히면 §4-3 누락
- [ ] 빌드 결과물에 비밀값이 없음 — `service_role` · `sb_secret_` 과, 토큰 교환 앱이면 JWT 비밀값도
      (`grep -r "sb_secret_\|service_role" dist/`)

## 11. 끝나고 사용자에게 안내할 것

AI 는 작업 결과와 함께 아래를 **그대로** 사용자에게 알린다.

1. **환경변수 등록** — 배포 사이트(§2 에서 확인한 곳)의 환경변수 화면에 §3 의 변수를 넣고 **재배포**.
   publishable key 값은 경영지원파트에 요청하거나 Supabase 대시보드(Settings → API Keys)에서 확인.
   **코드가 읽는 이름을 그대로 알려 준다**(스택에 따라 `VITE_` / `NEXT_PUBLIC_` 이 다르다 — §3).
   §4-2 를 쓰는 앱이면 비밀값 전달·등록 순서(§4-2)와 "환경변수 등록 → 병합 → 배포" 순서를 같이 알린다.
2. **계정 센터 연결 승인** — "이 앱에서 처음 비밀번호를 바꾸면 계정 센터 「연결된 앱」에 승인 대기로 올라갑니다.
   경영지원파트에 허용을 부탁하세요. 배포 직후부터 [앱으로 돌아가기] 버튼이 필요하면 앱 주소
   (`https://…`) 미리 등록을 요청하세요." — 허용 전에도 로그인·비밀번호 변경은 정상 동작한다.
3. **권한 명단** — 관리자 판정 자리를 만들었다면, 채워야 할 곳(환경변수 이름/파일)을 알려 준다.
4. **DB 변경** — 마이그레이션 PR 을 올렸다면 그 링크와 "머지하면 바로 운영 DB 에 적용된다"는 점.
5. **이 앱 저장소 규칙** — 작업은 브랜치 + PR 로 올리고 머지는 담당자가 한다(main 직접 푸시 금지).

## 12. AI 금지 사항 요약

- 회원가입 · 비밀번호 찾기 · 재설정 · 변경 화면을 앱에 만들지 않는다.
- 키·URL 을 코드에 적지 않는다. `service_role`/`sb_secret_` 을 브라우저 쪽에 두지 않는다.
- `ai_data_hub` 의 JWT 비밀값·`service_role` 키를 요청하지 않는다. 로그인 확인은 공개키(JWKS)로 한다(§7).
  데이터가 다른 Supabase 프로젝트에 있어 **그쪽** 토큰을 만들어야 하는 경우만 §4-2 를 따른다.
- 계정 센터 주소를 코드에 적지 않는다.
- 거래처 등 외부 계정을 사내 로그인(`ai_data_hub`)에 만들지 않는다. 사용자가 요청하지 않은 외부 로그인을 만들지 않는다(§8-1).
- `role === "authenticated"` 로 직원 여부를 판단하지 않는다(§1).
- `user_metadata` 로 권한·강제 플래그를 판단하지 않는다.
- 관리자 기준을 임의로 정하지 않는다.
- 공유 DB 에 DDL·데이터 변경을 직접 실행하지 않는다.
- 다른 사용자의 계정 상태·비밀번호를 바꾸지 않는다(Admin API 사용 금지 — 계정 관리는 경영지원 몫).
- ②형태에서 §7 없이 "완료"라고 보고하지 않는다. §4-2 를 쓰면서 RLS 를 조이지 않고 "완료"라고 하지 않는다.

## 13. 적용 사례 (2026-09 기준)

| 앱 | 구조 | 어떻게 했나 |
|---|---|---|
| MS_FLO (`ms-flo.vercel.app`) | Vite + 자체 API 서버, 데이터 `ai_data_hub` | 자체 비밀번호 찾기·변경을 전부 걷어내고 계정 센터 링크로 교체(§9) |
| MS_device-manager | Vite, 데이터 `ai_data_hub` | 로그인 + 계정 센터 링크 |
| OS_scm (`os-scm.vercel.app`) | 빌드 스크립트 + 정적 앱 + Vercel 함수, 데이터는 **다른 Supabase 프로젝트** | §4-2 토큰 교환. 관리자 구분은 교환 토큰의 email 기준. 비밀값은 담당 부서 → 경영지원 전달 후 등록 |
| LG_S-POMS (`lg-s-poms.vercel.app`) | Vite + Express(Vercel 함수), 거래처 사용 | 거래처 로그인은 앱 자체 방식 유지(§8-1). 직원 로그인·API 보호(§7) 적용 예정 |

- 처음 두 앱은 고정 주소 설정(§5-1)이 나오기 전에 적용해서, 배포별 임시 주소로 접속하면 돌아가기 버튼이 안 뜬다.
  §9-3 대로 한 줄을 더하면 해결된다.
- 새 앱은 이 표를 참고만 하고, 구조 판별(§2)부터 자기 앱 기준으로 다시 한다.

## 14. 경영지원파트 체크리스트 (앱 담당자용 아님)

1. 배포 플랫폼에 환경변수 등록 — 앱이 읽는 **이름**을 먼저 확인(§3). 값은 코드·PR·채팅에 남기지 않는다.
2. §4-2 앱이면 비밀값을 사내 메신저로 받아 Sensitive 로 등록하고, 받은 메시지는 지운다.
   등록은 Production/Preview 에만 한다.
3. 환경변수 등록이 끝난 뒤 병합·배포한다.
4. 앱이 처음 쓰이면 계정 센터 `/admin` → 연결된 앱에 **승인 대기**로 올라온다 → 주소를 확인하고 [허용].
   모르는 주소는 [차단]. Vercel 배포별 임시 주소는 올라오지 않는다(정상).
5. 앱마다 이름·메모(담당자, 저장소)를 적어 두면 나중에 누가 쓰는 앱인지 찾기 쉽다.
6. 거래처 등 외부 계정은 **관리하지 않는다** — 필요한 앱이 자체 개발·운영한다(§8-1).
   사내 로그인(`ai_data_hub`)에 외부 계정이 생기지 않았는지만 가끔 확인한다(사번 없는 계정·회사 외 메일).
