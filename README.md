# 아마존 광고 에이전트 테스트 (일본 SP)

아마존 광고 API(일본)에 연결해 Sponsored Products 캠페인을 읽고, 성과가 나쁜 캠페인 후보를 뽑고,
입찰가·예산·검색상단%를 아주 조금 바꿨다가 원복하는 쓰기 테스트를 하는 Python 도구입니다.

- 담당자: SPEEDRACK-JunyoungKim
- 배포: Replit (예정)
- DB: 없음 (Supabase 미사용, 결과는 로컬 `logs/` · `backups/` 파일)
- 상태: 개발중


## 1. 레플릿 준비
1. 레플릿에서 새 프로젝트 만들기 → 템플릿은 **Python**
2. 파일 2개 올리기: `ads_api.py`, `main.py` (기본으로 생긴 main.py는 이걸로 덮어쓰기)
3. 왼쪽 **Secrets(자물쇠)** 메뉴에 아래 값 넣기

| 이름 | 값 |
|---|---|
| ADS_CLIENT_ID | 광고 API 클라이언트 ID |
| ADS_CLIENT_SECRET | 광고 API 클라이언트 시크릿 |
| ADS_REFRESH_TOKEN | 리프레시 토큰 |
| ADS_PROFILE_ID | 처음엔 비워두기 → 1단계에서 확인 |

## 2. 실행 (Shell 탭에서 한 줄씩)

**① 연결 확인** — 아무것도 안 바꿈
```
python main.py check
```
나오는 목록에서 "← 일본" 표시된 프로필ID를 Secrets의 ADS_PROFILE_ID 에 넣고 한 번 더 실행.

**② 쓰레기 캠페인 후보 뽑기** — 아무것도 안 바꿈, 1~10분 걸림
```
python main.py candidates
```

**③ 쓰기 테스트**
```
python main.py test 캠페인ID
```
- 입찰가 1엔, 예산 1엔, 검색상단 1%만 바꿈 → 콘솔에서 눈으로 확인 → 엔터 치면 원래대로 되돌림
- 그 사이 헬리움 등이 값을 바꿨으면 덮어쓰지 않고 "건너뜀"으로 알려줌

**④ 문제 생겼을 때 강제 원복**
```
python main.py rollback backups/백업파일이름.json
```

## 3. 로컬(내 PC)에서 실행

```
git clone <이 저장소 주소>
cd amazon-ads-jp
python -m venv .venv
source .venv/bin/activate        # 윈도우: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

**아마존 연결 없이 테스트** (가짜 데이터, 실제 광고 안 건드림)
```
pytest -v
```
- `passed` = 정상 동작 확인
- `xfailed` = **아직 안 고친 알려진 문제** (아래 참고). 고치면 이 테스트가 통과로 바뀜

**실제 연결** — `.env.example`을 `.env`로 복사해서 키를 채운 뒤 위 2번과 같은 명령 실행.
`.env`는 `.gitignore`에 있어서 깃허브에 올라가지 않음.

## 4. 알려진 문제 — 고치기 전엔 `test` / 강제 `rollback` 실행 금지
- 백업이 값을 **바꾼 뒤에** 저장됨 → 중간 오류 시 백업 없이 일부만 바뀔 수 있음
- 중간에 오류/종료되면 **자동 원복 없음**
- 원복 후 실제 값을 다시 읽어 **확인하지 않고** `OK` 출력
- 강제 `rollback`은 헬리움·사람이 나중에 바꾼 값까지 덮어씀

## 5. 기록
- `logs/changes.csv` : 언제 무엇을 몇에서 몇으로 바꿨는지 전부
- `backups/` : 바꾸기 전 값
