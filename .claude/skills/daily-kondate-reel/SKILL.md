---
name: daily-kondate-reel
description: 毎朝の「きょうの夕ごはん」Instagramリール（家族4人分・一汁二菜・1000円以内、約60秒・ナレーション＋BGM・AIイラスト）を、献立決め・価格調べ・レシピ照合・イラスト生成・台本・動画書き出し・最終チェック・投稿記録・Buffer予約まで一貫して制作する。「今日の献立動画を作って」「献立リールを作成」「きょうの夕ごはん動画」「デイリー献立」などの依頼や、毎朝の定期タスクから呼ばれたときに使う。
---

# 毎朝の献立リール制作

家族4人分・一汁二菜＋ごはん・食材費1000円以内の夕食献立を1つ決め、約60秒の縦型動画（1080×1920）と投稿文に仕上げる。各工程は専門のサブエージェントに任せ、このスキルは進行役として順番・受け渡し・差し戻しを管理する。

## 最初に読むもの

- `references/rules.md`：全工程のルール（テーマ、献立の決め方、価格、レシピ照合、イラスト、ナレーション、投稿文）。進行役も全文を読む。
- `references/post-log.md`：投稿記録スプレッドシートのIDと列。
- `references/story-schema.md`：動画の設計図 story.json の書き方。
- `references/publishing.md`：GitHubへの動画の配置、Bufferへの9:00予約、承認の通知。

以下、このスキルのフォルダ（「Base directory for this skill」に表示される絶対パス）を SKILL_DIR と呼ぶ。サブエージェントにはこの絶対パスを必ず渡す。

## 準備

1. 日本時間の今日の日付と曜日を確かめる（現在時刻のツールがあれば使う）。以下 DATE＝`YYYYMMDD`。
2. 作業フォルダ `kondate-work/DATE/` と、その中の `images/` を作る（以下 WORK。絶対パスで扱う）。
3. `bash SKILL_DIR/scripts/setup.sh` を実行する。`SETUP OK` 以外なら、何が足りないかをユーザーに伝えて止まる。
4. Google Sheets コネクタで投稿記録の1行目を読む（`get_values`）。使えなければ、ユーザーにGoogle Sheetsコネクタを有効にするよう伝えて止まる。
5. Figma コネクタが使えることを確かめる（`whoami`）。使えなければ、ユーザーにFigmaコネクタを有効にするよう伝えて止まる。
6. Buffer コネクタが使えることを確かめる（`get_account`）。使えなくても制作は続け、最後に動画と投稿文を送る。

## 工程（サブエージェントを順番に呼ぶ）

Agent ツールで呼ぶ（環境によっては `kondate-reel:kondate-menu-planner` のようにプラグイン名が前に付く。一覧に無いときは、`agents/<名前>.md`（リポジトリの写しでは `.claude/agents/<名前>.md`）の本文を依頼文の先頭に付けて general-purpose エージェントに渡す）。各依頼文には、SKILL_DIR、WORK、DATE（曜日も）、その工程で読むファイルと書くファイルを明記する。受け渡しはすべて WORK 内のファイルで行う。

| # | 工程 | サブエージェント | 読む | 書く |
|---|---|---|---|---|
| 1 | 献立と価格 | kondate-menu-planner | 投稿記録 | WORK/menu.json、WORK/menu.md |
| 2 | レシピ照合 | kondate-recipe-checker | menu.json | WORK/recipes.json、WORK/recipe_check.md（menu.json の量・金額を直すことがある） |
| 3 | イラスト | kondate-illustrator | menu.json、recipes.json | WORK/images/*.png、WORK/images.md |
| 4 | 台本と投稿文 | kondate-writer | menu.json、recipes.json、images.md | WORK/story.json、WORK/caption.txt |
| 5 | 動画書き出し | kondate-video-producer | story.json | WORK/stills/、WORK/out/<output_name>.mp4、WORK/render.md |
| 6 | 最終チェック | kondate-final-reviewer | すべて | WORK/review.md |

### 差し戻しのルール

- 2のレシピ照合が `FAIL`（根拠が2か所見つからない料理がある／量を直したら1000円を超えた）のとき：recipe_check.md の理由を添えて 1 に戻し、その料理を差し替えてもらう。2回続けて FAIL なら `見送り`。
- 3で、作り直しの上限（rules.md 5章）までに献立どおりの絵ができなかった料理があれば、その料理だけプログラムの絵に戻してよい（images.md に書く）。お盆の絵ができなければ、お盆もプログラムの絵に戻す。
- 5で文字を短くしたときは、意味・数字を変えていない（削っただけ）ことを render.md に書く。
- 6の最終チェックが `差し戻し` のとき：review.md に書かれた戻り先の工程からやり直す。差し戻しは合計2回まで。3回目が必要になったら制作を止め、投稿記録に `見送り` で1行残して理由をユーザーに知らせる。

## 仕上げ（承認つき自動投稿）

1. 投稿記録に1行追記する（`append_values`、range `'投稿記録'!A1`、列は post-log.md のとおり、ステータスは `制作済`）。review.md の「投稿記録に書く内容」を使う。
2. `references/publishing.md` を読む。Buffer のチャンネルが「未設定」なら予約せず、動画・投稿文・recipe_check.md を SendUserFile で送り、SendUserMessage で献立と合計金額を1〜2行で知らせて終える。
3. チャンネルが設定済みなら、publishing.md の手順で動画をGitHubに置き、Bufferに9:00で予約し、投稿記録を `予約済` に更新し、承認の通知を送る。
4. 予約に失敗したとき（GitHubに置けない、Bufferがエラー）は、動画と投稿文を送り、「今日は手動で投稿してください」と理由を添えて伝える。ステータスは `制作済` のまま。

## 進行役が自分でやらないこと

- 献立・価格・レシピ・絵・台本・レイアウトの判断を自分で済ませない。必ず担当のサブエージェントに任せ、その結果ファイルを読んで次に渡す。
- サブエージェントの結果をうのみにしない。各工程のあと、書かれるはずのファイルが実在し、空でないことを確かめてから次に進む。
