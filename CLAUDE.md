# economy-brief-videos

Instagram @economy_brief_daily（ECONOMY BRIEF）の毎朝の経済ニュースリールと、献立リール「きょうの夕ごはん」の制作・投稿用リポジトリ。

- `videos/`：Buffer が読み込む公開動画置き場（7日より古いものは自動で削除）
- `.claude/skills/daily-keizai-reel/`：毎朝の制作〜予約投稿の手順（進行役）。SKILL_DIR はこのフォルダの絶対パス
- `.claude/skills/keizai-reel-post-check/`：7:20 の投稿確認
- `.claude/agents/`：工程ごとのサブエージェント（news-collector, news-editor, script-writer, fact-checker, reel-designer, video-producer, final-reviewer）

このリポジトリの `.claude/` は keizai-news-reel プラグインの写しです。プラグインが読み込まれていない定期実行では、こちらを使います。

## 献立リール（きょうの夕ごはん）

- `kondate/`：献立リールの公開動画置き場（7日より古いものは削除）。`videos/` とは混ぜない
- `.claude/skills/daily-kondate-reel/`：毎朝の献立リール制作〜9:00予約の手順（進行役）。SKILL_DIR はこのフォルダの絶対パス
- `.claude/skills/kondate-reel-post-check/`：9:20 の投稿確認
- `.claude/agents/kondate-*.md`：工程ごとのサブエージェント（kondate-menu-planner, kondate-recipe-checker, kondate-illustrator, kondate-writer, kondate-video-producer, kondate-final-reviewer）

これらは kondate-reel プラグインの写しです。プラグインが読み込まれていない定期実行では、こちらを使います。

