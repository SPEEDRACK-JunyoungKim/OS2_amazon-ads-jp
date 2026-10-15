"""아마존 광고 API 테스트 (0~1단계)

python main.py check                 연결 확인 + 일본 프로필 ID 찾기 (읽기만)
python main.py candidates            최근 30일 '안 팔리는데 돈 쓰는' 캠페인 후보 뽑기 (읽기만)
python main.py test <캠페인ID>        쓰기 테스트: 입찰가·예산·검색상단% 를 아주 조금 바꿨다가 원복
python main.py rollback <백업파일>    백업 파일 기준으로 전부 원래 값으로 되돌리기
"""
import csv
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ads_api import AdsAPI

JST = ZoneInfo("Asia/Tokyo")
os.makedirs("logs", exist_ok=True)
os.makedirs("backups", exist_ok=True)
LOG_FILE = "logs/changes.csv"

MIN_BID = 2      # 일본 최소 입찰가(엔)
MIN_BUDGET = 100  # 일본 최소 일 예산(엔)


def now():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def log(stage, kind, campaign, target_id, target_name, before, after, result):
    new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["시각(JST)", "단계", "종류", "캠페인", "대상ID", "대상", "전", "후", "결과"])
        w.writerow([now(), stage, kind, campaign, target_id, target_name, before, after, result])


def top_pct(campaign):
    for p in (campaign.get("dynamicBidding") or {}).get("placementBidding", []):
        if p.get("placement") == "PLACEMENT_TOP":
            return int(p.get("percentage", 0))
    return 0


def dyn_with_top(campaign, pct):
    """기존 게재위치 설정은 그대로 두고 검색 상단 %만 바꾼 설정을 만든다"""
    dyn = dict(campaign.get("dynamicBidding") or {})
    places = [dict(p) for p in dyn.get("placementBidding", []) if p.get("placement") != "PLACEMENT_TOP"]
    places.append({"placement": "PLACEMENT_TOP", "percentage": int(pct)})
    out = {"placementBidding": places}
    if dyn.get("strategy"):
        out["strategy"] = dyn["strategy"]
    return out


# ---------------------------------------------------------------- check
def cmd_check(api):
    print("1) 토큰 발급...", end=" ")
    api.token()
    print("OK")
    print("2) 프로필 목록")
    for p in api.profiles():
        acc = p.get("accountInfo", {})
        mark = "  ← 일본" if p.get("countryCode") == "JP" else ""
        print(f"   프로필ID {p['profileId']} | {p.get('countryCode')} | {acc.get('name')} | {acc.get('type')}{mark}")
    if not api.profile_id:
        print("\n→ 위에서 '일본' 프로필ID를 Secrets의 ADS_PROFILE_ID 로 넣고 다시 check 하세요.")
        return
    print(f"3) 캠페인 읽기 (프로필 {api.profile_id})...")
    camps = api.list_campaigns()
    on = [c for c in camps if c["state"] == "ENABLED"]
    print(f"   전체 {len(camps)}개 / 켜짐 {len(on)}개 / 꺼짐 {len(camps) - len(on)}개")
    for c in on[:5]:
        print(f"   예) {c['name']} | 예산 {c['budget']['budget']}엔 | 검색상단 {top_pct(c)}%")
    print("\n연결 정상. 다음: python main.py candidates")


# ---------------------------------------------------------------- candidates
def cmd_candidates(api):
    end = (datetime.now(JST) - timedelta(days=1)).date()
    start = end - timedelta(days=29)
    print(f"최근 30일({start}~{end}) 캠페인 성과 받는 중...")
    rows = api.campaign_report(str(start), str(end))
    camps = {str(c["campaignId"]): c for c in api.list_campaigns(states=("ENABLED",))}

    cands = []
    for r in rows:
        cid = str(r.get("campaignId"))
        if cid not in camps:
            continue
        cost = float(r.get("cost") or 0)
        sales = float(r.get("sales14d") or 0)
        orders = int(r.get("purchases14d") or 0)
        if cost <= 0:
            continue
        acos = cost / sales * 100 if sales else None
        if orders == 0 or (acos and acos >= 50):
            c = camps[cid]
            cands.append({
                "캠페인ID": cid, "캠페인": c["name"], "방식": c.get("targetingType"),
                "30일 비용": round(cost), "30일 매출": round(sales), "주문": orders,
                "ACOS%": round(acos, 1) if acos else "매출없음",
                "일예산": c["budget"]["budget"], "검색상단%": top_pct(c),
            })
    cands.sort(key=lambda x: (x["주문"], -x["30일 비용"]))
    path = "logs/candidates.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        if cands:
            w = csv.DictWriter(f, fieldnames=list(cands[0].keys()))
            w.writeheader()
            w.writerows(cands)
    print(f"\n후보 {len(cands)}개 (주문 적고 비용 큰 순) — 전체는 {path}")
    for x in cands[:10]:
        print(f"  {x['캠페인ID']} | {x['캠페인']} | {x['방식']} | 비용 {x['30일 비용']}엔 | 매출 {x['30일 매출']}엔 | ACOS {x['ACOS%']}")
    print("\n다음: python main.py test <캠페인ID>  (가능하면 방식이 MANUAL인 것)")


# ---------------------------------------------------------------- test
def cmd_test(api, campaign_id):
    camp = api.get_campaign(campaign_id)
    name = camp["name"]
    print(f"테스트 캠페인: {name} ({campaign_id}) / 상태 {camp['state']}")

    # 바꿀 대상 1개: 입찰가가 직접 들어간 키워드 → 없으면 타겟
    target = None
    kws = [k for k in api.list_keywords(campaign_id) if k.get("bid") is not None]
    if kws:
        k = kws[0]
        target = {"type": "keyword", "id": str(k["keywordId"]), "name": f"{k['keywordText']} ({k['matchType']})", "bid": float(k["bid"])}
    else:
        tg = [t for t in api.list_targets(campaign_id) if t.get("bid") is not None]
        if tg:
            t = tg[0]
            expr = t.get("expression") or [{}]
            target = {"type": "target", "id": str(t["targetId"]), "name": f"타겟 {expr[0].get('type')} {expr[0].get('value', '')}", "bid": float(t["bid"])}

    budget = float(camp["budget"]["budget"])
    top = top_pct(camp)
    plan = []
    if target:
        new_bid = target["bid"] - 1 if target["bid"] - 1 >= MIN_BID else target["bid"] + 1
        plan.append(("입찰가", target["name"], target["bid"], new_bid))
    else:
        print("  (입찰가가 직접 들어간 키워드/타겟이 없어 입찰가 테스트는 건너뜀)")
    new_budget = budget - 1 if budget - 1 >= MIN_BUDGET else budget + 1
    plan.append(("일예산", name, budget, new_budget))
    plan.append(("검색상단%", name, top, top + 1 if top < 900 else top - 1))

    print("\n[계획] 아래를 1씩만 바꿨다가, 확인 후 원래대로 되돌립니다.")
    for kind, tname, b, a in plan:
        print(f"  - {kind}: {tname} | {b} → {a}")
    if input("\n진행할까요? (y 입력): ").strip().lower() != "y":
        print("취소했습니다.")
        return

    # 백업
    stamp = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    backup = {"campaignId": str(campaign_id), "campaignName": name, "time": now(),
              "budget": budget, "budgetType": camp["budget"].get("budgetType", "DAILY"),
              "dynamicBidding": camp.get("dynamicBidding"), "target": target, "after": {}}
    bpath = f"backups/backup_{stamp}_{campaign_id}.json"

    # 실행
    print("\n[실행]")
    if target:
        new_bid = plan[0][3]
        if target["type"] == "keyword":
            api.update_keywords([{"keywordId": target["id"], "bid": new_bid}])
            got = float(api.get_keyword(target["id"])["bid"])
        else:
            api.update_targets([{"targetId": target["id"], "bid": new_bid}])
            got = float(api.get_target(target["id"])["bid"])
        ok = got == new_bid
        backup["after"]["bid"] = new_bid
        log("테스트변경", "입찰가", name, target["id"], target["name"], target["bid"], new_bid, "확인OK" if ok else f"불일치(읽은값 {got})")
        print(f"  입찰가 {target['bid']} → {new_bid} : {'OK' if ok else f'확인 필요(읽은 값 {got})'}")

    api.update_campaigns([{"campaignId": str(campaign_id), "budget": {"budget": new_budget, "budgetType": backup["budgetType"]}}])
    got = float(api.get_campaign(campaign_id)["budget"]["budget"])
    backup["after"]["budget"] = new_budget
    log("테스트변경", "일예산", name, campaign_id, name, budget, new_budget, "확인OK" if got == new_budget else f"불일치(읽은값 {got})")
    print(f"  일예산 {budget} → {new_budget} : {'OK' if got == new_budget else f'확인 필요(읽은 값 {got})'}")

    new_top = plan[-1][3]
    api.update_campaigns([{"campaignId": str(campaign_id), "dynamicBidding": dyn_with_top(camp, new_top)}])
    got = top_pct(api.get_campaign(campaign_id))
    backup["after"]["top"] = new_top
    log("테스트변경", "검색상단%", name, campaign_id, name, top, new_top, "확인OK" if got == new_top else f"불일치(읽은값 {got})")
    print(f"  검색상단 {top}% → {new_top}% : {'OK' if got == new_top else f'확인 필요(읽은 값 {got})'}")

    with open(bpath, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"\n백업 저장: {bpath}")
    print("→ 지금 광고 콘솔에서 이 캠페인을 열어 값이 바뀌었는지 눈으로 확인하세요.")
    input("확인했으면 엔터 → 원래 값으로 되돌립니다: ")
    restore(api, backup, only_if_unchanged=True)


# ---------------------------------------------------------------- restore
def restore(api, b, only_if_unchanged):
    """only_if_unchanged=True 이면, 그 사이 다른 쪽(헬리움 등)이 값을 바꿨을 때는 덮어쓰지 않고 경고만"""
    cid, name, after = b["campaignId"], b["campaignName"], b.get("after", {})
    print("\n[원복]")
    t = b.get("target")
    if t and "bid" in after:
        cur = api.get_keyword(t["id"]) if t["type"] == "keyword" else api.get_target(t["id"])
        cur_bid = float(cur["bid"]) if cur else None
        if only_if_unchanged and cur_bid != after["bid"]:
            msg = f"건너뜀 — 현재 {cur_bid} (다른 곳에서 바뀜, 직접 확인 필요)"
        else:
            if t["type"] == "keyword":
                api.update_keywords([{"keywordId": t["id"], "bid": t["bid"]}])
            else:
                api.update_targets([{"targetId": t["id"], "bid": t["bid"]}])
            msg = "OK"
        log("원복", "입찰가", name, t["id"], t["name"], cur_bid, t["bid"], msg)
        print(f"  입찰가 → {t['bid']} : {msg}")

    camp = api.get_campaign(cid)
    if "budget" in after:
        cur = float(camp["budget"]["budget"])
        if only_if_unchanged and cur != after["budget"]:
            msg = f"건너뜀 — 현재 {cur} (다른 곳에서 바뀜, 직접 확인 필요)"
        else:
            api.update_campaigns([{"campaignId": cid, "budget": {"budget": b["budget"], "budgetType": b["budgetType"]}}])
            msg = "OK"
        log("원복", "일예산", name, cid, name, cur, b["budget"], msg)
        print(f"  일예산 → {b['budget']} : {msg}")

    if "top" in after:
        camp = api.get_campaign(cid)
        cur = top_pct(camp)
        orig = top_pct({"dynamicBidding": b.get("dynamicBidding")})
        if only_if_unchanged and cur != after["top"]:
            msg = f"건너뜀 — 현재 {cur}% (다른 곳에서 바뀜, 직접 확인 필요)"
        else:
            api.update_campaigns([{"campaignId": cid, "dynamicBidding": dyn_with_top(camp, orig)}])
            msg = "OK"
        log("원복", "검색상단%", name, cid, name, cur, orig, msg)
        print(f"  검색상단 → {orig}% : {msg}")
    print(f"\n끝. 기록은 {LOG_FILE}")


def cmd_rollback(api, path):
    with open(path, encoding="utf-8") as f:
        b = json.load(f)
    print(f"{b['campaignName']} 을 {b['time']} 이전 값으로 되돌립니다 (현재 값과 상관없이 강제).")
    if input("진행할까요? (y 입력): ").strip().lower() == "y":
        restore(api, b, only_if_unchanged=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit()
    api = AdsAPI()
    cmd = sys.argv[1]
    if cmd == "check":
        cmd_check(api)
    elif cmd == "candidates":
        cmd_candidates(api)
    elif cmd == "test" and len(sys.argv) > 2:
        cmd_test(api, sys.argv[2])
    elif cmd == "rollback" and len(sys.argv) > 2:
        cmd_rollback(api, sys.argv[2])
    else:
        print(__doc__)
