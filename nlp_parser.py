import re
from datetime import datetime, timedelta
from underthesea import word_tokenize, ner
from dateutil.parser import parse as dateutil_parse

def preprocess(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+',' ', text)
    
    # <--- THAY ĐỔI / MỚI (Bổ sung các biến thể không dấu)
    replacements = {
        'thứ 2': 'thứ_2', 'thu 2': 'thứ_2',
        'thứ 3': 'thứ_3', 'thu 3': 'thứ_3',
        'thứ 4': 'thứ_4', 'thu 4': 'thứ_4',
        'thứ 5': 'thứ_5', 'thu 5': 'thứ_5',
        'thứ 6': 'thứ_6', 'thu 6': 'thứ_6',
        'thứ 7': 'thứ_7', 'thu 7': 'thứ_7',
        'chủ nhật': 'chủ_nhật', 'chu nhat': 'chủ_nhật', 'cn': 'chủ_nhật',
        'ngày mai': 'ngày_mai', 'ngay mai': 'ngày_mai',
        'ngày kia': 'ngày_kia', 'ngay kia': 'ngày_kia',
        'hôm nay': 'hôm_nay', 'hom nay': 'hôm_nay',
        'cuối tuần': 'cuối_tuần', 'cuoi tuan': 'cuối_tuần',
        'tuần sau': 'tuần_sau', 'tuan sau': 'tuần_sau',
        'tuần tới': 'tuần_tới', 'tuan toi': 'tuần_tới',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def extract_ner_entities(text: str) -> (dict, str):
    ner_tags = ner(text)
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
            if current_entity_text:
                if current_entity_type in entities:
                    entities[current_entity_type].append(current_entity_text.strip())
            current_entity_text = word
            current_entity_type = tag_type
            
        elif prefix == "I" and current_entity_type == tag_type:
            current_entity_text += " " + word
            
        elif prefix == "O":
            if current_entity_text:
                if current_entity_type in entities:
                    entities[current_entity_type].append(current_entity_text.strip())
            current_entity_type = ""
            current_entity_text = ""
            
    if current_entity_text and current_entity_type in entities:
        entities[current_entity_type].append(current_entity_text.strip())
    
    remaining_text = text
    for time_str in entities["TIME"]:
        remaining_text = remaining_text.replace(time_str, "")
    for loc_str in entities["LOCATION"]:
        remaining_text = remaining_text.replace(loc_str, "")
        
    remaining_text = remaining_text.replace("  ", " ").strip()
    
    return entities, remaining_text   

def extract_rule_entities(original_text: str, remaining_text: str) -> dict:
    # <--- THAY ĐỔI (Default reminder = 0, thêm duration)
    rules = {
        "reminder_minutes": 0,
        "duration_minutes": None
    }

    # 1. Trích xuất nhắc nhở (Reminder) - Nâng cấp
    # <--- THAY ĐỔI (Xử lý "giờ", "tiếng", "phút" và "một")
    reminder_match = re.search(r"nhắc trước (\d+|một) (phút|giờ|tiếng)", remaining_text)
    if reminder_match:
        value_str = reminder_match.group(1)
        value = 1 if value_str == "một" else int(value_str)
        unit = reminder_match.group(2)
        
        if unit == "giờ" or unit == "tiếng":
            value *= 60 # Chuyển đổi giờ sang phút
        
        rules["reminder_minutes"] = value
        remaining_text = remaining_text.replace(reminder_match.group(0), "")
    
    # 2. Trích xuất thời lượng (Duration) - MỚI
    # <--- MỚI (Xử lý "trong X giờ/phút")
    duration_match = re.search(r"trong (\d+|một) (phút|giờ|tiếng)", remaining_text)
    if duration_match:
        value_str = duration_match.group(1)
        value = 1 if value_str == "một" else int(value_str)
        unit = duration_match.group(2)
        
        if unit == "giờ" or unit == "tiếng":
            value *= 60 # Chuyển đổi giờ sang phút
        
        rules["duration_minutes"] = value
        remaining_text = remaining_text.replace(duration_match.group(0), "")

    # 3. Trích xuất tên sự kiện
    event_name = remaining_text.replace("ở", "").replace("tại", "").replace("lúc", "").strip()
    event_name = " ".join(event_name.split())
    rules["event"] = event_name if event_name else None
    
    return rules
    

def parse_vietnamese_time(time_text: str) -> datetime:
    if not time_text:
        return None
    
    now = datetime.now()
    text = time_text.lower()

    base_date = now

    if "mai" in text or "ngày_mai" in text:
        base_date = now + timedelta(days = 1)
    elif "kia" in text or "ngày_kia" in text:
        base_date = now + timedelta(days = 2)
    elif "hôm_nay" in text or "nay" in text:
        base_date = now
        
    weekday_map = {
        "thứ hai": 0,
        "thứ_2": 0,
        "thứ ba": 1,
        "thứ_3": 1,
        "thứ tư": 2,
        "thứ_4": 2,
        "thứ năm": 3,
        "thứ_5": 3,
        "thứ sáu": 4,
        "thứ_6": 4,
        "thứ bảy": 5,
        "thứ_7": 5,
        "chủ nhật": 6,
        "chủ_nhật": 6
    }
    
    # <--- SỬA LOGIC (Chỉ thay đổi ngày nếu có "tới" hoặc "sau")
    day_found = False
    for day, day_num in weekday_map.items():
        if day in text:
            day_found = True
            if ("tới" in text or "sau" in text or "tuần_sau" in text or "tuần_tới" in text):
                days_ahead = day_num - base_date.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                base_date = base_date + timedelta(days = days_ahead)
            else:
                # Mặc định là tuần này
                days_ahead = day_num - base_date.weekday()
                base_date = base_date + timedelta(days = days_ahead)
            break
    
    if "cuối_tuần" in text:
        days_ahead = 5 - base_date.weekday() # Mặc định là thứ 6
        if "sau" in text or "tới" in text:
            if days_ahead <= 0:
                days_ahead += 7
        base_date = base_date + timedelta(days = days_ahead)
        
    if ("tuần_sau" in text or "tuần_tới" in text) and not day_found:
        base_date = base_date + timedelta(weeks = 1)

    hour, minute = None, 0
    try:
        # Tách riêng ngày và giờ để xử lý chính xác hơn
        dt_from_parser = dateutil_parse(text, fuzzy=True, default=base_date)
        
        # Nếu dateutil không đổi ngày (vẫn là base_date)
        if dt_from_parser.date() == base_date.date():
             # Kiểm tra xem text có chứa thông tin ngày rõ ràng không (ví dụ: "25/10")
             if not any(c in text for c in '/-'): # không có ngày cụ thể
                # giữ base_date đã tính toán ở trên
                pass
             else:
                base_date = dt_from_parser
        else:
             base_date = dt_from_parser

        hour, minute = dt_from_parser.hour, dt_from_parser.minute

        # Nếu `dateutil` không tìm thấy giờ, nó có thể trả về 00:00
        if hour == 0 and minute == 0:
             # Thử tìm giờ bằng regex (ưu tiên hơn)
             time_match = re.search(r"(\d{1,2})[h:](\d{1,2})", text) # 10h30, 10:30
             if time_match:
                 hour = int(time_match.group(1))
                 minute = int(time_match.group(2))
             else:
                 time_match_simple = re.search(r"(\d{1,2})h", text) # 10h
                 if time_match_simple:
                     hour = int(time_match_simple.group(1))
                     minute = 0
                 else:
                     time_match_simple_gio = re.search(r"(\d{1,2}) giờ", text) # 10 giờ
                     if time_match_simple_gio:
                         hour = int(time_match_simple_gio.group(1))
                         minute = 0

    except ValueError:
         # dateutil thất bại hoàn toàn, dùng regex
        time_match = re.search(r"(\d{1,2})[h:](\d{1,2})", text) # 10h30, 10:30
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
        else:
            time_match_simple = re.search(r"(\d{1,2})h", text) # 10h
            if time_match_simple:
                hour = int(time_match_simple.group(1))
            else:
                 time_match_simple_gio = re.search(r"(\d{1,2}) giờ", text) # 10 giờ
                 if time_match_simple_gio:
                    hour = int(time_match_simple_gio.group(1))
    
    if hour is None:
        if "sáng" in text: hour = 9
        elif "trưa" in text: hour = 12
        elif "chiều" in text: hour = 14
        elif "tối" in text: hour = 20
        else:
            # Nếu không có giờ cụ thể, không thể tạo sự kiện
            return None
            
    if "chiều" in text and hour < 12: hour += 12
    if "tối" in text and hour < 12: hour += 12

    try:
        # Đảm bảo phút được gán đúng nếu regex tìm thấy giờ nhưng không có phút
        if minute == 0 and 'h' in text and ':' not in text:
            minute_match = re.search(r"\d{1,2}[h:](\d{1,2})", text)
            if minute_match:
                minute = int(minute_match.group(1))

        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        return None

def parse_sentence(sentence: str) -> dict:
    if not sentence:
        return {"error": "Câu rỗng."}

    # 1. Preprocessing
    text = preprocess(sentence)
    
    # 2. NER Extraction (Model-based)
    ner_entities, remaining_text = extract_ner_entities(text)
    
    # 3. Rule-based Extraction (Đã được nâng cấp)
    rule_entities = extract_rule_entities(text, remaining_text)

    # 4. Time Parsing
    time_text = ner_entities["TIME"][0] if ner_entities["TIME"] else None
    start_time_dt = parse_vietnamese_time(time_text)
    
    start_time_iso = None
    end_time_iso = None # <--- THAY ĐỔI (Khởi tạo là None)
    
    if start_time_dt:
        start_time_iso = start_time_dt.isoformat()
        
        # <--- MỚI (Xử lý end_time từ duration)
        duration_minutes = rule_entities.get("duration_minutes")
        if duration_minutes:
            end_time_dt = start_time_dt + timedelta(minutes=duration_minutes)
            end_time_iso = end_time_dt.isoformat()
            
    else:
        # Nếu NER không tìm thấy TIME, thử phân tích toàn bộ câu
        # Đây là một cải tiến nhỏ nếu NER thất bại
        start_time_dt = parse_vietnamese_time(text)
        if start_time_dt:
             start_time_iso = start_time_dt.isoformat()
             # Thử lại logic duration
             duration_minutes = rule_entities.get("duration_minutes")
             if duration_minutes:
                 end_time_dt = start_time_dt + timedelta(minutes=duration_minutes)
                 end_time_iso = end_time_dt.isoformat()
        else:
            return {"error": "Không thể xác định thời gian sự kiện."}


    # 5. Hợp nhất & Validation
    location = ner_entities["LOCATION"][0] if ner_entities["LOCATION"] else None

    event_name = rule_entities.get("event")
    if not event_name:
        return {"error": "Không thể xác định tên sự kiện."}

    return {
        "event": event_name,
        "start_time": start_time_iso,
        "end_time": end_time_iso, # <--- THAY ĐỔI
        "location": location,
        "reminder_minutes": rule_entities.get("reminder_minutes") # Sẽ là 0 nếu không có
    }

if __name__ == "__main__":
    test_sentence_1 = "Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302, nhắc trước 15 phút."
    test_sentence_2 = "Đi cafe với bạn thứ hai tới lúc 8h tối"
    
    # <--- TEST CASE MỚI
    test_sentence_3 = "Họp dự án trong 2 tiếng lúc 3h chiều nay, nhắc trước 1 giờ"
    test_sentence_4 = "di choi voi ban luc 8h toi thu 7" # Test không dấu
    test_sentence_5 = "Học tiếng Anh ở thư viện lúc 10h sáng chủ nhật tuần sau" # Test không nhắc nhở, không duration
    
    print(f"Câu: {test_sentence_1}")
    print(parse_sentence(test_sentence_1))
    
    print(f"\nCâu: {test_sentence_2}")
    print(parse_sentence(test_sentence_2))
    
    print(f"\nCâu: {test_sentence_3}") # Test duration và reminder "giờ"
    print(parse_sentence(test_sentence_3))

    print(f"\nCâu: {test_sentence_4}") # Test không dấu
    print(parse_sentence(test_sentence_4))
    
    print(f"\nCâu: {test_sentence_5}") # Test default reminder = 0
    print(parse_sentence(test_sentence_5))
