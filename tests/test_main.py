"""아마존에 연결하지 않고 가짜 광고 데이터(FakeAPI)로 main.py 흐름을 확인하는 테스트.

실행: pytest -v
"""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main  # noqa: E402

CID = "111"


class FakeAPI:
    """AdsAPI와 같은 메서드를 가진 메모리 속 가짜 광고 계정"""

    def __init__(self):
        self.profile_id = "999"
        self.campaigns = {
            CID: {"campaignId": CID, "name": "테스트캠페인", "state": "ENABLED", "targetingType": "MANUAL",
                  "budget": {"budget": 1000.0, "budgetType": "DAILY"},
                  "dynamicBidding": {"strategy": "LEGACY_FOR_SALES",
                                     "placementBidding": [{"placement": "PLACEMENT_TOP", "percentage": 20},
                                                          {"placement": "PLACEMENT_PRODUCT_PAGE", "percentage": 5}]}},
            "222": {"campaignId": "222", "name": "잘팔림", "state": "ENABLED", "targetingType": "AUTO",
                    "budget": {"budget": 500.0, "budgetType": "DAILY"}, "dynamicBidding": {}},
        }
        self.keywords = {"k1": {"keywordId": "k1", "campaignId": CID, "keywordText": "水筒",
                                "matchType": "EXACT", "bid": 30.0}}
        self.targets = {}
        self.report_rows = [
            {"campaignId": CID, "cost": 5000, "sales14d": 0, "purchases14d": 0},
            {"campaignId": "222", "cost": 1000, "sales14d": 10000, "purchases14d": 5},
        ]
        self.fail_on = None   # 예: "update_campaigns" → 그 호출에서 오류 발생시킴

    def token(self):
        return "fake"

    def profiles(self):
        return [{"profileId": 999, "countryCode": "JP", "accountInfo": {"name": "샵", "type": "seller"}}]

    def list_campaigns(self, states=("ENABLED", "PAUSED")):
        return [copy.deepcopy(c) for c in self.campaigns.values() if c["state"] in states]

    def get_campaign(self, cid):
        return copy.deepcopy(self.campaigns[str(cid)])

    def update_campaigns(self, items):
        if self.fail_on == "update_campaigns":
            raise RuntimeError("가짜 아마존 오류")
        for it in items:
            c = self.campaigns[it["campaignId"]]
            if "budget" in it:
                c["budget"] = dict(it["budget"])
            if "dynamicBidding" in it:
                c["dynamicBidding"] = copy.deepcopy(it["dynamicBidding"])

    def list_keywords(self, cid):
        return [dict(k) for k in self.keywords.values() if k["campaignId"] == str(cid)]

    def get_keyword(self, kid):
        return dict(self.keywords[kid]) if kid in self.keywords else None

    def update_keywords(self, items):
        for it in items:
            self.keywords[it["keywordId"]]["bid"] = it["bid"]

    def list_targets(self, cid):
        return [dict(t) for t in self.targets.values() if t["campaignId"] == str(cid)]

    def get_target(self, tid):
        return dict(self.targets[tid]) if tid in self.targets else None

    def update_targets(self, items):
        for it in items:
            self.targets[it["targetId"]]["bid"] = it["bid"]

    def campaign_report(self, start, end):
        return self.report_rows


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)   # logs/, backups/ 를 임시 폴더에 만듦
    os.makedirs("logs")
    os.makedirs("backups")
    return FakeAPI()


def answers(monkeypatch, *replies):
    it = iter(replies)
    monkeypatch.setattr("builtins.input", lambda *_: next(it))


def snapshot(api):
    c = api.campaigns[CID]
    return c["budget"]["budget"], main.top_pct(c), api.keywords["k1"]["bid"]


# ---------------------------------------------------------------- 읽기 전용
def test_check_reads_only(api, capsys):
    before = copy.deepcopy(api.campaigns)
    main.cmd_check(api)
    out = capsys.readouterr().out
    assert "← 일본" in out and "연결 정상" in out
    assert api.campaigns == before


def test_candidates_picks_no_order_campaign(api):
    main.cmd_candidates(api)
    with open("logs/candidates.csv", encoding="utf-8-sig") as f:
        text = f.read()
    assert "테스트캠페인" in text and "잘팔림" not in text


# ---------------------------------------------------------------- 쓰기 테스트
def test_dyn_with_top_keeps_other_placements():
    out = main.dyn_with_top(FakeAPI().campaigns[CID], 21)
    assert {"placement": "PLACEMENT_PRODUCT_PAGE", "percentage": 5} in out["placementBidding"]
    assert {"placement": "PLACEMENT_TOP", "percentage": 21} in out["placementBidding"]
    assert out["strategy"] == "LEGACY_FOR_SALES"


def test_cancel_changes_nothing(api, monkeypatch):
    before = snapshot(api)
    answers(monkeypatch, "n")
    main.cmd_test(api, CID)
    assert snapshot(api) == before


def test_change_then_restore(api, monkeypatch):
    before = snapshot(api)
    seen = {}

    def reply(prompt=""):
        if "진행" in prompt:
            return "y"
        seen["during"] = snapshot(api)   # 엔터 누르기 직전 = 바뀐 상태
        return ""

    monkeypatch.setattr("builtins.input", reply)
    main.cmd_test(api, CID)
    assert seen["during"] == (999.0, 21, 29.0)
    assert snapshot(api) == before
    assert len(os.listdir("backups")) == 1


def test_restore_skips_if_someone_else_changed(api, monkeypatch):
    def reply(prompt=""):
        if "진행" in prompt:
            return "y"
        api.campaigns[CID]["budget"]["budget"] = 1500.0   # 그 사이 헬리움이 예산 변경
        return ""

    monkeypatch.setattr("builtins.input", reply)
    main.cmd_test(api, CID)
    assert api.campaigns[CID]["budget"]["budget"] == 1500.0   # 덮어쓰지 않음
    assert api.keywords["k1"]["bid"] == 30.0                  # 나머지는 원복


def test_forced_rollback_overwrites(api, monkeypatch):
    answers(monkeypatch, "y", "")
    main.cmd_test(api, CID)
    path = os.path.join("backups", os.listdir("backups")[0])
    api.campaigns[CID]["budget"]["budget"] = 1500.0           # 사람이 나중에 바꾼 값
    answers(monkeypatch, "y")
    main.cmd_rollback(api, path)
    assert api.campaigns[CID]["budget"]["budget"] == 1000.0   # 강제 원복은 덮어씀 (주의!)


# ---------------------------------------------------------------- 알려진 문제 (아직 안 고침)
@pytest.mark.xfail(strict=True, reason="알려진 문제: 백업이 변경 '후'에 저장됨")
def test_backup_exists_even_if_change_fails(api, monkeypatch):
    api.fail_on = "update_campaigns"   # 입찰가는 바뀐 뒤 예산 변경에서 오류
    answers(monkeypatch, "y", "")
    with pytest.raises(RuntimeError):
        main.cmd_test(api, CID)
    assert os.listdir("backups"), "입찰가는 이미 바뀌었는데 백업 파일이 없음"


@pytest.mark.xfail(strict=True, reason="알려진 문제: 중간 오류 시 자동 원복 없음")
def test_auto_restore_on_failure(api, monkeypatch):
    api.fail_on = "update_campaigns"
    answers(monkeypatch, "y", "")
    with pytest.raises(RuntimeError):
        main.cmd_test(api, CID)
    assert api.keywords["k1"]["bid"] == 30.0, "입찰가가 바뀐 채로 남음"


@pytest.mark.xfail(strict=True, reason="알려진 문제: 원복 후 실제 값을 다시 읽어 확인하지 않음")
def test_restore_verifies_result(api, monkeypatch):
    answers(monkeypatch, "y", "")
    original_update = api.update_keywords
    calls = {"n": 0}

    def flaky(items):   # 원복 요청을 아마존이 조용히 무시한 상황
        calls["n"] += 1
        if calls["n"] == 1:
            original_update(items)

    api.update_keywords = flaky
    main.cmd_test(api, CID)
    with open("logs/changes.csv", encoding="utf-8-sig") as f:
        last_bid_row = [r for r in f if "원복" in r and "입찰가" in r][-1]
    assert "OK" not in last_bid_row, "실제론 원복 안 됐는데 OK로 기록됨"
