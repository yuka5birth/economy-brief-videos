# economy-brief-videos

Instagram @economy_brief_daily（ECONOMY BRIEF）の毎朝の経済ニュースリールの制作・投稿用リポジトリ。

- `videos/`：Buffer が読み込む公開動画置き場（7日より古いものは自動で削除）
- `.claude/skills/daily-keizai-reel/`：毎朝の制作〜予約投稿の手順（進行役）。SKILL_DIR はこのフォルダの絶対パス
- `.claude/skills/keizai-reel-post-check/`：7:20 の投稿確認
- `.claude/agents/`：工程ごとのサブエージェント（news-collector, news-editor, script-writer, fact-checker, reel-designer, video-producer, final-reviewer）

このリポジトリの `.claude/` は keizai-news-reel プラグインの写しです。プラグインが読み込まれていない定期実行では、こちらを使います。
