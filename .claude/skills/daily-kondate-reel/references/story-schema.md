# story.json（動画の設計図）の書き方

`scripts/kondate.py` が読む。実例は `examples/story-20261125.json`（投稿文の実例は `examples/caption-20261125.txt`）。

## 全体

| キー | 内容 | 例 |
|---|---|---|
| output_name | 出力ファイル名（拡張子なし） | `kondate_20261126` |
| series | シリーズ名（左上のラベル） | `きょうの夕ごはん` |
| style | 表紙の緑のラベル | `一汁二菜` |
| date_label | 各シーン右上の日付 | `11/26（木）` |
| date_long | 表紙の日付 | `11月26日（木）` |
| price_badge | 表紙の丸いバッジ（2行） | `["4人分で", "約930円"]` |
| note | 価格の注意書き（合計のシーンに出る） | rules.md 3章の文 |
| tray | お盆の4品の割り当て | `{"side1": "goma", "main": "teri", "rice": "rice", "soup": "soup"}` |
| ai_dir | AI画像のフォルダ（story.json からの相対パス） | `images` |
| ai_images | 料理キー → 画像ファイル名。`tray` はお盆全体の絵 | `{"tray": "tray.png", "teri": "main.png", "goma": "side.png", "soup": "soup.png"}` |
| scenes | シーンの配列（下の順番が基本） | |

- 料理キー（`teri` など）は自由な英小文字で決めてよい。`ai_images` に同じキーで画像を登録し、`tray`・`main.dish`・`pair.cards[].dish` から同じキーで指す。
- ごはんは `rice`（プログラムで描く絵）のままでよい。お盆の絵（`ai_images.tray`）があれば、お盆はその1枚が使われる。

## シーンの型（基本の並び）

すべてのシーンに `narration`（1〜2文、数字は漢字・かな）が必要。`min_duration`（秒）を付けると、その長さ以上になる。長さは基本、ナレーションの長さ＋約1.1秒で自動的に決まる。

1. **hook**（表紙・サムネイル。最初の1コマから全部見えている）：`min_duration: 4.5`
2. **menu**：`chip`（例：こんだて）、`title`（例：今日の4品）、`items`：`[{"cat": "主菜|副菜|汁物|主食", "name": "料理名"}]`（4つ）
3. **main**：`chip`（主菜）、`dish`（料理キー）、`title`：2行の配列（1行目は短め、2行目は料理名の最後の部分。例：`["鶏もも肉と大根の", "照り煮"]`）、`price`（例：約620円）、`points`：特長を3つ（各18字程度まで）
4. **howto**：`chip`（主菜の作り方）、`title`（例：3ステップ）、`steps`：3つ（長い行は `\n` で改行、1行17字程度まで）、`tip`：火の通りの見極め（例：大根に竹串がすっと通ればOK）、`min_duration: 8.0`
5. **pair**：`chip`（副菜・汁物）、`title`（10字以内）、`cards`：2枚 `[{"dish": 料理キー, "name": "料理名（長ければ\nで改行）", "price": "約90円", "desc": ["説明1行目", "説明2行目"]}]`（説明は各13字程度まで）
6. **cost**：`chip`（おかね）、`title`（1食の合計）、`rows`：`[["料理名", "620円"], ...]`（4行。ごはんも入れる）、`total`（例：約930円）、`stamp`：`["1000円", "以内！"]`
7. **shopping**：`chip`（かいもの）、`title`（買い物リスト）、`items`：`[["食材", "量"], ...]`（10個まで）、`ribbon`（保存してお買い物へ）、`min_duration: 7.0`
8. **steps**：`chip`（だんどり）、`title`（作る順番）、`badge`：`["おかず", "約30分"]`、`steps`：5つ（各16字程度まで）、`min_duration: 7.0`
9. **outro**：`title`：`["明日の献立も", "お楽しみに"]`、`sub`：2行、`cta`（フォロー・保存してね）、`handle`（`@kyou_no_yuugohan`）、`ai_note`（※AIが考えた献立です。分量は複数のレシピで確認しています。）、`min_duration: 4.0`

## コマンド

```
bash SKILL_DIR/scripts/setup.sh                                # 初回・毎回OK
python3 SKILL_DIR/scripts/kondate.py check  WORK/story.json    # 文字の長さ・はみ出し・画像の有無
python3 SKILL_DIR/scripts/kondate.py stills WORK/story.json WORK/stills   # 各シーンの完成画像
python3 SKILL_DIR/scripts/kondate.py render WORK/story.json WORK/out      # 動画（check も自動で行う）
```
