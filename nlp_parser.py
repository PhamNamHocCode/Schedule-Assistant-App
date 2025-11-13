import re
from datetime import datetime, timedelta
from underthesea import word_tokenize, ner
from dateutil.parser import parse as dateutil_parse

# ======================================================================
# BƯỚC 1: PREPROCESSING (RULE) - Giữ nguyên phiên bản tốt nhất của bạn
# ======================================================================
def preprocess(text: str) -> str:
    """Bước 1: Chuẩn hóa text"""
    text = text.lower().strip()
    
    replacements_with_space = {
        'thứ 2': 'thứ_hai', 'thu 2': 'thứ_hai', 'thứ hai': 'thứ_hai', 'thu hai': 'thứ_hai',
        'thứ 3': 'thứ_ba', 'thu 3': 'thứ_ba', 'thứ ba': 'thứ_ba', 'thu ba': 'thứ_ba',
        'thứ 4': 'thứ_tư', 'thứ tư': 'thứ_tư', 'thu 4': 'thứ_tư', 'thu tu': 'thứ_tư',
        'thứ 5': 'thứ_năm', 'thứ năm': 'thứ_năm', 'thu 5': 'thứ_năm', 'thu nam': 'thứ_năm',
        'thứ 6': 'thứ_sáu', 'thứ sáu': 'thứ_sáu', 'thu 6': 'thứ_sáu', 'thu sau': 'thứ_sáu',
        'thứ 7': 'thứ_bảy', 'thứ bảy': 'thứ_bảy', 'thu 7': 'thứ_bảy', 'thu bay': 'thứ_bảy',
        'chủ nhật': 'chủ_nhật', 'chu nhat': 'chủ_nhật', 'cn': 'chủ_nhật',
        'ngày mai': 'ngày_mai', 'ngay mai': 'ngày_mai',
        'hôm nay': 'hôm_nay', 'hom nay': 'hôm_nay',
        'ngày kia': 'ngày_kia', 'ngay kia': 'ngày_kia',
        'tuần sau': 'tuần_sau', 'tuan sau': 'tuần_sau',
        'tuần tới': 'tuần_tới', 'tuan toi': 'tuần_tới',
        'cuối tuần': 'cuối_tuần', 'cuoi tuan': 'cuối_tuần',
    }
    
    for old, new in replacements_with_space.items():
        text = text.replace(old, new)
    
    no_tone_replacements = {
        r'\bdi choi\b': 'đi chơi', r'\bvoi ban\b': 'với bạn', r'\bvoi\b': 'với',
        r'\bhop nhom\b': 'họp nhóm', r'\bhop\b': 'họp', r'\bnhom\b': 'nhóm',
        r'\bchieu\b': 'chiều', r'\btoi\b': 'tối', r'\bsang\b': 'sáng',
    }
    
    for pattern, replacement in no_tone_replacements.items():
        text = re.sub(pattern, replacement, text)
    
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ======================================================================
# COMPONENT 2: MODEL-BASED (NER) - Thêm lại hàm này
# ======================================================================
def extract_ner_entities(text: str) -> tuple[dict, str]:
    """
    Component 2: Model-based (NER) để nhận diện thực thể.
    Dùng underthesea.ner để tìm TIME và LOCATION.
    """
    try:
        ner_tags = ner(text)
    except Exception as e:
        print(f"[Lỗi NER] {e}")
        return {"TIME": [], "LOCATION": []}, text
    
    entities = {"TIME": [], "LOCATION": []}
    current_entity_text = ""
    current_entity_type = ""
    
    # Tái cấu trúc text từ các token
    reconstructed_text = text
    offset = 0

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
    
    if current_entity_text and current_entity_type in entities:
        entities[current_entity_type].append(current_entity_text.strip())
    
    # Xóa entities đã trích xuất khỏi text
    remaining_text = text
    for time_str in entities["TIME"]:
        remaining_text = remaining_text.replace(time_str, '', 1) # Chỉ thay thế 1 lần
    for loc_str in entities["LOCATION"]:
        remaining_text = remaining_text.replace(loc_str, '', 1) # Chỉ thay thế 1 lần
    
    remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()
    return entities, remaining_text

# ======================================================================
# COMPONENT 3: RULE-BASED EXTRACTORS - Giữ nguyên
# ======================================================================

def extract_time_info(text: str) -> tuple[str, str]:
    """(Rule-based) Trích xuất cụm thời gian (Phiên bản nâng cấp V2).

    Sử dụng "glue" pattern để xử lý các từ nối như 'lúc', 'vào'.
    Ưu tiên các pattern dài nhất, đầy đủ nhất (greedy) trước.
    """

    # Định nghĩa các phần cơ bản của một cụm thời gian
    # (re.IGNORECASE sẽ được dùng)
    p_time = r'\d{1,2}\s*(?:h|giờ|gio|:)\s*\d{0,2}'  # 10h, 10:30, 8 gio
    p_period = r'sáng|sang|trưa|trua|chiều|chieu|tối|toi' # sáng, tối...
    p_day = r'ngày_mai|mai|hôm_nay|nay|ngày_kia|kia|thứ_\w+|chủ_nhật|cuối_tuần' # ngày mai, thứ_bảy, cuối_tuần
    p_modifier = r'tuần_sau|tuần_tới|tới|toi|này|nay|sau' # tuần sau, tới, này
    
    # === SỬA LỖI: Thêm "Glue" Pattern ===
    # Đây là "chất kết dính" giữa các phần, cho phép từ "lúc", "vào"
    p_glue = r'\s*(?:lúc|luc|vào|vao)?\s*'

    # Sắp xếp các pattern từ DÀI NHẤT/PHỨC TẠP NHẤT đến NGẮN NHẤT
    # (?i) = Bật cờ IGNORECASE
    time_patterns = [
        # 1. Full combo (Time + Period + Day + Mod): "10h sáng thứ_năm tuần_sau"
        # 2. Full combo (Day + Mod + Time + Period): "thứ_bảy tới lúc 8h tối" (Sửa: thêm p_glue)
        # 3. Full combo (Period + Day + Mod): "sáng thứ_năm tuần_sau"
        fr'(?i)((?:{p_time})\s*(?:{p_period})?{p_glue}(?:{p_day})\s*(?:{p_modifier})?)',
        fr'(?i)((?:{p_day})\s*(?:{p_modifier})?{p_glue}(?:{p_time})\s*(?:{p_period})?)',
        fr'(?i)((?:{p_period})\s+(?:{p_day})\s*(?:{p_modifier})?)',

        # 4. Day + Time (no period): "thứ_năm tuần_sau 8h", "cuối_tuần 7h" (Sửa: thêm p_glue)
        fr'(?i)((?:{p_day})\s*(?:{p_modifier})?{p_glue}(?:{p_time}))',

        # 5. Day + Mod (no time): "thứ_năm tuần_sau", "thứ 6 này"
        fr'(?i)((?:{p_day})\s+(?:{p_modifier}))',

        # 6. Time + Period (no day): "10h sáng", "8h tối"
        fr'(?i)((?:{p_time})\s*(?:{p_period}))',
        
        # 7. Day standalone: "thứ_năm", "cuối_tuần", "ngày_mai"
        fr'(?i)({p_day})',

        # 8. Time standalone: "10h", "8h30"
        fr'(?i)({p_time})',
        
        # 9. Period standalone: "sáng", "tối" (ít ưu tiên nhất)
        fr'(?i)({p_period})'
    ]

    for pattern in time_patterns:
        m = re.search(pattern, text)
        if not m:
            continue

        # Đã tìm thấy match dài nhất phù hợp
        try:
            # Luôn lấy group(1) vì chúng ta đã bọc toàn bộ pattern trong ( )
            time_str = m.group(1) 
            start, end = m.span(1)
        except IndexError:
            continue # Lỗi không mong muốn, thử pattern tiếp theo

        # Cắt chính xác phần thời gian khỏi chuỗi (dùng span)
        remaining = text[:start] + text[end:]
        remaining = re.sub(r'\s+', ' ', remaining).strip()
        
        print(f"[Debug Rule Time] Pattern: {pattern}")
        print(f"[Debug Rule Time] Matched: '{time_str.strip()}'")

        return time_str.strip(), remaining

    return None, text

def extract_location(text: str) -> tuple[str, str]:
    """(Rule-based) Trích xuất địa điểm"""
    location_patterns = [
        r'(?:ở|o|tại|tai)\s+([^\s,]+(?:\s+[^\s,]+){0,4})', 
        r'([^\s]+\s*(?:phòng|nhà hàng|quán|công ty|trường)\s+[^\s,]+)', 
    ]
    for pattern in location_patterns:
        loc_match = re.search(pattern, text)
        if loc_match:
            location = loc_match.group(1).strip()
            remaining = text.replace(loc_match.group(0), '', 1)
            remaining = re.sub(r'\s+', ' ', remaining).strip()
            return location, remaining
    return None, text

def extract_reminder(text: str) -> tuple[int, str]:
    """(Rule-based) Trích xuất reminder minutes"""
    reminder_patterns = [
        r'nhắc trước\s*(\d+)\s*(?:phút|phut|p)',
        r'nhac trước\s*(\d+)\s*(?:phút|phut|p)',
        r'nhac trc\s*(\d+)\s*(?:phút|phut|p)',
        r'nhắc\s+(\d+)\s*(?:phút|phut|p)',
        r'nhac\s+(\d+)\s*(?:phút|phut|p)',
    ]
    for pattern in reminder_patterns:
        reminder_match = re.search(pattern, text)
        if reminder_match:
            minutes = int(reminder_match.group(1))
            remaining = text.replace(reminder_match.group(0), '', 1)
            remaining = re.sub(r'\s+', ' ', remaining).strip()
            return minutes, remaining
    return None, text

# ======================================================================
# COMPONENT 4: TIME PARSING (RULE) - Giữ nguyên
# ======================================================================
def parse_vietnamese_time(time_text: str, base_now: datetime = None) -> datetime:
    """(Rule-based) Chuyển đổi cụm thời gian tiếng Việt sang datetime"""
    if not time_text:
        return None
    now = base_now if base_now else datetime.now()
    text = time_text.lower()
    base_date = now
    week_offset = 0
    if "tuần_sau" in text or "tuần_tới" in text:
        week_offset = 1
    if "ngày_mai" in text or "mai" in text:
        base_date = now + timedelta(days=1)
    elif "ngày_kia" in text or "kia" in text:
        base_date = now + timedelta(days=2)
    elif "hôm_nay" in text or "hôm nay" in text or "nay" in text:
        base_date = now
    
    weekday_map = {
        "thứ_hai": 0, "thứ_ba": 1, "thứ_tư": 2, "thứ_năm": 3,
        "thứ_sáu": 4, "thứ_bảy": 5, "chủ_nhật": 6,
    }
    found_weekday = False
    for day_name, day_num in weekday_map.items():
        if day_name in text:
            found_weekday = True
            current_weekday = now.weekday()
            days_ahead = day_num - current_weekday
            
            if "tới" in text or "sau" in text or week_offset > 0:
                if days_ahead <= 0: # Bao gồm cả hôm nay
                    days_ahead += 7
            elif days_ahead < 0:
                 days_ahead += 7
            base_date = now + timedelta(days=days_ahead)
            break
            
    if week_offset > 0 and not found_weekday:
        base_date = base_date + timedelta(weeks=week_offset)
    if "cuối_tuần" in text or "cuoi_tuan" in text:
        current_weekday = base_date.weekday()
        days_ahead = 5 - current_weekday
        if days_ahead <= 0:
            days_ahead += 7
        base_date = base_date + timedelta(days=days_ahead)
    
    hour, minute = None, 0
    time_match = re.search(r'(\d{1,2})\s*[h:](\d{1,2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    else:
        time_match_simple = re.search(r'(\d{1,2})\s*(?:h|giờ|gio)', text)
        if time_match_simple:
            hour = int(time_match_simple.group(1))
            minute = 0
            
    period = None
    if "sáng" in text or "sang" in text: period = "morning"
    elif "trưa" in text or "trua" in text: period = "noon"
    elif "chiều" in text or "chieu" in text: period = "afternoon"
    elif "tối" in text: period = "evening"
    
    if hour is None:
        if period == "morning": hour = 9
        elif period == "noon": hour = 12
        elif period == "afternoon": hour = 14
        elif period == "evening": hour = 20
        else: hour = 9 # Mặc định
    else:
        if period == "afternoon" and hour < 12: hour += 12
        elif period == "evening" and hour < 12: hour += 12
    
    try:
        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        return None

# ======================================================================
# COMPONENT 5: "NHẠC TRƯỞNG" HYBRID - VIẾT LẠI HOÀN TOÀN
# ======================================================================
def parse_sentence(sentence: str) -> dict:
    """
    Hàm chính (Hybrid): Phân tích câu theo kiến trúc 5 bước
    """
    if not sentence or not sentence.strip():
        return {"error": "Câu rỗng."}
    
    try:
        # === BƯỚC 1: PREPROCESSING (RULE) ===
        text = preprocess(sentence)
        
        # === BƯỚC 2: TRÍCH XUẤT REMINDER (RULE) ===
        # Ưu tiên Rule cho Reminder vì nó rõ ràng và đáng tin cậy.
        reminder_minutes, text_after_reminder = extract_reminder(text)
        
        # === BƯỚC 3: TRÍCH XUẤT TIME & LOCATION (HYBRID) ===
        
        # -- PLAN A: DÙNG MODEL (underthesea.ner) --
        # (Component 2: Model-based (NER) để nhận diện thực thể)
        print(f"[Debug] Chạy Model NER trên: '{text_after_reminder}'")
        ner_entities, text_after_ner = extract_ner_entities(text_after_reminder)
        
        time_str = ner_entities["TIME"][0] if ner_entities["TIME"] else None
        location_str = ner_entities["LOCATION"][0] if ner_entities["LOCATION"] else None
        
        # -- PLAN B: DÙNG RULE (Fallback) --
        # (Component 3: Rule-based extraction)
        
        # Nếu Model KHÔNG tìm thấy TIME, hãy dùng Rule-based Fallback
        if not time_str:
            print("[Debug] Model NER không tìm thấy TIME. Chuyển sang Rule-based Fallback...")
            # Lấy text_after_ner (là text model ko tìm thấy gì)
            time_str, text_after_rule_time = extract_time_info(text_after_ner)
            remaining_text = text_after_rule_time # Cập nhật remaining text
        else:
            print(f"[Debug] Model NER tìm thấy TIME: {time_str}")
            remaining_text = text_after_ner # Model đã dọn dẹp, tin tưởng nó
        
        # Nếu Model KHÔNG tìm thấy LOCATION, hãy dùng Rule-based Fallback
        if not location_str:
            print("[Debug] Model NER không tìm thấy LOCATION. Chuyển sang Rule-based Fallback...")
            # Lấy remaining_text (đã có thể bị dọn dẹp bởi time rule)
            location_str, final_remaining_text = extract_location(remaining_text)
        else:
            print(f"[Debug] Model NER tìm thấy LOCATION: {location_str}")
            # Do text_after_ner đã xóa cả TIME và LOCATION,
            # final_remaining_text chính là text_after_ner
            final_remaining_text = remaining_text 

        # === BƯỚC 4: PARSE THỜI GIAN (RULE) ===
        # (Component 4: Phân tích thời gian)
        if not time_str:
            return {"error": "Không thể xác định thời gian sự kiện."}
        
        start_time_dt = parse_vietnamese_time(time_str)
        if not start_time_dt:
            return {"error": f"Không thể phân tích chuỗi thời gian: '{time_str}'"}
        
        start_time_iso = start_time_dt.isoformat()
        
        # === BƯỚC 5: HỢP NHẤT & LẤY TÊN SỰ KIỆN ===
        # (Component 5: Hợp nhất & xử lý lỗi)
        
        # Tên sự kiện = phần text cuối cùng còn sót lại
        event_name = final_remaining_text
        
        # Dọn dẹp tên sự kiện lần cuối
        stop_words = ['nhắc tôi', 'nhac toi', 'cho tôi', 'cho toi',
                      'ở', 'o', 'tại', 'tai', 
                      'lúc', 'luc', 'vào', 'vao', 'cho', 'để', 'de', 'và', 'va']
        
        for word in stop_words:
            # Dùng regex để đảm bảo xóa chính xác (tránh xóa 1 phần của từ)
            event_name = re.sub(r'\b' + re.escape(word) + r'\b', ' ', event_name)
        
        event_name = re.sub(r'[,.]', '', event_name)
        event_name = re.sub(r'\s+', ' ', event_name).strip()
        
        if not event_name or len(event_name.strip()) == 0:
            return {"error": "Không thể xác định tên sự kiện."}
        
        # === BƯỚC 6: TRẢ VỀ KẾT QUẢ ===
        return {
            "event": event_name,
            "start_time": start_time_iso,
            "end_time": None,
            "location": location_str,
            "reminder_minutes": reminder_minutes
        }
        
    except Exception as e:
        print(f"[LỖI NGHIÊM TRỌNG] {e}")
        return {"error": f"Lỗi xử lý: {str(e)}"}

# ======================================================================
# TEST CASES
# ======================================================================
if __name__ == "__main__":
    test_cases = [
        # Case 1: Model NER hoạt động TỐT (NER nên tìm thấy "10 giờ sáng mai" và "phòng 302")
        "Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302, nhắc trước 15 phút",
        # Case 2: Model NER hoạt động TỐT (NER nên tìm thấy "thứ hai tới" và "8h tối")
        "Đi cafe với bạn thứ hai tới lúc 8h tối",
        # Case 3: Case lỗi cũ (Model NER KHÔNG TÌM THẤY TIME/LOC, Rule Fallback sẽ chạy)
        "Họp nhóm 10 sáng mai, ở phòng 302, nhắc trước 15p",
        # Case 4: Không dấu (Rule Preprocess + Rule Fallback)
        "Di choi voi ban 10h sang mai",
        # Case 5: Không dấu (Rule Preprocess + Rule Fallback)
        "hop nhom 2h chieu thu 3 toi",
        # Case 6: Model NER TỐT (NER nên tìm thấy "9h30 sáng mai" và "văn phòng")
        "Họp team 9h30 sáng mai tại văn phòng",
        # Case 7: Rule Fallback cho Time (Model có thể chỉ thấy "thứ 6 này")
        "Gặp khách hàng thứ 6 này 2h chiều nhắc 30 phút",
        # Case 8: Rule Fallback cho Time (Model có thể không thấy "cuối tuần 7h sáng")
        "Đi gym cuối tuần 7h sáng",
        # Case 9: Model TỐT (NER nên thấy "thứ 7 tới 6h tối" và "nhà hàng ABC")
        "Sinh nhật bạn thứ 7 tới 6h tối ở nhà hàng ABC nhắc trước 60 phút",
        # Case 10: Model NER TỐT (NER nên thấy "9h sáng thứ 5 tuần sau")
        "Họp với sếp 9h sáng thứ 5 tuần sau",
    ]
    
    print("=" * 80)
    print("TEST CASES - NLP MODULE (HYBRID ARCHITECTURE)")
    print(f"Thời gian chạy test (Giả định): {datetime.now().isoformat()}")
    print("=" * 80)
    
    success_count = 0
    for i, sentence in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Câu: {sentence}")
        result = parse_sentence(sentence)
        print(f"Kết quả:")
        
        if "error" not in result:
            success_count += 1
            print(f"  ✓ Event: {result['event']}")
            print(f"  ✓ Time: {result['start_time']}")
            print(f"  ✓ Location: {result['location']}")
            print(f"  ✓ Reminder: {result['reminder_minutes']} phút")
        else:
            print(f"  ✗ {result['error']}")
        print("-" * 80)
    
    print(f"\nTỷ lệ thành công: {success_count}/{len(test_cases)} = {success_count/len(test_cases)*100:.1f}%")