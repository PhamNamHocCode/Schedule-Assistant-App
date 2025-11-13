from flask import Flask, render_template, request, redirect, url_for, flash, session
import threading
import time
import queue
from datetime import datetime, timedelta
from datetime import time as dt_time
import json

# Import các module cốt lõi của bạn
import nlp_parser
from Database import database as db

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Thay đổi thành key bí mật thực tế

# --- 1. HỆ THỐNG NHẮC NHỞ (BACKGROUND THREAD) ---
notification_queue = queue.Queue()

def reminder_checker(notif_queue):
    print("Luồng nhắc nhở đã bắt đầu...")
    while True:
        try:
            now_iso = datetime.now().isoformat()
            
            # 1. KIỂM TRA: Gọi DB để tìm sự kiện cần nhắc
            events_to_notify = db.get_events_to_notify(now_iso)
            
            for event in events_to_notify:
                # 2. GỬI THÔNG BÁO: Đẩy tên sự kiện vào "hàng đợi"
                notif_queue.put(event['event'])
                
                # 3. ĐÁNH DẤU: Đánh dấu là đã nhắc
                db.set_event_notified(event['id'])
                
        except Exception as e:
            print(f"Lỗi trong luồng nhắc nhở: {e}")
        
        # 4. ĐỊNH KỲ: Ngủ 60 giây
        time.sleep(60)

# Initialize the reminder thread when the app starts
with app.app_context():
    db.init_db()
    thread = threading.Thread(target=reminder_checker, args=(notification_queue,), daemon=True)
    thread.start()

# --- 2. ROUTES ---
@app.route('/', methods=['GET'])
def index():
    all_events_db = db.get_all_events()
    app.logger.info(f"Dữ liệu sự kiện từ cơ sở dữ liệu: {all_events_db}")

    # Chuẩn bị dữ liệu cho lịch
    calendar_events = []
    for event in all_events_db:
        try:
            start_dt = datetime.fromisoformat(event['start_time'])
        except (ValueError, TypeError):
            continue  # Bỏ qua sự kiện lỗi

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

    try:
        events_json = json.dumps(calendar_events)
    except (TypeError, ValueError) as e:
        events_json = "[]"  # Mặc định là mảng JSON rỗng nếu phân tích cú pháp thất bại
        app.logger.error(f"Lỗi khi phân tích sự kiện thành JSON: {e}")

    # Chuẩn bị dữ liệu cho danh sách sự kiện
    events = []
    for event in all_events_db:
        ev = event.copy()
        try:
            start_dt = datetime.fromisoformat(ev['start_time'])
            if ev['end_time']:
                end_time_display = ev['end_time']
            else:
                end_time_display = (start_dt + timedelta(hours=1)).isoformat() + " (Tự động)"
        except ValueError:
            end_time_display = "Lỗi thời gian bắt đầu"
        ev['end_time_display'] = end_time_display
        events.append(ev)

    # Chuẩn bị dữ liệu chỉnh sửa nếu có
    editing_event_id = session.get('editing_event_id')
    edited_event = None
    if editing_event_id:
        for e in all_events_db:
            if e['id'] == editing_event_id:
                edited_event = e.copy()
                break
        if edited_event:
            try:
                start_dt = datetime.fromisoformat(edited_event['start_time'])
            except ValueError:
                start_dt = datetime.now()
            edited_event['start_date'] = start_dt.date().isoformat()
            edited_event['start_time_of_day'] = start_dt.time().strftime('%H:%M')

            if edited_event['end_time']:
                try:
                    end_dt = datetime.fromisoformat(edited_event['end_time'])
                except ValueError:
                    end_dt = start_dt + timedelta(hours=1)
            else:
                end_dt = start_dt + timedelta(hours=1)
            edited_event['end_date'] = end_dt.date().isoformat()
            edited_event['end_time_of_day'] = end_dt.time().strftime('%H:%M')

            total_minutes = edited_event.get('reminder_minutes', 0) or 0
            edited_event['remind_hours'] = total_minutes // 60
            edited_event['remind_minutes'] = total_minutes % 60

    # Lấy thông báo nhắc nhở từ queue
    reminder_messages = []
    while not notification_queue.empty():
        event_name = notification_queue.get()
        reminder_messages.append(f"🔔 Nhắc nhở: {event_name} sắp diễn ra!")

    return render_template(
        'index.html',
        events=events,
        editing_event_id=editing_event_id,
        edited_event=edited_event,
        events_json=events_json,
        reminder_messages=reminder_messages
    )

@app.route('/add', methods=['POST'])
def add_event():
    nlp_input = request.form.get('nlp_input')
    if nlp_input:
        parsed_data = nlp_parser.parse_sentence(nlp_input)
        if "error" in parsed_data:
            flash(f"Lỗi phân tích: {parsed_data['error']}", 'error')
        else:
            try:
                event_id = db.add_event(parsed_data)
                flash(f"✅ Đã thêm: '{parsed_data['event']}'", 'success')
            except Exception as e:
                flash(f"Lỗi khi thêm vào database: {e}", 'error')
    else:
        flash("Vui lòng nhập câu yêu cầu.", 'warning')
    return redirect(url_for('index'))

@app.route('/edit/<int:event_id>', methods=['GET'])
def edit_event(event_id):
    session['editing_event_id'] = event_id
    return redirect(url_for('index'))

@app.route('/cancel_edit', methods=['GET'])
def cancel_edit():
    session.pop('editing_event_id', None)
    return redirect(url_for('index'))

@app.route('/update/<int:event_id>', methods=['POST'])
def update_event(event_id):
    updated_data = {}
    updated_data['event'] = request.form['event']
    
    start_date_str = request.form['start_date']
    start_time_str = request.form['start_time']
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    start_time = dt_time.fromisoformat(start_time_str)
    start_dt = datetime.combine(start_date, start_time)
    updated_data['start_time'] = start_dt.isoformat()
    
    end_date_str = request.form['end_date']
    end_time_str = request.form['end_time']
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    end_time = dt_time.fromisoformat(end_time_str)
    end_dt = datetime.combine(end_date, end_time)
    
    if end_dt < start_dt:
        flash("Ngày kết thúc phải bằng hoặc lớn hơn ngày bắt đầu.", 'error')
        return redirect(url_for('index'))
    else:
        if end_dt == start_dt + timedelta(hours=1):
            updated_data['end_time'] = None
        else:
            updated_data['end_time'] = end_dt.isoformat()
    
    updated_data['location'] = request.form['location']
    
    remind_hours = int(request.form['remind_hours'])
    remind_minutes = int(request.form['remind_minutes'])
    updated_data['reminder_minutes'] = (remind_hours * 60) + remind_minutes
    
    db.update_event(event_id, updated_data)
    flash(f"🔄 Đã cập nhật sự kiện ID {event_id}", 'success')
    session.pop('editing_event_id', None)
    return redirect(url_for('index'))

@app.route('/delete/<int:event_id>', methods=['POST'])
def delete_event_route(event_id):
    event = next((e for e in db.get_all_events() if e['id'] == event_id), None)
    if event:
        db.delete_event(event_id)
        flash(f"❌ Đã xóa sự kiện: {event['event']}", 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)