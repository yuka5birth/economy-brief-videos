---
name: keizai-reel-post-check
description: 毎朝7:00に予約した経済ニュースリールが、Instagramに実際に投稿されたかをBufferで確かめ、投稿記録スプレッドシートを「投稿済／投稿エラー／取消」に更新し、失敗していればユーザーに通知する。「今朝のリールは投稿された？」「投稿の確認」「リールの投稿チェック」や、7:20の定期タスクから呼ばれたときに使う。
---

# 今朝のリール投稿の確認

1. 日本時間の今日の日付を確かめる。
2. 投稿記録を読む：Google Sheets `get_values`、スプレッドシートID `1Y3GSoRvbH_xEaLbZUQVdotP6cflNNREdtROphPPz3jI`、range `'投稿記録'!A:M`。今日の行を探す。無ければ「今日の行がない（制作が止まった可能性）」としてユーザーに通知して終える。
3. 今日の行のステータス（L列）が `見送り` なら何もせず終える。
4. Buffer の `list_posts` で確かめる：organizationId `68e720bcf1f50a087b4a7497`、channelIds `["6b06457c8541f09ecb95871a"]`、dueAt を今日の 0:00〜23:59（+09:00）、status は指定しない。M列に `Buffer予約 <id>` があれば、その id を `get_post` で直接見てもよい。
5. 結果に応じて今日の行を `update_values` で更新する：
   - `sent`：L列 `投稿済`、M列に `externalLink`（InstagramのURL）
   - `error`：L列 `投稿エラー`、H列の末尾に「／投稿エラー：<error の内容>」を追記。PushNotification（届かなければ SendUserMessage）で「今朝のリール投稿が失敗しました：<要点>。動画は <GitHubの公開URL> にあります」と知らせる
   - まだ `scheduled`（予約時刻を過ぎていない）：何もしない
   - 今日の予約が見つからない：L列 `取消`（ユーザーが取り消したとみなす）
6. 最後に1行で結果を報告する。正常（投稿済）のときは通知を送らない。
