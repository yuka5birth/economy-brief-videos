# 投稿記録（Googleスプレッドシート）

- ファイル名：献立リール 投稿記録
- スプレッドシートID：`1McrMfOLByvTwDzUH8HL3wvRabswI4M2aC-JGN0UwT-Y`
- URL：https://docs.google.com/spreadsheets/d/1McrMfOLByvTwDzUH8HL3wvRabswI4M2aC-JGN0UwT-Y/edit
- タブ名：`投稿記録`
- 使うコネクタ：Google Sheets（読み：`get_values`、追記：`append_values`、更新：`update_values`）

## 列

| 列 | 見出し | 書き方 |
|---|---|---|
| A | 投稿日 | `2026-11-26`（日本時間の投稿予定日） |
| B | 主菜 | 料理名 |
| C | 副菜 | 料理名 |
| D | 汁物 | 料理名 |
| E | 主な食材（重複判定用） | ` / ` 区切り。主菜の主材料を先頭に（例：鶏もも肉 / 大根 / にんじん / 玉ねぎ） |
| F | 合計金額 | `約930円` |
| G | 価格の根拠 | 主な出典を短く（例：農水省 食品価格動向調査 2026年11月、米 5kg 2,747円） |
| H | レシピ照合 | `PASS（主菜3件・副菜2件・汁物2件）` のように件数つき。差し戻しがあれば回数も |
| I | イラスト | 生成枚数（作り直しを含む）。例：`4枚（8クレジット）` |
| J | 動画ファイル | 出力ファイル名（.mp4） |
| K | ステータス | `制作済` / `予約済` / `投稿済` / `投稿エラー` / `取消` / `見送り` |
| L | 投稿URL | 予約時は `Buffer予約 <post id>`、投稿後は InstagramのURL |
| M | メモ | 見送りの理由、差し戻しの内容、気づいたこと |

## 使い方

- 読む：`get_values` で `'投稿記録'!A:M`。直近30日分を、かぶり判定（rules.md 2章）に使う。
- 追記：制作完了後に `append_values`、range は `'投稿記録'!A1`。
- ステータスの「予約済」は daily-kondate-reel が、「投稿済／投稿エラー／取消」は kondate-reel-post-check が書く。
- 見送った日も `見送り` で1行残し、理由をM列に書く。
