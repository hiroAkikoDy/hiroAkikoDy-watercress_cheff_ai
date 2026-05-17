// 自己進化グラフ用スキーマ初期化
// 既存の制約・インデックスには影響しない

// StagedChange: エージェントの提案を一時保存する下書きノード
CREATE CONSTRAINT staged_change_id IF NOT EXISTS
  FOR (s:StagedChange) REQUIRE s.id IS UNIQUE;

// BackfillTask: 不足データの補充タスクを管理するノード
CREATE CONSTRAINT backfill_task_id IF NOT EXISTS
  FOR (t:BackfillTask) REQUIRE t.id IS UNIQUE;

// status でフィルタするためのインデックス
CREATE INDEX staged_status IF NOT EXISTS
  FOR (s:StagedChange) ON (s.status);

// 優先度順で取得するためのインデックス
CREATE INDEX backfill_priority IF NOT EXISTS
  FOR (t:BackfillTask) ON (t.priority);
