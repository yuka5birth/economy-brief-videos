# 投稿（承認つき自動投稿）

最終チェックが「承認」になった動画を、毎朝9:00（日本時間）にInstagramへ自動投稿されるよう予約し、ユーザーに通知する。ユーザーは9:00までにBufferのアプリで取り消し・修正できる（これが「承認」の機会）。

## 固定の設定

| 項目 | 値 |
|---|---|
| 動画置き場（GitHub） | `yuka5birth/economy-brief-videos`（公開）、フォルダ `kondate/`（経済ニュースの `videos/` とは分ける） |
| 動画の公開URL | `https://raw.githubusercontent.com/yuka5birth/economy-brief-videos/main/kondate/<ファイル名>.mp4` |
| Buffer の組織 | My Organization（`68e720bcf1f50a087b4a7497`） |
| Buffer のチャンネル | **未設定**（献立用のInstagramアカウントを作成中）。決まったらここにアカウント名とチャンネルIDを書く |
| 投稿時刻 | 毎朝 9:00（Asia/Tokyo） |
| Instagramの設定 | `type: reel`、`shouldShareToFeed: true`、`isAiGenerated: true`、`schedulingType: automatic` |

**チャンネルが「未設定」のあいだは予約しない。** 動画・投稿文・レシピチェックの記録を SendUserFile で送り、SendUserMessage で「献立アカウントが未設定のため予約していません。手動で投稿するか、アカウントができたら教えてください」と伝える。投稿記録のステータスは `制作済` のまま。経済ニュースのチャンネル（@economy_brief_daily）には**絶対に予約しない**。

## 手順（チャンネルが設定済みのとき）

1. **GitHubに置く**
   - リポジトリがこのセッションに無ければ、`add_repo`（owner `yuka5birth`、repo `economy-brief-videos`、access `push`）で追加し、指示どおり1回だけ clone する。
   - `kondate/` に mp4 をコピーし、`git add` → `git commit -m "Add kondate reel YYYY-MM-DD"` → `git -c push.negotiate=true push`。コミットの名前とメールは `yuka5birth` / `yuka5birth@users.noreply.github.com`。
   - `kondate/` の7日より古い動画は同じコミットで `git rm` して消す（`videos/` には触らない）。
   - push が「Claude doesn't have GitHub access」で拒否されたら、予約せずに止まり、ユーザーに「ClaudeのGitHubアプリに economy-brief-videos への書き込みを許可してください」と伝える。
2. **公開URLを確かめる**：`curl -sIL <URL>` で `HTTP/2 200` と `content-length` が mp4 のサイズと一致すること。最大3回・30秒おきに確かめる。
3. **Bufferに予約する**：`create_post`
   - `channelId`：上の表、`schedulingType`：`automatic`、`mode`：`customScheduled`
   - `dueAt`：今日の `09:00:00+09:00`。`get_account` の `currentTime` が 8:45 を過ぎていたら、`currentTime` の30分後（5分単位に切り上げ）にする
   - `text`：caption.txt の全文
   - `assets`：`[{"video": {"url": "<公開URL>", "metadata": {"thumbnailOffset": 0}}}]`（0秒＝表紙の1コマ目がサムネイルになる）
   - `metadata`：`{"instagram": {"type": "reel", "shouldShareToFeed": true, "isAiGenerated": true}}`
   - 返ってきた投稿の `status` が `scheduled` であることを確かめる。`error` があれば予約できていないので、ユーザーに伝えて止まる。
4. **投稿記録を更新する**：その日の行の K列（ステータス）を `予約済`、L列（投稿URL）に `Buffer予約 <post id>` と書く。
5. **ユーザーに通知する（承認の依頼）**：PushNotification（届かない環境では SendUserMessage）で、1行で：
   `9:00投稿予定「<主菜名>ほか 約〇〇〇円」。問題があればBufferアプリの予約投稿から取り消してください`
   あわせて SendUserMessage で献立・合計金額・レシピ照合の結果・投稿文を、SendUserFile で動画を送る。

## 投稿後の確認（9:20の確認タスク）

`kondate-reel-post-check` スキルが行う。
