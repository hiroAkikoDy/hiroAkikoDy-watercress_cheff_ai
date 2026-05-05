module phase4_dialog

-- =====================
-- 基本型定義
-- =====================

abstract sig ToolType {}
one sig TYPE0, TYPE1, TYPE3 extends ToolType {}

-- 対話の状態
abstract sig DialogState {}
one sig Waiting,    -- ユーザー入力待ち
        Collecting, -- 条件収集中
        Complete    -- 条件収集完了
    extends DialogState {}

-- 収集する条件
abstract sig Condition {}
sig PersonCount, Genre, Usage extends Condition {}

-- 対話セッション
sig DialogSession {
    turn: Int,              -- 現在の往復数（0〜3）
    state: one DialogState,
    collected: set Condition
}

-- ペルソナの順序
abstract sig Persona {}
one sig MC, Chef, Nutritionist extends Persona {}

sig PersonaOutput {
    speaker: one Persona,
    order: Int  -- 発言順序（1〜4）
}

-- =====================
-- 制約（INV_11〜INV_14）
-- =====================

-- INV_11: TYPE_3はTYPE_0・TYPE_1に分類されないものすべて
fact TYPE3IsDefault {
    -- TYPE_0・TYPE_1はそれぞれ排他的な集合
    -- TYPE_3はその補集合
    TYPE0 != TYPE1
    TYPE0 != TYPE3
    TYPE1 != TYPE3
}

-- INV_12: 対話は最大3往復で完了する
fact MaxThreeTurns {
    all s: DialogSession |
        s.turn >= 0 and s.turn <= 3
}

-- 3往復目で強制完了
fact ForceCompleteAtTurn3 {
    all s: DialogSession |
        s.turn = 3 implies s.state = Complete
}

-- INV_13: ペルソナの発言順序
fact PersonaOrder {
    -- 司会が最初（order=1）
    all p: PersonaOutput |
        p.speaker = MC and p.order = 1
            or p.speaker = Chef and p.order = 2
            or p.speaker = Nutritionist and p.order = 3
            or p.speaker = MC and p.order = 4

    -- 発言順序は1〜4の範囲
    all p: PersonaOutput |
        p.order >= 1 and p.order <= 4
}

-- INV_14: TYPE_2は存在しない（TYPE_3に統合済み）
fact NoTYPE2 {
    no t: ToolType |
        t != TYPE0 and t != TYPE1 and t != TYPE3
}

-- =====================
-- 検証アサーション
-- =====================

-- 検証①: 対話は必ず3往復以内で完了する（無限ループなし）
assert NoInfiniteDialog {
    all s: DialogSession |
        s.turn <= 3
}

-- 検証②: 3往復目は必ずCompleteになる（強制完了）
assert ForceCompleteWorks {
    all s: DialogSession |
        s.turn = 3 implies s.state = Complete
}

-- 検証③: MCは必ず最初と最後に発言する（order=1とorder=4）
assert MCLeadsAndCloses {
    all p: PersonaOutput |
        p.speaker = MC implies
            (p.order = 1 or p.order = 4)
}

-- 検証④: ChefとNutritionistはMCの間に発言する
assert ExpertsInMiddle {
    all p: PersonaOutput |
        p.speaker = Chef implies p.order = 2
    all p: PersonaOutput |
        p.speaker = Nutritionist implies p.order = 3
}

check NoInfiniteDialog for 5
check ForceCompleteWorks for 5
check MCLeadsAndCloses for 5
check ExpertsInMiddle for 5
