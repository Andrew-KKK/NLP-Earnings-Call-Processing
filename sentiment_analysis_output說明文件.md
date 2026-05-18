# sentiment_analysis.py Output 說明文件

## 1. Output 輸出位置

`sentiment_analysis.py` 執行完成後，會依照 `config.ini` 中的 `output_dir` 與 `company_prefix` 建立輸出資料夾。

```text
{output_dir}/{company_prefix}/
```

範例：

```text
sentiment_output/nvda/
```

---

## 2. Output 檔案總覽

目前程式會輸出三個必要 JSON 檔案：

```text
sentiment_output/{company_prefix}/
├── qna_sentiment_summary.json
├── section_sentiment_summary.json
└── company_tone_shift_summary.json
```

| 檔案名稱 | 分析層級 | 主要用途 |
|---|---|---|
| `qna_sentiment_summary.json` | 單題 Q&A | 分析每一題問題與回答的語氣落差 |
| `section_sentiment_summary.json` | 段落類型 | 比較 prepared、question、answer 的整體情緒 |
| `company_tone_shift_summary.json` | 公司層級 | 比較 Prepared Remarks 與 Q&A Answer 的語氣轉變 |

建議閱讀順序：

```text
company_tone_shift_summary.json
        ↓
section_sentiment_summary.json
        ↓
qna_sentiment_summary.json
```

---

# 3. qna_sentiment_summary.json

## 3.1 檔案用途

`qna_sentiment_summary.json` 是最重要的 output，分析單位是「每一組 Q&A」。

每一筆資料代表：

```text
一位分析師的問題 + 管理層對該問題的回答
```

主要用途：

1. 判斷分析師是否提出負面問題。
2. 比較管理層回答是否比問題更正向或中性。
3. 找出可能存在風險淡化的 Q&A。
4. 建立後續人工複查清單。

---

## 3.2 JSON 結構

```json
{
  "metadata": {
    "module": "qna_sentiment_summary",
    "company": "nvda",
    "description": "Question-answer sentiment comparison and tone gap results.",
    "total_records": 10
  },
  "qna_results": [
    {
      "company": "nvda",
      "pair_id": 1,
      "question_text": "...",
      "question_sentiment": "negative",
      "question_positive_score": 0.05,
      "question_neutral_score": 0.30,
      "question_negative_score": 0.65,
      "answer_text": "...",
      "answer_sentiment": "positive",
      "answer_positive_score": 0.60,
      "answer_neutral_score": 0.35,
      "answer_negative_score": 0.05,
      "tone_gap_label": "negative_question_positive_answer",
      "negative_question_soft_answer_flag": true,
      "negative_score_gap": 0.60,
      "risk_downplay_flag": true
    }
  ]
}
```

---

## 3.3 qna_results 欄位說明

| 欄位名稱 | 說明 |
|---|---|
| `company` | 公司代號 |
| `pair_id` | Q&A 配對編號 |
| `question_text` | 分析師問題原文 |
| `answer_text` | 管理層回答原文 |
| `question_sentiment` | 問題情緒分類，可能為 positive / neutral / negative |
| `answer_sentiment` | 回答情緒分類，可能為 positive / neutral / negative |
| `question_positive_score` | 問題正向分數 |
| `question_neutral_score` | 問題中性分數 |
| `question_negative_score` | 問題負向分數 |
| `answer_positive_score` | 回答正向分數 |
| `answer_neutral_score` | 回答中性分數 |
| `answer_negative_score` | 回答負向分數 |
| `tone_gap_label` | 問題與回答的語氣落差分類 |
| `negative_question_soft_answer_flag` | 負面問題是否被較溫和地回答 |
| `negative_score_gap` | 問題與回答的負向分數差距 |
| `risk_downplay_flag` | 是否可能存在風險淡化 |

---

## 3.4 重要欄位解讀

### tone_gap_label

`tone_gap_label` 用來描述問題與回答的情緒組合。

| tone_gap_label | 意義 |
|---|---|
| `aligned` | 問題與回答情緒一致 |
| `negative_question_positive_answer` | 問題偏負面，但回答偏正向 |
| `negative_question_neutral_answer` | 問題偏負面，但回答偏中性 |
| `neutral_question_positive_answer` | 問題偏中性，但回答偏正向 |
| `positive_question_less_positive_answer` | 問題偏正向，但回答較不正向 |
| `unknown` | 問題或回答情緒缺失 |

---

### negative_question_soft_answer_flag

判斷邏輯：

```text
question_sentiment == negative
且 answer_sentiment 是 neutral 或 positive
```

| 值 | 意義 |
|---|---|
| `true` | 負面問題被中性或正向回答，適合人工複查 |
| `false` | 未出現此情況 |

---

### negative_score_gap

計算方式：

```text
negative_score_gap = question_negative_score - answer_negative_score
```

| negative_score_gap | 解讀 |
|---:|---|
| 大於 0 | 問題比回答更負面 |
| 接近 0 | 問題與回答負面程度接近 |
| 小於 0 | 回答比問題更負面 |

範例：

```text
question_negative_score = 0.75
answer_negative_score = 0.20
negative_score_gap = 0.55
```

代表分析師問題明顯比管理層回答更負面。

---

### risk_downplay_flag

判斷邏輯：

```text
negative_score_gap > 0.4
```

| 值 | 意義 |
|---|---|
| `true` | 可能存在風險淡化，需要人工複查 |
| `false` | 未偵測到明顯風險淡化訊號 |

注意：`risk_downplay_flag = true` 不代表公司一定說謊，只代表問題與回答之間存在明顯語氣差異。

---

## 3.5 建議使用方式

後續同學可優先篩選：

```text
risk_downplay_flag == true
```

再依照：

```text
negative_score_gap 由大到小排序
```

找出最值得人工閱讀的 Q&A。

適合製作：

| 圖表 / 表格 | 用途 |
|---|---|
| Q&A tone gap table | 顯示每題問題與回答的情緒落差 |
| negative_score_gap bar chart | 排序顯示語氣落差最大的 Q&A |
| risk_downplay_flag count | 統計可能風險淡化題數 |
| 高風險 Q&A 清單 | 供人工複查與報告撰寫 |

---

# 4. section_sentiment_summary.json

## 4.1 檔案用途

`section_sentiment_summary.json` 是段落層級的情緒摘要，用來比較同一家公司在不同段落類型中的平均情緒分數。

目前段落類型包含：

```text
prepared
question
answer
```

---

## 4.2 JSON 結構

```json
{
  "metadata": {
    "module": "section_sentiment_summary",
    "company": "nvda",
    "description": "Average sentiment scores by company and section type.",
    "total_records": 3
  },
  "section_results": [
    {
      "company": "nvda",
      "section_type": "prepared",
      "positive_score": 0.70,
      "neutral_score": 0.25,
      "negative_score": 0.05
    },
    {
      "company": "nvda",
      "section_type": "question",
      "positive_score": 0.20,
      "neutral_score": 0.45,
      "negative_score": 0.35
    },
    {
      "company": "nvda",
      "section_type": "answer",
      "positive_score": 0.55,
      "neutral_score": 0.35,
      "negative_score": 0.10
    }
  ]
}
```

---

## 4.3 section_results 欄位說明

| 欄位名稱 | 說明 |
|---|---|
| `company` | 公司代號 |
| `section_type` | 段落類型，包含 prepared / question / answer |
| `positive_score` | 該段落類型的平均正向分數 |
| `neutral_score` | 該段落類型的平均中性分數 |
| `negative_score` | 該段落類型的平均負向分數 |

---

## 4.4 section_type 解讀

| section_type | 意義 | 解讀重點 |
|---|---|---|
| `prepared` | 公司簡報段落 | 公司主動想傳達的敘事，通常較正向 |
| `question` | 分析師問題 | 若 negative_score 高，代表市場疑慮較強 |
| `answer` | 管理層回答 | 可觀察公司面對追問時是否更保守或更樂觀 |

---

## 4.5 解讀範例

| company | section_type | positive_score | neutral_score | negative_score |
|---|---|---:|---:|---:|
| nvda | prepared | 0.70 | 0.25 | 0.05 |
| nvda | question | 0.20 | 0.45 | 0.35 |
| nvda | answer | 0.55 | 0.35 | 0.10 |

可解讀為：

1. 公司簡報明顯偏正向。
2. 分析師問題比公司簡報更負面。
3. 管理層回答比問題更正向。
4. 後續可回到 `qna_sentiment_summary.json` 找出具體是哪幾題造成差異。

---

## 4.6 建議視覺化

| 圖表 | 用途 |
|---|---|
| grouped bar chart | 比較 prepared、question、answer 的正中負分數 |
| stacked bar chart | 顯示各段落的情緒比例 |
| radar chart | 呈現不同段落的語氣結構 |
| heatmap | 比較各 section 的情緒強度 |

---

# 5. company_tone_shift_summary.json

## 5.1 檔案用途

`company_tone_shift_summary.json` 是公司層級的語氣轉變摘要，用來比較：

```text
Prepared Remarks vs Q&A Answer
```

也就是比較公司事先準備好的簡報語氣，與管理層被分析師提問後的回答語氣。

此檔案可用來判斷公司在 Q&A 階段是否透露更多負面訊號。

---

## 5.2 JSON 結構

```json
{
  "metadata": {
    "module": "company_tone_shift_summary",
    "company": "nvda",
    "description": "Tone shift comparison between prepared remarks and Q&A answers.",
    "total_records": 1
  },
  "tone_shift_results": [
    {
      "company": "nvda",
      "prepared_positive_score": 0.70,
      "prepared_neutral_score": 0.25,
      "prepared_negative_score": 0.05,
      "answer_positive_score": 0.50,
      "answer_neutral_score": 0.30,
      "answer_negative_score": 0.20,
      "positive_score_shift": -0.20,
      "negative_score_shift": 0.15,
      "tone_shift_flag": false
    }
  ]
}
```

---

## 5.3 tone_shift_results 欄位說明

| 欄位名稱 | 說明 |
|---|---|
| `company` | 公司代號 |
| `prepared_positive_score` | Prepared Remarks 平均正向分數 |
| `prepared_neutral_score` | Prepared Remarks 平均中性分數 |
| `prepared_negative_score` | Prepared Remarks 平均負向分數 |
| `answer_positive_score` | Q&A Answer 平均正向分數 |
| `answer_neutral_score` | Q&A Answer 平均中性分數 |
| `answer_negative_score` | Q&A Answer 平均負向分數 |
| `positive_score_shift` | Q&A Answer 相對於 Prepared Remarks 的正向分數變化 |
| `negative_score_shift` | Q&A Answer 相對於 Prepared Remarks 的負向分數變化 |
| `tone_shift_flag` | Q&A Answer 是否明顯比 Prepared Remarks 更負面 |

---

## 5.4 positive_score_shift

計算方式：

```text
positive_score_shift = answer_positive_score - prepared_positive_score
```

| positive_score_shift | 意義 |
|---:|---|
| 大於 0 | Q&A 回答比公司簡報更正向 |
| 接近 0 | Q&A 回答與公司簡報正向程度接近 |
| 小於 0 | Q&A 回答比公司簡報更不正向 |

---

## 5.5 negative_score_shift

計算方式：

```text
negative_score_shift = answer_negative_score - prepared_negative_score
```

| negative_score_shift | 意義 |
|---:|---|
| 大於 0 | Q&A 回答比公司簡報更負面 |
| 接近 0 | Q&A 回答與公司簡報負面程度接近 |
| 小於 0 | Q&A 回答比公司簡報更不負面 |

---

## 5.6 tone_shift_flag

判斷邏輯：

```text
negative_score_shift > 0.15
```

| 值 | 意義 |
|---|---|
| `true` | Q&A 回答明顯比公司簡報更負面 |
| `false` | 沒有明顯負向語氣轉變 |

若 `tone_shift_flag = true`，代表公司在 Q&A 階段可能透露更多風險訊號，後續應回到 `qna_sentiment_summary.json` 找出具體 Q&A。

---

## 5.7 解讀範例

| company | prepared_positive_score | prepared_negative_score | answer_positive_score | answer_negative_score | positive_score_shift | negative_score_shift | tone_shift_flag |
|---|---:|---:|---:|---:|---:|---:|---|
| nvda | 0.70 | 0.05 | 0.50 | 0.22 | -0.20 | 0.17 | true |

可解讀為：

1. 公司簡報階段較正向。
2. Q&A 回答階段正向程度下降、負向程度上升。
3. `negative_score_shift = 0.17`，超過 0.15，因此 `tone_shift_flag = true`。
4. 後續應回到 `qna_sentiment_summary.json` 檢查是哪幾題造成語氣轉負。

---

## 5.8 建議視覺化

| 圖表 | 用途 |
|---|---|
| prepared vs answer bar chart | 比較簡報與回答的正負向分數 |
| tone shift indicator card | 顯示 tone_shift_flag 是否為 true |
| positive / negative shift chart | 顯示正向與負向分數變化 |
| company ranking | 多家公司時比較誰的語氣轉變最大 |

---

# 6. 建議分析流程

## Step 1：先看公司層級語氣轉變

使用：

```text
company_tone_shift_summary.json
```

觀察：

```text
tone_shift_flag
positive_score_shift
negative_score_shift
```

若 `tone_shift_flag = true`，代表公司在 Q&A 階段可能比 prepared remarks 更負面。

---

## Step 2：再看段落類型平均情緒

使用：

```text
section_sentiment_summary.json
```

比較：

```text
prepared
question
answer
```

如果 `question` 的 `negative_score` 明顯高於 `prepared`，代表分析師提問較有壓力。

如果 `answer` 的 `negative_score` 高於 `prepared`，代表管理層回答比簡報階段更保守。

---

## Step 3：最後回到具體 Q&A

使用：

```text
qna_sentiment_summary.json
```

優先檢查：

```text
risk_downplay_flag = true
negative_question_soft_answer_flag = true
negative_score_gap 高
```

這些 Q&A 是後續報告最值得深入分析的內容。

---

# 7. 總結

| Output | 分析層級 | 最適合用途 |
|---|---|---|
| `qna_sentiment_summary.json` | 單題 Q&A | 找出高風險問答與語氣落差 |
| `section_sentiment_summary.json` | 段落類型 | 比較 prepared、question、answer 的整體情緒 |
| `company_tone_shift_summary.json` | 公司層級 | 判斷 Q&A 是否比 prepared remarks 更負面 |

重點使用方式：

1. 做視覺化：優先使用 `section_sentiment_summary.json` 與 `company_tone_shift_summary.json`。
2. 做洞察分析：優先使用 `qna_sentiment_summary.json`。
3. 做人工複查：優先查看 `risk_downplay_flag = true` 且 `negative_score_gap` 高的 Q&A。
