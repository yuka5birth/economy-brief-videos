---
name: kondate-reel-post-check
description: 毎朝9:00に予約した献立リールが、Instagramに実際に投稿されたかをBufferで確かめ、献立リールの投稿記録スプレッドシートを「投稿済／投稿エラー／取消」に更新し、失敗していればユーザーに通知する。「今朝の献立リールは投稿された？」「献立の投稿の確認」や、9:20の定期タスクから呼ばれたときに使う。
---

# 今朝の献立リール投稿の確認

1. 日本時間の今日の日付を確かめる。
2. daily-kondate-reel スキルの `references/publishing.md` を読み、Buffer のチャンネルを確かめる。チャンネルが「未設定」なら、何もせず「献立アカウント未設定のため確認なし」と1行報告して終える（通知は送らない）。
3. 投稿記録を読む：Google Sheets `get_values`、スプレッドシートID `1McrMfOLByvTwDzUH8HL3wvRabswI4M2aC-JGN0UwT-Y`、range `'投稿記録'!A:M`。今日の行を探す。無ければ「今日の行がない（制作が止まった可能性）」として PushNotification（届かなければ SendUserMessage）で知らせて終える。
4. 今日の行のステータス（K列）が `見送り` または `制作済`（予約していない）なら何もせず終える。
5. Buffer で確かめる：L列に `Buffer予約 <id>` があれば `get_post` でその投稿を見る。無ければ `list_posts`（organizationId `68e720bcf1f50a087b4a7497`、channelIds は publishing.md のチャンネル、dueAt を今日の 0:00〜23:59（+09:00））。
6. 結果に応じて今日の行を `update_values` で更新する：
   - `sent`：K列 `投稿済`、L列に `externalLink`（InstagramのURL）
   - `error`：K列 `投稿エラー`、M列の末尾に「／投稿エラー：<error の内容>」を追記。PushNotification（届かなければ SendUserMessage）で「今朝の献立リール投稿が失敗しました：<要点>。動画は <GitHubの公開URL> にあります」と知らせる
   - まだ `scheduled`（予約時刻を過ぎていない）：何もしない
   - 今日の予約が見つからない：K列 `取消`（ユーザーが取り消したとみなす）
7. 最後に1行で結果を報告する。正常（投稿済）のときは通知を送らない。
