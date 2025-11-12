import re
from datetime import datetime, timedelta
from underthesea import word_tokenize, ner
from dateutil.parser import parse as dateutil_parse

def preprocess(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+',' ', text)
    replacements = {
        'thứ 2': 'thứ_2',
        'thứ 3': 'thứ_3',
        'thứ 4': 'thứ_4',
        'thứ 5': 'thứ_5',
        'thứ 6': 'thứ_6',
        'thứ 7': 'thứ_7',
        'chủ nhật': 'chủ_nhật',
        'ngày mai': 'ngày_mai'
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
    rules ={}

    reminder_match = re.search(r"nhắc trước (\d+) phút", remaining_text)
    if reminder_match:
        rules["reminder_minutes"] = int (reminder_match.group(1))
        remaining_text = remaining_text.replace(reminder_match.group(0), "")
    else:
        rules["reminder_minutes"] = None
    
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

    if "mai" in text or "ngày mai" in text:
        base_date = now + timedelta(days = 1)
    elif "kia" in text or "ngày kia" in text:
        base_date = now + timedelta(days = 2)
    elif "hôm nay" in text or "nay" in text:
        base_date = now
        
    weekday_map = {
        "thứ hai": 0,
        "thứ 2": 0,
        "thứ ba": 1,
        "thứ 3": 1,
        "thứ tư": 2,
        "thứ 4": 2,
        "thứ năm": 3,
        "thứ 5": 3,
        "thứ sáu": 4,
        "thứ 6": 4,
        "thứ bảy": 5,
        "thứ 7": 5,
        "chủ nhật": 6,
        "cn": 6
    }
    for day, day_num in weekday_map.items():
        if day in text and ("tới" in text or "sau" in text or "tuần sau" in text):
            days_ahead = day_num - base_date.weekday()
            if days_ahead <=0:
                days_ahead +=7
            base_date = base_date + timedelta(days = days_ahead)
            break
    
    if "cuối tuần" in text:
        days_ahead = 5 - base_date.weekday()
        if days_ahead <=0:
            days_ahead +=7
        base_date = base_date + timedelta(days = days_ahead)
        
    if "tuần sau" in text or "tuần tới" in text and not any(day in text for day in weekday_map.keys()):
        base_date = base_date + timedelta(weeks = 1)

    hour, minute = None, 0
    try:
        dt = dateutil_parse(text, fuzzy=True)
        if dt.year != now.year or dt.month != now.month or dt.day != now.day:
            base_date = dt.replace(hour = 0, minute = 0)
            
        hour, minute = dt.hour, dt.minute
    except ValueError:
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
            return None
            
    if "chiều" in text and hour < 12: hour += 12
    if "tối" in text and hour < 12: hour += 12

    try:
        return base_date.replace(hour=hour, minute=minute)
    except ValueError:
        return None
def parse_sentence(sentence: str) -> dict:
    if not sentence:
        return {"error": "Câu rỗng."}

    # 1. Preprocessing
    text = preprocess(sentence)
    
    # 2. NER Extraction (Model-based)
    ner_entities, remaining_text = extract_ner_entities(text)
    
    # 3. Rule-based Extraction
    rule_entities = extract_rule_entities(text, remaining_text)

    # 4. Time Parsing
    time_text = ner_entities["TIME"][0] if ner_entities["TIME"] else None
    start_time_dt = parse_vietnamese_time(time_text)
    
    start_time_iso = None
    if start_time_dt:
        start_time_iso = start_time_dt.isoformat()
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
        "end_time": None,
        "location": location,
        "reminder_minutes": rule_entities.get("reminder_minutes")
    }

if __name__ == "__main__":
    test_sentence_1 = "Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302, nhắc trước 15 phút."
    test_sentence_2 = "Đi cafe với bạn thứ hai tới lúc 8h tối"
    
    print(f"Câu: {test_sentence_1}")
    print(parse_sentence(test_sentence_1))
    
    print(f"\nCâu: {test_sentence_2}")
    print(parse_sentence(test_sentence_2))