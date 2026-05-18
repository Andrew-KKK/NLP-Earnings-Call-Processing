import json
import configparser
from pathlib import Path
from collections import Counter

import pandas as pd
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential


# ============================================================
# 1. 讀取 config.ini
# ============================================================

def load_config(config_path="config.ini"):
    """
    讀取 config.ini 中的 Azure 金鑰、輸入路徑、輸出路徑與執行設定。
    """
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    settings = {
        "azure_key": config["azure"]["language_key"],
        "azure_endpoint": config["azure"]["language_endpoint"],

        "input_dir": config["path"].get("input_dir", "input"),
        "keyphrase_output_dir": config["path"].get(
            "keyphrase_output_dir",
            "keyphrase_output"
        ),

        "company_prefix": config["input"]["company_prefix"],

        # key phrase 模組專用設定：
        # true  = 一律用 translated_text
        # false = 一律用 original_text
        # auto  = 中文資料用 translated_text，英文資料用 original_text
        "keyphrase_use_translated": config["setting"].get(
            "keyphrase_use_translated",
            fallback="auto"
        ),

        "batch_size": config["setting"].getint("batch_size", fallback=10),
        "max_chars": config["setting"].getint("max_chars", fallback=4500),
    }

    return settings


def create_text_analytics_client(azure_key, azure_endpoint):
    """
    建立 Azure Language Service Client。
    """
    credential = AzureKeyCredential(azure_key)

    client = TextAnalyticsClient(
        endpoint=azure_endpoint,
        credential=credential
    )

    return client


# ============================================================
# 2. 讀取 JSON 檔案
# ============================================================

def load_json(file_path):
    """
    讀取 JSON 檔案。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def should_use_translated_text(source_language, keyphrase_use_translated):
    """
    判斷 Key Phrase Extraction 是否使用翻譯文字。

    keyphrase_use_translated:
    - true：一律使用 translated_text
    - false：一律使用 original_text
    - auto：中文資料使用 translated_text，英文資料使用 original_text
    """
    setting = str(keyphrase_use_translated).strip().lower()

    if setting == "true":
        return True

    if setting == "false":
        return False

    if setting == "auto":
        return source_language.lower().startswith("zh")

    return False


# ============================================================
# 3. 段落過濾與 Q&A 起點判斷
# ============================================================

def is_qna_start(text):
    """
    判斷完整逐字稿是否真的進入 Q&A 段落。

    注意：
    不可只看到 Q&A 就停止，因為開場可能只是說稍後會有 Q&A。
    """
    if not text:
        return False

    text_lower = text.lower().strip()

    qna_start_patterns = [
        # 英文正式轉場
        "this concludes our prepared statements",
        "this concludes our prepared remarks",
        "now let's begin the q&a session",
        "now let us begin the q&a session",
        "we will now begin the question-and-answer session",
        "we will now begin the question and answer session",
        "we will now transition to q&a",
        "we will now transition to the q&a",
        "operator, can we proceed with the first participant",
        "operator, please poll for questions",

        # 中文正式轉場
        "問答環節：",
        "進入問答環節",
        "接下來進入問答",
        "接下來是問答時間",
        "現在開始問答"
    ]

    return any(pattern in text_lower for pattern in qna_start_patterns)


def is_irrelevant_transcript_paragraph(text):
    """
    判斷是否為法說會開場、操作說明、免責聲明等低分析價值段落。
    這些段落不應送進 Key Phrase Extraction。
    """
    if not text:
        return True

    text_lower = text.lower()

    irrelevant_patterns = [
        # 會議操作與接線員說明
        "conference operator",
        "all lines have been placed on mute",
        "background noise",
        "press star",
        "telephone keypad",
        "withdraw your question",
        "your line is open",
        "we'll pause",
        "compile the q&a roster",
        "operator, please",
        "thank you. so, you may begin your conference",

        # webcast / replay / IR 網站
        "webcast",
        "replay",
        "investor relations website",

        # 免責聲明與法遵揭露
        "forward-looking statements",
        "safe harbor",
        "actual results may differ materially",
        "non-gaap",
        "gaap financial measures",
        "sec",
        "securities and exchange commission",
        "10-k",
        "10-q",
        "form 8-k",

        # 常見轉場寒暄
        "let me turn the call over",
        "with that, let me turn",
        "thank you for taking my question",
        "thanks for taking my question"
    ]

    return any(pattern in text_lower for pattern in irrelevant_patterns)


def is_low_information_paragraph(text):
    """
    判斷段落是否資訊量過低。
    用於排除過短、純寒暄、純轉場文字。
    """
    if not text:
        return True

    text_clean = text.strip()

    if len(text_clean) < 30:
        return True

    low_info_phrases = [
        "good afternoon",
        "good morning",
        "thank you",
        "thanks",
        "hello everyone",
        "大家好",
        "謝謝",
        "午安"
    ]

    text_lower = text_clean.lower()

    # 若段落很短且主要是寒暄，排除
    if len(text_clean) < 80:
        if any(phrase in text_lower for phrase in low_info_phrases):
            return True

    return False


# ============================================================
# 4. 整理 Prepared Remarks 與 Q&A
# ============================================================

def extract_prepared_remarks(full_json, company, keyphrase_use_translated="auto"):
    """
    從 full_transcript_translation.json 中擷取公司簡報 Prepared Remarks。

    Key Phrase Extraction 建議：
    - 英文法說會：使用 original_text
    - 中文法說會：使用 translated_text
    """
    rows = []

    metadata = full_json.get("metadata", {})
    source_language = metadata.get("source_language", "")
    target_language = metadata.get("target_language", "")

    use_translated = should_use_translated_text(
        source_language=source_language,
        keyphrase_use_translated=keyphrase_use_translated
    )

    content = full_json.get("content", [])

    for item in content:
        paragraph_index = item.get("paragraph_index")
        original_text = item.get("original_text", "")
        translated_text = item.get("translated_text", "")

        check_text = f"{original_text} {translated_text}"

        # 避免第一、二段開場提到 Q&A session 就誤判
        if paragraph_index and paragraph_index > 3:
            if is_qna_start(check_text):
                break

        if use_translated:
            text = translated_text
            used_text_type = "translated"
        else:
            text = original_text
            used_text_type = "original"

        if text and text.strip():
            if is_irrelevant_transcript_paragraph(text):
                continue

            if is_low_information_paragraph(text):
                continue

            rows.append({
                "company": company,
                "section_type": "prepared",
                "pair_id": None,
                "text_id": paragraph_index,
                "text": text.strip(),
                "source_language": source_language,
                "target_language": target_language,
                "used_text_type": used_text_type
            })

    return rows


def extract_qna_texts(qna_json, company, keyphrase_use_translated="auto"):
    """
    從 extracted_qna_translation.json 中擷取 question 與 answer。

    Key Phrase Extraction 建議：
    - 英文 Q&A：使用 question / answer
    - 中文 Q&A：使用 question_translated / answer_translated
    """
    rows = []

    metadata = qna_json.get("metadata", {})
    source_language = metadata.get("source_language", "")
    target_language = metadata.get("target_language", "")

    use_translated = should_use_translated_text(
        source_language=source_language,
        keyphrase_use_translated=keyphrase_use_translated
    )

    qna_list = qna_json.get("qna_list", [])

    for idx, item in enumerate(qna_list, start=1):

        if use_translated:
            question_text = item.get("question_translated", "")
            answer_text = item.get("answer_translated", "")
            used_text_type = "translated"
        else:
            question_text = item.get("question", "")
            answer_text = item.get("answer", "")
            used_text_type = "original"

        if question_text and question_text.strip():
            rows.append({
                "company": company,
                "section_type": "question",
                "pair_id": idx,
                "text_id": f"Q{idx}",
                "text": question_text.strip(),
                "source_language": source_language,
                "target_language": target_language,
                "used_text_type": used_text_type
            })

        if answer_text and answer_text.strip():
            rows.append({
                "company": company,
                "section_type": "answer",
                "pair_id": idx,
                "text_id": f"A{idx}",
                "text": answer_text.strip(),
                "source_language": source_language,
                "target_language": target_language,
                "used_text_type": used_text_type
            })

    return rows


def build_keyphrase_input_dataframe(
    input_dir,
    company_prefix,
    keyphrase_use_translated="auto"
):
    """
    只讀取 config.ini 指定的單一公司 JSON，
    整理成關鍵字擷取用 DataFrame。
    """
    input_path = Path(input_dir)

    full_path = input_path / f"{company_prefix}_full_transcript_translation.json"
    qna_path = input_path / f"{company_prefix}_extracted_qna_translation.json"

    if not full_path.exists():
        raise FileNotFoundError(f"找不到完整逐字稿檔案：{full_path}")

    if not qna_path.exists():
        raise FileNotFoundError(f"找不到 Q&A 檔案：{qna_path}")

    full_json = load_json(full_path)
    qna_json = load_json(qna_path)

    prepared_rows = extract_prepared_remarks(
        full_json=full_json,
        company=company_prefix,
        keyphrase_use_translated=keyphrase_use_translated
    )

    qna_rows = extract_qna_texts(
        qna_json=qna_json,
        company=company_prefix,
        keyphrase_use_translated=keyphrase_use_translated
    )

    all_rows = prepared_rows + qna_rows

    df = pd.DataFrame(all_rows)

    return df


# ============================================================
# 5. Key Phrase 後處理規則
# ============================================================

def normalize_phrase(phrase):
    """
    將 key phrase 做基本標準化，方便後續比對。
    """
    if phrase is None:
        return ""

    return str(phrase).strip().lower()


GENERIC_STOP_PHRASES = {
    # 開場 / 會議流程雜訊
    "good afternoon",
    "good morning",
    "conference operator",
    "background noise",
    "answer session",
    "question and answer session",
    "telephone keypad",
    "all lines",
    "line",
    "lines",
    "mute",
    "star",
    "number",
    "operator",
    "speaker",
    "remarks",
    "today",
    "everyone",
    "name",
    "time",
    "thank you",
    "thanks",
    "question",
    "questions",
    "answer",
    "answers",
    "sarah",
    "christian",

    # 法說會固定揭露雜訊
    "safe harbor",
    "forward-looking statements",
    "non-gaap",
    "gaap",
    "webcast",
    "replay",
    "investor relations website",
    "press release",
    "sec",
    "10-k",
    "10-q",
    "form 8-k"
}


FINANCE_KEYWORDS = {
    # 財務表現
    "revenue",
    "sales",
    "growth",
    "gross margin",
    "margin",
    "operating margin",
    "profit",
    "profitability",
    "eps",
    "roe",
    "cash flow",
    "free cash flow",
    "capex",
    "capital expenditure",
    "guidance",
    "outlook",
    "pricing",
    "price",
    "cost",
    "tax",
    "inventory",
    "earnings",
    "income",
    "expense",

    # 供需與營運
    "demand",
    "supply",
    "capacity",
    "utilization",
    "constraint",
    "bottleneck",
    "customer",
    "customers",
    "order",
    "shipment",
    "shipments",
    "visibility",
    "ramp",
    "production",
    "manufacturing",
    "fab",
    "cleanroom",
    "tool",
    "equipment",
    "supplier",
    "working capital",

    # 產業與技術
    "ai",
    "ai demand",
    "ai server",
    "ai servers",
    "data center",
    "hpc",
    "gpu",
    "asic",
    "blackwell",
    "rubin",
    "cuda",
    "spectrum",
    "nvlink",
    "cowos",
    "n3",
    "n2",
    "3 nanometer",
    "2 nanometer",
    "advanced packaging",
    "memory",
    "smartphone",
    "pc",
    "server",
    "servers",
    "networking",
    "cloud",
    "csp",
    "hyperscaler",
    "inference",
    "training",
    "compute",
    "robotics",
    "ev",
    "semiconductor",

    # 風險與競爭
    "competition",
    "competitor",
    "risk",
    "tariff",
    "geopolitical",
    "china",
    "arizona",
    "japan",
    "taiwan",
    "customer demand",
    "pricing pressure"
}


def is_generic_noise_phrase(phrase):
    """
    判斷 key phrase 是否為一般會議雜訊或太泛用詞。
    """
    normalized = normalize_phrase(phrase)

    if not normalized:
        return True

    # 太短的詞通常沒有分析價值
    if len(normalized) <= 2:
        return True

    # 單一常見詞通常沒有分析價值
    if normalized in GENERIC_STOP_PHRASES:
        return True

    # 包含明顯會議流程雜訊
    for stop_phrase in GENERIC_STOP_PHRASES:
        if stop_phrase in normalized:
            return True

    return False


def is_finance_relevant_phrase(phrase):
    """
    判斷 key phrase 是否與法說會財務、營運、技術、風險主題相關。
    """
    normalized = normalize_phrase(phrase)

    if not normalized:
        return False

    for keyword in FINANCE_KEYWORDS:
        if keyword in normalized:
            return True

    # 多詞片語通常比單詞有價值，例如 "strong demand", "capacity expansion"
    if len(normalized.split()) >= 2 and len(normalized) >= 8:
        return True

    return False


def unique_preserve_order(items):
    """
    去除重複 key phrases，但保留原本出現順序。
    """
    seen = set()
    output = []

    for item in items:
        normalized = normalize_phrase(item)

        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(item)

    return output


def clean_key_phrases(key_phrases):
    """
    清理 Azure 回傳的 key phrases：
    1. 移除會議雜訊
    2. 移除太短或太泛用詞
    3. 優先保留財務、營運、技術與風險相關詞
    4. 去除重複
    """
    cleaned = []

    for phrase in key_phrases:
        if is_generic_noise_phrase(phrase):
            continue

        if not is_finance_relevant_phrase(phrase):
            continue

        cleaned.append(phrase)

    return unique_preserve_order(cleaned)


# ============================================================
# 6. Azure Key Phrase Extraction
# ============================================================

def split_text_by_max_chars(text, max_chars=4500):
    """
    避免單一文件太長，先切成多個 chunk。
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []

    for start in range(0, len(text), max_chars):
        chunk = text[start:start + max_chars]
        chunks.append(chunk)

    return chunks


def chunk_list(data, batch_size=10):
    """
    將 list 切成 batch。
    """
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]


def extract_key_phrases_batch(client, texts):
    """
    呼叫 Azure extract_key_phrases。
    """
    try:
        results = client.extract_key_phrases(documents=texts)
        return results

    except Exception as e:
        print(f"[Azure Error] {e}")
        return []


def analyze_one_record_keyphrases(client, record, max_chars=4500, batch_size=10):
    """
    分析單一 record。
    若文字太長，會切成多個 chunk，再合併 key phrases。
    """
    text = record["text"]
    text_chunks = split_text_by_max_chars(text, max_chars=max_chars)

    all_key_phrases = []
    errors = []

    for batch in chunk_list(text_chunks, batch_size=batch_size):
        azure_results = extract_key_phrases_batch(client, batch)

        for chunk_text, result in zip(batch, azure_results):
            if result.is_error:
                errors.append(result.error.message)
            else:
                all_key_phrases.extend(list(result.key_phrases))

    raw_key_phrases = unique_preserve_order(all_key_phrases)
    cleaned_key_phrases = clean_key_phrases(all_key_phrases)

    return {
        **record,
        "raw_key_phrases": raw_key_phrases,
        "raw_key_phrase_count": len(raw_key_phrases),
        "key_phrases": cleaned_key_phrases,
        "key_phrase_count": len(cleaned_key_phrases),
        "chunk_count": len(text_chunks),
        "error": "; ".join(errors) if errors else None
    }


def run_keyphrase_extraction(client, input_df, max_chars=4500, batch_size=10):
    """
    對所有 prepared / question / answer 執行關鍵字擷取。
    """
    result_rows = []

    records = input_df.to_dict("records")
    total = len(records)

    for idx, record in enumerate(records, start=1):
        print(
            f"正在擷取第 {idx}/{total} 筆："
            f"{record['company']} - {record['section_type']} - {record['text_id']}"
        )

        analyzed_record = analyze_one_record_keyphrases(
            client=client,
            record=record,
            max_chars=max_chars,
            batch_size=batch_size
        )

        result_rows.append(analyzed_record)

    return pd.DataFrame(result_rows)


# ============================================================
# 7. Q&A 關鍵字比對
# ============================================================

def calculate_overlap(question_phrases, answer_phrases):
    """
    計算 question 與 answer 的 key phrase overlap。
    """
    q_set = set(normalize_phrase(p) for p in question_phrases if normalize_phrase(p))
    a_set = set(normalize_phrase(p) for p in answer_phrases if normalize_phrase(p))

    overlap = q_set.intersection(a_set)

    if len(q_set) == 0:
        overlap_ratio = 0.0
    else:
        overlap_ratio = len(overlap) / len(q_set)

    return {
        "overlap_phrases": sorted(list(overlap)),
        "overlap_count": len(overlap),
        "question_phrase_count": len(q_set),
        "answer_phrase_count": len(a_set),
        "overlap_ratio": round(overlap_ratio, 4)
    }


def build_qna_keyphrase_summary(keyphrase_result_df):
    """
    將 question 與 answer 的 key phrases 合併成同一列，
    並計算 topic overlap / mismatch。
    """
    qna_df = keyphrase_result_df[
        keyphrase_result_df["section_type"].isin(["question", "answer"])
    ].copy()

    question_df = qna_df[qna_df["section_type"] == "question"].copy()
    answer_df = qna_df[qna_df["section_type"] == "answer"].copy()

    question_df = question_df.rename(columns={
        "text": "question_text",
        "key_phrases": "question_key_phrases",
        "key_phrase_count": "question_key_phrase_count"
    })

    answer_df = answer_df.rename(columns={
        "text": "answer_text",
        "key_phrases": "answer_key_phrases",
        "key_phrase_count": "answer_key_phrase_count"
    })

    question_cols = [
        "company",
        "pair_id",
        "question_text",
        "question_key_phrases",
        "question_key_phrase_count"
    ]

    answer_cols = [
        "company",
        "pair_id",
        "answer_text",
        "answer_key_phrases",
        "answer_key_phrase_count"
    ]

    merged_df = pd.merge(
        question_df[question_cols],
        answer_df[answer_cols],
        on=["company", "pair_id"],
        how="inner"
    )

    overlap_rows = []

    for _, row in merged_df.iterrows():
        overlap_info = calculate_overlap(
            row["question_key_phrases"],
            row["answer_key_phrases"]
        )

        overlap_rows.append(overlap_info)

    overlap_df = pd.DataFrame(overlap_rows)

    result_df = pd.concat([merged_df.reset_index(drop=True), overlap_df], axis=1)

    result_df["topic_mismatch_flag"] = result_df["overlap_ratio"] < 0.2

    return result_df


# ============================================================
# 8. Repeated Emphasis：公司反覆強調主題
# ============================================================

def build_topic_emphasis_summary(keyphrase_result_df, top_n=30):
    """
    統計 prepared / question / answer 中高頻 key phrases。
    用來判斷公司與分析師各自反覆強調什麼主題。
    """
    rows = []

    for section_type in ["prepared", "question", "answer"]:
        section_df = keyphrase_result_df[
            keyphrase_result_df["section_type"] == section_type
        ]

        phrase_counter = Counter()

        for phrases in section_df["key_phrases"]:
            for phrase in phrases:
                normalized = normalize_phrase(phrase)

                if normalized:
                    phrase_counter[normalized] += 1

        for phrase, count in phrase_counter.most_common(top_n):
            rows.append({
                "section_type": section_type,
                "topic": phrase,
                "frequency": count
            })

    return pd.DataFrame(rows)


# ============================================================
# 9. 輸出 JSON
# ============================================================

def clean_for_json(obj):
    """
    遞迴清理資料，將 NaN / None-like 值轉成標準 JSON 的 null。
    避免 json.dump(..., allow_nan=False) 報錯。
    """
    if isinstance(obj, dict):
        return {key: clean_for_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [clean_for_json(item) for item in obj]

    # pandas / numpy 的 NaN、NaT 都會在這裡被轉成 None
    if pd.isna(obj):
        return None

    return obj


def save_dataframe_as_json(df, output_path, metadata, records_key="results"):
    """
    將 DataFrame 輸出成標準 JSON。
    會將 pandas NaN 轉成 JSON null。
    """
    records = df.to_dict(orient="records")
    clean_records = clean_for_json(records)

    data = {
        "metadata": metadata,
        records_key: clean_records
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)

def save_outputs(
    output_dir,
    company_prefix,
    qna_keyphrase_summary_df,
    topic_emphasis_df
):
    """
    只輸出 MVP 必要 JSON。
    每家公司會有自己的輸出資料夾：
    keyphrase_output/{company_prefix}/

    保留項目：
    1. qna_keyphrase_summary.json
       - Q&A 問題與回答的關鍵詞比對
       - 用於分析 topic overlap / topic mismatch

    2. topic_emphasis_summary.json
       - prepared / question / answer 各段落高頻主題
       - 用於分析公司與分析師各自反覆強調的議題
    """
    output_dir = Path(output_dir) / company_prefix
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Q&A key phrase summary
    qna_json = output_dir / "qna_keyphrase_summary.json"

    save_dataframe_as_json(
        df=qna_keyphrase_summary_df,
        output_path=qna_json,
        metadata={
            "module": "qna_keyphrase_summary",
            "company": company_prefix,
            "description": "Question-answer key phrase comparison and topic mismatch results.",
            "total_records": len(qna_keyphrase_summary_df)
        },
        records_key="qna_results"
    )

    # 2. Topic emphasis summary
    emphasis_json = output_dir / "topic_emphasis_summary.json"

    save_dataframe_as_json(
        df=topic_emphasis_df,
        output_path=emphasis_json,
        metadata={
            "module": "topic_emphasis_summary",
            "company": company_prefix,
            "description": "High-frequency key phrases by section type.",
            "total_records": len(topic_emphasis_df)
        },
        records_key="topic_results"
    )

    print("\n已輸出必要 JSON 檔案：")
    print(f"- {qna_json}")
    print(f"- {emphasis_json}")

# ============================================================
# 10. Main
# ============================================================

def main():
    print("========== Azure Key Phrase Extraction Module ==========")

    config = load_config("config.ini")

    input_dir = config["input_dir"]
    output_dir = config["keyphrase_output_dir"]
    company_prefix = config["company_prefix"]
    keyphrase_use_translated = config["keyphrase_use_translated"]
    batch_size = config["batch_size"]
    max_chars = config["max_chars"]

    print("\n[Config]")
    print(f"company_prefix             : {company_prefix}")
    print(f"input_dir                  : {input_dir}")
    print(f"keyphrase_output_dir       : {output_dir}/{company_prefix}")
    print(f"keyphrase_use_translated   : {keyphrase_use_translated}")
    print(f"batch_size                 : {batch_size}")
    print(f"max_chars                  : {max_chars}")

    print("\n[1/5] 建立 Azure Text Analytics Client...")
    client = create_text_analytics_client(
        azure_key=config["azure_key"],
        azure_endpoint=config["azure_endpoint"]
    )

    print("\n[2/5] 讀取單一公司 JSON 並建立 keyphrase input DataFrame...")
    keyphrase_input_df = build_keyphrase_input_dataframe(
        input_dir=input_dir,
        company_prefix=company_prefix,
        keyphrase_use_translated=keyphrase_use_translated
    )

    print(f"共整理出 {len(keyphrase_input_df)} 筆待分析文字。")

    if keyphrase_input_df.empty:
        print("沒有找到可分析資料，請確認 input 資料夾與 JSON 檔名。")
        return

    print("\n[3/5] 執行 Azure Key Phrase Extraction...")
    keyphrase_result_df = run_keyphrase_extraction(
        client=client,
        input_df=keyphrase_input_df,
        max_chars=max_chars,
        batch_size=batch_size
    )

    print("\n[4/5] 建立 Q&A Topic Overlap 與 Repeated Emphasis...")
    qna_keyphrase_summary_df = build_qna_keyphrase_summary(keyphrase_result_df)
    topic_emphasis_df = build_topic_emphasis_summary(
        keyphrase_result_df,
        top_n=30
    )

    print("\n[5/5] 輸出 JSON...")
    save_outputs(
        output_dir=output_dir,
        company_prefix=company_prefix,
        qna_keyphrase_summary_df=qna_keyphrase_summary_df,
        topic_emphasis_df=topic_emphasis_df
    )

    print("\n========== Key Phrase Extraction Finished ==========")


if __name__ == "__main__":
    main()