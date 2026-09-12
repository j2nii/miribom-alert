"""data/mock/*.json 9종을 생성한다. 거제시 기준, 값은 가짜지만 자릿수·날짜범위·항목수는 실제와 유사하게 맞춘다.

실데이터가 도착하면 이 스크립트는 버리고 data/prod/로 교체한다.

사용법:
    python scripts/gen_mock.py
"""

import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mock"
random.seed(20260912)

REGION = {"code": "48310", "name": "거제시"}
TODAY = date(2026, 9, 12)
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

DATALAB = {
    "name": "한국관광 데이터랩 지역별 방문자 통계",
    "provider": "한국관광공사",
    "retrieved_at": "2026-09-12",
    "url": "https://datalab.visitkorea.or.kr/",
}
TELECOM = {
    "name": "이동통신 기반 유동인구",
    "provider": "한국관광공사(통신사 제휴 데이터)",
    "retrieved_at": "2026-09-12",
    "note": "관광 데이터랩 제공 가공 지표",
}
CARD = {
    "name": "신용카드 가맹점 소비 통계",
    "provider": "한국관광공사(카드사 제휴 데이터)",
    "retrieved_at": "2026-09-12",
}
YOUTUBE = {
    "name": "YouTube Data API v3",
    "provider": "Google",
    "retrieved_at": "2026-09-12",
    "note": "'거제' 검색 결과 중 최근 90일 업로드 영상",
}
MANUAL_SRC = {
    "name": "지속가능한 관광지 혼잡도 운영 관리 매뉴얼",
    "provider": "한국관광공사",
    "retrieved_at": "2026-09-12",
    "url": "https://datalab.visitkorea.or.kr/site/portal/ex/bbs/View.do?cbIdx=1603&bcIdx=310400",
}

MOCK_CAVEAT = "목업 데이터임 — 실데이터 도착 시 전량 교체 대상. 수치로 판단하지 말 것."


def envelope(source, start, end, caveat, granularity="일"):
    return {
        "_mock": True,
        "generated_at": "2026-09-12T13:00:00+09:00",
        "source": source,
        "period": {"start": start, "end": end, "granularity": granularity},
        "caveat": [MOCK_CAVEAT] + caveat,
    }


def write(name, payload):
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  생성 {path.relative_to(ROOT)}")


def daily_visitors(d: date) -> int:
    """여름 피크 + 주말 가중 + 노이즈. 거제 연 방문 규모(수백만 명)에 맞춘 일 단위 값."""
    seasonal = 1 + 0.45 * math.cos((d.timetuple().tm_yday - 213) / 365 * 2 * math.pi)
    weekend = {5: 1.55, 6: 1.30}.get(d.weekday(), 0.85)
    return int(21000 * seasonal * weekend * random.uniform(0.92, 1.08))


def signal_status():
    payload = envelope([TELECOM, DATALAB, YOUTUBE], "2026-08-13", "2026-09-12", [
        "3중 교차검증은 서로 출처가 다른 지표를 쓴다. 같은 원천에서 파생된 지표는 독립 신호로 세지 않는다.",
        "밀도는 구역 면적 추정치를 사용하므로 절대값보다 단계 변화에 의미를 둔다.",
    ])
    payload["data"] = {
        "region": REGION,
        "as_of": "2026-09-12",
        "alert_level": "주의",
        "previous_alert_level": "관심",
        "congestion_level": 3,
        "density": {"value": 0.52, "unit": "명/㎡", "slope_corrected": False},
        "cross_validation": [
            {
                "signal": "이동통신 유동인구 전주 대비 증가율",
                "provider": "한국관광공사(통신사 제휴 데이터)",
                "value": 0.34,
                "threshold": 0.25,
                "unit": "비율",
                "exceeded": True,
                "trend": "상승",
            },
            {
                "signal": "유튜브 관련 영상 조회수 증가율",
                "provider": "YouTube Data API v3",
                "value": 2.7,
                "threshold": 1.5,
                "unit": "배",
                "exceeded": True,
                "trend": "상승",
            },
            {
                "signal": "카드 소비 건수 전주 대비 증가율",
                "provider": "한국관광공사(카드사 제휴 데이터)",
                "value": 0.11,
                "threshold": 0.20,
                "unit": "비율",
                "exceeded": False,
                "trend": "상승",
            },
        ],
        "agreement": {"exceeded_count": 2, "total": 3},
        "basis": "독립 신호 3개 중 2개가 임계를 초과하여 경보를 관심에서 주의로 상향했다. 소비 지표는 아직 임계 미만으로, 방문은 늘었으나 소비 전환은 따라오지 않은 상태다.",
        "manual_ref": {
            "document": "지속가능한 관광지 혼잡도 운영 관리 매뉴얼(한국관광공사, 2026.03)",
            "page": 20,
            "section": "II. 기획·설계 및 준비 > 관광지 혼잡도 운영관리 시나리오 > 임계치 기반 경보·알림 운용",
            "quote": "경보 기준 설정: 혼잡 단계(4~5), 지속시간, 유입증가율, 정체 고착시간 기준값 정의",
        },
    }
    write("signal_status", payload)


def forecast():
    start = TODAY + timedelta(days=1)
    days = [start + timedelta(days=i) for i in range(90)]
    end = days[-1]

    daily = []
    for d in days:
        predicted = daily_visitors(d)
        spread = int(predicted * 0.18)
        level = "경계" if predicted > 34000 else "주의" if predicted > 27000 else "관심"
        entry = {
            "date": d.isoformat(),
            "predicted": predicted,
            "lower": predicted - spread,
            "upper": predicted + spread,
            "expected_alert_level": level,
            "is_holiday": d.isoformat() in {"2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-09", "2026-12-25"},
        }
        if d.isoformat() == "2026-10-17":
            entry["event"] = "거제 섬&섬 축제(가상)"
        daily.append(entry)

    weekday_totals = {w: 0 for w in WEEKDAY_KR}
    for d, row in zip(days, daily):
        weekday_totals[WEEKDAY_KR[d.weekday()]] += row["predicted"]
    total = sum(weekday_totals.values())

    peaks = sorted(daily, key=lambda r: -r["predicted"])[:5]

    payload = envelope([DATALAB, TELECOM], start.isoformat(), end.isoformat(), [
        "예측 구간(lower~upper)은 검증 기간 잔차의 80% 구간이다. 구간을 벗어나는 날이 5일 중 1일 정도 발생한다.",
        "축제·기상 등 일회성 요인은 모델에 반영되지 않아 별도 event 필드로 표기한다.",
    ])
    payload["data"] = {
        "region": REGION,
        "model": {
            "name": "SARIMAX(주간 계절성 + 공휴일 더미)",
            "trained_on": {"start": "2023-01-01", "end": "2026-08-31", "granularity": "일"},
            "metric": {
                "name": "MAPE",
                "value": 11.4,
                "validation_period": {"start": "2026-06-01", "end": "2026-08-31", "granularity": "일"},
            },
            "features": ["요일", "공휴일", "월별 계절성", "전년 동기 방문객", "기상(강수 여부)"],
        },
        "daily": daily,
        "weekday_concentration": [
            {"weekday": w, "ratio": round(weekday_totals[w] / total, 4)} for w in WEEKDAY_KR
        ],
        "peak_days": [
            {
                "date": p["date"],
                "predicted": p["predicted"],
                "expected_alert_level": p["expected_alert_level"],
                "reason": "주말 + 성수기 잔여 수요가 겹치는 날",
            }
            for p in peaks
        ],
    }
    write("forecast", payload)


def visitor_profile():
    gender_age = []
    weights = {"10대": 0.05, "20대": 0.24, "30대": 0.23, "40대": 0.20, "50대": 0.17, "60대이상": 0.11}
    for band, w in weights.items():
        gender_age.append({"gender": "남", "age_band": band, "ratio": round(w * 0.47, 4)})
        gender_age.append({"gender": "여", "age_band": band, "ratio": round(w * 0.53, 4)})

    payload = envelope([DATALAB, TELECOM, CARD], "2026-06-01", "2026-08-31", [
        "이동통신 기반 추정치로 실제 방문객 수와 차이가 있다. 구성비 해석에 사용하고 절대 규모 비교에는 쓰지 않는다.",
        "소비 데이터는 카드 결제분만 집계되어 현금 결제가 많은 업종은 과소 추정된다.",
    ], granularity="월")
    payload["data"] = {
        "region": REGION,
        "total_visitors": 2184000,
        "local_external_mix": {"local": 0.28, "external": 0.72},
        "gender_age": gender_age,
        "residence": [
            {"sido": "경상남도", "sigungu": "창원시", "ratio": 0.147},
            {"sido": "부산광역시", "ratio": 0.213},
            {"sido": "경상남도", "sigungu": "김해시", "ratio": 0.061},
            {"sido": "서울특별시", "ratio": 0.094},
            {"sido": "경기도", "ratio": 0.088},
            {"sido": "대구광역시", "ratio": 0.052},
        ],
        "distance": [
            {"band": "50km 미만", "ratio": 0.312},
            {"band": "50~100km", "ratio": 0.244},
            {"band": "100~200km", "ratio": 0.186},
            {"band": "200km 이상", "ratio": 0.258},
        ],
        "spending": [
            {"category": "음식", "amount_krw": 48200000000, "ratio": 0.361, "per_capita_krw": 22069},
            {"category": "숙박", "amount_krw": 31500000000, "ratio": 0.236, "per_capita_krw": 14423},
            {"category": "소매", "amount_krw": 24100000000, "ratio": 0.180, "per_capita_krw": 11035},
            {"category": "여가서비스", "amount_krw": 18700000000, "ratio": 0.140, "per_capita_krw": 8562},
            {"category": "교통", "amount_krw": 11100000000, "ratio": 0.083, "per_capita_krw": 5082},
        ],
        "companion": [
            {"type": "가족", "ratio": 0.402},
            {"type": "친구·연인", "ratio": 0.361},
            {"type": "나홀로", "ratio": 0.143},
            {"type": "단체", "ratio": 0.094},
        ],
        "profile_tags": ["20대비중높음", "외지인우세", "근거리당일치기혼재"],
    }
    write("visitor_profile", payload)


def hotspots():
    spots = [
        ("바람의 언덕", 34.7761, 128.6893, 0.72, "실외 공간 가치 체류 중심형", 4, 0.11),
        ("외도 보타니아 선착장", 34.7415, 128.7268, 0.58, "네트워크 보행 흐름형", 4, 0.08),
        ("매미성", 34.9142, 128.7481, 0.51, "지형·경사 이동·저항 흐름형", 3, 0.19),
        ("거제 포로수용소 유적공원", 34.8802, 128.6237, 0.29, "실내 공간 가치 체류 중심형", 3, 0.24),
        ("windy hill 주차장 일대", 34.7772, 128.6871, 0.44, "네트워크 보행 흐름형", 4, 0.16),
        ("신선대", 34.7846, 128.6543, 0.33, "지형·경사 이동·저항 흐름형", 3, 0.13),
        ("구조라 해수욕장", 34.8195, 128.7102, 0.21, "실외 공간 가치 체류 중심형", 2, 0.31),
        ("고현시장 일대", 34.8806, 128.6214, 0.09, "네트워크 보행 흐름형", 2, 0.68),
    ]
    ranking = []
    for i, (name, lat, lng, change, stype, level, local) in enumerate(spots, 1):
        entry = {
            "rank": i,
            "poi_name": name,
            "coord": {"lat": lat, "lng": lng},
            "visitors": int(48000 * (1 - 0.09 * i) * random.uniform(0.9, 1.1)),
            "change_rate": change,
            "visitor_mix": {"local": local, "external": round(1 - local, 2)},
            "congestion_level": level,
            "spatial_type": stype,
        }
        if stype == "지형·경사 이동·저항 흐름형":
            entry["bottleneck"] = {
                "name": f"{name} 진입 계단 구간",
                "dwell_minutes": round(random.uniform(6, 14), 1),
                "avg_speed_mps": round(random.uniform(0.62, 0.88), 2),
            }
        ranking.append(entry)

    payload = envelope([TELECOM, DATALAB], "2026-08-13", "2026-09-12", [
        "증감률은 직전 30일 대비다. 방문객 수가 적은 지점은 소수 인원 변동에도 증감률이 크게 흔들린다.",
        "공간 유형은 매뉴얼 p.13 분류 기준을 지점별로 적용한 값으로, 현장 확인을 거치지 않은 잠정 분류다.",
    ])
    payload["data"] = {
        "region": REGION,
        "baseline_period": {"start": "2026-07-14", "end": "2026-08-12", "granularity": "일"},
        "ranking": ranking,
    }
    write("hotspots", payload)


def content_type():
    videos = [
        ("dQw4w9Wg001", "거제 바람의 언덕 이 뷰 실화냐", "여행하는 소희", "2026-08-21", 412000, "포토스팟형", 0.89,
         "영상 8분 중 6분이 전망대 사진 촬영 장면이며 '인생샷'이 7회 언급됨", ["바람의 언덕"]),
        ("dQw4w9Wg002", "거제 3대 횟집 다 가봤습니다", "먹방로드", "2026-08-29", 287000, "맛집형", 0.94,
         "영상 전체가 식당 3곳 방문·시식으로 구성됨", ["고현시장 일대"]),
        ("dQw4w9Wg003", "매미성 가는 길 주차 꿀팁", "캠핑브이로그", "2026-09-02", 156000, "포토스팟형", 0.71,
         "주차·접근 정보가 절반이나 목적지 선택 이유가 '사진 명소'로 서술됨", ["매미성"]),
        ("dQw4w9Wg004", "외도 보타니아 당일치기 코스", "주말여행연구소", "2026-08-15", 98000, "자연경관형", 0.83,
         "식물원 경관 소개 중심, 음식·체험 언급 minimal", ["외도 보타니아 선착장"]),
        ("dQw4w9Wg005", "거제 카약 체험 후기", "액티비티 기록", "2026-09-05", 74000, "체험·액티비티형", 0.91,
         "카약 예약·장비·코스 설명이 영상 대부분을 차지", ["구조라 해수욕장"]),
        ("dQw4w9Wg006", "거제 포로수용소 생각보다 볼게 많음", "역사여행", "2026-08-08", 61000, "자연경관형", 0.42,
         "실내 전시 관람 중심이나 유형 판단 근거가 약함", ["거제 포로수용소 유적공원"]),
        ("dQw4w9Wg007", "신선대 일출 보러 새벽 4시 출발", "새벽러", "2026-09-07", 53000, "포토스팟형", 0.86,
         "일출 촬영이 영상의 목적으로 명시됨", ["신선대"]),
        ("dQw4w9Wg008", "거제 섬&섬 축제 미리보기", "경남여행", "2026-09-09", 22000, "축제·이벤트형", 0.88,
         "10월 축제 일정·프로그램 안내가 전체 내용", []),
    ]
    items = []
    for vid, title, channel, pub, views, ctype, conf, evidence, pois in videos:
        items.append({
            "video_id": vid,
            "title": title,
            "channel": channel,
            "published_at": pub,
            "view_count": views,
            "like_count": int(views * random.uniform(0.02, 0.05)),
            "comment_count": int(views * random.uniform(0.002, 0.006)),
            "content_type": ctype,
            "confidence": conf,
            "evidence": evidence,
            "poi_mentioned": pois,
            "sentiment": "긍정",
        })

    counts = {}
    for item in items:
        if item["confidence"] >= 0.6:
            counts.setdefault(item["content_type"], []).append(item)
    classified = sum(len(v) for v in counts.values())

    payload = envelope([YOUTUBE], "2026-06-14", "2026-09-12", [
        "신뢰도 0.6 미만 항목은 집계에서 제외했다. 제외 건수는 unclassified_count에 표시한다.",
        "조회수는 수집 시점 기준이며 이후 변동한다.",
        "검색 결과 상위 영상만 수집해 소규모 채널 콘텐츠가 과소 대표될 수 있다.",
    ])
    payload["data"] = {
        "region": REGION,
        "model": {"name": "claude-sonnet-5", "prompt_version": "agent2_content_type_v0.1", "temperature": 0},
        "items": items,
        "summary": [
            {
                "content_type": ctype,
                "count": len(group),
                "ratio": round(len(group) / classified, 4),
                "total_views": sum(i["view_count"] for i in group),
            }
            for ctype, group in sorted(counts.items(), key=lambda kv: -len(kv[1]))
        ],
        "unclassified_count": len(items) - classified,
    }
    write("content_type", payload)


def checklist():
    sample = json.loads((ROOT / "manual" / "checklist_items.sample.json").read_text(encoding="utf-8"))
    items = []
    for entry in sample["items"]:
        if "주의" not in entry["단계"]:
            continue
        items.append({
            "id": entry["id"],
            "phase": entry["시점"],
            "action": entry["조치"],
            "owner": entry["담당"],
            "priority": entry["우선순위"],
            "alert_level": "주의",
            "spatial_type": entry["공간유형"],
            "profile_tags": entry["프로파일"],
            "manual_ref": {
                "document": "지속가능한 관광지 혼잡도 운영 관리 매뉴얼(한국관광공사, 2026.03)",
                "page": entry["근거"]["쪽"],
                "section": entry["근거"]["절"],
                "quote": entry["근거"]["원문"],
            },
            "match_reason": "경보 단계 '주의'에 해당하며 공간 유형 조건을 충족함",
        })

    payload = envelope([MANUAL_SRC], "2026-09-12", "2026-09-12", [
        "매뉴얼 구조화 작업이 진행 중이어서 현재는 샘플 5건 기준으로만 매칭된다. 전체 항목 반영 시 결과가 달라진다.",
        "매뉴얼은 공공누리 4유형(출처표시·상업적이용금지·변경금지) 조건으로 이용한다.",
    ])
    payload["data"] = {
        "region": REGION,
        "matched_for": {
            "alert_level": "주의",
            "congestion_level": 3,
            "spatial_type": "지형·경사 이동·저항 흐름형",
            "content_type": "포토스팟형",
            "profile_tags": ["20대비중높음", "외지인우세"],
        },
        "items": items,
        "excluded_count": len(sample["items"]) - len(items),
    }
    write("checklist", payload)


def precedent():
    payload = envelope([MANUAL_SRC, DATALAB], "2023-01-01", "2026-08-31", [
        "선례의 성과 수치는 각 지자체 공개 자료 기준이며 측정 방식이 서로 달라 직접 비교가 어렵다.",
        "유사도는 공간 유형·경보 단계·방문객 구성 3개 축의 일치 정도로 산출한 값이다.",
    ], granularity="년")
    payload["data"] = {
        "region": REGION,
        "matched_for": {
            "spatial_type": "지형·경사 이동·저항 흐름형",
            "content_type": "포토스팟형",
            "alert_level": "주의",
        },
        "cases": [
            {
                "case_id": "PC-001",
                "region_name": "부산 감천문화마을",
                "year": 2024,
                "situation": "경사 골목 구간에서 사진 촬영 대기가 발생해 보행 흐름이 끊기고 주민 통행로가 막힘",
                "spatial_type": "지형·경사 이동·저항 흐름형",
                "content_type": "포토스팟형",
                "actions": [
                    "구간별 일방통행 지정",
                    "촬영 대기선 표시 및 대기 구역 분리",
                    "주민 전용 통행로 확보",
                ],
                "outcome": {
                    "summary": "주말 병목 구간 평균 체류시간이 감소하고 주민 민원이 줄었다고 보고됨",
                    "metric": "병목 구간 체류 시간",
                    "measured": False,
                },
                "similarity": 0.81,
                "source": {
                    "name": "경사 보정 이동 혼잡도 지표 적용 사례(감천문화마을)",
                    "provider": "한국관광공사",
                    "retrieved_at": "2026-09-12",
                    "note": "매뉴얼 p.54 사례",
                },
            },
            {
                "case_id": "PC-002",
                "region_name": "강릉 안목해변",
                "year": 2023,
                "situation": "영상 콘텐츠 확산 후 주말 방문이 급증하여 주차 대기열이 진입로를 막음",
                "spatial_type": "실외 공간 가치 체류 중심형",
                "content_type": "포토스팟형",
                "actions": ["외곽 주차장 셔틀 운행", "진입 차량 사전 안내", "집중 시간대 분산 홍보"],
                "outcome": {
                    "summary": "진입로 정체 시간이 줄었다고 발표됨",
                    "metric": "유입/유출 비율",
                    "measured": False,
                },
                "similarity": 0.64,
                "source": {
                    "name": "지자체 혼잡 관리 보도자료",
                    "provider": "강릉시",
                    "retrieved_at": "2026-09-12",
                },
            },
        ],
    }
    write("precedent", payload)


def before_after():
    payload = envelope([TELECOM, CARD, MANUAL_SRC], "2026-07-01", "2026-08-31", [
        "전후 비교 구간의 계절성이 달라 개선분 전부를 조치 효과로 볼 수 없다.",
        "KPI 명칭은 매뉴얼 p.15의 3-tier 체계를 그대로 사용한다.",
    ])
    payload["data"] = {
        "region": REGION,
        "intervention": {
            "name": "매미성 진입 계단 구간 상·하행 분리 및 우회 안내",
            "applied_at": "2026-08-01",
            "actions": [
                "구간별 수용인원·밀집 상한 설정 및 상·하행 분리",
                "우회 경로 유도 안내",
            ],
            "checklist_ids": ["CL-024", "CL-007"],
        },
        "comparison_window": {
            "before": {"start": "2026-07-01", "end": "2026-07-31", "granularity": "일"},
            "after": {"start": "2026-08-01", "end": "2026-08-31", "granularity": "일"},
        },
        "metrics": [
            {
                "kpi": "병목 구간 체류 시간",
                "tier": 2,
                "before": 13.8,
                "after": 9.1,
                "unit": "분",
                "change_rate": -0.34,
                "direction": "낮을수록좋음",
                "significance": "7월 대비 8월은 방문객이 더 많은 기간이므로, 방문 증가에도 체류시간이 줄어든 점에 의미가 있다.",
            },
            {
                "kpi": "단위 면적당 인원수(경사도 보정)",
                "tier": 2,
                "before": 0.61,
                "after": 0.48,
                "unit": "명/㎡",
                "change_rate": -0.21,
                "direction": "낮을수록좋음",
                "significance": "경사 16.5° 구간 기준 보정값. 4단계(0.342 이상) 진입 빈도가 감소.",
            },
            {
                "kpi": "혼잡 임계치 초과 횟수/지속시간",
                "tier": 2,
                "before": 22,
                "after": 13,
                "unit": "회/월",
                "change_rate": -0.41,
                "direction": "낮을수록좋음",
            },
            {
                "kpi": "구간별 평균 이동 속도",
                "tier": 3,
                "before": 0.68,
                "after": 0.79,
                "unit": "m/s",
                "change_rate": 0.16,
                "direction": "높을수록좋음",
            },
        ],
    }
    write("before_after", payload)


def timeline():
    payload = envelope([YOUTUBE, TELECOM, DATALAB], "2026-06-20", "2026-08-25", [
        "민원 건수는 지자체 공개 통계 기준이며 접수 경로에 따라 누락이 있다.",
        "lead_time_days는 이 사례 한 건의 값으로, 다른 사례에 그대로 적용할 수 없다.",
    ])
    payload["data"] = {
        "case_id": "TL-001",
        "region": REGION,
        "title": "매미성 영상 확산 이후 경사 구간 혼잡 발생 및 대응",
        "spatial_type": "지형·경사 이동·저항 흐름형",
        "content_type": "포토스팟형",
        "lead_time_days": 18,
        "events": [
            {
                "date": "2026-06-20",
                "type": "콘텐츠 확산",
                "description": "매미성 소개 영상이 업로드 후 1주일 만에 조회수 30만을 넘김",
                "value": 312000,
                "unit": "회",
                "source": YOUTUBE,
                "is_signal": True,
            },
            {
                "date": "2026-07-08",
                "type": "방문 급증",
                "description": "주말 방문객이 직전 4주 평균 대비 2.1배로 증가",
                "value": 2.1,
                "unit": "배",
                "source": TELECOM,
                "is_signal": True,
            },
            {
                "date": "2026-07-13",
                "type": "혼잡 발생",
                "description": "진입 계단 구간에서 평균 이동속도가 0.7m/s 아래로 떨어짐",
                "value": 0.68,
                "unit": "m/s",
                "source": TELECOM,
                "is_signal": True,
            },
            {
                "date": "2026-07-19",
                "type": "민원 발생",
                "description": "주차·소음 관련 민원이 주간 기준 최고치 기록",
                "value": 47,
                "unit": "건",
                "source": {
                    "name": "지자체 민원 접수 통계",
                    "provider": "거제시",
                    "retrieved_at": "2026-09-12",
                },
                "is_signal": False,
            },
            {
                "date": "2026-08-01",
                "type": "조치 시행",
                "description": "상·하행 분리 및 우회 경로 안내 시행",
                "source": MANUAL_SRC,
                "is_signal": False,
            },
            {
                "date": "2026-08-25",
                "type": "완화",
                "description": "병목 구간 평균 체류시간이 13.8분에서 9.1분으로 감소",
                "value": 9.1,
                "unit": "분",
                "source": TELECOM,
                "is_signal": False,
            },
        ],
    }
    write("timeline", payload)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("목업 생성 (거제시 기준)\n")
    signal_status()
    forecast()
    visitor_profile()
    hotspots()
    content_type()
    checklist()
    precedent()
    before_after()
    timeline()
    print("\n완료 — 9종")
