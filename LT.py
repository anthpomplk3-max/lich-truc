import streamlit as st
import pandas as pd
import calendar
import numpy as np
from datetime import datetime
import random

# Tiêu đề ứng dụng
st.set_page_config(page_title="Xếp lịch trực TBA 500kV", layout="wide")
st.title("🔄 Xếp lịch trực TBA 500kV - Tối ưu Tăng Ca & Luân Phiên")
st.markdown("---")

# 1. DANH SÁCH NHÂN VIÊN & ƯU TIÊN
truong_kiep = ["Nguyễn Minh Dũng", "Ngô Quang Việt", "Nguyễn Trọng Tình", "Đặng Nhật Nam"]
van_hanh_vien = ["Trương Hoàng An", "Lê Vũ Vĩnh Lợi", "Nguyễn Cao Cường", "Trần Văn Võ"]
all_staff = truong_kiep + van_hanh_vien

# Thứ tự ưu tiên (Index càng thấp ưu tiên càng cao)
priority_tk = {name: idx for idx, name in enumerate(["Nguyễn Minh Dũng", "Ngô Quang Việt", "Nguyễn Trọng Tình", "Đặng Nhật Nam"])}
priority_vhv = {name: idx for idx, name in enumerate(["Trương Hoàng An", "Lê Vũ Vĩnh Lợi", "Nguyễn Cao Cường", "Trần Văn Võ"])}

# Khởi tạo session state
if 'schedule_created' not in st.session_state:
    st.session_state.update({
        'schedule_created': False, 'schedule_data': None, 'staff_stats': None,
        'staff_horizontal_schedule': None, 'day_off': {s: [] for s in all_staff},
        'business_trip': {s: [] for s in all_staff}, 'line_inspection': [],
        'night_shift_goals': {s: 0 for s in all_staff}, 'original_schedule': None
    })

# SIDEBAR CÀI ĐẶT
with st.sidebar:
    st.header("Thông tin tháng")
    month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1)
    year = st.selectbox("Năm", range(2023, 2030), index=datetime.now().year-2023)
    num_days = calendar.monthrange(year, month)[1]
    
    st.header("Cài đặt")
    training_day = st.slider("Ngày đào tạo", 1, num_days, 15)
    tk_substitute_vhv = st.checkbox("Cho phép TK thay VHV khi cấp bách", value=True)

# --- CÁC HÀM LOGIC CỐT LÕI ---

def get_staff_priority_score(staff, staff_data, is_overtime_mode):
    """
    Tính điểm để chọn người: 
    1. Ưu tiên người chưa đủ 17 công.
    2. Nếu tăng ca: Ưu tiên người có số lần tăng ca ít hơn (luân phiên).
    3. Cuối cùng mới xét đến thứ tự tên (An, Lợi...).
    """
    p_map = priority_tk if staff in truong_kiep else priority_vhv
    p_idx = p_map.get(staff, 99)
    
    overtime_count = staff_data[staff].get('overtime_count', 0)
    total_credits = staff_data[staff]['current_total_credits']
    
    # Điểm càng thấp càng được chọn trước
    if not is_overtime_mode:
        # Chế độ bình thường: Ưu tiên người ít công nhất
        return total_credits * 100 + p_idx
    else:
        # Chế độ tăng ca: Ưu tiên người ít lần tăng ca nhất để luân phiên, sau đó tới thứ tự tên
        return overtime_count * 1000 + p_idx

def select_staff(available_list, staff_data, day, shift_type, is_vhv_role, allow_overtime, night_goal_15):
    """Hàm chọn nhân viên thỏa mãn các quy tắc cứng"""
    eligible = []
    
    for s in available_list:
        data = staff_data[s]
        
        # Quy tắc 17 công
        if not allow_overtime and data['current_total_credits'] >= 17:
            continue
            
        # Quy tắc 24h: Không trực ca Ngày nếu vừa trực ca Đêm sáng hôm đó (và ngược lại)
        if data['last_shift_day'] == day:
            continue

        # Quy tắc ca liên tiếp
        max_consecutive = 4 if (data['night_shift_goal'] >= 15 or night_goal_15) else 3
        if shift_type == 'night' and data['consecutive_night'] >= max_consecutive:
            continue
        if shift_type == 'day' and data['consecutive_day'] >= max_consecutive:
            continue
            
        eligible.append(s)
    
    if not eligible:
        return None
    
    # Sắp xếp theo điểm ưu tiên và luân phiên
    eligible.sort(key=lambda x: get_staff_priority_score(x, staff_data, allow_overtime))
    return eligible[0]

def update_stats(staff_data, name, day, shift_type):
    """Cập nhật trạng thái sau mỗi ca trực"""
    sd = staff_data[name]
    sd['total_shifts'] += 1
    if shift_type == 'day':
        sd['day_shifts'] += 1
        sd['consecutive_day'] += 1
        sd['consecutive_night'] = 0
    else:
        sd['night_shifts'] += 1
        sd['consecutive_night'] += 1
        sd['consecutive_day'] = 0
    
    sd['last_shift_day'] = day
    sd['last_shift_type'] = shift_type
    
    # Tính toán công
    sd['current_total_credits'] = sd['admin_credits'] + sd['total_shifts']
    if sd['current_total_credits'] > 17:
        sd['overtime_count'] = sd['current_total_credits'] - 17

def generate_schedule(is_emergency=False, start_from=1, existing_history=None):
    """Hàm tạo lịch chính"""
    staff_data = {}
    for s in all_staff:
        # Tính công hành chính (Đào tạo + Kiểm tra + Công tác)
        li_days = [g['day'] for g in st.session_state.line_inspection if g['tk'] == s or g['vhv'] == s]
        bt_days = st.session_state.business_trip.get(s, [])
        admin_credits = 1 + len(li_days) + len(bt_days) # 1 là ngày đào tạo
        
        staff_data[s] = {
            'total_shifts': 0, 'day_shifts': 0, 'night_shifts': 0,
            'consecutive_night': 0, 'consecutive_day': 0,
            'last_shift_day': -1, 'last_shift_type': None,
            'night_shift_goal': st.session_state.night_shift_goals.get(s, 0),
            'admin_credits': admin_credits, 'current_total_credits': admin_credits,
            'overtime_count': 0, 'unavailable': set(st.session_state.day_off.get(s, []) + bt_days + li_days)
        }

    new_schedule = []
    # Nếu là điều chỉnh đột xuất, copy lại lịch cũ trước ngày start_from
    if is_emergency and existing_history:
        for shift in existing_history:
            if shift['Ngày'] < start_from:
                new_schedule.append(shift)
                update_stats(staff_data, shift['Trưởng kiếp'], shift['Ngày'], 'day' if 'Ngày' in shift['Ca'] else 'night')
                update_stats(staff_data, shift['Vận hành viên'], shift['Ngày'], 'day' if 'Ngày' in shift['Ca'] else 'night')

    # Kiểm tra xem có ai đăng ký 15 ca đêm không để nới lỏng quy tắc 4 ca
    has_15_night = any(g >= 15 for g in st.session_state.night_shift_goals.values())
    
    # Xác định có đang trong tình trạng thiếu người (phải tăng ca) không
    any_business_trip = any(len(v) > 0 for v in st.session_state.business_trip.values())

    for d in range(start_from, num_days + 1):
        if d == training_day: continue
        
        for shift_name, s_type in [("Ngày (6h-18h)", "day"), ("Đêm (18h-6h)", "night")]:
            # Lọc danh sách người rảnh
            avail_tk = [s for s in truong_kiep if d not in staff_data[s]['unavailable']]
            avail_vhv = [s for s in van_hanh_vien if d not in staff_data[s]['unavailable']]
            
            # 1. Chọn Trưởng Kiếp
            sel_tk = select_staff(avail_tk, staff_data, d, s_type, False, any_business_trip, has_15_night)
            
            # 2. Chọn Vận Hành Viên
            sel_vhv = select_staff(avail_vhv, staff_data, d, s_type, True, any_business_trip, has_15_night)
            
            # Trường hợp khẩn cấp: TK thay VHV
            if not sel_vhv and tk_substitute_vhv:
                avail_tk_rem = [s for s in avail_tk if s != sel_tk]
                sel_vhv = select_staff(avail_tk_rem, staff_data, d, s_type, False, any_business_trip, has_15_night)

            if sel_tk and sel_vhv:
                update_stats(staff_data, sel_tk, d, s_type)
                update_stats(staff_data, sel_vhv, d, s_type)
                new_schedule.append({
                    'Ngày': d, 'Ca': shift_name, 'Trưởng kiếp': sel_tk, 'Vận hành viên': sel_vhv,
                    'Ghi chú': "Tăng ca" if staff_data[sel_tk]['current_total_credits'] > 17 or staff_data[sel_vhv]['current_total_credits'] > 17 else ""
                })
    
    return sorted(new_schedule, key=lambda x: (x['Ngày'], x['Ca'])), staff_data

# --- GIAO DIỆN TABS ---
tab1, tab2, tab3 = st.tabs(["📅 Thiết lập", "📊 Lịch trực", "📋 Thống kê & Điều chỉnh"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Ngày nghỉ & Mục tiêu ca đêm")
        for s in all_staff:
            with st.expander(f"Nhân viên: {s}"):
                st.session_state.day_off[s] = st.multiselect(f"Ngày nghỉ ({s})", range(1, num_days+1), default=st.session_state.day_off.get(s, []))
                st.session_state.night_shift_goals[s] = st.number_input(f"Mục tiêu ca đêm ({s})", 0, 15, value=st.session_state.night_shift_goals.get(s, 0))
    with col2:
        st.subheader("Công tác & Kiểm tra")
        for s in all_staff:
            st.session_state.business_trip[s] = st.multiselect(f"Ngày công tác ({s})", range(1, num_days+1), default=st.session_state.business_trip.get(s, []))

with tab2:
    if st.button("🎯 Tạo lịch trực mới", type="primary"):
        res_schedule, res_stats = generate_schedule()
        st.session_state.schedule_data = res_schedule
        st.session_state.staff_stats = res_stats
        st.session_state.schedule_created = True
        st.session_state.original_schedule = res_schedule.copy()
        st.success("Đã tạo lịch thành công!")

    if st.session_state.schedule_created:
        # Hiển thị lịch dạng bảng ngang cho dễ nhìn
        df_schedule = pd.DataFrame(st.session_state.schedule_data)
        st.dataframe(df_schedule, use_container_width=True)

with tab3:
    if st.session_state.schedule_created:
        st.subheader("Thống kê công")
        stat_list = []
        for s, data in st.session_state.staff_stats.items():
            stat_list.append({
                "Nhân viên": s, "Tổng công": data['current_total_credits'],
                "Số ca trực": data['total_shifts'], "Ca đêm": data['night_shifts'],
                "Số lần tăng ca": data['overtime_count'], "Trạng thái": "🔥 Tăng ca" if data['current_total_credits'] > 17 else "✅ Đủ"
            })
        st.table(pd.DataFrame(stat_list))

        st.divider()
        st.subheader("🚨 Điều chỉnh công tác đột xuất")
        col_e1, col_e2, col_e3 = st.columns(3)
        e_staff = col_e1.selectbox("Người đi đột xuất", all_staff)
        e_start = col_e2.number_input("Từ ngày", 1, num_days, 10)
        e_end = col_e3.number_input("Đến ngày", e_start, num_days, e_start + 2)
        
        if st.button("🔄 Cập nhật lịch & Tính tăng ca"):
            # Cập nhật ngày công tác mới
            st.session_state.business_trip[e_staff] = list(set(st.session_state.business_trip[e_staff] + list(range(e_start, e_end + 1))))
            # Chạy lại lịch từ ngày e_start
            new_res, new_stat = generate_schedule(is_emergency=True, start_from=e_start, existing_history=st.session_state.original_schedule)
            st.session_state.schedule_data = new_res
            st.session_state.staff_stats = new_stat
            st.rerun()
