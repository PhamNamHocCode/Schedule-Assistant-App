import solara
from datetime import datetime
import_ok = True

# --- 1. Import các module bạn đã tạo ---
try:
    from Database.database import init_db, add_event, get_all_events, delete_event
    from nlp_parser import parse_sentence
except ImportError:
    print("Lỗi: Không thể import 'database.py' hoặc 'nlp_parser.py'.")
    print("Hãy đảm bảo các file này nằm đúng vị trí.")
    import_ok = False

# --- 2. Khởi tạo & Quản lý trạng thái (State) ---

# Khởi tạo CSDL khi ứng dụng bắt đầu
if import_ok:
    init_db()

# Biến reactive để lưu trữ danh sách sự kiện
events_list = solara.reactive(get_all_events() if import_ok else [])

# Biến reactive cho ô nhập liệu
text_input = solara.reactive("")

# Biến reactive để hiển thị thông báo
snackbar_message = solara.reactive("")
show_snackbar = solara.reactive(False)

def show_message(message: str):
    """Hiển thị thông báo nhanh"""
    snackbar_message.set(message)
    show_snackbar.set(True)

# --- 3. Logic xử lý sự kiện ---

def handle_add_event():
    """Được gọi khi người dùng bấm nút 'Thêm sự kiện'"""
    if not text_input.value:
        show_message("Vui lòng nhập nội dung sự kiện.")
        return

    # Gọi module NLP của bạn
    parsed_data = parse_sentence(text_input.value)
    
    if parsed_data.get("error"):
        # Nếu NLP không xử lý được
        show_message(f"Lỗi NLP: {parsed_data['error']}")
    else:
        # Nếu NLP thành công, gọi module Database của bạn
        try:
            add_event(parsed_data)
            show_message("Đã thêm sự kiện thành công!")
            # Xóa nội dung ô nhập
            text_input.set("")
            # Tải lại danh sách sự kiện
            refresh_events()
        except Exception as e:
            show_message(f"Lỗi CSDL: {e}")

def handle_delete_event(event_id: int):
    """Được gọi khi người dùng bấm nút 'Xóa'"""
    try:
        delete_event(event_id)
        show_message("Đã xóa sự kiện.")
        # Tải lại danh sách sự kiện
        refresh_events()
    except Exception as e:
        show_message(f"Lỗi khi xóa: {e}")

def refresh_events():
    """Hàm tải lại danh sách sự kiện từ CSDL"""
    events_list.set(get_all_events())

def format_time(iso_str: str) -> str:
    """Định dạng thời gian ISO thành dạng dễ đọc"""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M ngày %d-%m-%Y")
    except ValueError:
        return iso_str

# --- 4. Định nghĩa Component Giao diện ---

@solara.component
def EventCard(event: dict):
    """Một card hiển thị thông tin của một sự kiện"""
    with solara.Card("", style={"margin": "10px 0", "padding": "15px"}):
        solara.Markdown(f"### {event.get('event', 'Không có tên sự kiện')}")
        solara.Markdown(f"**Bắt đầu:** {format_time(event.get('start_time'))}")
        
        if event.get('location'):
            solara.Markdown(f"**Tại:** {event.get('location')}")
        if event.get('reminder_minutes'):
            solara.Markdown(f"**Nhắc trước:** {event.get('reminder_minutes')} phút")
        
        with solara.Row(justify="flex-end", style={"margin-top": "10px"}):
            solara.Button(
                "Xóa", 
                on_click=lambda: handle_delete_event(event.get('id')), 
                color="error",
                icon_name="mdi-delete"
            )

@solara.component
def Page():
    if not import_ok:
        solara.Error("Lỗi import! Vui lòng kiểm tra terminal để biết chi tiết.")
        return

    # Sử dụng message state để hiển thị thông báo
    message_text = snackbar_message.value if show_snackbar.value else ""

    with solara.Column(style={"max-width": "900px", "margin": "20px auto", "padding": "20px"}):
        solara.Markdown("# 🗓️ Trợ lý Lịch trình cá nhân")
        
        # --- Ô nhập liệu ---
        solara.Markdown("Nhập yêu cầu của bạn (ví dụ: 'Họp nhóm lúc 10h sáng mai ở phòng 302')")
        
        with solara.Row(style={"gap": "10px", "align-items": "center"}):
            solara.InputText(
                label="Thêm sự kiện mới",
                value=text_input,
                continuous_update=False,
                style={"flex": "1"}
            )
            solara.Button(
                "Thêm sự kiện", 
                on_click=handle_add_event, 
                color="primary"
            )
        
        solara.HTML(tag="hr", unsafe_innerHTML="")
        
        # --- Danh sách sự kiện ---
        solara.Markdown("### 📅 Danh sách sự kiện của bạn")
        if not events_list.value:
            solara.Info("Bạn chưa có sự kiện nào. Hãy thêm một sự kiện mới!")
        else:
            for event in events_list.value:
                EventCard(event)
        
        # --- Hiển thị thông báo ---
        if message_text:
            solara.Success(message_text)