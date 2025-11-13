import re
from datetime import datetime, timedelta
from underthesea import word_tokenize, ner
import re
from datetime import datetime, timedelta
from underthesea import word_tokenize, ner
from dateutil.parser import parse as dateutil_parse

def preprocess(text: str) -> str:
    """Bước 1: Chuẩn hóa text"""
    original_text = text
    text = text.lower().strip()
    
    # BƯỚC 1: Xử lý các cụm từ cố định trước (có dấu)
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
    
    # BƯỚC 2: Xử lý từ không dấu thường gặp (dán liền nhau)
    # Chỉ thay thế nếu từ đứng RIÊNG (có space 2 bên hoặc đầu/cuối câu)
    no_tone_replacements = {
        r'\bdi choi\b': 'đi chơi',
        r'\bvoi ban\b': 'với bạn', 
        r'\bvoi\b': 'với',
        r'\bhop nhom\b': 'họp nhóm',
        r'\bhop\b': 'họp',
        r'\bnhom\b': 'nhóm',
        r'\bchieu\b': 'chiều',
        r'\btoi\b': 'tới',
        r'\bsang\b': 'sáng',
    }
    
    for pattern, replacement in no_tone_replacements.items():
        text = re.sub(pattern, replacement, text)
    
    # BƯỚC 3: Normalize space cuối cùng
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_time_info(text: str) -> tuple[str, str]:
    """Trích xuất cụm thời gian từ `text`.

    Thay vì dùng `replace` để loại bỏ chuỗi khớp (có thể dẫn tới xóa nhầm
    khi có nhiều phần giống nhau), hàm này dùng vị trí (span) của match để
    cắt chính xác phần thời gian khỏi chuỗi gốc. Tìm kiếm sẽ không phân biệt
    hoa thường (`re.IGNORECASE`).

    Trả về: (time_string, remaining_text) hoặc (None, text) nếu không tìm thấy.
    """

    # Pattern mở rộng để bắt toàn bộ cụm thời gian (ưu tiên các cụm đầy đủ trước)
    time_patterns = [
        # Giờ cụ thể + buổi + ngày + tuần: "10h sáng thứ_năm tuần_sau"
        r'(\d{1,2}\s*(?:h|giờ|gio|:)\s*\d{0,2}\s*(?:sáng|sang|trưa|trua|chiều|chieu|tối|toi)?\s*(?:ngày_mai|mai|hôm_nay|nay|ngày_kia|kia|thứ_\w+|chủ_nhật)?\s*(?:tuần_sau|tuần_tới|tới|toi|này|nay|sau)?)',
        # Buổi + ngày + tuần: "sáng thứ_năm tuần_sau"
        r'((?:sáng|sang|trưa|trua|chiều|chieu|tối|toi)\s+(?:ngày_mai|mai|hôm_nay|nay|ngày_kia|kia|thứ_\w+|chủ_nhật)?\s*(?:tuần_sau|tuần_tới|tới|toi|này|nay|sau)?)',
        # Ngày + tuần + giờ: "thứ_năm tuần_sau 8h", "thứ_năm tuần_tới 10h30"
        r'((?:thứ_\w+|chủ_nhật|cuối_tuần)\s*(?:tuần_sau|tuần_tới)?\s*(?:\d{1,2}\s*(?:h|giờ|gio|:)\s*\d{0,2})?)',
        # Chỉ ngày + tuần: "thứ_năm tuần_sau", "thứ_năm tuần_tới"
        r'((?:thứ_\w+|chủ_nhật|cuối_tuần)\s+(?:tuần_sau|tuần_tới))',
        # Tuần đơn lẻ: "tuần_sau", "tuần_tới"
        r'(tuần_sau|tuần_tới)',
        # Chỉ ngày: "thứ_hai tới", "cuối_tuần", "thứ_năm"
        r'((?:thứ_\w+|chủ_nhật|cuối_tuần)\s*(?:tới|toi|này|nay|sau)?)',
        # Chỉ giờ: "10h", "8h30"
        r'(\d{1,2}\s*(?:h|giờ|gio|:)\s*\d{0,2})',
    ]

    flags = re.IGNORECASE

    for pattern in time_patterns:
        m = re.search(pattern, text, flags)
        if not m:
            continue

        # Lấy chuỗi khớp ưu tiên (group 1 nếu tồn tại, ngược lại group 0)
        try:
            time_str = m.group(1) if m.groups() else m.group(0)
        except IndexError:
            time_str = m.group(0)

        # Lấy span tương ứng với nhóm đã lấy (nếu group(1) không tồn tại, dùng span(0))
        if m.groups():
            start, end = m.span(1)
        else:
            start, end = m.span(0)

        # Cắt chính xác phần thời gian khỏi chuỗi (dùng span để tránh xóa nhầm)
        remaining = text[:start] + text[end:]
        remaining = re.sub(r'\s+', ' ', remaining).strip()

        return time_str.strip(), remaining

    return None, text

    

def extract_location(text: str) -> tuple[str, str]:
    """Trích xuất địa điểm, trả về (location, remaining_text)"""
    # Pattern: "ở/tại + địa điểm"
    location_patterns = [
        r'(?:ở|o|tại|tai)\s+([^\s,]+(?:\s+[^\s,]+){0,4})',  # "ở phòng 302", "tại văn phòng"
        r'([^\s]+\s*(?:phòng|nhà hàng|quán|công ty|trường)\s+[^\s,]+)',  # "phòng 302", "nhà hàng ABC"
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
    """Trích xuất reminder minutes, trả về (minutes, remaining_text)"""
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

def parse_vietnamese_time(time_text: str, base_now: datetime = None) -> datetime:
    """Chuyển đổi cụm thời gian tiếng Việt sang datetime"""
    if not time_text:
        return None
    
    now = base_now if base_now else datetime.now()
    text = time_text.lower()
    
    base_date = now
    week_offset = 0
    
    # Xử lý "tuần sau/tới" - lưu offset
    if "tuần_sau" in text or "tuần_tới" in text:
        week_offset = 1
    
    # Xử lý ngày tương đối
    if "ngày_mai" in text or "mai" in text:
        base_date = now + timedelta(days=1)
    elif "ngày_kia" in text or "kia" in text:
        base_date = now + timedelta(days=2)
    elif "hôm_nay" in text or "hôm nay" in text or "nay" in text:
        base_date = now
    
    # Xử lý thứ trong tuần
    weekday_map = {
        "thứ_hai": 0, "thứ_ba": 1, "thứ_tư": 2, "thứ_năm": 3,
        "thứ_sáu": 4, "thứ_bảy": 5, "chủ_nhật": 6,
    }
    
    found_weekday = False
    for day_name, day_num in weekday_map.items():
        if day_name in text:
            found_weekday = True
            current_weekday = now.weekday()  # Luôn tính từ hôm nay
            
            if "tới" in text or "sau" in text or week_offset > 0:
                # Thứ X tuần sau: tính từ tuần sau
                days_ahead = day_num - current_weekday
                if days_ahead < 0:  # Chưa tới ngày đó trong tuần này
                    days_ahead += 7
                elif days_ahead == 0:  # Hôm nay chính là ngày đó
                    days_ahead = 7  # Muốn ngày đó tuần sau, cộng 7 ngày
                # Nếu có "tuần_sau/tuần_tới", cộng 7 thêm (không dùng weeks=week_offset vì đã tính trong days_ahead)
                if week_offset > 0:
                    # "tuần_sau" có nghĩa là tuần tới, bằng +7 ngày từ hôm nay
                    # nếu days_ahead đã >= 7, không cộng thêm
                    # nếu days_ahead < 7, cộng thêm 7 để chắc là tuần sau
                    if days_ahead < 7:
                        days_ahead += 7
                base_date = now + timedelta(days=days_ahead)
            elif "này" in text or "nay" in text:
                # Thứ X tuần này
                days_ahead = day_num - current_weekday
                if days_ahead < 0:
                    days_ahead += 7
                base_date = now + timedelta(days=days_ahead)
            else:
                # Mặc định: thứ X gần nhất
                days_ahead = day_num - current_weekday
                if days_ahead < 0:
                    days_ahead += 7
                base_date = now + timedelta(days=days_ahead)
            break
    
    # Nếu có "tuần sau" nhưng không có thứ cụ thể
    if week_offset > 0 and not found_weekday:
        base_date = base_date + timedelta(weeks=week_offset)
    
    # Xử lý "cuối tuần"
    if "cuối_tuần" in text or "cuoi_tuan" in text:
        current_weekday = base_date.weekday()
        days_ahead = 5 - current_weekday  # Thứ 7
        if days_ahead <= 0:
            days_ahead += 7
        base_date = base_date + timedelta(days=days_ahead)
    
    # Trích xuất giờ phút
    hour, minute = None, 0
    
    # Pattern: 10h30, 10:30
    time_match = re.search(r'(\d{1,2})\s*[h:](\d{1,2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    else:
        # Pattern: 10h, 10 giờ
        time_match_simple = re.search(r'(\d{1,2})\s*(?:h|giờ|gio)', text)
        if time_match_simple:
            hour = int(time_match_simple.group(1))
            minute = 0
    
    # Xác định buổi trong ngày
    period = None
    if "sáng" in text or "sang" in text:
        period = "morning"
    elif "trưa" in text or "trua" in text:
        period = "noon"
    elif "chiều" in text or "chieu" in text:
        period = "afternoon"
    elif "tối" in text:
        period = "evening"
    
    # Nếu không có giờ cụ thể, dùng giờ mặc định theo buổi
    if hour is None:
        if period == "morning":
            hour = 9
        elif period == "noon":
            hour = 12
        elif period == "afternoon":
            hour = 14
        elif period == "evening":
            hour = 20
        else:
            # Nếu không có giờ và không có buổi, trả về giờ mặc định
            hour = 9  # Mặc định 9h sáng
    else:
        # Điều chỉnh AM/PM nếu có giờ cụ thể
        if period == "afternoon" and hour < 12:
            hour += 12
        elif period == "evening" and hour < 12:
            hour += 12
    
    # Tạo datetime kết quả
    try:
        result = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return result
    except ValueError:
        return None

def parse_sentence(sentence: str) -> dict:
    """
    Hàm chính: Phân tích câu tiếng Việt và trích xuất thông tin sự kiện
    """
    if not sentence or not sentence.strip():
        return {"error": "Câu rỗng hoặc không hợp lệ."}
    
    try:
        # Bước 1: Preprocessing
        text = preprocess(sentence)
        original_text = text
        
        # Bước 2: Trích xuất reminder TRƯỚC (để tránh nhầm với location)
        reminder_minutes, text = extract_reminder(text)
        
        # Bước 3: Trích xuất thời gian
        time_str, remaining = extract_time_info(text)
        
        # Bước 4: Trích xuất địa điểm
        location, remaining = extract_location(remaining)
        
        # Bước 5: Parse thời gian
        if not time_str:
            return {"error": "Không thể xác định thời gian sự kiện."}
        
        start_time_dt = parse_vietnamese_time(time_str)
        if not start_time_dt:
            return {"error": "Không thể xác định thời gian sự kiện."}
        
        start_time_iso = start_time_dt.isoformat()
        
        # Bước 6: Trích xuất tên sự kiện
        # Loại bỏ các từ phụ trợ
        event_name = remaining
        stop_words = ['nhắc tôi', 'nhac toi', 'cho tôi', 'cho toi',
                      'ở', 'o', 'tại', 'tai', 
                      'lúc', 'luc', 'vào', 'vao', 'cho', 'để', 'de',
                      'và', 'va']
        
        for word in stop_words:
            event_name = event_name.replace(word, ' ')
        
        # Loại bỏ các ký tự đặc biệt và khoảng trắng thừa
        event_name = re.sub(r'[,.]', '', event_name)
        event_name = re.sub(r'\s+', ' ', event_name).strip()
        
        if not event_name or len(event_name.strip()) == 0:
            return {"error": "Không thể xác định tên sự kiện."}
        
        # Bước 7: Trả về kết quả
        return {
            "event": event_name,
            "start_time": start_time_iso,
            "end_time": None,
            "location": location,
            "reminder_minutes": reminder_minutes
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
        "Họp với sếp 9h sáng thứ 5 tuần sau",
        "Đi du lịch cuối tuần này",
        "Ăn trưa với đồng nghiệp 12h mai tại quán A",
    ]
    
    print("=" * 80)
    print("TEST CASES - NLP MODULE (IMPROVED)")
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