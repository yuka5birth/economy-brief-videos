---
name: daily-keizai-reel
description: 毎朝の「今日の経済ニュース」Instagramリール（60秒・ナレーション＋BGM付き）を、情報収集から選定・台本・ファクトチェック・デザイン・動画書き出し・最終チェック・投稿記録まで一貫して制作する。「今日の経済ニュース動画を作って」「今朝のリールを作成」「デイリー経済リール」「経済ニュースの動画を作って」「今日のインスタ動画」などの依頼や、毎朝の定期タスクから呼ばれたときに使う。
---

# 毎朝の経済ニュースリール制作

会社員向けに、その日いちばん押さえておくべき経済ニュースを1本選び、60秒の縦型動画（1080×1920）と投稿文に仕上げる。各工程は専門のサブエージェントに任せ、このスキルは進行役として順番・受け渡し・差し戻しを管理する。

## 最初に読むもの

- `references/editorial-rules.md`：全工程のルール（視聴者、選び方、重複、フラットな表現、構成、ナレーション）。進行役も全文を読む。
- `references/post-log.md`：投稿記録スプレッドシートのIDと列。
- `references/story-schema.md`：動画の設計図 story.json の書き方。
- `references/publishing.md`：GitHubへの動画の配置、Bufferへの7:00予約、承認の通知。

以下、このスキルのフォルダ（「Base directory for this skill」に表示される絶対パス）を SKILL_DIR と呼ぶ。サブエージェントにはこの絶対パスを必ず渡す（サブエージェントからはプラグインの場所が分からないため）。

## 準備

1. 日本時間の今日の日付を確かめる（現在時刻のツールがあれば使う）。以下 DATE＝`YYYYMMDD`。
2. 作業フォルダ `reel-work/DATE/` を作る（以下 WORK。絶対パスで扱う）。
3. `bash SKILL_DIR/scripts/setup.sh` を実行する。`SETUP OK` 以外なら、何が足りないかをユーザーに伝えて止まる。
4. Google Sheets コネクタが使えることを確かめる（`get_values` で投稿記録の1行目を読む）。使えなければ、ユーザーにGoogle Sheetsコネクタを有効にするよう伝えて止まる。
5. Buffer コネクタが使えることを確かめる（`get_account`）。使えなければ、制作は続けて動画と投稿文をユーザーに送り、手動で投稿するよう伝える。

## 工程（サブエージェントを順番に呼ぶ）

サブエージェントは Agent ツールで呼ぶ。名前は下の表のとおり（環境によっては `keizai-news-reel:news-collector` のようにプラグイン名が前に付く）。各サブエージェントへの依頼文には、必ず SKILL_DIR、WORK、DATE、その工程で読むファイルと書くファイルを明記する。サブエージェント同士は会話を共有しないので、受け渡しはすべて WORK 内のファイルで行う。

| # | 工程 | サブエージェント | 読む | 書く |
|---|---|---|---|---|
| 1 | 情報収集 | news-collector | — | WORK/candidates.json |
| 2 | 選定・整理 | news-editor | candidates.json、投稿記録 | WORK/selection.md、WORK/brief.json |
| 3 | 台本 | script-writer | brief.json | WORK/story.json、WORK/caption.txt |
| 4 | ファクトチェック | fact-checker | brief.json、story.json、caption.txt | WORK/factcheck.md |
| 5 | デザイン | reel-designer | story.json | story.json（レイアウト調整）、WORK/stills/、WORK/design.md |
| 6 | 動画書き出し | video-producer | story.json | WORK/out/<output_name>.mp4、WORK/render.md |
| 7 | 最終チェック | final-reviewer | すべて | WORK/review.md |

### 差し戻しのルール

- 4のファクトチェックが `FAIL` のとき：factcheck.md の修正指示を添えて 3（script-writer）に戻し、修正後にもう一度 4 を行う。2回続けて FAIL なら、2（news-editor）に戻って次点の候補に切り替える。
- 5・6で文字を短くしたときは、事実の追加・変更がない（削っただけ）ことを reel-designer / video-producer が design.md・render.md に書く。事実が変わった場合は 4 をやり直す。
- 7の最終チェックが `差し戻し` のとき：review.md に書かれた戻り先の工程からやり直す。差し戻しは合計2回まで。3回目が必要になったら、制作を止めて理由をユーザーに報告する（投稿記録には `見送り` で1行残す）。
- 1で候補が足りない、2で重複しない候補が1本も無いときは、無理に作らず `見送り` として記録し、ユーザーに伝える。

## 仕上げ（承認つき自動投稿）

1. 投稿記録に1行追記する（`append_values`、range `'投稿記録'!A1`、列は post-log.md のとおり、ステータスは `制作済`）。
2. `references/publishing.md` の手順で、動画をGitHubに置き、Bufferに今日の7:00（日本時間）で予約し、投稿記録を `予約済` に更新する。
3. ユーザーに承認を依頼する：PushNotification で「7:00投稿予定「テーマ」。問題があればBufferアプリから取り消してください」と知らせ、SendUserMessage と SendUserFile で、テーマ（1行）・選んだ理由（1行）・続報かどうか・ファクトチェック結果・投稿文・動画を送る。
4. 予約に失敗したとき（GitHubに置けない、Bufferがエラー）は、動画と投稿文を送り、「今日は手動で投稿してください」と理由を添えて伝える。投稿記録のステータスは `制作済` のままにする。
5. 投稿されたかの確認は 7:20 の `keizai-reel-post-check` が行う。このスキルでは確認しない。

## 進行役が自分でやらないこと

- ニュースの選定・台本・事実確認・レイアウト判断を自分で済ませない。必ず担当のサブエージェントに任せ、その結果ファイルを読んで次に渡す。
- サブエージェントの結果をうのみにしない。各工程のあと、書かれるはずのファイルが実在し、空でないことを確かめてから次に進む。
