import os
import json
import uuid
import time
import requests
import configparser
import re
from typing import List, Tuple
from pydantic import BaseModel, Field
from openai import AzureOpenAI

# ==========================================
# 1. 讀取 config.ini 設定檔
# ==========================================
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

AOAI_KEY = config['AzureOpenAI']['API_KEY']
AOAI_ENDPOINT = config['AzureOpenAI']['API_ENDPOINT']  
AOAI_VERSION = config['AzureOpenAI']['API_VERSION']
AOAI_DEPLOYMENT = config['AzureOpenAI']['DEPLOYMENT_NAME']

TRANS_KEY = config['AzureTranslator']['TRANSLATOR_KEY']
TRANS_REGION = config['AzureTranslator']['TRANSLATOR_REGION']
TRANS_ENDPOINT = config.get('AzureTranslator', 'TRANSLATOR_ENDPOINT', fallback='https://api.cognitive.microsofttranslator.com')

aoai_client = AzureOpenAI(
    api_key=AOAI_KEY,
    api_version=AOAI_VERSION,
    azure_endpoint=AOAI_ENDPOINT
)

# ==========================================
# 2. 核心功能：語言自動偵測 ( Auto-Detect)
# ==========================================
def detect_language(text: str) -> Tuple[str, str]:
    """
    抓取前 500 字元，利用正規表達式計算中文漢字的數量。
    回傳: (source_language, target_language)
    """
    sample = text[:500]
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', sample)
    
    # 如果前 500 字中出現超過 10 個中文字，高度機率為中文法說會 (如鴻海)
    if len(chinese_chars) > 10:
        return "zh-Hant", "en"
    else:
        return "en", "zh-Hant"

# ==========================================
# 3. 定義 Pydantic 結構 (用於 LLM 強制輸出)
# ==========================================
class QnAPair(BaseModel):
    question: str = Field(..., description="分析師的提問原文。絕不能包含管理層的回答。")
    answer: str = Field(..., description="管理層的回答原文。絕不能為空字串，也不可包含分析師的提問。")

class QnAExtraction(BaseModel):
    qna_list: List[QnAPair] = Field(..., description="這段文本中擷取出的所有 Q&A 配對陣列")

# ==========================================
# 4. Azure Translator 翻譯模組
# ==========================================
translator_session = requests.Session()

def translate_text(text: str, target_lang: str) -> str:
    if not text or len(text.strip()) == 0:
        return ""
        
    path = '/translate'
    constructed_url = TRANS_ENDPOINT + path
    params = {'api-version': '3.0', 'to': [target_lang]}
    headers = {
        'Ocp-Apim-Subscription-Key': TRANS_KEY,
        'Ocp-Apim-Subscription-Region': TRANS_REGION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text}]
    
    for attempt in range(3):
        try:
            response = translator_session.post(constructed_url, params=params, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result[0]['translations'][0]['text']
        except Exception as e:
            print(f"    [警告] 翻譯發生異常 (嘗試 {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return text

# ==========================================
# 5. 文本切塊工具
# ==========================================
def chunk_text(text: str, chunk_size: int = 8000, overlap: int = 1500) -> List[str]:
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        if len(current_chunk) + len(para) > chunk_size and len(current_chunk) > 0:
            chunks.append(current_chunk.strip())
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            last_period = overlap_text.find('. ')
            if last_period != -1:
                overlap_text = overlap_text[last_period+2:]
            current_chunk = overlap_text + "\n\n" + para
        else:
            current_chunk += para + "\n\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# ==========================================
# 6. OpenAI Q&A 擷取邏輯
# ==========================================
def extract_qna_from_chunk(chunk_text: str) -> List[dict]:
    system_prompt = """
    你是一位專業的金融數據萃取專家。
    請從法說會逐字稿中，精準找出「提問 (Question)」與「回答 (Answer)」。

    【嚴格規則】：
    1. 100% 複製原文，不可摘要。
    2. Question 絕對不可包含回答。Answer 絕對不可為空。
    3. 過濾掉 "Operator: The first question is..." 等無意義的串場。
    4. 當語氣轉為「給予解答的陳述句」時（例如 "We expect...", "Let me answer..." 或中文的 "我們預期..."），這就是【回答的起點】，必須在此狠心切斷。
    """
    try:
        response = aoai_client.beta.chat.completions.parse(
            model=AOAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"請萃取：\n\n{chunk_text}"}
            ],
            response_format=QnAExtraction,
            temperature=0.0
        )
        extracted_data = response.choices[0].message.parsed
        
        valid_pairs = []
        for pair in extracted_data.qna_list:
            q = pair.question.strip()
            a = pair.answer.strip()
            if len(a) > 5 and len(q) > 5:
                valid_pairs.append(pair.model_dump())
            else:
                print("\n    [過濾] 🚨 偵測到異常擷取，此筆資料已被自動丟棄！")
                print(f"      ❌ 被丟棄的 Question 內容: {q}")
                print(f"      ❌ 被丟棄的 Answer 內容: {a}\n")
        return valid_pairs
    except Exception as e:
        print(f"擷取發生錯誤: {e}")
        return []

# ==========================================
# 7. 雙軌主程式 (結合自動判斷與 Metadata 結構)
# ==========================================
def generate_full_transcript_json(full_text: str, source_lang: str, target_lang: str) -> dict:
    """軌道一：完整逐字稿純翻譯 (Metadata + Payload 結構)"""
    print(f"\n[軌道一] 開始處理完整逐字稿 (來源: {source_lang} -> 目標: {target_lang})...")
    paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
    
    content_list = []
    total_paras = len(paragraphs)
    
    for idx, para in enumerate(paragraphs, start=1):
        if idx % 10 == 0:
            print(f"  -> 處理完整段落 {idx}/{total_paras}...")
            
        translated_para = translate_text(para, target_lang)
        
        content_list.append({
            "paragraph_index": idx,
            "original_text": para,
            "translated_text": translated_para
        })
        time.sleep(0.1)
        
    print("  ✅ [軌道一] 完整逐字稿處理完成！")
    
    # 封裝成階層式 JSON
    return {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_paragraphs": total_paras
        },
        "content": content_list
    }

def generate_extracted_qna_json(qna_text: str, source_lang: str, target_lang: str) -> dict:
    """軌道二：Q&A 擷取與翻譯 (Metadata + Payload 結構)"""
    print(f"\n[軌道二] 開始進行 Q&A 智慧擷取 (來源: {source_lang} -> 目標: {target_lang})...")
    
    chunks = chunk_text(qna_text, chunk_size=8000, overlap=1500)
    all_qna = []
    
    print(f"  -> 開始 OpenAI 擷取 (共 {len(chunks)} 塊)...")
    for chunk in chunks:
        qna_pairs = extract_qna_from_chunk(chunk)
        all_qna.extend(qna_pairs)
        
    print("  -> 進行去重覆處理 (Deduplication)...")
    unique_qna = []
    seen_questions = set()
    for item in all_qna:
        q_key = item['question'][:50].strip().lower()
        if q_key not in seen_questions and len(q_key) > 10:
            seen_questions.add(q_key)
            unique_qna.append(item)
            
    print(f"  -> 擷取完成，去重覆後共 {len(unique_qna)} 組有效 Q&A。開始獨立翻譯...")
    
    for idx, item in enumerate(unique_qna):
        print(f"    - 正在翻譯 Q&A 第 {idx+1} 組...")
        item['question_translated'] = translate_text(item['question'], target_lang)
        time.sleep(0.1)
        item['answer_translated'] = translate_text(item['answer'], target_lang)
        time.sleep(0.1)
        
    print("  ✅ [軌道二] Q&A 擷取處理完成！")
    
    # 封裝成階層式 JSON，保持雙軌資料庫風格統一
    return {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_qna_pairs": len(unique_qna)
        },
        "qna_list": unique_qna
    }

# ==========================================
# 測試執行區塊 (全自動批次處理)
# ==========================================
if __name__ == "__main__":
    # 只需要定義公司名稱，語言完全交給程式自動判斷！
    companies = ["tsmc", "nvda", "foxconn"]
    
    os.makedirs("output", exist_ok=True)
    
    for prefix in companies:
        print(f"\n{'='*60}")
        print(f"🚀 開始處理公司: {prefix.upper()}")
        print(f"{'='*60}")
        
        full_call_path = f"data/{prefix}_earnings_call.txt"
        qna_only_path = f"data/{prefix}_qna.txt"
        
        raw_transcript_json_path = f"output/{prefix}_full_transcript_translation.json"
        extracted_qna_json_path = f"output/{prefix}_extracted_qna_translation.json"
        
        try:
            # 讀取完整檔案並「自動偵測語言」
            print(f"📥 讀取並分析語言: {full_call_path}")
            with open(full_call_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            
            source_lang, target_lang = detect_language(full_text)
            print(f"   [系統偵測] 發現來源語言為: {source_lang}，目標翻譯設定為: {target_lang}")
                
            # --- 執行軌道一 ---
            full_transcript_result = generate_full_transcript_json(full_text, source_lang, target_lang)
            with open(raw_transcript_json_path, "w", encoding="utf-8") as f:
                json.dump(full_transcript_result, f, indent=2, ensure_ascii=False)
                
            # --- 執行軌道二 ---
            print(f"\n📥 讀取純 Q&A 檔案: {qna_only_path}")
            with open(qna_only_path, "r", encoding="utf-8") as f:
                qna_text = f.read()
                
            qna_result = generate_extracted_qna_json(qna_text, source_lang, target_lang)
            with open(extracted_qna_json_path, "w", encoding="utf-8") as f:
                json.dump(qna_result, f, indent=2, ensure_ascii=False)
                
            print(f"\n🎉 公司 {prefix.upper()} 處理完畢！")
            
        except FileNotFoundError as e:
            print(f"\n❌ 找不到 {prefix.upper()} 的檔案，跳過處理。")
            print(f"   請確認 data/ 資料夾下有 {prefix}_earnings_call.txt 與 {prefix}_qna.txt")
            continue
