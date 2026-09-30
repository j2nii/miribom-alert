# -*- coding: utf-8 -*-
"""
네이버 검색어 트렌드 — 기간 지정 전수 수집 (T1 관심, 일 해상도)
사용법 예:
  python collect_naver_all.py --start 2023-01-01 --end 2024-12-31 \
    --output naver_period_202301_202412.csv \
    --progress naver_progress_202301_202412.json

브라우저 크롤러와 병렬 실행할 수 있다. 인증정보는 코드에 저장하지 않고
data-dir의 .env에서 NAVER_KEY_ID / NAVER_KEY_SECRET을 읽는다.

── 왜 이렇게 복잡한가 ───────────────────────────────────
네이버는 "한 번의 호출 안에서" 최대값을 100으로 잡아 상대지수를 준다.
따라서 배치가 다르면 스케일이 다르고, 그대로 붙이면 지역 간 비교가 불가능하다.
→ 모든 배치에 앵커를 하나씩 넣고, 앵커 평균이 같아지도록 배치를 재정규화한다.

그런데 앵커가 하나면 문제가 생긴다. 강남구와 울릉군을 같은 호출에 넣으면
울릉군 값이 0.0x 로 뭉개져 소수점이 날아간다(정밀도 붕괴).
→ 지역 규모를 먼저 재서 계층으로 나누고, 계층마다 앵커를 둔다.
→ 계층 앵커들을 '이웃끼리만' 짝지어 호출한다(사슬 호출). T0-T1, T1-T2, ...
   한 호출에 전국 규모를 다 넣으면 사슬 자체가 뭉개지므로, 한 칸씩만 건넌다.

── 2패스로 돌린다 ──────────────────────────────────────
1패스: 방문자수를 규모 프록시로 쓴다. 이건 근사치일 뿐이다 —
       도시 자치구는 방문자는 많아도 아무도 검색하지 않는다(동작구, 진해구).
       그래서 앵커가 뭉개지고 계층이 어긋난다.
확장 수집: 기존 naver_all_daily_v2.csv의 실측 검색지수로 계층을 정한다.
       방문자수는 수집 대상 228개 지역을 확정하는 용도로 쓴다.
"""
import argparse, json, os, re, sys, time
from datetime import date
from pathlib import Path
import pandas as pd, numpy as np, requests

N_TIERS = 5
SLEEP = 0.6


def parse_args():
    base = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="네이버 검색 트렌드 기간별 전수 수집")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--data-dir", type=Path, default=(base / "..").resolve(),
                   help="signals_visitors_v2.csv 등이 있는 yaho 폴더")
    p.add_argument("--seed", default="naver_all_daily_v2.csv",
                   help="검색 규모 계층을 정할 기존 정본 CSV")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--progress", type=Path, required=True)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--tiers", type=int, default=N_TIERS)
    p.add_argument("--sleep", type=float, default=SLEEP)
    args = p.parse_args()
    for value, label in ((args.start, "--start"), (args.end, "--end")):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            p.error(f"{label}는 YYYY-MM-DD 형식이어야 합니다: {value}")
        try:
            date.fromisoformat(value)
        except ValueError:
            p.error(f"{label} 날짜가 올바르지 않습니다: {value}")
    if args.start > args.end:
        p.error("--start가 --end보다 늦습니다.")
    if args.tiers < 2:
        p.error("--tiers는 2 이상이어야 합니다.")
    return args


def load_dotenv(path: Path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


ARGS = parse_args()
BASE = Path(__file__).resolve().parent
DATA_DIR = ARGS.data_dir.resolve()
START, END = ARGS.start, ARGS.end
N_TIERS, SLEEP = ARGS.tiers, ARGS.sleep
OUTCSV = ARGS.output if ARGS.output.is_absolute() else (BASE / ARGS.output).resolve()
PROG = ARGS.progress if ARGS.progress.is_absolute() else (BASE / ARGS.progress).resolve()
REPORT = ARGS.report or OUTCSV.with_name(OUTCSV.stem + "_report.txt")
REPORT = REPORT if REPORT.is_absolute() else (BASE / REPORT).resolve()
OUTCSV.parent.mkdir(parents=True, exist_ok=True)
PROG.parent.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)

load_dotenv(DATA_DIR / ".env")
CLIENT_ID = os.getenv("NAVER_KEY_ID", "").strip()
CLIENT_SECRET = os.getenv("NAVER_KEY_SECRET", "").strip()
if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        f"{DATA_DIR / '.env'}에 NAVER_KEY_ID와 NAVER_KEY_SECRET을 설정하세요. "
        "인증정보를 Python 파일에 직접 적지 마세요."
    )

URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
HDR = {"X-NCP-APIGW-API-KEY-ID": CLIENT_ID.strip(),
       "X-NCP-APIGW-API-KEY":    CLIENT_SECRET.strip(),
       "Content-Type": "application/json"}
out = REPORT.open("w", encoding="utf-8")
def say(*a):
    s = " ".join(str(x) for x in a); print(s); out.write(s + "\n")

# ══ 1. 지역 목록 + 규모 ═══════════════════════════════
visitors_path = DATA_DIR / "signals_visitors_v2.csv"
if not visitors_path.exists():
    visitors_path = DATA_DIR / "signals_visitors.csv"
if not visitors_path.exists():
    raise SystemExit(f"방문자수 파일을 찾을 수 없습니다: {DATA_DIR}")
sv = pd.read_csv(visitors_path, dtype={"region": str, "tou_div": str})
sv["value"] = pd.to_numeric(sv["value"], errors="coerce")
ext = sv[sv["tou_div"].astype(str) == "2"]              # 외지인
visit_size = ext.groupby("region")["value"].mean().sort_values(ascending=False)

seed_path = Path(ARGS.seed)
if not seed_path.is_absolute():
    seed_path = DATA_DIR / seed_path
if not seed_path.exists():
    raise SystemExit(f"검색 규모 기준 정본을 찾을 수 없습니다: {seed_path}")
p1 = pd.read_csv(seed_path, dtype={"region": str})
measured = p1.groupby("region")["value"].mean()
# 기존 v2에서 인천 서구권은 과거 코드 28260으로 저장됐다.
# 수집 대상 정본 키인 INCHEON_WEST의 계층 규모로만 연결한다.
if "INCHEON_WEST" not in measured.index and "28260" in measured.index:
    measured.loc["INCHEON_WEST"] = measured.loc["28260"]
fallback = measured[measured > 0].min() / 10 if (measured > 0).any() else 1e-6
size = measured.reindex(visit_size.index).fillna(fallback).sort_values(ascending=False)

try:
    m = pd.read_csv(DATA_DIR / "region_master.csv", dtype=str)
    NAME = dict(zip(m["region"], m["name"]))
except Exception:
    NAME = {}
# build_signals.py 와 fix_codes.py 가 합산그룹 키를 다르게 쓰므로 양쪽 다 등록한다.
# 이름이 없으면 코드 문자열("41590")이 검색어로 들어가 결과가 0이 된다.
GROUP_LABELS = {"IC_MID": "인천 중구권", "INCHEON_MID": "인천 중구권",
                "INCHEON_WEST": "인천 서구권", "HWASEONG": "화성시",
                "41590": "화성시", "28260": "인천 서구"}

# 자동 생성이 통하지 않는 지역만 손으로 지정
KW_OVERRIDE = {
    "41590":  ["화성시", "화성"],
    "28260":  ["인천 서구"],
    "IC_MID": ["인천 중구"],
    "INCHEON_MID": ["인천 중구"],
    "INCHEON_WEST": ["인천 서구"],
    "HWASEONG": ["화성시", "화성"],
}

SIDO_SHORT = {"11":"서울","26":"부산","27":"대구","28":"인천","29":"광주","30":"대전",
              "31":"울산","36":"세종","41":"경기","42":"강원","51":"강원","43":"충북",
              "44":"충남","45":"전북","52":"전북","46":"전남","47":"경북","48":"경남","50":"제주"}

say(f"═══ 확장 수집 ═══  지역 {len(size)}개 · 기간 {START} ~ {END}")
say(f"규모 기준: {seed_path.name} 검색량 실측 · 방문자 목록: {visitors_path.name}\n")

# ══ 2. 검색 키워드 만들기 ══════════════════════════════
def strip_suffix(nm):
    nm = nm.strip()
    return nm[:-1] if len(nm) > 2 and nm[-1] in "시군구" else nm

raw_name = {c: (NAME.get(c) or GROUP_LABELS.get(c) or c) for c in size.index}
stripped = {c: strip_suffix(n) for c, n in raw_name.items()}
dup = pd.Series(list(stripped.values())).value_counts()
dup = set(dup[dup > 1].index)

KW, ambiguous = {}, []
for c, nm in raw_name.items():
    st = stripped[c]
    if c in KW_OVERRIDE:
        KW[c] = KW_OVERRIDE[c]
        ambiguous.append((c, nm, "수동 지정 (합산그룹/이름 누락)"))
    elif c.isdigit() is False and not nm.endswith(("시", "군", "구")):                  # 합산그룹은 통칭이 없음
        KW[c] = [st]
        ambiguous.append((c, nm, "합산그룹 — 검색 신뢰도 낮음"))
    elif st in dup:
        sd = SIDO_SHORT.get(c[:2])
        if c[:2] == "12" and nm.endswith("구"):
            sd = "광주"                                  # 12번대 자치구는 전부 광주
        pre = f"{sd} " if sd else ""
        KW[c] = list(dict.fromkeys([f"{pre}{nm}", f"{pre}{st}"]))
        ambiguous.append((c, nm, f"동명 지역 — '{pre}{nm}' 로 검색"))
    elif nm == c:
        KW[c] = [c]
        ambiguous.append((c, nm, "⚠ 이름 누락 — 코드가 검색어로 들어감. GROUP_LABELS 에 추가하세요"))
    else:
        KW[c] = sorted({nm, st}, key=len, reverse=True)

missing_name = [c for c, nm, why in ambiguous if why.startswith("⚠ 이름 누락")]
if missing_name:
    say(f"⚠⚠ 이름을 못 찾은 지역 {len(missing_name)}개 — 이대로 돌리면 결과가 0으로 나옵니다:")
    for c in missing_name:
        say(f"      {c}")
    say("   → 스크립트 상단 GROUP_LABELS / KW_OVERRIDE 에 추가한 뒤 다시 실행하세요\n")

say(f"── 키워드 ── 고유 {len(size)-len(ambiguous)}개 · 접두어/주의 {len(ambiguous)}개")
for c, nm, why in ambiguous[:15]:
    say(f"    {c} {nm:<12s} {KW[c]}  ({why})")
if len(ambiguous) > 15:
    say(f"    … 외 {len(ambiguous)-15}개 (리포트 하단 전체 목록)")

# ══ 3. 규모 계층 + 앵커 ════════════════════════════════
codes = list(size.index)
tiers = np.array_split(codes, N_TIERS)                   # 큰 지역부터 순서대로
def is_si_gun(c):
    """자치구·일반구는 검색어로 잡히지 않는다 — 앵커에서 뺀다."""
    nm = raw_name.get(c, "")
    return nm.endswith(("시", "군")) and " " not in nm

anchors, anchor_note = [], []
for t in tiers:
    s = size[list(t)]
    cand = [c for c in s.index if is_si_gun(c)]
    if cand:
        med = s[cand].median()
        a = min(cand, key=lambda c: abs(s[c] - med))     # 계층 중앙에 가장 가까운 시·군
        anchor_note.append("")
    else:
        a = s.index[len(s) // 2]
        anchor_note.append("  ⚠ 시·군 후보 없음 — 구를 앵커로 씀")
    anchors.append(a)

say(f"\n── 규모 계층 {N_TIERS}개 (외지인 일평균 기준) ──")
for i, t in enumerate(tiers):
    s = size[list(t)]
    say(f"  T{i}  {len(t):>3d}개  {s.max():>12,.1f} ~ {s.min():>10,.1f}"
        f"   앵커 {raw_name[anchors[i]]}({anchors[i]}) {size[anchors[i]]:,.1f}{anchor_note[i]}")

# ══ 4. 호출 ════════════════════════════════════════════
prog = json.load(PROG.open(encoding="utf-8")) if PROG.exists() else {}
expected_meta = {"start": START, "end": END, "tiers": N_TIERS}
if "_meta" in prog and prog["_meta"] != expected_meta:
    raise SystemExit(
        f"진행 파일의 기간/계층이 현재 실행과 다릅니다: {PROG}\n"
        "잘못된 캐시 재사용을 막았습니다. 다른 --progress 파일명을 사용하세요."
    )
prog.setdefault("_meta", expected_meta)
PROG.write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")

def fetch(key, group_codes):
    """key 로 캐시. 이미 받았으면 재호출 안 함."""
    if key in prog:
        return prog[key]
    body = {"startDate": START, "endDate": END, "timeUnit": "date",
            "keywordGroups": [{"groupName": c, "keywords": KW[c][:20]} for c in group_codes]}
    for attempt in range(4):
        try:
            r = requests.post(URL, headers=HDR, data=json.dumps(body), timeout=90)
        except Exception as e:
            say(f"    ! 통신 오류 {e} — 재시도 {attempt+1}/4"); time.sleep(3 * (attempt + 1)); continue
        if r.status_code == 200:
            prog[key] = r.json()
            PROG.write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")
            time.sleep(SLEEP)
            return prog[key]
        if r.status_code == 429:
            say(f"    ! 호출 한도 — 60초 대기 (재시도 {attempt+1}/4)"); time.sleep(60); continue
        say(f"    ! [{r.status_code}] {r.text[:300]}")
        if r.status_code in (401, 403):
            say("\n  인증 실패입니다. 키와 헤더 이름(X-NCP-APIGW-API-KEY-ID)을 확인하세요.")
            PROG.write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")
            sys.exit(1)
        time.sleep(3 * (attempt + 1))
    return None

def to_df(j, batch):
    return pd.DataFrame([{"region": res["title"], "date": d["period"],
                          "ratio": d["ratio"], "batch": batch}
                         for res in j["results"] for d in res["data"]])

# 4-1. 사슬 호출 — 이웃 계층 앵커끼리만 짝지어 스케일을 잇는다
say(f"\n── 사슬 호출 ({len(anchors)-1}회: 이웃 계층끼리) ──")
chain, ref = [], {}
for i in range(len(anchors) - 1):
    j = fetch(f"CHAIN_{i}", [anchors[i], anchors[i + 1]])
    if j is None: sys.exit(f"사슬 호출 CHAIN_{i} 실패 — 중단합니다")
    chain.append(to_df(j, f"CHAIN_{i}"))

ref[anchors[0]] = 100.0                                   # 기준점(임의)
for i, cdf in enumerate(chain):
    mu = cdf.groupby("region")["ratio"].mean()
    lo, hi = anchors[i], anchors[i + 1]
    if mu.get(lo, 0) == 0:
        sys.exit(f"CHAIN_{i}: 앵커 {raw_name[lo]} 값이 0 — 키워드를 확인하세요")
    ref[hi] = ref[lo] * (mu[hi] / mu[lo])
    say(f"    CHAIN_{i}  {raw_name[lo]:<10s} → {raw_name[hi]:<10s}"
        f"  비율 {mu[hi]/mu[lo]:>7.4f}   원본 최소 {mu.min():>7.3f}")
for a in anchors:
    say(f"    기준값  {raw_name[a]:<12s} {ref[a]:>12.4f}")
rv = [ref[a] for a in anchors]
if any(rv[i] <= rv[i + 1] for i in range(len(rv) - 1)):
    say("  ⚠ 기준값이 계층 순서대로 줄지 않습니다 — 앵커가 규모를 대표하지 못한다는 뜻.")
    say("     1패스면 정상입니다(방문자수 기준이라 검색량과 어긋남). 2패스에서 이 경고가 남으면 조사 필요.")
else:
    say("  ✅ 기준값이 계층 순서대로 감소 — 앵커가 규모를 제대로 대표함")

# 앵커 자신의 시계열은 사슬 호출에서 가져온다 (배치에선 중복이라 버림)
anchor_rows = []
for i, a in enumerate(anchors):
    src_i = min(i, len(chain) - 1)
    sub = chain[src_i][chain[src_i].region == a].copy()
    sub["ratio"] *= ref[a] / sub["ratio"].mean()
    sub["batch"] = "ANCHOR"
    anchor_rows.append(sub)
anchor_df = pd.concat(anchor_rows, ignore_index=True)

# 4-2. 계층별 배치
jobs = []
for i, t in enumerate(tiers):
    others = [c for c in t if c != anchors[i]]
    for k in range(0, len(others), 4):
        jobs.append((f"T{i}_B{k//4}", anchors[i], others[k:k + 4]))

say(f"\n── 배치 {len(jobs)}개 (이미 받은 것 {sum(1 for j_,_,_ in jobs if j_ in prog)}개) ──")
frames = []
failed = []
for key, anc, grp in jobs:
    cached = key in prog
    j = fetch(key, [anc] + grp)
    if j is None:
        failed.append(key); say(f"  {key}  실패"); continue
    frames.append(to_df(j, key))
    if not cached:
        say(f"  {key}  {[raw_name[c] for c in grp]}")

df = pd.concat(frames, ignore_index=True)

# ══ 5. 재정규화 ════════════════════════════════════════
say("\n── 재정규화 (배치 앵커를 사다리 기준에 맞춤) ──")
scales, bad_scale = {}, []
for key, anc, _ in jobs:
    sub = df[(df.batch == key) & (df.region == anc)]["ratio"]
    if not len(sub) or sub.mean() == 0:
        bad_scale.append(key); continue
    s = ref[anc] / sub.mean()
    scales[key] = s
    df.loc[df.batch == key, "ratio"] *= s

if scales:
    v = pd.Series(scales)
    say(f"  배율 전체 범위 {v.min():.4f} ~ {v.max():.4f}  (계층마다 다른 게 정상)")
    say("  ※ 배율은 배치 내 '일별 최대값'에 비례한다. 스파이크가 큰 지역이 들어간 배치는")
    say("    배율이 커지는 게 정상이며, 실제 손실 여부는 아래 '검증 2'가 판정한다.")
    for i in range(len(tiers)):                      # 계층 '안'에서의 편차만 문제다
        tv = v[[k for k in v.index if k.startswith(f"T{i}_")]]
        if len(tv) < 2: continue
        spread = tv.max() / max(tv.min(), 1e-9)
        flag = "  (스파이크 큰 지역이 섞인 배치가 있음 — 검증 2가 통과하면 문제 없음)" if spread > 5 else ""
        say(f"    T{i}  배치 {len(tv):>2d}개 · 계층 내 편차 {spread:>5.2f}배{flag}")
if bad_scale:
    say(f"  ⚠ 앵커가 0이라 보정 못 한 배치: {bad_scale}")

# 앵커 중복 제거 → 사슬에서 가져온 값으로 교체
df = df[~df.region.isin(set(anchors))]
df = pd.concat([df, anchor_df], ignore_index=True)

# ══ 6. 검증 ════════════════════════════════════════════
say("\n── 검증 1: 앵커 시계열이 배치마다 같은 모양인가 ──")
lad_piv = anchor_df.pivot_table(index="date", columns="region", values="ratio")
worst = []
for key, anc, _ in jobs:
    b = pd.concat(frames, ignore_index=True)
    s = b[(b.batch == key) & (b.region == anc)].set_index("date")["ratio"]
    r = lad_piv[anc].reindex(s.index)
    r = r.dropna()
    s = s.reindex(r.index)
    if len(s) < 30 or s.std() == 0 or r.std() == 0: continue
    corr = np.corrcoef(s.values, r.values)[0, 1]
    worst.append((corr, key, anc))
worst.sort()
if worst:
    say(f"  상관계수 최저 5개 (1.0 에 가까워야 정상):")
    for corr, key, anc in worst[:5]:
        flag = "  ⚠ 재설계 필요" if corr < 0.99 else ""
        say(f"    {key:<10s} {raw_name[anc]:<12s} r={corr:.4f}{flag}")
    if worst[0][0] < 0.99:
        say("  ⚠ 상관이 0.99 미만인 배치가 있습니다. 지역 간 비교가 위험합니다.")
        say("     → 해당 배치만 다시 받거나(progress 에서 해당 키 삭제), 탐지 지표를 데이터랩으로 전환 검토")
    else:
        say("  ✅ 전 배치 r ≥ 0.99 — 배치 간 비교 가능")

say("\n── 검증 2: 정밀도 (원본 ratio 기준) ──")
say("  네이버는 호출 안에서 최대=100 으로 맞추고 소수 4자리로 끊는다.")
say("  같은 호출에 큰 지역이 섞이면 작은 지역이 0.0001 로 뭉개져 되살릴 수 없다.")
_raw = pd.concat(frames, ignore_index=True)          # 보정 전
peak_raw = _raw.groupby(["batch", "region"])["ratio"].max()
tiny = peak_raw[peak_raw < 1.0]
say(f"  원본 최대값 1.0 미만: {len(tiny)}건 / {len(peak_raw)}건")
for (b, c), v_ in tiny.sort_values().head(10).items():
    say(f"    [{b}] {raw_name.get(c, c)} ({c})  원본 최대 {v_:.4f}")
if len(tiny):
    say(f"  → 해당 배치를 {PROG.name} 에서 지우고 --tiers를 늘려 다시 받으세요")
else:
    say("  ✅ 전 배치 원본 최대값 ≥ 1.0 — 계층 분리가 제대로 됐습니다")
ch_min = min(c.groupby("region")["ratio"].max().min() for c in chain)
say(f"  사슬 호출 최소 원본 최대값: {ch_min:.4f}"
    + ("   ⚠ 이웃 계층 간에도 규모차가 큽니다 — N_TIERS 를 늘리세요" if ch_min < 1.0 else "   ✅"))
piv = df.pivot_table(index="date", columns="region", values="ratio")

say("\n── 검증 3: 사례 지역 확인 ──")
for c, nm in [("48310","거제"),("51750","영월"),("51210","속초"),
              ("47940","울릉"),("12130","여수"),("51810","인제")]:
    if c in piv.columns:
        s = piv[c].dropna()
        say(f"    {nm:<4s} {len(s):>4d}일 · 평균 {s.mean():>8.2f} · 최대 {s.max():>8.2f}")
    else:
        say(f"    {nm:<4s} ⚠ 없음")

# ══ 7. 저장 ════════════════════════════════════════════
o = df[["region", "date", "ratio"]].rename(columns={"ratio": "value"}).copy()
o["date"] = pd.to_datetime(o["date"]).dt.strftime("%Y-%m-%d")
o = o.sort_values(["region", "date"])
duplicate_count = int(o.duplicated(["region", "date"]).sum())
expected_days = (date.fromisoformat(END) - date.fromisoformat(START)).days + 1
counts = o.groupby("region")["date"].nunique()
incomplete = counts[counts != expected_days]
if duplicate_count:
    say(f"❌ 지역·일자 중복 {duplicate_count:,}건 — 결과를 정본으로 쓰면 안 됩니다.")
if len(incomplete):
    say(f"❌ 예상 {expected_days:,}일과 다른 지역 {len(incomplete):,}개 — 수집이 불완전합니다.")
    for code, count in incomplete.head(20).items():
        say(f"    {raw_name.get(code, code)} ({code})  {count:,}일")
o.to_csv(OUTCSV, index=False, encoding="utf-8-sig")
say(f"\n[완료] {OUTCSV.name} · {len(o):,}행 · {o['region'].nunique()}개 지역")
lost = sorted(set(size.index) - set(o["region"]))
if lost:
    say(f"⚠ 결과가 아예 없는 지역 {len(lost)}개 (검색량 0 → 네이버가 빈 배열 반환):")
    for c in lost:
        say(f"    {raw_name.get(c, c)} ({c})")
    say("    → 전수 탐지 대상에서 제외하고, 제외 사유를 문서에 남기세요")
if failed:
    say(f"⚠ 실패한 배치 {len(failed)}개: {failed}  → 다시 실행하면 이 배치만 재시도합니다")

say("\n── 접두어/주의 지역 전체 ──")
for c, nm, why in ambiguous:
    say(f"  {c} {nm:<14s} {KW[c]}  ({why})")
out.close()
if failed or lost or duplicate_count or len(incomplete):
    raise SystemExit(2)
