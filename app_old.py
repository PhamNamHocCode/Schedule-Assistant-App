import streamlit as st
import threading
import time
import queue
from datetime import datetime

# Import các module cốt lõi của bạn
import nlp_parser  #
from Database import database as db  #

# Import component lịch bạn đã cung cấp
try:
    from streamlit_calendar import calendar  #
except ImportError:
    st.error("Không tìm thấy thư viện 'streamlit_calendar'. Hãy đảm bảo bạn đã cài đặt nó.")
    st.stop()

# --- 1. HỆ THỐNG NHẮC NHỞ (BACKGROUND THREAD) ---

def reminder_checker(notification_queue):
    """
    Hàm này chạy trong một luồng (thread) riêng biệt.
    Nó kiểm tra database mỗi 60 giây cho các sự kiện cần nhắc.
    """
    print("Luồng nhắc nhở đã bắt đầu...")
    while True:
        try:
            now_iso = datetime.now().isoformat()
            # Lấy các sự kiện cần thông báo
            events_to_notify = db.get_events_to_notify(now_iso)
            
            for event in events_to_notify:
                # Gửi tên sự kiện vào queue để UI hiển thị
                notification_queue.put(event['event'])
                # Đánh dấu là đã thông báo
                db.set_event_notified(event['id'])
                print(f"Đã gửi nhắc nhở cho: {event['event']}")
                
        except Exception as e:
            print(f"Lỗi trong luồng nhắc nhở: {e}")
        
        # Ngủ 60 giây (theo yêu cầu đồ án)
        time.sleep(60)

# Khởi tạo queue và luồng chỉ một lần
if 'notification_queue' not in st.session_state:
    st.session_state.notification_queue = queue.Queue()

if 'reminder_thread_started' not in st.session_state:
    # Khởi tạo DB khi ứng dụng chạy lần đầu
    db.init_db()
    
    # Bắt đầu luồng kiểm tra nhắc nhở
    print("Bắt đầu luồng nhắc nhở...")
    thread = threading.Thread(target=reminder_checker, args=(st.session_state.notification_queue,), daemon=True)
    thread.start()
    st.session_state.reminder_thread_started = True

# --- 2. GIAO DIỆN NGƯỜI DÙNG (STREAMLIT UI) ---

st.set_page_config(page_title="Trợ lý Lịch trình", layout="wide")
st.title("🗓️ Trợ lý Quản lý Lịch trình Cá nhân")
st.caption("Xử lý lịch trình bằng ngôn ngữ tự nhiên tiếng Việt")

# Hiển thị pop-up (toast) nếu có thông báo mới từ luồng
while not st.session_state.notification_queue.empty():
    event_name = st.session_state.notification_queue.get()
    st.toast(f"🔔 Nhắc nhở: {event_name} sắp diễn ra!")

# --- 3. KHUNG NHẬP LIỆU NLP ---

st.header("Thêm sự kiện nhanh")
nlp_input = st.text_input("Nhập câu yêu cầu lịch trình:", placeholder="VD: Họp nhóm 10h sáng mai ở phòng 302, nhắc trước 15 phút")

if st.button("Thêm sự kiện"):
    if nlp_input:
        # Gọi module NLP để xử lý câu
        parsed_data = nlp_parser.parse_sentence(nlp_input)
        
        if "error" in parsed_data:
            st.error(f"Lỗi phân tích: {parsed_data['error']}")
        else:
            try:
                # Thêm sự kiện vào DB
                event_id = db.add_event(parsed_data)
                st.success(f"Đã thêm sự kiện: '{parsed_data['event']}' (ID: {event_id})")
                st.rerun() # Tải lại trang để cập nhật lịch
            except Exception as e:
                st.error(f"Lỗi khi thêm vào database: {e}")
    else:
        st.warning("Vui lòng nhập câu yêu cầu.")

st.divider()

# --- 4. LỊCH (CALENDAR GRID) ---

st.header("Lịch của bạn")

# Lấy tất cả sự kiện từ DB
all_events_db = db.get_all_events()

# Chuyển đổi định dạng sự kiện của DB sang định dạng mà streamlit_calendar yêu cầu
calendar_events = []
for event in all_events_db:
    calendar_events.append({
        "title": event['event'],
        "start": event['start_time'],
        "end": event['end_time'] if event['end_time'] else event['start_time'], # Xử lý end_time null
        "extendedProps": {
            "id": event['id'], # Lưu ID để quản lý
            "location": event['location'],
            "reminder": f"{event['reminder_minutes']} phút trước"
        }
    })

# Cấu hình cho calendar
calendar_options = {
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay",
    },
    "initialView": "dayGridMonth",
    "selectable": True,
    "editable": True, # Cho phép kéo thả (cần xử lý callback nếu muốn lưu)
}

# Hiển thị lịch
st_calendar = calendar(
    events=calendar_events,
    options=calendar_options,
    custom_css="""
        .fc-event-main-frame { font-size: 13px; }
        .fc-event-time { font-weight: bold; }
    """,
)

st.write(st_calendar) # Bỏ comment để debug (xem sự kiện khi click)

st.divider()

# --- 5. QUẢN LÝ SỰ KIỆN (DANH SÁCH, SỬA, XÓA) ---

st.header("Danh sách & Quản lý Sự kiện")

# Dùng session_state để theo dõi sự kiện đang được sửa
if 'editing_event_id' not in st.session_state:
    st.session_state.editing_event_id = None

if not all_events_db:
    st.info("Bạn chưa có sự kiện nào trong lịch.")
else:
    # Hiển thị tiêu đề
    col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
    col1.subheader("Sự kiện")
    col2.subheader("Thời gian")
    col3.subheader("Địa điểm")
    
    st.markdown("---")

    # Lặp qua các sự kiện để hiển thị
    for event in reversed(all_events_db): # Hiển thị cái mới nhất lên trước
        event_id = event['id']
        
        # Nếu sự kiện này đang được sửa, hiển thị form
        if st.session_state.editing_event_id == event_id:
            with st.form(key=f"form_edit_{event_id}"):
                st.subheader(f"Chỉnh sửa sự kiện: {event['event']}")
                updated_data = {}
                updated_data['event'] = st.text_input("Tên sự kiện", value=event['event'])
                
                c1, c2 = st.columns(2)
                updated_data['start_time'] = c1.text_input("Bắt đầu (ISO)", value=event['start_time'])
                updated_data['end_time'] = c2.text_input("Kết thúc (ISO)", value=event.get('end_time', ''))
                
                updated_data['location'] = st.text_input("Địa điểm", value=event.get('location', ''))
                updated_data['reminder_minutes'] = st.number_input("Nhắc trước (phút)", value=event['reminder_minutes'], min_value=0)
                
                btn_save, btn_cancel = st.columns(2)
                
                if btn_save.form_submit_button("Lưu thay đổi"):
                    # Cập nhật vào DB
                    db.update_event(event_id, updated_data)
                    st.session_state.editing_event_id = None
                    st.success(f"Đã cập nhật sự kiện ID {event_id}")
                    st.rerun()
                    
                if btn_cancel.form_submit_button("Hủy"):
                    st.session_state.editing_event_id = None
                    st.rerun()

        # Nếu không, hiển thị thông tin sự kiện bình thường
        else:
            col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
            
            with col1:
                st.write(f"**{event['event']}**")
                st.caption(f"Nhắc trước: {event['reminder_minutes']} phút")
            
            with col2:
                st.write(f"**Bắt đầu:** {event['start_time']}")
                st.write(f"**Kết thúc:** {event.get('end_time', 'N/A')}")
                
            with col3:
                st.write(event.get('location', 'N/A'))
                
            with col4:
                if st.button("Sửa", key=f"edit_{event_id}", help="Chỉnh sửa sự kiện này"):
                    st.session_state.editing_event_id = event_id
                    st.rerun()
                    
            with col5:
                if st.button("Xóa", key=f"delete_{event_id}", type="primary", help="Xóa sự kiện này"):
                    # Xóa khỏi DB
                    db.delete_event(event_id)
                    st.success(f"Đã xóa sự kiện ID {event_id}")
                    st.rerun()