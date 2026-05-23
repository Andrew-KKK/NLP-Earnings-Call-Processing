import os
import json
import uuid
import requests
import configparser
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

translator_session = requests.Session()

# ==========================================
# 2. 翻譯首段並判定語言
# ==========================================
def probe_and_translate_first_paragraph(first_para: str) -> Tuple[str, str, str]:
    """
    拿第一個段落去雙語探測，回傳語言判定與「該段落的翻譯結果」。
    已移除 429 限制防護。
    """
    path = '/translate'
    constructed_url = TRANS_ENDPOINT + path
    
    # 雙目標語言探測
    params = {'api-version': '3.0', 'to': ['zh-Hant', 'en']}
    headers = {
        'Ocp-Apim-Subscription-Key': TRANS_KEY,
        'Ocp-Apim-Subscription-Region': TRANS_REGION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': first_para}]
    
    try:
        # 放寬 Timeout 到 30 秒
        response = translator_session.post(constructed_url, params=params, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        detected_info = result[0].get('detectedLanguage')
        if not detected_info:
            raise ValueError("Azure 無法從這段首段文字中確認語言")
            
        detected_lang = detected_info['language']
        translations = result[0]['translations']
        trans_dict = {t['to']: t['text'] for t in translations} 
        source_lang = detected_lang 
        
        if 'zh' in detected_lang.lower():
            target_lang = "en"
            translated_first_para = trans_dict.get('en', first_para)
        else:
            target_lang = "zh-Hant"
            translated_first_para = trans_dict.get('zh-Hant', first_para)
            
        return source_lang, target_lang, translated_first_para
        
    except Exception as e:
        print(f"    [錯誤] API 首段探測失敗 ({type(e).__name__}: {e})。系統將保留原文。")
        return "en", "zh-Hant", first_para

# ==========================================
# 3. Azure Translator 一般批次翻譯 (單一目標)
# ==========================================
def translate_text(text: str, target_lang: str) -> str:
    """
    呼叫 Azure Translator 進行後續段落的單向翻譯。
    已移除 429 限制防護。
    """
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
    
    try:
        response = translator_session.post(constructed_url, params=params, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result[0]['translations'][0]['text']
    except Exception as e:
        print(f"\n    [錯誤] 翻譯服務發生例外錯誤 ({type(e).__name__})。系統將保留原文。")
        return text

# ==========================================
# 4. 定義 Pydantic 結構
# ==========================================
class QnAPair(BaseModel):
    question: str = Field(..., description="分析師的提問原文。絕不能包含管理層的回答。")
    answer: str = Field(..., description="管理層的回答原文。絕不能為空字串，也不可包含分析師的提問。")

class QnAExtraction(BaseModel):
    qna_list: List[QnAPair] = Field(..., description="這段文本中擷取出的所有 Q&A 配對陣列")

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
        return valid_pairs
    except Exception as e:
        print(f"    [錯誤] 擷取發生異常: {type(e).__name__}")
        return []

# ==========================================
# 7. 雙軌輸出與封裝 (極致無損版)
# ==========================================
def generate_full_transcript_json(paragraphs: List[str], source_lang: str, target_lang: str, first_para_trans: str) -> dict:
    print(f"\n[軌道一] 開始處理完整逐字稿 (來源: {source_lang} -> 目標: {target_lang})...")
    
    content_list = []
    total_paras = len(paragraphs)
    
    for idx, para in enumerate(paragraphs, start=1):
        if idx % 10 == 0:
            print(f"  -> 處理完整段落 {idx}/{total_paras}...")
            
        if idx == 1:
            translated_para = first_para_trans
        else:
            translated_para = translate_text(para, target_lang)
            # 已移除 time.sleep(0.1)
            
        content_list.append({
            "paragraph_index": idx,
            "original_text": para,
            "translated_text": translated_para
        })
        
    print("  ✅ [軌道一] 完整逐字稿處理完成！")
    return {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_paragraphs": total_paras
        },
        "content": content_list
    }

def generate_extracted_qna_json(qna_text: str, source_lang: str, target_lang: str) -> dict:
    print(f"\n[軌道二] 開始進行 Q&A 智慧擷取 (來源: {source_lang} -> 目標: {target_lang})...")
    
    chunks = chunk_text(qna_text, chunk_size=8000, overlap=1500)
    all_qna = []
    
    for chunk in chunks:
        all_qna.extend(extract_qna_from_chunk(chunk))
        
    unique_qna = []
    seen_questions = set()
    for item in all_qna:
        q_key = item['question'][:50].strip().lower()
        if q_key not in seen_questions and len(q_key) > 10:
            seen_questions.add(q_key)
            unique_qna.append(item)
            
    print(f"  -> 擷取完成，去重覆後共 {len(unique_qna)} 組有效 Q&A。開始翻譯...")
    
    for idx, item in enumerate(unique_qna):
        print(f"    - 正在翻譯 Q&A 第 {idx+1} 組...")
        item['question_translated'] = translate_text(item['question'], target_lang)
        item['answer_translated'] = translate_text(item['answer'], target_lang)
        
    print("  ✅ [軌道二] Q&A 擷取處理完成！")
    return {
        "metadata": {
            "source_language": source_lang,
            "target_language": target_lang,
            "total_qna_pairs": len(unique_qna)
        },
        "qna_list": unique_qna
    }

# ==========================================
# 8. 全自動批次執行區塊
# ==========================================
if __name__ == "__main__":
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
            print(f"📥 讀取並執行「首段語言探測」: {full_call_path}")
            with open(full_call_path, "r", encoding="utf-8") as f:
                full_text = f.read()
                
            paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
            if not paragraphs:
                continue
                
            first_paragraph = paragraphs[0]
            source_lang, target_lang, first_para_trans = probe_and_translate_first_paragraph(first_paragraph)
            
            print(f"   [系統探測] Azure 判定原文為: {source_lang}，後續管線全面切換為單向翻譯: {target_lang}")
                
            full_transcript_result = generate_full_transcript_json(paragraphs, source_lang, target_lang, first_para_trans)
            with open(raw_transcript_json_path, "w", encoding="utf-8") as f:
                json.dump(full_transcript_result, f, indent=2, ensure_ascii=False)
                
            print(f"\n📥 讀取純 Q&A 檔案: {qna_only_path}")
            with open(qna_only_path, "r", encoding="utf-8") as f:
                qna_text = f.read()
                
            qna_result = generate_extracted_qna_json(qna_text, source_lang, target_lang)
            with open(extracted_qna_json_path, "w", encoding="utf-8") as f:
                json.dump(qna_result, f, indent=2, ensure_ascii=False)
                
            print(f"\n🎉 公司 {prefix.upper()} 處理完畢！")
            
        except FileNotFoundError as e:
            print(f"\n❌ 找不到 {prefix.upper()} 的檔案，跳過處理。")
            continue
