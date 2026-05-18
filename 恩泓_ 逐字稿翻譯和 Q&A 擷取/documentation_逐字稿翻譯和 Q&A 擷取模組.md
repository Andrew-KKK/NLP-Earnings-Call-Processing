# documentation: 逐字稿翻譯和 Q&A 擷取模組

## 1. 產出檔案說明 (Output Files)

執行完 `qa_pipeline.py` 後，`output/` 資料夾下會針對每家公司（例如 `tsmc`, `nvda`, `foxconn`）產出兩份 JSON 檔案：

### 📁 軌道一：完整逐字稿翻譯

- **檔名格式**: `{prefix}_full_transcript_translation.json`
- **特性**: 一段原文對應一段翻譯，完整保留所有簡報 (Prepared Remarks) 與過場廢話。

### 📁 軌道二：Q&A 擷取+翻譯

- **檔名格式**: `{prefix}_extracted_qna_translation.json`
- **特性**: 已經過濾掉些許雜訊。若管理層未回答或 LLM 產生幻覺，該筆瑕疵資料已在程式層面被**靜默丟棄 (Silent Drop)**，確保資料品質。

## 2. 資料結構定義 (JSON Schema)

為了方便下游 Python 腳本讀取，兩份檔案皆採用 **Metadata + Payload** 的階層式結構。

### 軌道一 (`_full_transcript_translation.json`)

```python
{
  "metadata": {
    "source_language": "en",
    "target_language": "zh-Hant",
    "total_paragraphs": 125
  },
  "content": [
    {
      "paragraph_index": 1,
      "original_text": "Good afternoon, everyone...",
      "translated_text": "大家午安..."
    }
  ]
}
```

### 軌道二 (`_extracted_qna_translation.json`)

⚠️ **下游開發者請注意**：為了支援「英翻中」與「中翻英」，翻譯欄位的 key 已經統一命名為 `question_translated` 與 `answer_translated`。

```python
{
  "metadata": {
    "source_language": "en",
    "target_language": "zh-Hant",
    "total_qna_pairs": 34
  },
  "qna_list": [
    {
      "question": "What is the visibility for the next two years?",
      "answer": "The visibility is very clear from our CSP customers.",
      "question_translated": "未來兩年的能見度如何？",
      "answer_translated": "我們從 CSP 客戶那裡看到的能見度非常清晰。"
    }
  ]
}
```

## 4. 下游應用開發指南 (For 瑾慈 & 其他組員)

如果你負責開發「情緒分析」或「實體擷取 (NER)」，請參考以下 Python 讀取範本：

```python
import json

# 1. 讀取高純度 Q&A 資料集
file_path = "output/tsmc_extracted_qna_translation.json"
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# 2. 檢查元資料 (可幫助你判斷要呼叫哪種語言的分析模型)
print(f"來源語言: {data['metadata']['source_language']}")
print(f"共 {data['metadata']['total_qna_pairs']} 題 Q&A")

# 3. 疊代每一題進行分析
for qna in data['qna_list']:
    # 建議情緒分析使用「原文 (answer)」跑國外開源模型如 FinBERT 較為精準
    management_response = qna['answer']

    # 呼叫你的情緒分析模組...
    # sentiment_score = analyze_sentiment(management_response)
```