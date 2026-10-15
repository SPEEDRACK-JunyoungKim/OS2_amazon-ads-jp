"""아마존 광고 API (일본) 연결 모듈 — 0~1단계용
- 토큰 발급, 프로필 조회
- SP 캠페인 / 키워드 / 타겟 읽기·수정
- 캠페인 리포트(비동기) 받기
"""
import gzip
import json
import os
import time

import requests

try:   # 로컬 실행용: .env 파일이 있으면 읽음 (레플릿 Secrets에는 영향 없음)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN_URL = "https://api.amazon.co.jp/auth/o2/token"      # 극동(일본) 토큰 주소
API_BASE = "https://advertising-api-fe.amazon.com"       # 극동(일본) 광고 API 주소

SP_CAMP = "application/vnd.spCampaign.v3+json"
SP_KW = "application/vnd.spKeyword.v3+json"
SP_TGT = "application/vnd.spTargetingClause.v3+json"
REPORT = "application/vnd.createasyncreportrequest.v3+json"


class AdsAPI:
    def __init__(self):
        try:
            self.client_id = os.environ["ADS_CLIENT_ID"]
            self.client_secret = os.environ["ADS_CLIENT_SECRET"]
            self.refresh_token = os.environ["ADS_REFRESH_TOKEN"]
        except KeyError as e:
            raise SystemExit(f"Secrets에 {e.args[0]} 가 없습니다. 자물쇠(Secrets) 메뉴에서 넣어주세요.")
        self.profile_id = os.environ.get("ADS_PROFILE_ID")
        self._token = None
        self._exp = 0

    # ---------- 기본 ----------
    def token(self):
        if self._token and time.time() < self._exp - 60:
            return self._token
        r = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }, timeout=30)
        if r.status_code != 200:
            raise SystemExit(f"토큰 발급 실패 ({r.status_code}): {r.text[:300]}")
        j = r.json()
        self._token = j["access_token"]
        self._exp = time.time() + int(j.get("expires_in", 3600))
        return self._token

    def _headers(self, ctype=None, accept=None, scope=True):
        h = {
            "Authorization": f"Bearer {self.token()}",
            "Amazon-Advertising-API-ClientId": self.client_id,
        }
        if scope:
            if not self.profile_id:
                raise SystemExit("Secrets에 ADS_PROFILE_ID 가 없습니다. 먼저 `python main.py check` 로 일본 프로필 ID를 확인하세요.")
            h["Amazon-Advertising-API-Scope"] = str(self.profile_id)
        if ctype:
            h["Content-Type"] = ctype
        if accept:
            h["Accept"] = accept
        return h

    def request(self, method, path, ctype=None, accept=None, body=None, scope=True):
        last = None
        for attempt in range(6):
            r = requests.request(
                method, API_BASE + path,
                headers=self._headers(ctype, accept, scope),
                data=json.dumps(body) if body is not None else None,
                timeout=60,
            )
            if r.status_code == 429 or r.status_code >= 500:   # 너무 자주 부름 / 아마존 쪽 오류 → 잠깐 쉬고 재시도
                try:
                    wait = int(r.headers.get("Retry-After", 2 ** attempt))
                except ValueError:
                    wait = 2 ** attempt
                last = f"{r.status_code}: {r.text[:200]}"
                time.sleep(min(wait, 60))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {path} 실패 ({r.status_code}): {r.text[:500]}")
            return r.json() if r.text else {}
        raise RuntimeError(f"{method} {path} 재시도 초과 — 마지막 응답 {last}")

    # ---------- 프로필 ----------
    def profiles(self):
        return self.request("GET", "/v2/profiles", scope=False)

    # ---------- 공통: 목록 페이지 넘기기 ----------
    def _list_all(self, path, ctype, key, body):
        out, token = [], None
        while True:
            b = dict(body)
            if token:
                b["nextToken"] = token
            j = self.request("POST", path, ctype, ctype, b)
            out += j.get(key, [])
            token = j.get("nextToken")
            if not token:
                return out

    @staticmethod
    def _check_update(j, key):
        res = j.get(key, {})
        errors = res.get("error", []) if isinstance(res, dict) else []
        if errors:
            raise RuntimeError(f"수정 거부됨: {json.dumps(errors, ensure_ascii=False)[:600]}")
        return res

    # ---------- 캠페인 ----------
    def list_campaigns(self, states=("ENABLED", "PAUSED")):
        return self._list_all("/sp/campaigns/list", SP_CAMP, "campaigns",
                              {"stateFilter": {"include": list(states)}, "maxResults": 1000})

    def get_campaign(self, campaign_id):
        c = self._list_all("/sp/campaigns/list", SP_CAMP, "campaigns",
                           {"campaignIdFilter": {"include": [str(campaign_id)]}})
        if not c:
            raise SystemExit(f"캠페인 {campaign_id} 를 찾을 수 없습니다.")
        return c[0]

    def update_campaigns(self, items):
        j = self.request("PUT", "/sp/campaigns", SP_CAMP, SP_CAMP, {"campaigns": items})
        return self._check_update(j, "campaigns")

    # ---------- 키워드 ----------
    def list_keywords(self, campaign_id):
        return self._list_all("/sp/keywords/list", SP_KW, "keywords", {
            "campaignIdFilter": {"include": [str(campaign_id)]},
            "stateFilter": {"include": ["ENABLED"]},
            "maxResults": 1000,
        })

    def get_keyword(self, keyword_id):
        k = self._list_all("/sp/keywords/list", SP_KW, "keywords",
                           {"keywordIdFilter": {"include": [str(keyword_id)]}})
        return k[0] if k else None

    def update_keywords(self, items):
        j = self.request("PUT", "/sp/keywords", SP_KW, SP_KW, {"keywords": items})
        return self._check_update(j, "keywords")

    # ---------- 타겟 (오토/ASIN/카테고리) ----------
    def list_targets(self, campaign_id):
        return self._list_all("/sp/targets/list", SP_TGT, "targetingClauses", {
            "campaignIdFilter": {"include": [str(campaign_id)]},
            "stateFilter": {"include": ["ENABLED"]},
            "maxResults": 1000,
        })

    def get_target(self, target_id):
        t = self._list_all("/sp/targets/list", SP_TGT, "targetingClauses",
                           {"targetIdFilter": {"include": [str(target_id)]}})
        return t[0] if t else None

    def update_targets(self, items):
        j = self.request("PUT", "/sp/targets", SP_TGT, SP_TGT, {"targetingClauses": items})
        return self._check_update(j, "targetingClauses")

    # ---------- 리포트 ----------
    def campaign_report(self, start, end):
        """start~end(YYYY-MM-DD, 최대 31일) 캠페인별 합계. 보통 1~10분 걸림."""
        body = {
            "name": f"campaigns {start}~{end}",
            "startDate": start,
            "endDate": end,
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["campaign"],
                "columns": ["campaignId", "campaignName", "campaignStatus", "campaignBudgetAmount",
                            "impressions", "clicks", "cost", "sales14d", "purchases14d"],
                "reportTypeId": "spCampaigns",
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
            },
        }
        try:
            report_id = self.request("POST", "/reporting/reports", REPORT, REPORT, body)["reportId"]
        except RuntimeError as e:   # 같은 리포트를 방금 요청했으면 기존 ID를 재사용
            msg = str(e)
            if "duplicate" in msg.lower() and ":" in msg:
                report_id = msg.split("duplicate of :")[-1].split('"')[0].strip()
            else:
                raise
        print(f"  리포트 요청됨 ({report_id}) — 아마존이 만드는 중, 기다리는 중...")
        for _ in range(120):   # 최대 약 20분
            j = self.request("GET", f"/reporting/reports/{report_id}", REPORT, REPORT)
            status = j.get("status")
            if status == "COMPLETED":
                raw = requests.get(j["url"], timeout=120).content
                return json.loads(gzip.decompress(raw))
            if status == "FAILED":
                raise RuntimeError(f"리포트 실패: {j.get('failureReason')}")
            time.sleep(10)
        raise RuntimeError("리포트가 20분 안에 안 나왔습니다. 잠시 뒤 다시 실행하세요.")
