import re
from datetime import datetime, timedelta
from underthesea import word_tokenize, ner
from dateutil.parser import parse as dateutil_parse

def preprocess(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    
    replacements = {
        'thứ 2': 'thứ_hai',
        'thứ 3': 'thứ_ba',
        'thứ 4': 'thứ_tư',
        'thứ 5': 'thứ_năm',
        'thứ 6': 'thứ_sáu',
        'thứ 7': 'thứ_bảy',
        'thứ hai': 'thứ_hai',
        'thứ ba': 'thứ_ba',
        'thứ tư': 'thứ_tư',
        'thu tu': 'thứ_tư',
        'thứ năm': 'thứ_năm',
        'thu nam': 'thứ_năm',
        'thứ sáu': 'thứ_sáu',
        'thu sau': 'thứ_sáu',
        'thứ bảy': 'thứ_bảy',
        'thu bay': 'thứ_bảy',
        'chủ nhật': 'chủ_nhật',
        'chu nhat': 'chủ_nhật',
        'cn': 'chủ_nhật',
        'ngày mai': 'ngày_mai',
        'ngay mai': 'ngày_mai',
        'hôm nay': 'hôm_nay',
        'hom nay': 'hôm_nay',
        'ngày kia': 'ngày_kia',
        'ngay kia': 'ngày_kia',
        'tuần sau': 'tuần_sau',
        'tuan sau': 'tuần_sau',
        'tuần tới': 'tuần_tới',
        'tuan toi': 'tuần_tới',
        'cuối tuần': 'cuối_tuần',
        'cuoi tuan': 'cuối_tuần'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text

def extract_ner_entities(text: str) -> tuple[dict, str]:
    try:
        ner_tags = ner(text)
    except Exception as e:
        print(f"Lỗi NER: {e}")
        return {"TIME": [], "LOCATION": []}, text
    
    entities = {
        "TIME": [],
        "LOCATION": [],
    }
    
    current_entity_text = ""
    current_entity_type = ""
    
    for word, pos_tag, chunk_tag, ner_tag in ner_tags:
        tag_type = ner_tag.split('-')[-1]
        prefix = ner_tag.split('-')[0]
        
        if prefix == 'B':
            if current_entity_text and current_entity_type in entities:
                entities[current_entity_type].append(current_entity_text.strip())
            
            current_entity_text = word
            current_entity_type = tag_type
            
        elif prefix == "I" and current_entity_type == tag_type:
            current_entity_text += " " + word
            
        elif prefix == "O":
            if current_entity_text and current_entity_type in entities:
                entities[current_entity_type].append(current_entity_text.strip())
            current_entity_type = ""
            current_entity_text = ""
    
    # Lưu entity cuối cùng
    if current_entity_text and current_entity_type in entities:
        entities[current_entity_type].append(current_entity_text.strip())
    
    # Loại bỏ entities đã trích xuất khỏi text
    remaining_text = text
    for time_str in entities["TIME"]:
        remaining_text = remaining_text.replace(time_str, "")
    for loc_str in entities["LOCATION"]:
        remaining_text = remaining_text.replace(loc_str, "")
    
    remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()
    
    return entities, remaining_text

def extract_rule_entities(original_text: str, remaining_text: str) -> dict:
    rules = {}
    
    # Pattern nhắc nhở: "nhắc trước 15 phút", "nhắc 30 phút", "nhac 10p"
    reminder_patterns = [
        r"(?:nhắc trước|nhắc|nhac trước|nhac trc|nhac)\s*(\d+)\s*(?:phút|phut|p)",
        r"(?:nhac|nhắc)\s+(\d+)\s*(?:phút|phut|p)",
    ]
    
    reminder_match = None
    for pattern in reminder_patterns:
        reminder_match = re.search(pattern, remaining_text)
        if reminder_match:
            break
    
    if not reminder_match:
        # Thử tìm trong text gốc
        for pattern in reminder_patterns:
            reminder_match = re.search(pattern, original_text)
            if reminder_match:
                break
    
    if reminder_match:
        try:
            rules["reminder_minutes"] = int(reminder_match.group(1))
            remaining_text = remaining_text.replace(reminder_match.group(0), "")
        except (ValueError, IndexError):
            rules["reminder_minutes"] = None
    else:
        rules["reminder_minutes"] = None
    
    # Trích xuất event name: loại bỏ các từ phụ trợ
    stop_words = ['ở', 'tại', 'lúc', 'vào', 'o', 'tai', 'luc', 'vao', 'cho', 'để', 'de']
    event_name = remaining_text
    
    for word in stop_words:
        event_name = event_name.replace(f" {word} ", " ")
    
    event_name = re.sub(r'\s+', ' ', event_name).strip()
    event_name = event_name.replace("nhắc tôi", "").replace("nhac toi", "")
    event_name = re.sub(r'\s+', ' ', event_name).strip()
    
    rules["event"] = event_name if event_name else None
    
    return rules

def parse_vietnamese_time(time_text: str, base_now: datetime = None) -> datetime:
    if not time_text:
        return None
    
    now = base_now if base_now else datetime.now()
    text = time_text.lower()
    
    base_date = now
    
    # Xử lý ngày tương đối
    if "ngày_mai" in text or "mai" in text:
        base_date = now + timedelta(days=1)
    elif "ngày_kia" in text or "kia" in text:
        base_date = now + timedelta(days=2)
    elif "hôm_nay" in text or "nay" in text:
        base_date = now
    
    # Xử lý thứ trong tuần
    weekday_map = {
        "thứ_hai": 0,
        "thứ_ba": 1,
        "thứ_tư": 2,
        "thứ_năm": 3,
        "thứ_sáu": 4,
        "thứ_bảy": 5,
        "chủ_nhật": 6,
    }
    
    for day_name, day_num in weekday_map.items():
        if day_name in text:
            if "tới" in text or "sau" in text or "tuần_sau" in text:
                # Thứ X tuần sau
                days_ahead = day_num - base_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                base_date = base_date + timedelta(days=days_ahead)
            else:
                # Thứ X tuần này
                days_ahead = day_num - base_date.weekday()
                if days_ahead < 0:
                    days_ahead += 7
                base_date = base_date + timedelta(days=days_ahead)
            break
    
    # Xử lý "cuối tuần"
    if "cuối_tuần" in text:
        days_ahead = 5 - base_date.weekday()  # Thứ 7
        if days_ahead <= 0:
            days_ahead += 7
        base_date = base_date + timedelta(days=days_ahead)
    
    # Xử lý "tuần sau" không có thứ cụ thể
    if ("tuần_sau" in text or "tuần_tới" in text) and \
       not any(day in text for day in weekday_map.keys()):
        base_date = base_date + timedelta(weeks=1)
    
    # Trích xuất giờ phút
    hour, minute = None, 0
    
    # Thử dùng dateutil trước
    try:
        dt = dateutil_parse(text, fuzzy=True)
        # Chỉ lấy giờ phút từ dateutil, giữ nguyên base_date
        hour, minute = dt.hour, dt.minute
    except (ValueError, AttributeError):
        pass
    
    # Nếu dateutil không extract được, dùng regex
    if hour is None:
        # Pattern: 10h30, 10:30
        time_match = re.search(r"(\d{1,2})[h:](\d{1,2})", text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
        else:
            # Pattern: 10h, 10 giờ
            time_match_simple = re.search(r"(\d{1,2})\s*(?:h|giờ|gio)", text)
            if time_match_simple:
                hour = int(time_match_simple.group(1))
                minute = 0
    
    # Nếu vẫn chưa có giờ, dùng giờ mặc định theo buổi
    if hour is None:
        if "sáng" in text or "sang" in text:
            hour = 9
        elif "trưa" in text or "trua" in text:
            hour = 12
        elif "chiều" in text or "chieu" in text:
            hour = 14
        elif "tối" in text or "toi" in text:
            hour = 20
        else:
            return None
    
    # Điều chỉnh AM/PM
    if ("chiều" in text or "chieu" in text) and hour < 12:
        hour += 12
    if ("tối" in text or "toi" in text) and hour < 12:
        hour += 12
    
    # Tạo datetime kết quả
    try:
        result = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return result
    except ValueError:
        return None

def parse_sentence(sentence: str) -> dict:
    if not sentence or not sentence.strip():
        return {"error": "Câu rỗng hoặc không hợp lệ."}
    
    try:
        # Bước 1: Preprocessing
        text = preprocess(sentence)
        
        # Bước 2: NER Extraction (Model-based)
        ner_entities, remaining_text = extract_ner_entities(text)
        
        # Bước 3: Rule-based Extraction
        rule_entities = extract_rule_entities(text, remaining_text)
        
        # Bước 4: Time Parsing
        time_text = ner_entities["TIME"][0] if ner_entities["TIME"] else None
        
        # Nếu NER không tìm thấy TIME, dùng regex trên remaining_text
        if not time_text:
            time_pattern = re.search(
                r"(\d{1,2}\s*(?:h|giờ|gio|:)\s*\d{0,2}|\d{1,2}\s*(?:h|giờ|gio)|"
                r"sáng|sang|trưa|trua|chiều|chieu|tối|toi|"
                r"ngày_mai|mai|hôm_nay|nay|ngày_kia|kia|"
                r"thứ_\w+|thu_\w+|chủ_nhật|chu_nhat|cn|"
                r"cuối_tuần|tuần_sau|tuần_tới)",
                remaining_text
            )
            if time_pattern:
                time_text = time_pattern.group(0)
            else:
                # Thử tìm trong text gốc
                time_pattern = re.search(
                    r"(\d{1,2}\s*(?:h|giờ|gio|:)\s*\d{0,2}|\d{1,2}\s*(?:h|giờ|gio)|"
                    r"sáng|sang|trưa|trua|chiều|chieu|tối|toi|"
                    r"ngày_mai|mai|hôm_nay|nay|ngày_kia|kia|"
                    r"thứ_\w+|thu_\w+|chủ_nhật|chu_nhat|cn|"
                    r"cuối_tuần|tuần_sau|tuần_tới)",
                    text
                )
                if time_pattern:
                    time_text = time_pattern.group(0)
        
        start_time_dt = parse_vietnamese_time(time_text)
        
        if not start_time_dt:
            return {"error": "Không thể xác định thời gian sự kiện."}
        
        start_time_iso = start_time_dt.isoformat()
        
        # Bước 5: Hợp nhất & Validation
        location = ner_entities["LOCATION"][0] if ner_entities["LOCATION"] else None
        
        event_name = rule_entities.get("event")
        if not event_name or len(event_name.strip()) == 0:
            return {"error": "Không thể xác định tên sự kiện."}
        
        # Trả về dictionary theo đúng format yêu cầu
        return {
            "event": event_name,
            "start_time": start_time_iso,
            "end_time": None,
            "location": location,
            "reminder_minutes": rule_entities.get("reminder_minutes")
        }
        
    except Exception as e:
        return {"error": f"Lỗi xử lý: {str(e)}"}

# Test cases
if __name__ == "__main__":
    test_cases = [
        "Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302, nhắc trước 15 phút",
        "Đi cafe với bạn thứ hai tới lúc 8h tối",
        "Học bài vào 3h chiều hôm nay",
        "Họp team 9h30 sáng mai tại văn phòng",
        "Gặp khách hàng thứ 6 này 2h chiều nhắc 30 phút",
        "Đi gym cuối tuần 7h sáng",
        "Sinh nhật bạn thứ 7 tới 6h tối ở nhà hàng ABC nhắc trước 60 phút",
        "Di choi voi ban 10h sang mai",  # Không dấu
        "hop nhom 2h chieu thu 3 toi",   # Không dấu
    ]
    
    print("=" * 80)
    print("TEST CASES - NLP MODULE")
    print("=" * 80)
    
    for i, sentence in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Câu: {sentence}")
        result = parse_sentence(sentence)
        print(f"Kết quả: {result}")
        print("-" * 80)