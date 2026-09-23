// The competition's data is frozen (docs/meeting-notes/DB/관광바이럴조기경보DB사용설명서.pdf,
// §11: "2026년 후반 값은 프로젝트 기준 시점보다 미래 날짜를 포함할 수 있다"). The screen's
// "오늘/현재" must not be the real wall-clock date -- it's this fixed virtual reference
// date, which matches the DB's actual latest loaded day (vw_daily_core_signal max
// observed_date = 2026-08-13, PDF's Test window ends 2026-08-14).
export const REFERENCE_DATE = "2026-08-14";
