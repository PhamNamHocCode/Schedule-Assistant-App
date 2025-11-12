# app.py
import solara
import threading
import time
from datetime import datetime
import nlp_parser  # Module NLP của chúng ta
from Database import database    # Module DB của chúng ta

# Khởi tạo DB khi app chạy
database.init_db()

# --- State của ứng dụng ---
# Biến này sẽ được chia sẻ giữa thread và UI
# (Đây là 'atom' trong Solara)
notifications_to_show = solara.reactive([])

# --- Logic Nhắc nhở (Background Thread) ---
def reminder_check_thread():
    """Luồng chạy nền kiểm tra nhắc nhở mỗi 60 giây."""
    print("Reminder thread started...")
    while True:
        now = datetime.now()
        now_iso = now.isoformat()
        
        try:
            events = database.get_events_to_notify(now_iso)
            
            new_notifications = []
            for event in events:
                print(f"Phát hiện nhắc nhở cho: {event['event']}")
                
                # Thêm vào danh sách để UI hiển thị
                new_notifications.append(event)
                
                # Đánh dấu đã thông báo
                database.set_event_notified(event['id'])
            
            if new_notifications:
                # Cập nhật biến reactive -> Solara UI sẽ tự động update
                # Phải dùng .value khi ở ngoài component
                current_list = notifications_to_show.value
                notifications_to_show.value = current_list + new_notifications

        except Exception as e:
            print(f"Lỗi trong reminder thread: {e}")
            
        # Chờ 60 giây
        time.sleep(60)

# Chỉ chạy thread một lần duy nhất khi app khởi động
# (Solara có thể render lại component, nên cần check)
if 'reminder_thread' not in globals():
    globals()['reminder_thread'] = threading.Thread(target=reminder_check_thread, daemon=True)
    globals()['reminder_thread'].start()


# --- Component Giao diện Solara ---
@solara.component
def NotificationPopup():
    """Component hiển thị Pop-up (Dialog) khi có thông báo."""
    
    # Lấy giá trị của biến reactive
    # Dùng .value khi ở trong component
    notifications = notifications_to_show.value

    if notifications:
        # Lấy thông báo đầu tiên
        event = notifications[0]
        
        # Hiển thị Pop-up (dùng solara.Modal)
        with solara.Modal("🔔 Thông báo nhắc lịch!", on_close=lambda: close_notification(event)):
            solara.Markdown(f"### Sự kiện: **{event['event']}**")
            solara.Markdown(f"Thời gian: **{event['start_time']}**")
            if event['location']:
                solara.Markdown(f"Địa điểm: **{event['location']}**")
            
            solara.Button("Đã xem", on_click=lambda: close_notification(event))

def close_notification(event_to_remove):
    """Xóa thông báo khỏi danh sách chờ sau khi user đóng."""
    current_list = notifications_to_show.value
    # Tạo list mới không chứa event đã đóng
    notifications_to_show.value = [e for e in current_list if e['id'] != event_to_remove['id']]

@solara.component
def Page():
    # State cho ô nhập liệu
    input_text, set_input_text = solara.use_state("")
    message, set_message = solara.use_state("")

    def handle_add_event():
        """Gọi NLP parser và thêm vào DB."""
        if not input_text:
            set_message("Vui lòng nhập câu lệnh.")
            return
            
        result = nlp_parser.parse_sentence(input_text)
        
        if "error" in result:
            set_message(f"Lỗi: {result['error']}")
        else:
            event_id = database.add_event(result)
            set_message(f"Đã thêm sự kiện: '{result['event']}' (ID: {event_id})")
            set_input_text("") # Xóa ô input
            # (Bạn có thể thêm logic refresh lại bảng lịch ở đây)

    # --- Giao diện người dùng ---
    
    # 1. Component hiển thị Pop-up
    NotificationPopup() 

    # 2. Ô nhập NLP
    solara.Markdown("## 🗓️ Trợ lý Lịch trình của bạn")
    solara.Markdown("Nhập yêu cầu của bạn (VD: 'Họp nhóm lúc 10h sáng mai ở 302, nhắc trước 15 phút')")
    
    solara.InputText("Yêu cầu", value=input_text, on_value=set_input_text, continuous_update=False)
    solara.Button("Thêm sự kiện", on_click=handle_add_event)
    
    if message:
        solara.Success(message) # Hoặc solara.Error

    # 3. Bảng lịch
    solara.Markdown("---")
    solara.Markdown("### Danh sách sự kiện")
    # (Đây là nơi bạn sẽ code bảng lịch - Giai đoạn 4)
    # Tạm thời chỉ hiển thị tất cả sự kiện
    
    events = database.get_all_events()
    with solara.Card("Tất cả sự kiện"):
        for event in events:
            with solara.Card(f"{event['event']} @ {event['start_time']}", subtitle=f"ID: {event['id']}"):
                if event['location']:
                    solara.Markdown(f"Địa điểm: {event['location']}")
                if event['reminder_minutes']:
                     solara.Markdown(f"Nhắc trước: {event['reminder_minutes']} phút")
                # (Thêm nút Sửa/Xóa ở đây)


# --- Chạy ứng dụng Solara ---
if __name__ == "__main__":
    Page()