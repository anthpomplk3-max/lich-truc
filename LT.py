import streamlit as st
import pandas as pd
import calendar
import numpy as np
from datetime import datetime
import random

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="Xếp lịch trực TBA 500kV",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== INITIALIZATION ====================
# Danh sách nhân viên
truong_kiep = [
    "Nguyễn Trọng Tình",
    "Nguyễn Minh Dũng", 
    "Ngô Quang Việt",
    "Đặng Nhật Nam"
]

van_hanh_vien = [
    "Trương Hoàng An",
    "Lê Vũ Vĩnh Lợi",
    "Nguyễn Cao Cường",
    "Trần Văn Võ"
]

all_staff = truong_kiep + van_hanh_vien

# Ưu tiên tăng ca
overtime_priority_tk = ["Nguyễn Minh Dũng", "Ngô Quang Việt", "Nguyễn Trọng Tình", "Đặng Nhật Nam"]
overtime_priority_vhv = ["Trương Hoàng An", "Lê Vũ Vĩnh Lợi", "Nguyễn Cao Cường", "Trần Văn Võ"]

overtime_priority_map = {}
for idx, name in enumerate(overtime_priority_tk):
    overtime_priority_map[name] = idx
for idx, name in enumerate(overtime_priority_vhv):
    overtime_priority_map[name] = idx + 10

# ==================== SESSION STATE ====================
def init_session_state():
    """Khởi tạo session state"""
    defaults = {
        'schedule_created': False,
        'schedule_data': None,
        'staff_stats': None,
        'staff_horizontal_schedule': None,
        'day_off': {staff: [] for staff in all_staff},
        'business_trip': {staff: [] for staff in all_staff},
        'line_inspection': [],
        'night_shift_goals': {staff: 0 for staff in all_staff},
        'tk_substitute_vhv': False,
        'original_schedule': None,
        'original_stats': None,
        'original_horizontal_schedule': None,
        'adjusted_horizontal_schedule': None,
        'balance_shifts': True
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ==================== HELPER FUNCTIONS ====================
def calculate_night_shift_priority(staff_data, shift_type):
    """Tính điểm ưu tiên dựa trên mục tiêu ca đêm"""
    if shift_type == 'night':
        night_goal = staff_data.get('night_shift_goal', 0)
        night_diff = night_goal - staff_data['night_shifts']
        return -night_diff
    else:
        night_goal = staff_data.get('night_shift_goal', 0)
        night_diff = staff_data['night_shifts'] - night_goal
        return -night_diff

def calculate_shift_balance_score(staff_data, shift_type, balance_shifts):
    """Tính điểm cân bằng ca ngày/đêm"""
    if not balance_shifts:
        return 0
    day_shifts = staff_data['day_shifts']
    night_shifts = staff_data['night_shifts']
    diff = day_shifts - night_shifts
    if shift_type == 'day':
        return max(0, diff)
    else:
        return max(0, -diff)

def update_staff_data(staff_data, staff, day, shift_type):
    """Cập nhật thông tin nhân viên sau khi phân công"""
    if shift_type == 'day':
        staff_data[staff]['total_shifts'] += 1
        staff_data[staff]['day_shifts'] += 1
        staff_data[staff]['consecutive_night'] = 0
        staff_data[staff]['consecutive_day'] = staff_data[staff].get('consecutive_day', 0) + 1
    else:
        staff_data[staff]['total_shifts'] += 1
        staff_data[staff]['night_shifts'] += 1
        staff_data[staff]['consecutive_night'] += 1
        staff_data[staff]['consecutive_day'] = 0
    
    staff_data[staff]['last_shift'] = shift_type
    staff_data[staff]['last_shift_day'] = day
    staff_data[staff]['day_night_diff'] = staff_data[staff]['day_shifts'] - staff_data[staff]['night_shifts']
    staff_data[staff]['last_assigned_day'] = day
    
    staff_data[staff]['current_total_credits'] = (
        staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
    )
    
    if staff_data[staff]['current_total_credits'] > 17:
        staff_data[staff]['overtime_count'] = staff_data[staff].get('overtime_count', 0) + 1

def select_staff_for_role(available_staff, staff_data, day, shift_type, role_type, 
                         balance_shifts=True, last_days_mode=False, is_training_day=False, 
                         allow_overtime=False, overtime_priority_map=None):
    """Chọn nhân viên phù hợp"""
    if not available_staff:
        return None
    
    for staff in available_staff:
        data = staff_data[staff]
        current_credits = data['current_total_credits']
        remaining_to_17 = 17 - current_credits
        data['remaining_to_17'] = remaining_to_17

    filtered_staff = []
    for staff in available_staff:
        data = staff_data[staff]
        
        if role_type == 'TK' and not data['is_tk']: 
            continue
        if role_type == 'VHV' and not data['is_vhv']: 
            continue
        if role_type == 'TK_AS_VHV' and not data['is_tk']: 
            continue
        
        if not allow_overtime and data['remaining_to_17'] <= 0:
            continue
        
        if shift_type == 'night':
            night_goal = data.get('night_shift_goal', 0)
            max_consecutive_night = 4 if night_goal == 15 else 3
            if data['consecutive_night'] >= max_consecutive_night:
                continue
        
        if shift_type == 'day':
            night_goal = data.get('night_shift_goal', 0)
            max_consecutive_day = 4 if night_goal == 15 else 100
            if data.get('consecutive_day', 0) >= max_consecutive_day:
                continue
        
        if shift_type == 'night' and not is_training_day and data['last_shift'] == 'day' and data['last_shift_day'] == day:
            continue
        
        if balance_shifts and not allow_overtime:
            if shift_type == 'day' and (data['day_shifts'] - data['night_shifts'] > 2): 
                continue
            if shift_type == 'night' and (data['night_shifts'] - data['day_shifts'] > 2): 
                continue
        
        filtered_staff.append(staff)
    
    if not filtered_staff:
        return None
    
    if allow_overtime:
        filtered_staff.sort(key=lambda x: (
            staff_data[x].get('overtime_count', 0),
            overtime_priority_map.get(x, 999) if overtime_priority_map else 999,
            staff_data[x]['total_shifts'],
            calculate_night_shift_priority(staff_data[x], shift_type),
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            random.random()
        ))
    else:
        filtered_staff.sort(key=lambda x: (
            -staff_data[x]['remaining_to_17'],
            staff_data[x]['total_shifts'],
            calculate_night_shift_priority(staff_data[x], shift_type),
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            random.random()
        ))
    
    return filtered_staff[0]

def convert_to_staff_horizontal_schedule(schedule_data, num_days, year, month, 
                                        line_inspection_groups, day_off_dict, 
                                        business_trip_dict, training_day):
    """Chuyển lịch trực sang dạng ngang"""
    day_to_weekday = {}
    for day in range(1, num_days + 1):
        weekday = calendar.day_name[calendar.weekday(year, month, day)]
        vietnamese_days = {
            'Monday': 'T2', 'Tuesday': 'T3', 'Wednesday': 'T4',
            'Thursday': 'T5', 'Friday': 'T6', 'Saturday': 'T7', 'Sunday': 'CN'
        }
        day_to_weekday[day] = vietnamese_days.get(weekday, weekday)
    
    columns = [f"Ngày {day}\n({day_to_weekday[day]})" for day in range(1, num_days + 1)]
    staff_schedule_df = pd.DataFrame(index=all_staff, columns=columns)
    
    for staff, off_days in day_off_dict.items():
        for day in off_days:
            col = f"Ngày {day}\n({day_to_weekday[day]})"
            staff_schedule_df.loc[staff, col] = "Nghỉ"
    
    for staff, trip_days in business_trip_dict.items():
        for day in trip_days:
            col = f"Ngày {day}\n({day_to_weekday[day]})"
            staff_schedule_df.loc[staff, col] = "CT"
    
    for group in line_inspection_groups:
        if group['tk'] and group['vhv'] and group['day']:
            day = group['day']
            col = f"Ngày {day}\n({day_to_weekday[day]})"
            staff_schedule_df.loc[group['tk'], col] = "KT"
            staff_schedule_df.loc[group['vhv'], col] = "KT"
    
    for schedule in schedule_data:
        day = schedule['Ngày']
        shift_type = schedule['Ca']
        col = f"Ngày {day}\n({day_to_weekday[day]})"
        
        tk = schedule['Trưởng kiếp']
        vhv = schedule['Vận hành viên']
        
        val_tk = "N" if 'Ngày' in shift_type else "Đ"
        val_vhv = "N" if 'Ngày' in shift_type else "Đ"
        
        if day == training_day:
            val_tk += " (ĐT)"
            val_vhv += " (ĐT)"
        
        staff_schedule_df.loc[tk, col] = val_tk
        staff_schedule_df.loc[vhv, col] = val_vhv

    training_col = f"Ngày {training_day}\n({day_to_weekday[training_day]})"
    for staff in all_staff:
        if pd.isna(staff_schedule_df.loc[staff, training_col]) or staff_schedule_df.loc[staff, training_col] == '':
            staff_schedule_df.loc[staff, training_col] = "ĐT"
    
    staff_schedule_df = staff_schedule_df.fillna("-")
    
    role_column = []
    for staff in all_staff:
        if staff in truong_kiep:
            role_column.append("TK")
        else:
            role_column.append("VHV")
    staff_schedule_df.insert(0, 'Vai trò', role_column)
    staff_schedule_df = staff_schedule_df.sort_values('Vai trò', ascending=False)
    
    return staff_schedule_df

# ==================== MAIN SCHEDULING FUNCTIONS ====================
def generate_advanced_schedule(month, year, training_day, day_off_dict, business_trip_dict, 
                              line_inspection_groups, night_shift_goals, balance_shifts=True, 
                              allow_tk_substitute_vhv=False):
    """Tạo lịch trực tự động"""
    num_days = calendar.monthrange(year, month)[1]
    schedule = []
    has_business_trip = any(len(days) > 0 for days in business_trip_dict.values())
    
    line_inspection_dict = {staff: set() for staff in all_staff}
    for group in line_inspection_groups:
        if group['tk'] and group['vhv'] and group['day']:
            line_inspection_dict[group['tk']].add(group['day'])
            line_inspection_dict[group['vhv']].add(group['day'])
    
    staff_data = {}
    for staff in all_staff:
        training_credits = 1
        line_inspection_credits = len(line_inspection_dict.get(staff, set())) * 1
        business_days = len(business_trip_dict.get(staff, []))
        business_credits = business_days * 1
        admin_credits = training_credits + line_inspection_credits + business_credits
        
        staff_data[staff] = {
            'role': 'TK' if staff in truong_kiep else 'VHV',
            'total_shifts': 0, 'day_shifts': 0, 'night_shifts': 0, 
            'consecutive_night': 0, 'consecutive_day': 0,
            'last_shift': None, 'last_shift_day': None,
            'target_shifts': max(0, 17 - admin_credits),
            'night_shift_goal': night_shift_goals.get(staff, 0),
            'unavailable_days': set(day_off_dict.get(staff, []) + business_trip_dict.get(staff, [])),
            'business_trip_days': set(business_trip_dict.get(staff, [])),
            'line_inspection_days': line_inspection_dict.get(staff, set()),
            'day_night_diff': 0, 'last_assigned_day': None,
            'training_credits': training_credits,
            'line_inspection_credits': line_inspection_credits,
            'business_credits': business_credits, 
            'admin_credits': admin_credits,
            'current_total_credits': admin_credits,
            'is_tk': staff in truong_kiep, 
            'is_vhv': staff in van_hanh_vien,
            'overtime_count': 0,
        }
        staff_data[staff]['unavailable_days'].update(line_inspection_dict.get(staff, set()))

    for day in range(1, num_days + 1):
        is_training_day = (day == training_day)
        last_days_mode = (day > num_days - 5)
        
        available_tk = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
        available_vhv = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
        
        # Day shift
        sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', 
                                      balance_shifts, last_days_mode, is_training_day, 
                                      allow_overtime=False, overtime_priority_map=overtime_priority_map)
        if not sel_tk and has_business_trip:
            sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', 
                                          balance_shifts, last_days_mode, is_training_day, 
                                          allow_overtime=True, overtime_priority_map=overtime_priority_map)
        
        sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', 
                                       balance_shifts, last_days_mode, is_training_day, 
                                       allow_overtime=False, overtime_priority_map=overtime_priority_map)
        if not sel_vhv and has_business_trip:
            sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', 
                                           balance_shifts, last_days_mode, is_training_day, 
                                           allow_overtime=True, overtime_priority_map=overtime_priority_map)
        
        if not sel_vhv and allow_tk_substitute_vhv and sel_tk:
            avail_tk_sub = [s for s in available_tk if s != sel_tk]
            sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', 
                                           balance_shifts, last_days_mode, is_training_day, 
                                           allow_overtime=False, overtime_priority_map=overtime_priority_map)
            if not sel_vhv and has_business_trip:
                sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', 
                                               balance_shifts, last_days_mode, is_training_day, 
                                               allow_overtime=True, overtime_priority_map=overtime_priority_map)
            if sel_vhv: 
                staff_data[sel_vhv]['is_substituting_vhv'] = True

        if sel_tk and sel_vhv:
            update_staff_data(staff_data, sel_tk, day, 'day')
            update_staff_data(staff_data, sel_vhv, day, 'day')
            note = ('Đào tạo + ' if is_training_day else '') + ('TK thay VHV' if sel_vhv in truong_kiep else '')
            schedule.append({
                'Ngày': day, 
                'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                'Ca': 'Ngày (6h-18h)', 
                'Trưởng kiếp': sel_tk, 
                'Vận hành viên': sel_vhv, 
                'Ghi chú': note
            })

        # Night shift
        if is_training_day:
            avail_tk_n = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
            avail_vhv_n = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
        else:
            avail_tk_n = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days'] 
                         and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]
            avail_vhv_n = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days'] 
                          and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]

        sel_tk_n = select_staff_for_role(avail_tk_n, staff_data, day, 'night', 'TK', 
                                        balance_shifts, last_days_mode, is_training_day, 
                                        allow_overtime=False, overtime_priority_map=overtime_priority_map)
        if not sel_tk_n and has_business_trip:
            sel_tk_n = select_staff_for_role(avail_tk_n, staff_data, day, 'night', 'TK', 
                                            balance_shifts, last_days_mode, is_training_day, 
                                            allow_overtime=True, overtime_priority_map=overtime_priority_map)

        sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', 
                                         balance_shifts, last_days_mode, is_training_day, 
                                         allow_overtime=False, overtime_priority_map=overtime_priority_map)
        if not sel_vhv_n and has_business_trip:
            sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', 
                                             balance_shifts, last_days_mode, is_training_day, 
                                             allow_overtime=True, overtime_priority_map=overtime_priority_map)

        if not sel_vhv_n and allow_tk_substitute_vhv and sel_tk_n:
            avail_tk_sub_n = [s for s in avail_tk_n if s != sel_tk_n]
            sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', 
                                             balance_shifts, last_days_mode, is_training_day, 
                                             allow_overtime=False, overtime_priority_map=overtime_priority_map)
            if not sel_vhv_n and has_business_trip:
                sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', 
                                                 balance_shifts, last_days_mode, is_training_day, 
                                                 allow_overtime=True, overtime_priority_map=overtime_priority_map)
            if sel_vhv_n: 
                staff_data[sel_vhv_n]['is_substituting_vhv'] = True

        if sel_tk_n and sel_vhv_n:
            update_staff_data(staff_data, sel_tk_n, day, 'night')
            update_staff_data(staff_data, sel_vhv_n, day, 'night')
            
            max_consecutive = 4 if staff_data[sel_tk_n].get('night_shift_goal') == 15 else 3
            if staff_data[sel_tk_n]['consecutive_night'] > max_consecutive: 
                staff_data[sel_tk_n]['consecutive_night'] = max_consecutive
            
            max_consecutive = 4 if staff_data[sel_vhv_n].get('night_shift_goal') == 15 else 3
            if staff_data[sel_vhv_n]['consecutive_night'] > max_consecutive: 
                staff_data[sel_vhv_n]['consecutive_night'] = max_consecutive
            
            note = ('Đào tạo + ' if is_training_day else '') + ('TK thay VHV' if sel_vhv_n in truong_kiep else '')
            schedule.append({
                'Ngày': day, 
                'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                'Ca': 'Đêm (18h-6h)', 
                'Trưởng kiếp': sel_tk_n, 
                'Vận hành viên': sel_vhv_n, 
                'Ghi chú': note
            })

    for staff in all_staff:
        staff_data[staff]['total_credits'] = staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
        
    return schedule, staff_data

# ==================== UI COMPONENTS ====================
def main():
    st.title("🔄 Xếp lịch trực TBA 500kV - Có chế độ Tăng Ca")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📅 Thông tin tháng")
        
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1)
        with col2:
            year = st.selectbox("Năm", range(2023, 2030), index=datetime.now().year-2023)
        
        num_days = calendar.monthrange(year, month)[1]
        st.info(f"**Tháng {month}/{year} có {num_days} ngày**")
        
        st.markdown("---")
        st.header("🎓 Ngày đào tạo")
        training_day = st.slider("Chọn ngày đào tạo", 1, num_days, 15)
        
        st.markdown("---")
        st.header("⚙️ Cài đặt phân công")
        st.session_state.balance_shifts = st.checkbox(
            "Cân bằng ca ngày và ca đêm (chênh lệch ≤ 2)", 
            value=True
        )
        
        st.session_state.tk_substitute_vhv = st.checkbox(
            "Cho phép Trưởng kiếp thay VHV (chỉ khi khó khăn)", 
            value=False,
            help="Chỉ kích hoạt khi thiếu VHV trầm trọng"
        )
        
        st.markdown("---")
        st.header("📋 Quy tắc xếp lịch")
        st.info("""
        **QUY TẮC:**
        1. Mỗi ca: 1 TK + 1 VHV
        2. Tổng công chuẩn: 17 công/người
        3. Không làm 24h liên tục
        4. Tối đa 3 ca đêm liên tiếp
        5. TK thay TK, VHV thay VHV
        
        **ƯU TIÊN TĂNG CA:**
        - VHV: An → Lợi → Cường → Võ
        - TK: Dũng → Việt → Tình → Nam
        """)
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Chọn ngày nghỉ & Công tác", 
        "📊 Xếp lịch & Xem lịch", 
        "📈 Thống kê", 
        "🚨 Điều chỉnh đột xuất"
    ])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Chọn ngày nghỉ & Công tác & Mục tiêu ca đêm")
            col_tk, col_vhv = st.columns(2)
            
            with col_tk:
                st.markdown("### Trưởng kiếp")
                for idx, tk in enumerate(truong_kiep):
                    with st.expander(f"**{tk}**", expanded=False):
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {tk}", 
                            list(range(1, num_days + 1)), 
                            default=st.session_state.day_off.get(tk, []), 
                            key=f"off_tk_{idx}"
                        )
                        if len(days_off) > 5: 
                            st.warning("Quá 5 ngày nghỉ! Đã tự động giới hạn.")
                            days_off = days_off[:5]
                        st.session_state.day_off[tk] = days_off
                        
                        business_days = st.multiselect(
                            f"Ngày công tác - {tk}", 
                            [d for d in range(1, num_days + 1) if d not in days_off and d != training_day], 
                            default=st.session_state.business_trip.get(tk, []), 
                            key=f"bus_tk_{idx}"
                        )
                        st.session_state.business_trip[tk] = business_days
                        
                        night_goal = st.slider(
                            f"Mục tiêu ca đêm - {tk}", 
                            0, 17, 
                            st.session_state.night_shift_goals.get(tk, 0), 
                            key=f"ng_tk_{idx}"
                        )
                        st.session_state.night_shift_goals[tk] = night_goal
            
            with col_vhv:
                st.markdown("### Vận hành viên")
                for idx, vhv in enumerate(van_hanh_vien):
                    with st.expander(f"**{vhv}**", expanded=False):
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {vhv}", 
                            list(range(1, num_days + 1)), 
                            default=st.session_state.day_off.get(vhv, []), 
                            key=f"off_vhv_{idx}"
                        )
                        if len(days_off) > 5: 
                            st.warning("Quá 5 ngày nghỉ! Đã tự động giới hạn.")
                            days_off = days_off[:5]
                        st.session_state.day_off[vhv] = days_off
                        
                        business_days = st.multiselect(
                            f"Ngày công tác - {vhv}", 
                            [d for d in range(1, num_days + 1) if d not in days_off and d != training_day], 
                            default=st.session_state.business_trip.get(vhv, []), 
                            key=f"bus_vhv_{idx}"
                        )
                        st.session_state.business_trip[vhv] = business_days
                        
                        night_goal = st.slider(
                            f"Mục tiêu ca đêm - {vhv}", 
                            0, 17, 
                            st.session_state.night_shift_goals.get(vhv, 0), 
                            key=f"ng_vhv_{idx}"
                        )
                        st.session_state.night_shift_goals[vhv] = night_goal
        
        with col2:
            st.subheader("🏞️ Kiểm tra đường dây")
            col_add, col_del = st.columns(2)
            if col_add.button("➕ Thêm nhóm"):
                st.session_state.line_inspection.append({'tk': None, 'vhv': None, 'day': None})
            if col_del.button("➖ Xóa nhóm") and len(st.session_state.line_inspection) > 0:
                st.session_state.line_inspection.pop()
            
            for i, group in enumerate(st.session_state.line_inspection):
                with st.expander(f"Nhóm {i+1}", expanded=True):
                    used_tk = [g['tk'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['tk']]
                    tk_options = ["(Chọn)"] + [t for t in truong_kiep if t not in used_tk]
                    tk = st.selectbox(f"TK - Nhóm {i+1}", tk_options, key=f"li_tk_{i}")
                    
                    used_vhv = [g['vhv'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['vhv']]
                    vhv_options = ["(Chọn)"] + [v for v in van_hanh_vien if v not in used_vhv]
                    vhv = st.selectbox(f"VHV - Nhóm {i+1}", vhv_options, key=f"li_vhv_{i}")
                    
                    if tk != "(Chọn)" and vhv != "(Chọn)":
                        invalid_days = set(
                            st.session_state.day_off.get(tk, []) + 
                            st.session_state.business_trip.get(tk, []) + 
                            st.session_state.day_off.get(vhv, []) + 
                            st.session_state.business_trip.get(vhv, []) + 
                            [training_day]
                        )
                        used_days = [g['day'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['day']]
                        avail_days = [d for d in range(1, num_days+1) if d not in invalid_days and d not in used_days]
                        day_options = ["(Chọn)"] + avail_days
                        day = st.selectbox(f"Ngày - Nhóm {i+1}", day_options, key=f"li_day_{i}")
                        
                        st.session_state.line_inspection[i] = {
                            'tk': tk if tk != "(Chọn)" else None, 
                            'vhv': vhv if vhv != "(Chọn)" else None, 
                            'day': day if day != "(Chọn)" else None
                        }
    
    with tab2:
        st.subheader("Tạo lịch trực tự động")
        
        if st.button("🎯 Tạo lịch trực", type="primary", use_container_width=True):
            with st.spinner("Đang xếp lịch..."):
                try:
                    schedule, staff_data = generate_advanced_schedule(
                        month, year, training_day, 
                        st.session_state.day_off, 
                        st.session_state.business_trip,
                        [g for g in st.session_state.line_inspection if g['tk'] and g['vhv'] and g['day']],
                        st.session_state.night_shift_goals, 
                        st.session_state.balance_shifts, 
                        st.session_state.tk_substitute_vhv
                    )
                    
                    if schedule:
                        st.session_state.schedule_data = schedule
                        st.session_state.staff_stats = staff_data
                        st.session_state.staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                            schedule, num_days, year, month, 
                            [g for g in st.session_state.line_inspection if g['tk'] and g['vhv'] and g['day']],
                            st.session_state.day_off, 
                            st.session_state.business_trip, 
                            training_day
                        )
                        st.session_state.schedule_created = True
                        st.session_state.original_schedule = schedule.copy()
                        st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
                        st.session_state.original_horizontal_schedule = st.session_state.staff_horizontal_schedule.copy()
                        
                        st.success("✅ Đã tạo lịch thành công!")
                    else:
                        st.error("❌ Không thể tạo lịch! Vui lòng kiểm tra lại các ràng buộc.")
                        
                except Exception as e:
                    st.error(f"❌ Lỗi khi tạo lịch: {str(e)}")
        
        if st.session_state.schedule_created and st.session_state.staff_horizontal_schedule is not None:
            st.subheader("📅 Lịch trực theo nhân viên")
            st.dataframe(
                st.session_state.staff_horizontal_schedule, 
                use_container_width=True, 
                height=600
            )
            
            csv = st.session_state.staff_horizontal_schedule.to_csv(encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải lịch (CSV)",
                data=csv,
                file_name=f"lich_truc_{month}_{year}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with tab3:
        if st.session_state.schedule_created and st.session_state.staff_stats:
            st.subheader("📊 Thống kê chi tiết")
            
            stats_data = []
            for staff, data in st.session_state.staff_stats.items():
                total = data['current_total_credits']
                status = "✅" if total >= 17 else "❌"
                if total > 17: 
                    status = "🔥 Tăng ca"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': data['role'] + (' (Thay VHV)' if data.get('is_substituting_vhv') else ''),
                    'Tổng công': total,
                    'Trạng thái': status,
                    'Số lần tăng ca': data.get('overtime_count', 0),
                    'Đã trực': data['total_shifts'],
                    'Ca ngày': data['day_shifts'],
                    'Ca đêm': data['night_shifts'],
                    'Đào tạo': data['training_credits'],
                    'Kiểm tra': data['line_inspection_credits'],
                    'Công tác': data['business_credits']
                })
            
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(stats_df, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Tổng nhân viên", len(all_staff))
            with col2:
                st.metric("Trưởng kíp", len(truong_kiep))
            with col3:
                st.metric("Vận hành viên", len(van_hanh_vien))
            
            st.info("🔥 **Lưu ý**: 'Tăng ca' xuất hiện khi nhân viên phải trực thay người đi công tác.")
    
    with tab4:
        st.subheader("🚨 Điều chỉnh lịch khi có công tác đột xuất")
        
        if st.session_state.schedule_created:
            col1, col2 = st.columns(2)
            with col1:
                emergency_staff = st.selectbox(
                    "Chọn nhân viên đi đột xuất", 
                    all_staff,
                    key="emergency_select"
                )
            with col2:
                start_day = st.number_input(
                    "Ngày bắt đầu", 
                    1, num_days, 
                    min(datetime.now().day + 1, num_days),
                    key="start_day"
                )
                end_day = st.number_input(
                    "Ngày kết thúc", 
                    start_day, num_days, 
                    min(start_day + 2, num_days),
                    key="end_day"
                )
            
            if st.button("🔄 Điều chỉnh & Tính tăng ca", type="primary", use_container_width=True):
                st.info("⚠️ Chức năng điều chỉnh đang được phát triển. Vui lòng tạo lịch mới với thông tin cập nhật.")
                st.success(f"Đã ghi nhận {emergency_staff} đi công tác từ ngày {start_day} đến {end_day}")
            
            if st.button("↩️ Khôi phục lịch gốc", use_container_width=True):
                st.session_state.schedule_data = st.session_state.original_schedule.copy()
                st.session_state.staff_stats = {k: v.copy() for k, v in st.session_state.original_stats.items()}
                st.session_state.staff_horizontal_schedule = st.session_state.original_horizontal_schedule.copy()
                st.session_state.adjusted_horizontal_schedule = None
                st.success("✅ Đã khôi phục lịch gốc!")
        else:
            st.info("ℹ️ Vui lòng tạo lịch ở Tab 2 trước.")

if __name__ == "__main__":
    main()
