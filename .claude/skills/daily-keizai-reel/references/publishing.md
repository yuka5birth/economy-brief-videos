# 投稿（承認つき自動投稿）

最終チェックが「承認」になった動画を、7:00（日本時間）にInstagramへ自動投稿されるよう予約し、ユーザーに通知する。ユーザーは7:00までにBufferのアプリで取り消し・修正できる（これが「承認」の機会）。

## 固定の設定

| 項目 | 値 |
|---|---|
| 動画置き場（GitHub） | `yuka5birth/economy-brief-videos`（公開）、フォルダ `videos/` |
| 動画の公開URL | `https://raw.githubusercontent.com/yuka5birth/economy-brief-videos/main/videos/<ファイル名>.mp4` |
| Buffer の組織 | My Organization（`68e720bcf1f50a087b4a7497`） |
| Buffer のチャンネル | Instagram @economy_brief_daily（`6b06457c8541f09ecb95871a`）。IDが変わっていたら `list_channels` で確かめる |
| 投稿時刻 | 毎朝 7:00（Asia/Tokyo） |
| Instagramの設定 | `type: reel`、`shouldShareToFeed: true`、`isAiGenerated: true`、`schedulingType: automatic` |

## 手順

1. **GitHubに置く**
   - リポジトリがこのセッションに無ければ、`add_repo`（owner `yuka5birth`、repo `economy-brief-videos`、access `push`）で追加し、指示どおり1回だけ clone する。
   - `videos/` に mp4 をコピーし、`git add` → `git commit -m "Add reel YYYY-MM-DD"` → `git -c push.negotiate=true push`。コミットの名前とメールは `yuka5birth` / `yuka5birth@users.noreply.github.com`。
   - 7日より古い動画は同じコミットで `git rm` して消す（Instagramに投稿済みの動画はBuffer・Instagram側に残るので問題ない）。
   - push が「Claude doesn't have GitHub access」で拒否されたら、予約せずに止まり、ユーザーに「ClaudeのGitHubアプリに economy-brief-videos への書き込みを許可してください」と伝える。
2. **公開URLを確かめる**：`curl -sIL <URL>` で `HTTP/2 200` と `content-length` が mp4 のサイズと一致すること。push 直後は数十秒かかることがあるので、最大3回・30秒おきに確かめる。
3. **Bufferに予約する**：`create_post`
   - `channelId`：上の表、`schedulingType`：`automatic`、`mode`：`customScheduled`
   - `dueAt`：今日の `07:00:00+09:00`。`get_account` の `currentTime` が 6:45 を過ぎていたら、取り消しの余裕を残すため `currentTime` の30分後（5分単位に切り上げ）にする
   - `text`：caption.txt の全文
   - `assets`：`[{"video": {"url": "<公開URL>", "metadata": {"thumbnailOffset": 0}}}]`（0秒＝hookの1コマ目がサムネイルになる）
   - `metadata`：`{"instagram": {"type": "reel", "shouldShareToFeed": true, "isAiGenerated": true}}`
   - 返ってきた投稿の `status` が `scheduled`、`assets[0].video.durationMs` が約60000であることを確かめる。`error` があれば予約できていないので、ユーザーに伝えて止まる。
4. **投稿記録を更新する**：その日の行の L列（ステータス）を `予約済`、M列（投稿URL）に `Buffer予約 <post id>` と書く。
5. **ユーザーに通知する（承認の依頼）**：PushNotification（届かない環境では SendUserMessage）で、200文字以内・1行で：
   `7:00投稿予定「<テーマ>」。問題があればBufferアプリの予約投稿から取り消してください`
   あわせて SendUserMessage で、テーマ・選んだ理由・ファクトチェック結果・投稿文・動画（SendUserFile）を送る。

## 投稿後の確認（7:20の確認タスク）

`keizai-reel-post-check` スキルが行う。Bufferの当日の投稿を `list_posts`（status: sent / error / scheduled）で確かめ、
- `sent`：投稿記録の L列を `投稿済`、M列に `externalLink`（InstagramのURL）
- `error`：L列を `投稿エラー`、H列の末尾にエラー内容を追記し、ユーザーに通知（手動で投稿するよう依頼）
- 予約が消えている：ユーザーが取り消したとみなし、L列を `取消`
