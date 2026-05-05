-- Phase 3b Tool Selector 形式仕様
-- 検証目標：全質問が必ずいずれか1つのTypeに分類される
--           同時に複数のTypeに分類されることはない

module tool_selector

-- 質問の型
abstract sig Question {}

-- Typeの型
abstract sig ToolType {}
one sig TYPE0, TYPE1, TYPE2 extends ToolType {}

-- キーワードの型
abstract sig Keyword {}
sig GreetingKW, ThankKW, StorageKW extends Keyword {}  -- TYPE_0
sig RegionKW, SeasonKW, UsageKW extends Keyword {}     -- TYPE_1
sig AmbiguousKW extends Keyword {}                     -- TYPE_2

-- 質問とキーワードの関係
sig UserQuestion extends Question {
    keywords: set Keyword,
    classified_as: one ToolType
}

-- 分類ルール
fact ClassificationRules {
    all q: UserQuestion |
        -- TYPE_0: 挨拶・感謝・保存・栄養キーワードがある
        (some k: q.keywords | k in (GreetingKW + ThankKW + StorageKW))
            implies q.classified_as = TYPE0

        -- TYPE_1: 地域・季節・用途キーワードがある（TYPE_0でない）
        else (some k: q.keywords | k in (RegionKW + SeasonKW + UsageKW))
            implies q.classified_as = TYPE1

        -- TYPE_2: それ以外
        else q.classified_as = TYPE2
}

-- 検証①: 全質問は必ず1つのTypeに分類される（排他性）
assert ExclusiveClassification {
    all q: UserQuestion |
        one t: ToolType | q.classified_as = t
}

-- 検証②: TYPE_0の質問にはRAGを適用しない（回避ゴール）
assert NoRAGForGreeting {
    all q: UserQuestion |
        q.classified_as = TYPE0
            implies q.classified_as != TYPE2
}

-- 検証③: キーワードなし質問はTYPE_2に落ちる
assert EmptyKeywordFallsToRAG {
    all q: UserQuestion |
        no q.keywords implies q.classified_as = TYPE2
}

check ExclusiveClassification for 10
check NoRAGForGreeting for 10
check EmptyKeywordFallsToRAG for 10
