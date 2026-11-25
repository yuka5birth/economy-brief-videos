# story.json の書き方（動画の設計図）

`scripts/reel.py` はこのJSONだけを読んで動画を作る。完成例は `examples/story-20261125.json`。

## トップレベル

| キー | 必須 | 内容 |
|---|---|---|
| output_name | ○ | 出力ファイル名（拡張子なし）。`reel_YYYYMMDD_テーマ英字` |
| date_label | ○ | 画面右上の日付。`2026.11.25  WED`（スペース2つ） |
| brand | | 左上の誌名。既定 `ECONOMY BRIEF` |
| sources | ○ | 画面下の出典。`ロイター、日経ほか（11/25時点の報道）` 40字以内 |
| total_seconds | | 既定 60 |
| scenes | ○ | シーンの配列。先頭は hook、最後は outro |

## 全シーン共通

| キー | 内容 |
|---|---|
| type | 下のシーン型のどれか |
| duration | 秒数（小数可）。全シーンの合計が total_seconds と一致すること |
| narration | 読み上げ原稿（editorial-rules.md 9章のルールで書く） |

章シーン（hook・outro以外）は共通で次も必須：

| キー | 内容 | 上限 |
|---|---|---|
| section | 章の小見出し（例：何が起きたのか） | 12字 |
| heading | 見出し。1〜2行の配列 | 1行あたり全角10字前後 |
| body | 本文（自動で折り返す） | 折り返し後5行（約110字） |

## シーン型

### hook（つかみ。1コマ目から全部表示＝サムネイル）
```json
{"type":"hook","duration":4,"kicker":"深掘り｜米国の通商政策",
 "headline":["米国の新関税、","第2弾へ。"],
 "lead":"日本を含む16か国・地域に関税を上乗せする方針が明らかになった。",
 "stat":{"value":"16","unit":"か国・地域が対象","sub":"中国・EU・日本・韓国など"},
 "narration":"..."}
```
- headline：1行あたり全角7字まで、2行まで
- lead：折り返し後4行まで
- stat.value：短い数字（3字以内が最も大きく表示される）。数字がないニュースでは stat を省く
- 続報のときは kicker を「続報｜〜」にする

### text（見出し＋本文だけ）
章共通キーのみ。

### grid（名前の一覧。対象国・企業など）
```json
"grid":{"label":"調査対象の16か国・地域","columns":4,"items":["中国","EU","日本"],"highlight":["日本"]}
```
- items 20個まで。1項目は全角7字まで（columns 4のとき）。長い名前が多いときは columns 3

### timeline（年表）
```json
"timeline":[{"date":"2026.02","event":"最高裁が無効と判断"},
            {"date":"2026.11","event":"第2弾を発表へ","highlight":true}]
```
- 5項目まで。event は全角18字まで。今回のニュースに highlight

### bars（横棒グラフ）
```json
"chart":{"title":"日本からの輸出品にかかる関税","rows":[
   {"label":"現在","value":12.5,"display":"12.5%","label_inside":true},
   {"label":"今後","value":15,"display":"最大15%？","highlight":true}],
 "marker":{"value":15,"label":"日米合意の上限"},
 "note":"※自動車・部品（15%）は別の関税で課税中"}
```
- rows 3本まで。label は全角3字まで。value は数値
- 最大の棒のラベルは棒の外（右）に出る。長いラベル（6字超）は label_inside:true にする
- marker（点線）は任意

### table（数字の一覧。市場の動きなど）
```json
"rows":[{"date":"11/24","name":"ナスダック総合指数","value":"−1.48%","note":"終値ベース"}]
```
- 3行まで。マイナスは全角の「−」を使う。value は短く（7字以内が理想）
- highlight:false にすると数字が黒になる（既定は赤）

### points（今後の予定・確認すべき点）
```json
"points":[{"title":"日本の税率","sub":"日米合意の15%以内に収まるか"}]
```
- 3つまで。title 全角8字まで、sub 全角22字まで

### summary（押さえておきたいポイント）
```json
"takeaways":["米国が日本を含む16か国・地域に関税の上乗せを準備","..."]
```
- 3つまで。1つ全角40字まで（2行に折り返す）

### outro（締め）
```json
{"type":"outro","duration":5,"narration":"明日も、最新のニュースをお届けします。お見逃しなく。"}
```
- 文言は固定（headline・sub・disclaimer を上書きできるが、通常は書かない）

## コマンド

```
python scripts/reel.py check  story.json          # 文字のはみ出し・秒数・必須項目を検査
python scripts/reel.py stills story.json OUT/     # 各シーンの完成状態のPNGと一覧（contact_sheet.png）
python scripts/reel.py audio  story.json OUT.wav  # ナレーションが各シーンに収まるかを表示
python scripts/reel.py render story.json OUT/     # 動画を書き出す（約1分）
```

audio/render の表示で `TOO LONG` が出たシーンは、ナレーションを短くする（話す速さの上限は1.3倍）。
