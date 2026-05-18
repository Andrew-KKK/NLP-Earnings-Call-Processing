# keyphrase_output 說明文件

## 1. Output 輸出位置

`key_phrase_extraction.py` 執行後，會依照 `config.ini` 中的 `keyphrase_output_dir` 與 `company_prefix` 建立輸出資料夾。

```text
{keyphrase_output_dir}/{company_prefix}/
```

若設定如下：

```ini
keyphrase_output_dir = keyphrase_output
company_prefix = nvda
```

則輸出位置為：

```text
keyphrase_output/nvda/
```

每家公司會各自建立一個資料夾，例如：

```text
keyphrase_output/
├── foxconn/
│   ├── qna_keyphrase_summary.json
│   └── topic_emphasis_summary.json
├── nvda/
│   ├── qna_keyphrase_summary.json
│   └── topic_emphasis_summary.json
└── tsmc/
    ├── qna_keyphrase_summary.json
    └── topic_emphasis_summary.json
```

---

## 2. Output 檔案總覽

Key Phrase Extraction 模組目前輸出兩個必要 JSON 檔案：

| 檔案名稱 | 分析層級 | 主要用途 |
|---|---|---|
| `qna_keyphrase_summary.json` | 單題 Q&A 層級 | 比較分析師問題與管理層回答的關鍵詞重疊程度 |
| `topic_emphasis_summary.json` | 段落類型層級 | 統計 prepared、question、answer 中反覆出現的高頻主題 |

---

## 3. 兩個 Output 的關係

```text
qna_keyphrase_summary.json
        ↓
觀察每一題 Q&A 是否有回答到問題主題

 topic_emphasis_summary.json
        ↓
觀察公司與分析師分別反覆強調哪些主題
```

建議使用順序：

```text
Step 1：先看 topic_emphasis_summary.json
        ↓
掌握公司簡報、分析師問題、管理層回答各自強調的主題

Step 2：再看 qna_keyphrase_summary.json
        ↓
檢查每一題 Q&A 中，回答是否有對應到問題關鍵詞
```

---

# 4. qna_keyphrase_summary.json

## 4.1 檔案用途

`qna_keyphrase_summary.json` 的分析單位是每一組 Q&A。

每一筆資料代表：

```text
一位分析師的問題
+
管理層對該問題的回答
```

這份檔案主要用來觀察：

1. 分析師問題中的核心關鍵詞是什麼。
2. 管理層回答是否涵蓋相同主題。
3. 問題與回答的主題重疊程度是否過低。
4. 哪些 Q&A 可能存在答非所問、迴避問題或轉移焦點。

---

## 4.2 JSON 結構

```json
{
  "metadata": {
    "module": "qna_keyphrase_summary",
    "company": "nvda",
    "description": "Question-answer key phrase comparison and topic mismatch results.",
    "total_records": 10
  },
  "qna_results": [
    {
      "company": "nvda",
      "pair_id": 1,
      "question_text": "...",
      "question_key_phrases": ["demand", "gross margin"],
      "question_key_phrase_count": 2,
      "answer_text": "...",
      "answer_key_phrases": ["demand", "capacity", "customer"],
      "answer_key_phrase_count": 3,
      "overlap_phrases": ["demand"],
      "overlap_count": 1,
      "question_phrase_count": 2,
      "answer_phrase_count": 3,
      "overlap_ratio": 0.5,
      "topic_mismatch_flag": false
    }
  ]
}
```

---

## 4.3 qna_results 欄位說明

| 欄位名稱 | 說明 |
|---|---|
| `company` | 公司代號 |
| `pair_id` | Q&A 配對編號 |
| `question_text` | 分析師問題原文 |
| `question_key_phrases` | 從問題中擷取出的關鍵詞 |
| `question_key_phrase_count` | 問題中的關鍵詞數量 |
| `answer_text` | 管理層回答原文 |
| `answer_key_phrases` | 從回答中擷取出的關鍵詞 |
| `answer_key_phrase_count` | 回答中的關鍵詞數量 |
| `overlap_phrases` | 問題與回答共同出現的關鍵詞 |
| `overlap_count` | 共同關鍵詞數量 |
| `question_phrase_count` | 問題關鍵詞去重後數量 |
| `answer_phrase_count` | 回答關鍵詞去重後數量 |
| `overlap_ratio` | 問題關鍵詞被回答涵蓋的比例 |
| `topic_mismatch_flag` | 問題與回答是否可能主題不一致 |

---

## 4.4 overlap_ratio 說明

`overlap_ratio` 用來衡量管理層回答是否涵蓋分析師問題中的主題。

計算方式：

```text
overlap_ratio = overlap_count / question_phrase_count
```

解讀方式：

| overlap_ratio | 解讀 |
|---:|---|
| 接近 1 | 回答高度涵蓋問題主題 |
| 約 0.5 | 回答部分涵蓋問題主題 |
| 接近 0 | 回答幾乎沒有涵蓋問題主題 |

範例：

```text
question_key_phrases = ["demand", "gross margin"]
answer_key_phrases = ["demand", "capacity", "customer"]
overlap_phrases = ["demand"]
overlap_ratio = 1 / 2 = 0.5
```

代表管理層回答有提到部分問題主題，但沒有完全涵蓋。

---

## 4.5 topic_mismatch_flag 說明

`topic_mismatch_flag` 用來標記問題與回答是否可能主題不一致。

判斷邏輯：

```text
overlap_ratio < 0.2
```

欄位值：

| 值 | 意義 |
|---|---|
| `true` | 問題與回答的關鍵詞重疊度很低，可能答非所問或轉移焦點 |
| `false` | 問題與回答仍有一定主題重疊 |

> 注意：`topic_mismatch_flag = true` 不代表管理層一定迴避問題，只代表問題與回答的關鍵詞重疊度偏低，需要人工複查。

---

## 4.6 qna_keyphrase_summary.json 建議使用方式

後續同學可以優先篩選：

```text
topic_mismatch_flag = true
```

再查看：

```text
question_text
answer_text
question_key_phrases
answer_key_phrases
overlap_ratio
```

用來判斷管理層是否有：

1. 沒有回答分析師問題核心。
2. 將焦點轉移到其他主題。
3. 只回答部分問題。
4. 用公司想強調的主題取代分析師關心的主題。

---

# 5. topic_emphasis_summary.json

## 5.1 檔案用途

`topic_emphasis_summary.json` 用來統計不同段落類型中反覆出現的高頻關鍵詞。

目前段落類型包含：

```text
prepared
question
answer
```

這份檔案主要用來觀察：

1. 公司在簡報中主動強調哪些主題。
2. 分析師在問題中反覆追問哪些主題。
3. 管理層在回答中反覆回到哪些主題。
4. 公司想講的重點與市場關心的重點是否一致。

---

## 5.2 JSON 結構

```json
{
  "metadata": {
    "module": "topic_emphasis_summary",
    "company": "nvda",
    "description": "High-frequency key phrases by section type.",
    "total_records": 30
  },
  "topic_results": [
    {
      "section_type": "prepared",
      "topic": "ai demand",
      "frequency": 5
    },
    {
      "section_type": "question",
      "topic": "gross margin",
      "frequency": 3
    },
    {
      "section_type": "answer",
      "topic": "capacity",
      "frequency": 4
    }
  ]
}
```

---

## 5.3 topic_results 欄位說明

| 欄位名稱 | 說明 |
|---|---|
| `section_type` | 段落類型，包含 prepared、question、answer |
| `topic` | 高頻出現的關鍵詞或主題詞 |
| `frequency` | 該主題在該段落類型中出現的次數 |

---

## 5.4 section_type 解讀

| section_type | 意義 | 可觀察重點 |
|---|---|---|
| `prepared` | 公司簡報內容 | 公司主動想強調的營運、產品或成長主題 |
| `question` | 分析師問題 | 市場或分析師真正關心、追問的議題 |
| `answer` | 管理層回答 | 管理層回應時反覆使用的主題與敘事 |

---

## 5.5 topic_emphasis_summary.json 建議使用方式

後續同學可以先依照 `section_type` 分組，觀察每個段落類型的高頻主題。

常見分析方向：

1. `prepared` 高頻主題：公司主動強調什麼？
2. `question` 高頻主題：分析師最關心什麼？
3. `answer` 高頻主題：管理層回答時反覆回到什麼？
4. 如果 `question` 高頻主題沒有出現在 `answer`，可能代表管理層沒有充分回應市場關切。
5. 如果 `prepared` 與 `question` 主題差異很大，代表公司主動敘事與市場關心議題可能不一致。

---

# 6. 建議分析流程

## Step 1：先看高頻主題

使用：

```text
topic_emphasis_summary.json
```

觀察三種段落的高頻主題：

```text
prepared：公司主動強調什麼
question：分析師追問什麼
answer：管理層回應什麼
```

---

## Step 2：再看 Q&A 主題重疊程度

使用：

```text
qna_keyphrase_summary.json
```

優先檢查：

```text
topic_mismatch_flag = true
overlap_ratio 偏低
```

這些 Q&A 是後續報告最值得深入分析的內容。

---

## Step 3：與 sentiment output 搭配使用

Key phrase output 適合回答：

```text
公司與分析師各自在談什麼？
管理層有沒有回答到問題主題？
```

Sentiment output 適合回答：

```text
問題與回答的語氣是否一致？
管理層是否用較溫和語氣回應負面問題？
```

建議將兩者結合：

| 情況 | 可能解讀 |
|---|---|
| `topic_mismatch_flag = true` 且 `risk_downplay_flag = true` | 回答可能同時存在主題偏移與風險淡化 |
| `overlap_ratio` 低，但情緒很正向 | 管理層可能用正向敘事轉移焦點 |
| `question` 高頻主題未出現在 `answer` | 市場關心議題可能沒有被充分回應 |

---
# 7. 總結

`key_phrase_extraction.py` 的 output 分成兩個層級：

| Output | 分析層級 | 最適合用途 |
|---|---|---|
| `qna_keyphrase_summary.json` | 單題 Q&A | 檢查管理層回答是否涵蓋分析師問題主題 |
| `topic_emphasis_summary.json` | 段落類型 | 比較公司、分析師、管理層各自反覆強調的主題 |

若後續同學要做視覺化，建議先使用：

```text
topic_emphasis_summary.json
```

若要做深度洞察，則回到：

```text
qna_keyphrase_summary.json
```

優先檢查：

```text
topic_mismatch_flag = true
overlap_ratio 偏低
```

再人工閱讀 `question_text` 與 `answer_text`，判斷管理層是否真正回答了分析師關心的問題。
