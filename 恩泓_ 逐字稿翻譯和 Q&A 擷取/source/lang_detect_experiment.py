import os
import uuid
import requests
import configparser
import re
import time

# ==========================================
# 1. 讀取 config.ini 設定檔
# ==========================================
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

TRANS_KEY = config['AzureTranslator']['TRANSLATOR_KEY']
TRANS_REGION = config['AzureTranslator']['TRANSLATOR_REGION']
TRANS_ENDPOINT = config.get('AzureTranslator', 'TRANSLATOR_ENDPOINT', fallback='https://api.cognitive.microsofttranslator.com')

translator_session = requests.Session()

# ==========================================
# 2. 實驗選手 A：Python 正規表達式 (段落級)
# ==========================================
def detect_language_regex_para(text: str) -> str:
    """
    檢查單一段落是否包含中文字元。
    回傳: "zh-Hant" 或 "en"
    """
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    # 只要段落中包含任何中文字元，就判定為中文
    if len(chinese_chars) > 0:
        return "zh-Hant"
    else:
        return "en"

# ==========================================
# 3. 實驗選手 B：Azure Translator API (全速無限制版)
# ==========================================
def detect_language_azure_para(text: str) -> str:
    """
    呼叫 Azure /translate 讓 AI 判斷該段落語言。
    """
    path = '/translate'
    constructed_url = TRANS_ENDPOINT + path
    
    params = {'api-version': '3.0', 'to': ['zh-Hant', 'en']}
    headers = {
        'Ocp-Apim-Subscription-Key': TRANS_KEY,
        'Ocp-Apim-Subscription-Region': TRANS_REGION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': text}]
    
    try:
        response = translator_session.post(constructed_url, params=params, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        detected_lang = result[0]['detectedLanguage']['language']
        
        if 'zh' in detected_lang.lower():
            return "zh-Hant"
        else:
            return "en"
            
    except Exception as e:
        return f"error: {type(e).__name__}"

# ==========================================
# 4. 實驗擂台：逐段比較並輸出差異
# ==========================================
if __name__ == "__main__":
    companies = ["tsmc", "nvda", "foxconn"]
    
    print("="*70)
    print("🔬 語言偵測深度實驗開始：逐段比較 (Regex vs Azure AI)")
    print("="*70)
    
    for prefix in companies:
        full_call_path = f"data/{prefix}_earnings_call.txt"
        
        try:
            with open(full_call_path, "r", encoding="utf-8") as f:
                full_text = f.read()
                
            paragraphs = [p.strip() for p in full_text.split('\n') if p.strip()]
            print(f"\n📂 正在分析 {prefix.upper()} 法說會 (共 {len(paragraphs)} 段)...")
            
            mismatches = []
            
            for idx, para in enumerate(paragraphs):
                # 顯示進度，避免以為程式當機
                if (idx + 1) % 10 == 0:
                    print(f"  -> 處理至第 {idx + 1}/{len(paragraphs)} 段...")
                    
                reg_result = detect_language_regex_para(para)
                az_result = detect_language_azure_para(para)
                
                # 如果雙方判斷不同，或是 Azure 發生錯誤，記錄下來
                if reg_result != az_result:
                    mismatches.append({
                        "index": idx + 1,
                        "text": para,
                        "regex": reg_result,
                        "azure": az_result
                    })
            
            # --- 印出該公司的對決結果 ---
            if not mismatches:
                print(f"  ✅ {prefix.upper()}: 完美一致！兩種方法在 {len(paragraphs)} 個段落中沒有任何分歧。")
            else:
                print(f"  ⚠️ {prefix.upper()}: 發現 {len(mismatches)} 個分歧段落！")
                for diff in mismatches:
                    print("\n  " + "-"*60)
                    print(f"  🔹 [段落 {diff['index']}]")
                    print(f"  🐍 Regex 判定 : {diff['regex']}")
                    print(f"  ☁️  Azure 判定 : {diff['azure']}")
                    # 如果段落太長，只印前 150 個字與最後 50 個字，方便閱讀
                    display_text = diff['text'] if len(diff['text']) < 200 else f"{diff['text'][:150]} ... [略] ... {diff['text'][-50:]}"
                    print(f"  📄 爭議原文   :\n{display_text}")
                print("  " + "-"*60)
                
        except FileNotFoundError:
            print(f"\n❌ 找不到 {prefix.upper()} 的測試檔案: {full_call_path}")
            continue
