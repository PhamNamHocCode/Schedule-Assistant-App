import streamlit as st
import threading
import time
import queue
from datetime import datetime, timedelta, time as dt_time

# Import các module cốt lõi của bạn
import nlp_parser  #
from Database import database as db  #

# Import component lịch
try:
    from streamlit_calendar import calendar  #
except ImportError:
    st.error("Không tìm thấy thư viện 'streamlit_calendar'. Hãy đảm bảo bạn đã cài đặt nó.")
    st.stop()

# --- 1. HỆ THỐNG NHẮC NHỞ (BACKGROUND THREAD) ---
def reminder_checker(notification_queue):
    print("Luồng nhắc nhở đã bắt đầu...")
    while True:
        try:
            now_iso = datetime.now().isoformat()
            
            # 1. KIỂM TRA: Gọi DB để tìm sự kiện cần nhắc
            events_to_notify = db.get_events_to_notify(now_iso) #
            
            for event in events_to_notify:
                # 2. GỬI THÔNG BÁO: Đẩy tên sự kiện vào "hàng đợi"
                notification_queue.put(event['event'])
                
                # 3. ĐÁNH DẤU: Đánh dấu là đã nhắc
                db.set_event_notified(event['id']) #
                
        except Exception as e:
            print(f"Lỗi trong luồng nhắc nhở: {e}")
        
        # 4. ĐỊNH KỲ: Ngủ 60 giây
        time.sleep(60)

if 'notification_queue' not in st.session_state:
    st.session_state.notification_queue = queue.Queue()
if 'reminder_thread_started' not in st.session_state:
    db.init_db() #
    thread = threading.Thread(target=reminder_checker, args=(st.session_state.notification_queue,), daemon=True)
    thread.start()
    st.session_state.reminder_thread_started = True

# --- 2. GIAO DIỆN NGƯỜI DÙNG (STREAMLIT UI) ---
st.set_page_config(page_title="Trợ lý Lịch trình", layout="wide")
st.title("🗓️ Trợ lý Quản lý Lịch trình Cá nhân")

# === BẮT ĐẦU KHỐI THÔNG BÁO ===
# 1. Thông báo nhắc nhở (từ thread)
while not st.session_state.notification_queue.empty():
    event_name = st.session_state.notification_queue.get()
    st.toast(f"🔔 Nhắc nhở: {event_name} sắp diễn ra!")

# 2. Thông báo hành động (Thêm, Sửa, Xóa)
if 'notifications' not in st.session_state:
    st.session_state.notifications = []

# Hiển thị và xóa thông báo
for message, icon in st.session_state.notifications:
    st.toast(message, icon=icon)

st.session_state.notifications = []
# === KẾT THÚC KHỐI THÔNG BÁO ===

# --- 3. KHUNG NHẬP LIỆU NLP ---
st.header("Thêm sự kiện nhanh")
nlp_input = st.text_input("Nhập câu yêu cầu lịch trình:", placeholder="VD: Họp nhóm 10h sáng mai ở phòng 302, nhắc trước 15 phút")
if st.button("Thêm sự kiện"):
    if nlp_input:
        parsed_data = nlp_parser.parse_sentence(nlp_input) #
        if "error" in parsed_data:
            st.error(f"Lỗi phân tích: {parsed_data['error']}")
        else:
            try:
                event_id = db.add_event(parsed_data) #
                # THAY ĐỔI: Dùng st.toast
                st.session_state.notifications.append((f"Đã thêm: '{parsed_data['event']}'", "✅"))
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi thêm vào database: {e}")
    else:
        st.warning("Vui lòng nhập câu yêu cầu.")
st.divider()

# --- 4. LỊCH (CALENDAR GRID) ---
st.header("Lịch của bạn")

all_events_db = db.get_all_events() #
calendar_events = []
for event in all_events_db:
    # Bọc trong try-except để phòng trường hợp start_time trong DB bị lỗi
    try:
        start_dt = datetime.fromisoformat(event['start_time'])
    except (ValueError, TypeError):
        continue # Bỏ qua sự kiện lỗi

    if event['end_time']:
        end_dt_iso = event['end_time']
    else:
        end_dt_iso = (start_dt + timedelta(hours=1)).isoformat()
        
    calendar_events.append({
        "title": event['event'].capitalize(),
        "start": event['start_time'],
        "end": end_dt_iso,
        "extendedProps": {
            "id": event['id'],
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
    "editable": True, 
    "dateClickable": False, 
    "eventClickable": False,
}

# YÊU CẦU 1 & 2: Chỉnh CSS cho lịch
custom_css = """
    .fc-view-harness { height: 600px; }
    .fc-today-button, .fc-dayGridMonth-button, .fc-timeGridWeek-button, .fc-timeGridDay-button {
        text-transform: capitalize;
    }
"""

# Hiển thị lịch
st_calendar = calendar(
    events=calendar_events,
    options=calendar_options,
    custom_css=custom_css,
)

st.divider()

# --- 5. QUẢN LÝ SỰ KIỆN (DANH SÁCH, SỬA, XÓA) ---
st.header("Danh sách & Quản lý Sự kiện")

# (Đã xóa khối 'delete_notifications' cũ - vì đã gộp chung ở trên)

if 'editing_event_id' not in st.session_state:
    st.session_state.editing_event_id = None

if not all_events_db:
    st.info("Bạn chưa có sự kiện nào trong lịch.")
else:
    col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
    col1.subheader("Sự kiện")
    col2.subheader("Thời gian")
    col3.subheader("Địa điểm")
    st.markdown("---")

    for event in reversed(all_events_db):
        event_id = event['id']
        
        # PHẦN CHỈNH SỬA (YÊU CẦU 4)
        if st.session_state.editing_event_id == event_id:
            with st.form(key=f"form_edit_{event_id}"):
                st.subheader(f"Chỉnh sửa sự kiện: {event['event'].capitalize()}")
                
                updated_data = {}
                updated_data['event'] = st.text_input("Tên sự kiện", value=event['event'])
                
                st.write("**Thời gian bắt đầu và kết thúc:**")
                col_start_date, col_start_time, col_end_date, col_end_time = st.columns(4)

                try:
                    start_dt = datetime.fromisoformat(event['start_time'])
                except ValueError:
                    start_dt = datetime.now()

                edit_start_date = col_start_date.date_input("Ngày bắt đầu", value=start_dt.date())
                edit_start_time = col_start_time.time_input("Giờ bắt đầu", value=start_dt.time())
                updated_data['start_time'] = datetime.combine(edit_start_date, edit_start_time).isoformat()

                try:
                    if event['end_time']:
                        end_dt = datetime.fromisoformat(event['end_time'])
                    else:
                        end_dt = start_dt + timedelta(hours=1)
                except (ValueError, TypeError, KeyError): 
                    st.warning("Phát hiện thời gian kết thúc không hợp lệ, sử dụng mặc định.")
                    end_dt = start_dt + timedelta(hours=1)

                edit_end_date = col_end_date.date_input("Ngày kết thúc", value=end_dt.date())
                edit_end_time = col_end_time.time_input("Giờ kết thúc", value=end_dt.time())

                if datetime.combine(edit_end_date, edit_end_time) < datetime.combine(edit_start_date, edit_start_time):
                    st.error("Ngày kết thúc phải bằng hoặc lớn hơn ngày bắt đầu.")
                else:
                    if datetime.combine(edit_end_date, edit_end_time) == (datetime.combine(edit_start_date, edit_start_time) + timedelta(hours=1)):
                        updated_data['end_time'] = None
                    else:
                        updated_data['end_time'] = datetime.combine(edit_end_date, edit_end_time).isoformat()

                updated_data['location'] = st.text_input("Địa điểm", value=event.get('location', ''))

                st.write("**Nhắc trước:**")
                col_rem_hr, col_rem_min = st.columns(2)
                
                total_minutes = event.get('reminder_minutes', 0) or 0
                default_hours = total_minutes // 60
                default_minutes = total_minutes % 60
                
                edit_remind_hours = col_rem_hr.number_input("Giờ", min_value=0, value=default_hours)
                edit_remind_minutes = col_rem_min.number_input("Phút", min_value=0, max_value=59, value=default_minutes, step=5)
                
                updated_data['reminder_minutes'] = (edit_remind_hours * 60) + edit_remind_minutes
                
                btn_save, btn_cancel = st.columns(2)
                save_pressed = btn_save.form_submit_button("Lưu thay đổi")
                cancel_pressed = btn_cancel.form_submit_button("Hủy")

                if save_pressed:
                    db.update_event(event_id, updated_data) #
                    st.session_state.editing_event_id = None
                    # THAY ĐỔI: Dùng st.toast
                    st.session_state.notifications.append((f"Đã cập nhật sự kiện ID {event_id}", "🔄"))
                    st.rerun()
                    
                if cancel_pressed:
                    st.session_state.editing_event_id = None
                    st.rerun()

        else:
            # PHẦN HIỂN THỊ DANH SÁCH (YÊU CẦU 3)
            col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
            with col1:
                st.write(f"**{event['event'].capitalize()}**") 
                st.caption(f"Nhắc trước: {event.get('reminder_minutes', 0) or 0} phút") # Sửa lỗi None
            with col2:
                st.write(f"**Bắt đầu:** {event['start_time']}")
                if event['end_time']:
                    end_time_display = event['end_time']
                else:
                    try:
                        start_dt = datetime.fromisoformat(event['start_time'])
                        end_time_display = (start_dt + timedelta(hours=1)).isoformat() + " (Tự động)"
                    except ValueError:
                        end_time_display = "Lỗi thời gian bắt đầu"
                st.write(f"**Kết thúc:** {end_time_display}")
            with col3:
                st.write(event.get('location', 'N/A'))
            with col4:
                if st.button("Sửa", key=f"edit_{event_id}"):
                    st.session_state.editing_event_id = event_id
                    st.rerun()
            with col5:
                if st.button("Xóa", key=f"delete_{event_id}", type="primary"):
                    db.delete_event(event_id) #
                    # THAY ĐỔI: Dùng st.toast
                    st.session_state.notifications.append((f"Đã xóa sự kiện: {event['event']}", "❌"))
                    st.rerun()

# (Đã xóa code thừa ở cuối)