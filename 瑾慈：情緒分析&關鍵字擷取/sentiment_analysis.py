import json
import configparser
from pathlib import Path

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
        "output_dir": config["path"].get("output_dir", "sentiment_output"),

        "company_prefix": config["input"]["company_prefix"],

        "use_translated": config["setting"].getboolean("use_translated", fallback=False),
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


# ============================================================
# 3. 整理 Prepared Remarks 與 Q&A
# ============================================================

def is_qna_start(text):
    """
    判斷完整逐字稿是否真的進入 Q&A 段落。

    注意：
    不能只看到 Q&A 就停止，因為開場常會說：
    "Later we will open the line for Q&A session."
    這不是 Q&A 開始。
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

def extract_prepared_remarks(full_json, company, use_translated=False):
    """
    從 full_transcript_translation.json 中擷取公司簡報 Prepared Remarks。
    """
    rows = []

    metadata = full_json.get("metadata", {})
    source_language = metadata.get("source_language", "")
    target_language = metadata.get("target_language", "")

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


def extract_qna_texts(qna_json, company, use_translated=False):
    """
    從 extracted_qna_translation.json 中擷取 question 與 answer。

    預期 JSON 結構：
    {
      "metadata": {...},
      "qna_list": [
        {
          "question": "...",
          "answer": "...",
          "question_translated": "...",
          "answer_translated": "..."
        }
      ]
    }

    每一題 Q&A 會拆成兩筆：
    1. question
    2. answer
    """
    rows = []

    metadata = qna_json.get("metadata", {})
    source_language = metadata.get("source_language", "")
    target_language = metadata.get("target_language", "")

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


def build_sentiment_input_dataframe(input_dir, company_prefix, use_translated=False):
    """
    只讀取 config.ini 指定的單一公司 JSON，
    整理成情緒分析用 DataFrame。
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
        use_translated=use_translated
    )

    qna_rows = extract_qna_texts(
        qna_json=qna_json,
        company=company_prefix,
        use_translated=use_translated
    )

    all_rows = prepared_rows + qna_rows

    df = pd.DataFrame(all_rows)

    return df


# ============================================================
# 4. Azure Sentiment Analysis
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


def analyze_sentiment_batch(client, texts):
    """
    呼叫 Azure analyze_sentiment。
    """
    try:
        results = client.analyze_sentiment(
            documents=texts,
            show_opinion_mining=True
        )
        return results

    except Exception as e:
        print(f"[Azure Error] {e}")
        return []


def get_sentiment_label(positive_score, neutral_score, negative_score):
    """
    根據平均後的 confidence score，重新決定 sentiment label。
    """
    score_dict = {
        "positive": positive_score,
        "neutral": neutral_score,
        "negative": negative_score
    }

    return max(score_dict, key=score_dict.get)


def analyze_one_record(client, record, max_chars=4500, batch_size=10):
    """
    分析單一 record。
    若文字太長，會切成多個 chunk，再把 score 平均。
    """
    text = record["text"]
    text_chunks = split_text_by_max_chars(text, max_chars=max_chars)

    chunk_results = []

    for batch in chunk_list(text_chunks, batch_size=batch_size):
        azure_results = analyze_sentiment_batch(client, batch)

        for chunk_text, result in zip(batch, azure_results):
            if result.is_error:
                chunk_results.append({
                    "sentiment": None,
                    "positive_score": None,
                    "neutral_score": None,
                    "negative_score": None,
                    "error": result.error.message
                })
            else:
                chunk_results.append({
                    "sentiment": result.sentiment,
                    "positive_score": result.confidence_scores.positive,
                    "neutral_score": result.confidence_scores.neutral,
                    "negative_score": result.confidence_scores.negative,
                    "error": None
                })

    valid_results = [r for r in chunk_results if r["error"] is None]

    if not valid_results:
        return {
            **record,
            "sentiment": None,
            "positive_score": None,
            "neutral_score": None,
            "negative_score": None,
            "chunk_count": len(text_chunks),
            "error": "All chunks failed."
        }

    positive_avg = sum(r["positive_score"] for r in valid_results) / len(valid_results)
    neutral_avg = sum(r["neutral_score"] for r in valid_results) / len(valid_results)
    negative_avg = sum(r["negative_score"] for r in valid_results) / len(valid_results)

    sentiment = get_sentiment_label(
        positive_score=positive_avg,
        neutral_score=neutral_avg,
        negative_score=negative_avg
    )

    return {
        **record,
        "sentiment": sentiment,
        "positive_score": round(positive_avg, 4),
        "neutral_score": round(neutral_avg, 4),
        "negative_score": round(negative_avg, 4),
        "chunk_count": len(text_chunks),
        "error": None
    }


def run_sentiment_analysis(client, input_df, max_chars=4500, batch_size=10):
    """
    對所有 prepared / question / answer 執行情緒分析。
    """
    result_rows = []

    records = input_df.to_dict("records")
    total = len(records)

    for idx, record in enumerate(records, start=1):
        print(
            f"正在分析第 {idx}/{total} 筆："
            f"{record['company']} - {record['section_type']} - {record['text_id']}"
        )

        analyzed_record = analyze_one_record(
            client=client,
            record=record,
            max_chars=max_chars,
            batch_size=batch_size
        )

        result_rows.append(analyzed_record)

    return pd.DataFrame(result_rows)


# ============================================================
# 5. Q&A Tone Gap
# ============================================================

def build_qna_sentiment_summary(sentiment_result_df):
    """
    將 question 與 answer 的情緒分析結果合併成同一列。
    """
    qna_df = sentiment_result_df[
        sentiment_result_df["section_type"].isin(["question", "answer"])
    ].copy()

    question_df = qna_df[qna_df["section_type"] == "question"].copy()
    answer_df = qna_df[qna_df["section_type"] == "answer"].copy()

    question_df = question_df.rename(columns={
        "text": "question_text",
        "sentiment": "question_sentiment",
        "positive_score": "question_positive_score",
        "neutral_score": "question_neutral_score",
        "negative_score": "question_negative_score"
    })

    answer_df = answer_df.rename(columns={
        "text": "answer_text",
        "sentiment": "answer_sentiment",
        "positive_score": "answer_positive_score",
        "neutral_score": "answer_neutral_score",
        "negative_score": "answer_negative_score"
    })

    question_cols = [
        "company",
        "pair_id",
        "question_text",
        "question_sentiment",
        "question_positive_score",
        "question_neutral_score",
        "question_negative_score"
    ]

    answer_cols = [
        "company",
        "pair_id",
        "answer_text",
        "answer_sentiment",
        "answer_positive_score",
        "answer_neutral_score",
        "answer_negative_score"
    ]

    merged_df = pd.merge(
        question_df[question_cols],
        answer_df[answer_cols],
        on=["company", "pair_id"],
        how="inner"
    )

    return merged_df


def classify_tone_gap(row):
    """
    判斷分析師問題與管理層回答之間的語氣落差。
    """
    q = row["question_sentiment"]
    a = row["answer_sentiment"]

    if pd.isna(q) or pd.isna(a):
        return "unknown"

    if q == a:
        return "aligned"

    if q == "negative" and a == "positive":
        return "negative_question_positive_answer"

    if q == "negative" and a == "neutral":
        return "negative_question_neutral_answer"

    if q == "neutral" and a == "positive":
        return "neutral_question_positive_answer"

    if q == "positive" and a in ["neutral", "negative"]:
        return "positive_question_less_positive_answer"

    return f"{q}_question_{a}_answer"


def add_qna_tone_gap_features(qna_summary_df):
    """
    加上 tone gap 相關欄位。
    """
    df = qna_summary_df.copy()

    df["tone_gap_label"] = df.apply(classify_tone_gap, axis=1)

    df["negative_question_soft_answer_flag"] = (
        (df["question_sentiment"] == "negative") &
        (df["answer_sentiment"].isin(["neutral", "positive"]))
    )

    df["negative_score_gap"] = (
        df["question_negative_score"] -
        df["answer_negative_score"]
    ).round(4)

    df["risk_downplay_flag"] = df["negative_score_gap"] > 0.4

    return df


# ============================================================
# 6. Prepared Remarks vs Q&A Tone Shift
# ============================================================

def summarize_company_section_sentiment(sentiment_result_df):
    """
    計算公司在 prepared / question / answer 的平均情緒分數。
    """
    summary_df = (
        sentiment_result_df
        .groupby(["company", "section_type"], as_index=False)
        .agg({
            "positive_score": "mean",
            "neutral_score": "mean",
            "negative_score": "mean"
        })
    )

    summary_df["positive_score"] = summary_df["positive_score"].round(4)
    summary_df["neutral_score"] = summary_df["neutral_score"].round(4)
    summary_df["negative_score"] = summary_df["negative_score"].round(4)

    return summary_df


def build_tone_shift_table(section_summary_df):
    """
    比較公司簡報 prepared remarks 與 Q&A answer 的語氣差異。
    """
    prepared_df = section_summary_df[
        section_summary_df["section_type"] == "prepared"
    ].copy()

    answer_df = section_summary_df[
        section_summary_df["section_type"] == "answer"
    ].copy()

    prepared_df = prepared_df.rename(columns={
        "positive_score": "prepared_positive_score",
        "neutral_score": "prepared_neutral_score",
        "negative_score": "prepared_negative_score"
    })

    answer_df = answer_df.rename(columns={
        "positive_score": "answer_positive_score",
        "neutral_score": "answer_neutral_score",
        "negative_score": "answer_negative_score"
    })

    tone_shift_df = pd.merge(
        prepared_df[
            [
                "company",
                "prepared_positive_score",
                "prepared_neutral_score",
                "prepared_negative_score"
            ]
        ],
        answer_df[
            [
                "company",
                "answer_positive_score",
                "answer_neutral_score",
                "answer_negative_score"
            ]
        ],
        on="company",
        how="inner"
    )

    tone_shift_df["positive_score_shift"] = (
        tone_shift_df["answer_positive_score"] -
        tone_shift_df["prepared_positive_score"]
    ).round(4)

    tone_shift_df["negative_score_shift"] = (
        tone_shift_df["answer_negative_score"] -
        tone_shift_df["prepared_negative_score"]
    ).round(4)

    tone_shift_df["tone_shift_flag"] = (
        tone_shift_df["negative_score_shift"] > 0.15
    )

    return tone_shift_df


# ============================================================
# 7. 輸出必要 JSON
# ============================================================

def clean_for_json(obj):
    """
    遞迴清理資料，將 pandas NaN / NaT / None-like 值轉成標準 JSON 的 null。
    避免 json.dump(..., allow_nan=False) 報錯。
    """
    if isinstance(obj, dict):
        return {key: clean_for_json(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [clean_for_json(item) for item in obj]

    if isinstance(obj, tuple):
        return [clean_for_json(item) for item in obj]

    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass

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
    qna_summary_df,
    section_summary_df,
    tone_shift_df
):
    """
    只輸出 MVP 必要 JSON。
    每家公司會有自己的輸出資料夾：
    sentiment_output/{company_prefix}/
    """
    output_dir = Path(output_dir) / company_prefix
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Q&A sentiment summary
    qna_json = output_dir / "qna_sentiment_summary.json"

    save_dataframe_as_json(
        df=qna_summary_df,
        output_path=qna_json,
        metadata={
            "module": "qna_sentiment_summary",
            "company": company_prefix,
            "description": "Question-answer sentiment comparison and tone gap results.",
            "total_records": len(qna_summary_df)
        },
        records_key="qna_results"
    )

    # 2. Section sentiment summary
    section_json = output_dir / "section_sentiment_summary.json"

    save_dataframe_as_json(
        df=section_summary_df,
        output_path=section_json,
        metadata={
            "module": "section_sentiment_summary",
            "company": company_prefix,
            "description": "Average sentiment scores by company and section type.",
            "total_records": len(section_summary_df)
        },
        records_key="section_results"
    )

    # 3. Company tone shift summary
    tone_json = output_dir / "company_tone_shift_summary.json"

    save_dataframe_as_json(
        df=tone_shift_df,
        output_path=tone_json,
        metadata={
            "module": "company_tone_shift_summary",
            "company": company_prefix,
            "description": "Tone shift comparison between prepared remarks and Q&A answers.",
            "total_records": len(tone_shift_df)
        },
        records_key="tone_shift_results"
    )

    print("\n已輸出必要 JSON 檔案：")
    print(f"- {qna_json}")
    print(f"- {section_json}")
    print(f"- {tone_json}")

# ============================================================
# 8. Main
# ============================================================

def main():
    print("========== Azure Sentiment Analysis Module ==========")

    config = load_config("config.ini")

    input_dir = config["input_dir"]
    output_dir = config["output_dir"]
    company_prefix = config["company_prefix"]
    use_translated = config["use_translated"]
    batch_size = config["batch_size"]
    max_chars = config["max_chars"]

    print("\n[Config]")
    print(f"company_prefix : {company_prefix}")
    print(f"input_dir      : {input_dir}")
    print(f"output_dir     : {output_dir}/{company_prefix}")
    print(f"use_translated : {use_translated}")
    print(f"batch_size     : {batch_size}")
    print(f"max_chars      : {max_chars}")

    print("\n[1/5] 建立 Azure Text Analytics Client...")
    client = create_text_analytics_client(
        azure_key=config["azure_key"],
        azure_endpoint=config["azure_endpoint"]
    )

    print("\n[2/5] 讀取單一公司 JSON 並建立 sentiment input DataFrame...")
    sentiment_input_df = build_sentiment_input_dataframe(
        input_dir=input_dir,
        company_prefix=company_prefix,
        use_translated=use_translated
    )

    print(f"共整理出 {len(sentiment_input_df)} 筆待分析文字。")

    if sentiment_input_df.empty:
        print("沒有找到可分析資料，請確認 input 資料夾與 JSON 檔名。")
        return

    print("\n[3/5] 執行 Azure Sentiment Analysis...")
    sentiment_result_df = run_sentiment_analysis(
        client=client,
        input_df=sentiment_input_df,
        max_chars=max_chars,
        batch_size=batch_size
    )

    print("\n[4/5] 建立 Q&A Tone Gap 與 Section Tone Shift...")
    qna_summary_df = build_qna_sentiment_summary(sentiment_result_df)
    qna_summary_df = add_qna_tone_gap_features(qna_summary_df)

    section_summary_df = summarize_company_section_sentiment(sentiment_result_df)
    tone_shift_df = build_tone_shift_table(section_summary_df)

    print("\n[5/5] 輸出 JSON...")
    save_outputs(
        output_dir=output_dir,
        company_prefix=company_prefix,
        qna_summary_df=qna_summary_df,
        section_summary_df=section_summary_df,
        tone_shift_df=tone_shift_df
    )

    print("\n========== Sentiment Analysis Finished ==========")


if __name__ == "__main__":
    main()