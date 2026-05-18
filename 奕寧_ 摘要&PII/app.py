import os
import json
import time
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient

# 1. 載入環境變數
load_dotenv(override=True)
endpoint = os.getenv("AZURE_LANGUAGE_ENDPOINT")
key = os.getenv("AZURE_LANGUAGE_KEY")

# 初始化 Azure Client
client = TextAnalyticsClient(
    endpoint=endpoint, 
    credential=AzureKeyCredential(key)
)

def run_pii_and_summary(filename):
    input_path = os.path.join("data", filename)
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename.replace(".json", "_pii_summary.json"))

    if not os.path.exists(input_path):
        print(f"跳過：找不到檔案 {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    is_qna = "qna_list" in data
    source_lang = data['metadata']['source_language']
    
    if is_qna:
        documents = [f"Q: {item['question']} A: {item['answer']}" for item in data['qna_list']]
    else:
        documents = [item['original_text'] for item in data['content']]

    print(f"\n==========================================")
    print(f"正在處理: {filename}")
    print(f"==========================================")

    # --- 功能一：PII 偵測 (維持不變) ---
    redacted_list = []
    batch_size = 5 
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        safe_batch = [doc[:5000] for doc in batch]
        try:
            result = client.recognize_pii_entities(
                safe_batch,
                language="zh-Hant" if source_lang == "zh-Hant" else "en",
            )
            for doc in result:
                redacted_list.append(doc.redacted_text if not doc.is_error else "PII Error")
        except:
            redacted_list.extend(safe_batch)

   # --- 功能二：高品質重點摘要優化 (強化戰略廣度) ---
    summary_sentences = []
    if not is_qna:
        print(f"--- 啟動高品質摘要引擎: {filename} ---")
        summary_lang = "zh" if "zh" in source_lang else "en"
        
        # 保持前後包夾策略，確保不遺漏結尾的展望
        part1 = data['content'][3:25]  
        part2 = data['content'][-15:] 
        combined_content = part1 + part2
        full_text_content = " ".join([item['original_text'] for item in combined_content])

        if len(full_text_content.strip()) > 50:
            try:
                # 維持 20 句上限，這是 Azure 的規範
                poller = client.begin_extract_summary(
                    [full_text_content[:8000]], 
                    language=summary_lang,
                    max_sentence_count=20 
                )
                extract_summary_results = poller.result()
                
                candidate_sentences = []
                for res in extract_summary_results:
                    if not res.is_error:
                        candidate_sentences = [s.text.strip() for s in res.sentences]

                # 關鍵字詞庫
                essential_keys = [
                    "元", "EPS", "營收", "毛利", "ROE", "%", 
                    "展望", "倍數", "倍增", "成長", "強勁", 
                    "AI", "Blackwell", "Sovereign", "2奈米", 
                    "CDMS", "EV", "電動車", "機器人", "Robot", 
                    "海外", "建廠", "熊本", "亞利桑那", "量產", 
                    "風險", "挑戰", "局勢", "關稅", "庫存"
                ]
                
                #### 修改處 1：雙軌篩選邏輯 (數字軌 + 策略軌) ####
                # 分開存放「硬數據」與「戰略描述」，確保最後混合輸出
                hard_data_points = []
                strategic_points = []

                for s in candidate_sentences:
                    # 如果包含具體財務數字 (兆/億/%)，放入硬數據軌
                    if any(x in s for x in ["兆", "億", "%", "EPS", "元"]):
                        hard_data_points.append(s)
                    # 如果包含戰略關鍵字但沒數字，放入策略軌
                    elif any(key in s for key in essential_keys):
                        strategic_points.append(s)
                
                # #### 修改處 2：混合平衡輸出 ####
                # 目標：前 5 名中，至少要有 2 點是關於「產能、佈局、風險」的策略資訊
                # 這樣就不會整份摘要全是數字
                final_combined = []
                
                # 先放前 3 點最強的硬數據
                final_combined.extend(hard_data_points[:3])
                # 再放前 2 點最重要的策略描述 (補足 AI 建議的 CDMS、建廠時程)
                final_combined.extend(strategic_points[:2])
                
                # 去重並確保總數為 5
                seen = set()
                summary_sentences = []
                for s in final_combined + hard_data_points + strategic_points:
                    if s not in seen and len(summary_sentences) < 5:
                        summary_sentences.append(s)
                        seen.add(s)
                #### ---------------------------------------------------- ####
                
                for s in summary_sentences:
                    print(f"* 擷取重點: {s[:50]}...")
            except Exception as e:
                print(f"摘要執行失敗: {e}")

    # 儲存結果
    final_output = {
        "source_file": filename,
        "total_records": len(redacted_list),
        "summary": summary_sentences,
        "pii_redacted_full": redacted_list
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)
    print(f"完成！摘要句數: {len(summary_sentences)}")

# 3. 執行主迴圈
if __name__ == "__main__":
    companies = ["tsmc", "nvda", "foxconn"]
    file_types = ["full_transcript_translation", "extracted_qna_translation"]
    for co in companies:
        for t in file_types:
            run_pii_and_summary(f"{co}_{t}.json")