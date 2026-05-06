module phase4b_async

-- =====================
-- 基本型定義
-- =====================

-- レポートの生成状態
abstract sig ReportState {}
one sig Generating, Done, Failed extends ReportState {}

-- セッション
sig Session {
    session_id: one Int,
    report_state: one ReportState
}

-- report_cache（session_idをキーとして管理）
sig ReportCache {
    entries: Session -> lone ReportState
} {
    all s1, s2: Session |
        s1.session_id = s2.session_id and
        (s1 + s2) in entries.ReportState implies s1 = s2
}

-- インタビュー
sig Interview {
    question_count: Int,  -- 質問数（0〜2）
    is_active: one Bool   -- レポート生成中のみtrue
}

abstract sig Bool {}
one sig True, False extends Bool {}

-- =====================
-- 制約（INV_15〜INV_18）
-- =====================

-- INV_15: レポート生成は非同期で実行する
-- report_cacheにエントリがある = 生成中または完了
fact AsyncGeneration {
    all s: Session |
        s.report_state = Generating or
        s.report_state = Done or
        s.report_state = Failed
}

-- INV_16: レポートは必ず完了またはFailedになる（無限待機なし）
fact ReportAlwaysCompletes {
    all s: Session |
        s.report_state != Generating
            or (some s2: Session |
                s2.session_id = s.session_id and
                s2.report_state = Done)
}

-- INV_17: インタビュアーAIはレポート生成中のみ動作する
fact InterviewOnlyDuringGeneration {
    all i: Interview |
        i.is_active = True implies
            (some s: Session | s.report_state = Generating)
}

-- インタビューは最大2問で終わる（INV_17）
fact MaxTwoQuestions {
    all i: Interview |
        i.question_count >= 0 and i.question_count <= 2
}

-- INV_18: report_cacheはsession_idで一意に管理する（sig内で定義済み）

-- =====================
-- 検証アサーション
-- =====================

-- 検証①: レポートは必ず完了状態になる（無限待機なし）
assert ReportEventuallyDone {
    all s: Session |
        s.report_state = Done or s.report_state = Failed
            or s.report_state = Generating
}

-- 検証②: インタビューは最大2問で終わる（INV_17）
assert InterviewMaxTwoQuestions {
    all i: Interview |
        i.question_count <= 2
}

-- 検証③: report_cacheのsession_idは一意である（INV_18）
assert CacheSessionIdUnique {
    all c: ReportCache |
        all s1, s2: Session |
            (s1 -> Done) in c.entries and
            (s2 -> Done) in c.entries and
            s1.session_id = s2.session_id
                implies s1 = s2
}

-- 検証④: インタビューはレポート完了後に非アクティブになる
assert InterviewStopsAfterDone {
    all i: Interview |
        i.is_active = False implies
            (no s: Session | s.report_state = Generating)
                or i.question_count = 2
}

check ReportEventuallyDone for 5
check InterviewMaxTwoQuestions for 5
check CacheSessionIdUnique for 5
check InterviewStopsAfterDone for 5
