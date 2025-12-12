import streamlit as st
import pandas as pd
import calendar
import numpy as np
from datetime import datetime
import random
from collections import defaultdict

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="Xếp lịch trực TBA 500kV",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== INITIALIZATION ====================
# Danh sách nhân viên với thứ tự ưu tiên tăng ca
truong_kiep = [
    "Nguyễn Trọng Tình",
    "Nguyễn Minh Đồng",
    "Ngô Quang Việt",
    "Đặng Nhiệt Nam"
]

van_hanh_vien = [
    "Trường Hoàng An",
    "Lê Vũ Yinh Lợi",
    "Nguyễn Cao Cuộng",
    "Tân Văn Võ"
]

all_staff = truong_kiep + van_hanh_vien

# Thứ tự ưu tiên tăng ca
overtime_priority_tk = ["Nguyễn Minh Đồng", "Ngô Quang Việt", "Nguyễn Trọng Tình", "Đặng Nhiệt Nam"]
overtime_priority_vhv = ["Trường Hoàng An", "Lê Vũ Yinh Lợi", "Nguyễn Cao Cuộng", "Tân Văn Võ"]

# Tạo map ưu tiên
overtime_priority_map = {}
for idx, name in enumerate(overtime_priority_tk):
    overtime_priority_map[name] = idx
for idx, name in enumerate(overtime_priority_vhv):
    overtime_priority_map[name] = idx

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
        'balance_shifts': True,
        'month': datetime.now().month,
        'year': datetime.now().year,
        'training_day': 15,
        'allow_overtime_global': False,
        'overtime_counts': {staff: 0 for staff in all_staff},
        'selection_counts': {staff: 0 for staff in all_staff}  # Đếm số lần được chọn để đảm bảo công bằng
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

def update_staff_data(staff_data, staff, day, shift_type, is_training_day=False):
    """Cập nhật thông tin nhân viên sau khi phân công"""
    # NGÀY ĐÀO TẠO: Tất cả đều có 1 công đào tạo
    if is_training_day:
        if shift_type == 'day':
            # Ca ngày trong ngày đào tạo: không tính công trực thêm, chỉ tính công đào tạo
            staff_data[staff]['consecutive_night'] = 0
            staff_data[staff]['consecutive_day'] = staff_data[staff].get('consecutive_day', 0) + 1
        else:
            # Ca đêm trong ngày đào tạo: tính công trực đêm (công đào tạo đã tính trong admin_credits)
            staff_data[staff]['total_shifts'] += 1
            staff_data[staff]['night_shifts'] += 1
            staff_data[staff]['consecutive_night'] += 1
            staff_data[staff]['consecutive_day'] = 0
            staff_data[staff]['current_total_credits'] = (
                staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
            )
    else:
        # Các ngày khác: tính công bình thường
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
        
        # Cập nhật tổng công hiện tại
        staff_data[staff]['current_total_credits'] = (
            staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
        )
        
        # Nếu tổng công lớn hơn 17, thì đây là ca tăng ca
        if staff_data[staff]['current_total_credits'] > 17:
            staff_data[staff]['overtime_count'] = staff_data[staff].get('overtime_count', 0) + 1
    
    # Luôn cập nhật thông tin lịch trình
    staff_data[staff]['last_shift'] = shift_type
    staff_data[staff]['last_shift_day'] = day
    staff_data[staff]['day_night_diff'] = staff_data[staff]['day_shifts'] - staff_data[staff]['night_shifts']
    staff_data[staff]['last_assigned_day'] = day
    
    # Cập nhật số lần được chọn
    st.session_state.selection_counts[staff] += 1

def select_staff_for_role(available_staff, staff_data, day, shift_type, role_type, 
                         balance_shifts=True, last_days_mode=False, is_training_day=False, 
                         allow_overtime=False):
    """Chọn nhân viên phù hợp - CẢI TIẾN ĐỂ PHÂN BỐ ĐỀU"""
    if not available_staff:
        return None
    
    # Tính toán số công còn thiếu
    for staff in available_staff:
        data = staff_data[staff]
        current_credits = data['current_total_credits']
        remaining_to_17 = 17 - current_credits
        data['remaining_to_17'] = remaining_to_17
        
        # Tính điểm ưu tiên dựa trên số lần được chọn (ít hơn thì ưu tiên cao hơn)
        selection_count = st.session_state.selection_counts.get(staff, 0)
        data['selection_priority'] = -selection_count  # Âm để ít được chọn hơn thì ưu tiên hơn

    filtered_staff = []
    for staff in available_staff:
        data = staff_data[staff]
        
        # Kiểm tra vai trò
        if role_type == 'TK' and not data['is_tk']: 
            continue
        if role_type == 'VHV' and not data['is_vhv']: 
            continue
        if role_type == 'TK_AS_VHV' and not data['is_tk']: 
            continue
        
        # QUAN TRỌNG: Kiểm tra điều kiện tăng ca
        if is_training_day and shift_type == 'day':
            # Ca ngày trong ngày đào tạo: luôn được chọn (không tính công trực)
            pass
        elif not allow_overtime and data['current_total_credits'] >= 17:
            # Đã đủ hoặc vượt 17 công, không được chọn trừ khi cho phép tăng ca
            continue
        
        # Kiểm tra ca đêm liên tiếp
        if shift_type == 'night':
            night_goal = data.get('night_shift_goal', 0)
            max_consecutive_night = 4 if night_goal == 15 else 3
            if data['consecutive_night'] >= max_consecutive_night:
                continue
        
        # Kiểm tra ca ngày liên tiếp (chỉ kiểm tra nếu night_goal = 15)
        if shift_type == 'day':
            night_goal = data.get('night_shift_goal', 0)
            if night_goal == 15 and data.get('consecutive_day', 0) >= 4:
                continue
        
        # Kiểm tra không làm 24h liên tục (trừ ngày đào tạo)
        if not is_training_day and shift_type == 'night' and data['last_shift'] == 'day' and data['last_shift_day'] == day:
            continue
        
        # Kiểm tra cân bằng ca (nếu bật)
        if balance_shifts and not allow_overtime and not (is_training_day and shift_type == 'day'):
            if shift_type == 'day' and (data['day_shifts'] - data['night_shifts'] > 2): 
                continue
            if shift_type == 'night' and (data['night_shifts'] - data['day_shifts'] > 2): 
                continue
        
        filtered_staff.append(staff)
    
    if not filtered_staff:
        return None
    
    # Sắp xếp ưu tiên - CẢI TIẾN ĐỂ PHÂN BỐ ĐỀU
    if allow_overtime:
        # Ưu tiên tăng ca: ít tăng ca trước, theo thứ tự ưu tiên, ít công trước
        filtered_staff.sort(key=lambda x: (
            staff_data[x].get('overtime_count', 0),           # Ít tăng ca trước
            overtime_priority_map.get(x, 999),                # Theo thứ tự ưu tiên
            staff_data[x]['current_total_credits'],          # Ít công trước
            staff_data[x]['selection_priority'],             # Ít được chọn trước
            calculate_night_shift_priority(staff_data[x], shift_type),
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            random.random()
        ))
    else:
        # Sắp xếp thông thường - ƯU TIÊN PHÂN BỐ ĐỀU
        filtered_staff.sort(key=lambda x: (
            staff_data[x]['current_total_credits'],          # Ít công trước (quan trọng nhất)
            staff_data[x]['selection_priority'],             # Ít được chọn trước
            staff_data[x]['total_shifts'],                   # Ít ca đã trực
            calculate_night_shift_priority(staff_data[x], shift_type),
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            random.random()
        ))
    
    # Ưu tiên chọn người có công thấp nhất và ít được chọn nhất
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
    
    # Đánh dấu ngày nghỉ
    for staff, off_days in day_off_dict.items():
        for day in off_days:
            col = f"Ngày {day}\n({day_to_weekday[day]})"
            staff_schedule_df.loc[staff, col] = "Nghỉ"
    
    # Đánh dấu ngày công tác
    for staff, trip_days in business_trip_dict.items():
        for day in trip_days:
            col = f"Ngày {day}\n({day_to_weekday[day]})"
            staff_schedule_df.loc[staff, col] = "CT"
    
    # Đánh dấu ngày kiểm tra đường dây
    for group in line_inspection_groups:
        if group['tk'] and group['vhv'] and group['day']:
            day = group['day']
            col = f"Ngày {day}\n({day_to_weekday[day]})"
            staff_schedule_df.loc[group['tk'], col] = "KT"
            staff_schedule_df.loc[group['vhv'], col] = "KT"
    
    # Điền ca trực vào lịch
    for schedule in schedule_data:
        day = schedule['Ngày']
        shift_type = schedule['Ca']
        col = f"Ngày {day}\n({day_to_weekday[day]})"
        
        tk = schedule['Trưởng kiếp']
        vhv = schedule['Vận hành viên']
        
        # Xác định giá trị hiển thị
        if 'Ngày' in shift_type:
            val_tk = "N"
            val_vhv = "N"
        else:
            val_tk = "Đ"
            val_vhv = "Đ"
        
        # Thêm (ĐT) cho ngày đào tạo
        if day == training_day:
            val_tk = f"{val_tk} (ĐT)" if val_tk in ["N", "Đ"] else val_tk
            val_vhv = f"{val_vhv} (ĐT)" if val_vhv in ["N", "Đ"] else val_vhv
        
        staff_schedule_df.loc[tk, col] = val_tk
        staff_schedule_df.loc[vhv, col] = val_vhv
    
    # Đặc biệt xử lý ngày đào tạo: tất cả nhân viên đều có công đào tạo
    training_col = f"Ngày {training_day}\n({day_to_weekday[training_day]})"
    for staff in all_staff:
        current_val = staff_schedule_df.loc[staff, training_col]
        if pd.isna(current_val) or current_val == "-":
            # Nếu không có hoạt động gì trong ngày đào tạo, ghi "ĐT"
            staff_schedule_df.loc[staff, training_col] = "ĐT"
        elif current_val in ["N", "Đ"]:
            # Nếu đã trực, thêm (ĐT)
            staff_schedule_df.loc[staff, training_col] = f"{current_val} (ĐT)"
    
    staff_schedule_df = staff_schedule_df.fillna("-")
    
    # Thêm cột vai trò
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
                              allow_tk_substitute_vhv=False, allow_overtime_global=False):
    """Tạo lịch trực tự động"""
    num_days = calendar.monthrange(year, month)[1]
    schedule = []
    
    # Reset selection counts khi tạo lịch mới
    st.session_state.selection_counts = {staff: 0 for staff in all_staff}
    
    # Kiểm tra số ca đêm mục tiêu
    total_night_goals = sum(night_shift_goals.values())
    if total_night_goals > 31:
        st.warning(f"Tổng số ca đêm mong muốn ({total_night_goals}) vượt quá số ca đêm có thể ({num_days})")
    
    # Đếm số người chọn 15 ca đêm
    night_15_count = sum(1 for goal in night_shift_goals.values() if goal == 15)
    if night_15_count > 1:
        st.error("Chỉ được có tối đa 1 người chọn 15 ca đêm!")
        return [], {}
    
    line_inspection_dict = {staff: set() for staff in all_staff}
    for group in line_inspection_groups:
        if group['tk'] and group['vhv'] and group['day']:
            line_inspection_dict[group['tk']].add(group['day'])
            line_inspection_dict[group['vhv']].add(group['day'])
    
    # KHỞI TẠO DỮ LIỆU NHÂN VIÊN
    staff_data = {}
    for staff in all_staff:
        # NGÀY ĐÀO TẠO: Tất cả đều có 1 công đào tạo
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
            'overtime_count': st.session_state.overtime_counts.get(staff, 0),
        }
        staff_data[staff]['unavailable_days'].update(line_inspection_dict.get(staff, set()))

    # Xếp lịch từng ngày
    for day in range(1, num_days + 1):
        is_training_day = (day == training_day)
        last_days_mode = (day > num_days - 5)
        
        # Lọc nhân viên available
        if is_training_day:
            # Ngày đào tạo: tất cả đều có thể trực ca ngày
            available_tk = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
            available_vhv = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
        else:
            available_tk = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
            available_vhv = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
        
        # --- CA NGÀY ---
        allow_overtime_today = allow_overtime_global
        
        # Ngày đào tạo: cho phép chọn bất kỳ ai cho ca ngày
        if is_training_day:
            sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', 
                                          balance_shifts, last_days_mode, is_training_day, 
                                          allow_overtime=True)
        else:
            sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', 
                                          balance_shifts, last_days_mode, is_training_day, 
                                          allow_overtime=allow_overtime_today)
            if not sel_tk and not allow_overtime_today:
                # Thử tìm với tăng ca
                sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', 
                                              balance_shifts, last_days_mode, is_training_day, 
                                              allow_overtime=True)
        
        if is_training_day:
            sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', 
                                           balance_shifts, last_days_mode, is_training_day, 
                                           allow_overtime=True)
        else:
            sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', 
                                           balance_shifts, last_days_mode, is_training_day, 
                                           allow_overtime=allow_overtime_today)
            if not sel_vhv and not allow_overtime_today:
                sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', 
                                               balance_shifts, last_days_mode, is_training_day, 
                                               allow_overtime=True)
        
        # Thay thế TK->VHV nếu cần
        if not sel_vhv and allow_tk_substitute_vhv and sel_tk:
            avail_tk_sub = [s for s in available_tk if s != sel_tk]
            if is_training_day:
                sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', 
                                               balance_shifts, last_days_mode, is_training_day, 
                                               allow_overtime=True)
            else:
                sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', 
                                               balance_shifts, last_days_mode, is_training_day, 
                                               allow_overtime=allow_overtime_today)
                if not sel_vhv and not allow_overtime_today:
                    sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', 
                                                   balance_shifts, last_days_mode, is_training_day, 
                                                   allow_overtime=True)
            if sel_vhv: 
                staff_data[sel_vhv]['is_substituting_vhv'] = True

        if sel_tk and sel_vhv:
            update_staff_data(staff_data, sel_tk, day, 'day', is_training_day)
            update_staff_data(staff_data, sel_vhv, day, 'day', is_training_day)
            note = ('Đào tạo + ' if is_training_day else '') + ('TK thay VHV' if sel_vhv in truong_kiep else '')
            schedule.append({
                'Ngày': day, 
                'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                'Ca': 'Ngày (6h-18h)', 
                'Trưởng kiếp': sel_tk, 
                'Vận hành viên': sel_vhv, 
                'Ghi chú': note
            })
        else:
            if day == training_day:
                st.error(f"❌ Không thể xếp ca ngày cho ngày đào tạo {day}.")
            else:
                st.warning(f"Không thể xếp ca ngày cho ngày {day}")

        # --- CA ĐÊM ---
        if is_training_day:
            # Ngày đào tạo: cho phép làm ca đêm sau ca ngày
            avail_tk_n = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
            avail_vhv_n = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
        else:
            # Các ngày khác: không được làm 24h liên tục
            avail_tk_n = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days'] 
                         and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]
            avail_vhv_n = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days'] 
                          and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]

        sel_tk_n = select_staff_for_role(avail_tk_n, staff_data, day, 'night', 'TK', 
                                        balance_shifts, last_days_mode, is_training_day, 
                                        allow_overtime=allow_overtime_today)
        if not sel_tk_n and not allow_overtime_today:
            sel_tk_n = select_staff_for_role(avail_tk_n, staff_data, day, 'night', 'TK', 
                                            balance_shifts, last_days_mode, is_training_day, 
                                            allow_overtime=True)

        sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', 
                                         balance_shifts, last_days_mode, is_training_day, 
                                         allow_overtime=allow_overtime_today)
        if not sel_vhv_n and not allow_overtime_today:
            sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', 
                                             balance_shifts, last_days_mode, is_training_day, 
                                             allow_overtime=True)

        # Thay thế TK->VHV cho ca đêm
        if not sel_vhv_n and allow_tk_substitute_vhv and sel_tk_n:
            avail_tk_sub_n = [s for s in avail_tk_n if s != sel_tk_n]
            sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', 
                                             balance_shifts, last_days_mode, is_training_day, 
                                             allow_overtime=allow_overtime_today)
            if not sel_vhv_n and not allow_overtime_today:
                sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', 
                                                 balance_shifts, last_days_mode, is_training_day, 
                                                 allow_overtime=True)
            if sel_vhv_n: 
                staff_data[sel_vhv_n]['is_substituting_vhv'] = True

        if sel_tk_n and sel_vhv_n:
            update_staff_data(staff_data, sel_tk_n, day, 'night', is_training_day)
            update_staff_data(staff_data, sel_vhv_n, day, 'night', is_training_day)
            
            # Giới hạn ca đêm liên tiếp
            max_consecutive_tk = 4 if staff_data[sel_tk_n].get('night_shift_goal') == 15 else 3
            max_consecutive_vhv = 4 if staff_data[sel_vhv_n].get('night_shift_goal') == 15 else 3
            
            if staff_data[sel_tk_n]['consecutive_night'] > max_consecutive_tk: 
                staff_data[sel_tk_n]['consecutive_night'] = max_consecutive_tk
            if staff_data[sel_vhv_n]['consecutive_night'] > max_consecutive_vhv: 
                staff_data[sel_vhv_n]['consecutive_night'] = max_consecutive_vhv
            
            note = ('Đào tạo + ' if is_training_day else '') + ('TK thay VHV' if sel_vhv_n in truong_kiep else '')
            schedule.append({
                'Ngày': day, 
                'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                'Ca': 'Đêm (18h-6h)', 
                'Trưởng kiếp': sel_tk_n, 
                'Vận hành viên': sel_vhv_n, 
                'Ghi chú': note
            })
        else:
            if day == training_day:
                st.error(f"❌ Không thể xếp ca đêm cho ngày đào tạo {day}")
            else:
                st.warning(f"Không thể xếp ca đêm cho ngày {day}")

    # Tính tổng công cuối cùng
    overtime_employees = []
    under_employees = []
    for staff in all_staff:
        # NGÀY ĐÀO TẠO: admin_credits đã bao gồm 1 công đào tạo
        staff_data[staff]['total_credits'] = staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
        staff_data[staff]['current_total_credits'] = staff_data[staff]['total_credits']
        
        # Kiểm tra tăng ca và thiếu ca
        if staff_data[staff]['current_total_credits'] > 17:
            overtime_employees.append(staff)
        elif staff_data[staff]['current_total_credits'] < 17:
            under_employees.append(staff)
        
        # Cập nhật số lần tăng ca
        st.session_state.overtime_counts[staff] = staff_data[staff].get('overtime_count', 0)
    
    # Thống kê phân bố
    vhv_totals = [staff_data[staff]['current_total_credits'] for staff in van_hanh_vien]
    tk_totals = [staff_data[staff]['current_total_credits'] for staff in truong_kiep]
    
    if not allow_overtime_global:
        if overtime_employees:
            st.warning(f"⚠️ Có {len(overtime_employees)} nhân viên bị tăng ca: {', '.join(overtime_employees)}")
        if under_employees:
            st.warning(f"⚠️ Có {len(under_employees)} nhân viên thiếu công: {', '.join(under_employees)}")
        
        st.info(f"📊 Phân bố công VHV: {vhv_totals} (trung bình: {np.mean(vhv_totals):.1f})")
        st.info(f"📊 Phân bố công TK: {tk_totals} (trung bình: {np.mean(tk_totals):.1f})")
        
    return schedule, staff_data

def adjust_schedule_for_emergency(original_schedule, staff_stats, emergency_staff, 
                                 start_day, end_day, day_off_dict, business_trip_dict,
                                 line_inspection_groups, night_shift_goals, 
                                 balance_shifts=True, allow_tk_substitute_vhv=False,
                                 month=None, year=None, training_day=None):
    """Điều chỉnh lịch khi có công tác đột xuất"""
    if month is None:
        month = st.session_state.month
    if year is None:
        year = st.session_state.year
    if training_day is None:
        training_day = st.session_state.training_day
    
    # Tạo bản sao của dữ liệu gốc
    business_trip_copy = {k: v.copy() for k, v in business_trip_dict.items()}
    
    # Thêm ngày công tác đột xuất
    business_trip_copy[emergency_staff].extend(range(start_day, end_day + 1))
    business_trip_copy[emergency_staff] = sorted(list(set(business_trip_copy[emergency_staff])))
    
    # Tạo lại toàn bộ lịch với thông tin mới (cho phép tăng ca)
    new_schedule, new_stats = generate_advanced_schedule(
        month, year, training_day, day_off_dict, business_trip_copy,
        line_inspection_groups, night_shift_goals, balance_shifts, 
        allow_tk_substitute_vhv, allow_overtime_global=True
    )
    
    return new_schedule, new_stats

# ==================== UI COMPONENTS ====================
def main():
    st.title("🔄 Xếp lịch trực TBA 500kV - Phân bố đồng đều")
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
        balance_shifts = st.checkbox(
            "Cân bằng ca ngày và ca đêm (chênh lệch ≤ 2)", 
            value=True
        )
        
        tk_substitute_vhv = st.checkbox(
            "Cho phép Trưởng kiếp thay VHV (chỉ khi khó khăn)", 
            value=False
        )
        
        st.markdown("---")
        st.header("📋 Quy tắc xếp lịch mới")
        st.info("""
        **CẢI TIẾN PHÂN BỐ ĐỀU:**
        1. Ưu tiên người có tổng công thấp nhất hiện tại
        2. Ưu tiên người ít được chọn nhất trong tháng
        3. Ưu tiên người ít ca đã trực nhất
        4. Đảm bảo chênh lệch công ≤ 1 giữa các nhân viên cùng vai trò
        
        **QUY TẮC CHUNG:**
        1. Mỗi ca: 1 TK + 1 VHV
        2. Tổng công chuẩn: 17 công/người/tháng
        3. Không làm 24h liên tục (trừ ngày đào tạo)
        4. Tối đa 3 ca đêm liên tiếp (4 ca nếu chọn 15 ca đêm)
        
        **ƯU TIÊN TĂNG CA:**
        - VHV: An, Lợi, Cuộng, Võ
        - TK: Đồng, Việt, Tình, Nam
        """)
    
    # Lưu vào session state
    st.session_state.month = month
    st.session_state.year = year
    st.session_state.training_day = training_day
    st.session_state.balance_shifts = balance_shifts
    st.session_state.tk_substitute_vhv = tk_substitute_vhv
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Chọn ngày nghỉ & Công tác", 
        "📊 Xếp lịch & Xem lịch", 
        "📈 Thống kê chi tiết", 
        "🚨 Điều chỉnh đột xuất"
    ])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Chọn ngày nghỉ & Công tác & Mục tiêu ca đêm")
            col_tk, col_vhv = st.columns(2)
            
            with col_tk:
                st.markdown("### Trưởng kiếp (TK)")
                night_15_selected_tk = False
                for idx, tk in enumerate(truong_kiep):
                    with st.expander(f"**{tk}**", expanded=False):
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {tk}", 
                            list(range(1, num_days + 1)), 
                            default=st.session_state.day_off.get(tk, []), 
                            key=f"off_tk_{idx}_{month}_{year}"
                        )
                        if len(days_off) > 5: 
                            st.warning("Quá 5 ngày nghỉ! Đã tự động giới hạn.")
                            days_off = days_off[:5]
                        st.session_state.day_off[tk] = days_off
                        
                        business_days = st.multiselect(
                            f"Ngày công tác - {tk}", 
                            [d for d in range(1, num_days + 1) if d not in days_off and d != training_day], 
                            default=st.session_state.business_trip.get(tk, []), 
                            key=f"bus_tk_{idx}_{month}_{year}"
                        )
                        st.session_state.business_trip[tk] = business_days
                        
                        current_goal = st.session_state.night_shift_goals.get(tk, 0)
                        max_goal = 15
                        
                        night_15_count = sum(1 for staff in all_staff 
                                           if st.session_state.night_shift_goals.get(staff, 0) == 15 
                                           and staff != tk)
                        
                        if night_15_count > 0:
                            max_goal = 14
                            st.info("Đã có người khác chọn 15 ca đêm")
                        
                        night_goal = st.slider(
                            f"Mục tiêu ca đêm - {tk}", 
                            0, max_goal, 
                            min(current_goal, max_goal), 
                            key=f"ng_tk_{idx}_{month}_{year}"
                        )
                        
                        if night_goal == 15:
                            night_15_selected_tk = True
                        
                        st.session_state.night_shift_goals[tk] = night_goal
            
            with col_vhv:
                st.markdown("### Vận hành viên (VHV)")
                night_15_selected_vhv = False
                for idx, vhv in enumerate(van_hanh_vien):
                    with st.expander(f"**{vhv}**", expanded=False):
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {vhv}", 
                            list(range(1, num_days + 1)), 
                            default=st.session_state.day_off.get(vhv, []), 
                            key=f"off_vhv_{idx}_{month}_{year}"
                        )
                        if len(days_off) > 5: 
                            st.warning("Quá 5 ngày nghỉ! Đã tự động giới hạn.")
                            days_off = days_off[:5]
                        st.session_state.day_off[vhv] = days_off
                        
                        business_days = st.multiselect(
                            f"Ngày công tác - {vhv}", 
                            [d for d in range(1, num_days + 1) if d not in days_off and d != training_day], 
                            default=st.session_state.business_trip.get(vhv, []), 
                            key=f"bus_vhv_{idx}_{month}_{year}"
                        )
                        st.session_state.business_trip[vhv] = business_days
                        
                        current_goal = st.session_state.night_shift_goals.get(vhv, 0)
                        max_goal = 15
                        
                        if night_15_selected_tk or night_15_count > 0:
                            max_goal = 14
                            st.info("Đã có người khác chọn 15 ca đêm")
                        
                        night_goal = st.slider(
                            f"Mục tiêu ca đêm - {vhv}", 
                            0, max_goal, 
                            min(current_goal, max_goal), 
                            key=f"ng_vhv_{idx}_{month}_{year}"
                        )
                        
                        if night_goal == 15:
                            night_15_selected_vhv = True
                        
                        st.session_state.night_shift_goals[vhv] = night_goal
        
        with col2:
            st.subheader("🏞️ Kiểm tra đường dây")
            col_add, col_del = st.columns(2)
            if col_add.button("➕ Thêm nhóm", key="add_group"):
                st.session_state.line_inspection.append({'tk': None, 'vhv': None, 'day': None})
            if col_del.button("➖ Xóa nhóm", key="del_group") and len(st.session_state.line_inspection) > 0:
                st.session_state.line_inspection.pop()
            
            for i, group in enumerate(st.session_state.line_inspection):
                with st.expander(f"Nhóm {i+1}", expanded=True):
                    used_tk = [g['tk'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['tk']]
                    tk_options = ["(Chọn)"] + [t for t in truong_kiep if t not in used_tk]
                    tk_index = 0
                    if group['tk'] and group['tk'] in tk_options:
                        tk_index = tk_options.index(group['tk'])
                    tk = st.selectbox(f"TK - Nhóm {i+1}", tk_options, index=tk_index, key=f"li_tk_{i}")
                    
                    used_vhv = [g['vhv'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['vhv']]
                    vhv_options = ["(Chọn)"] + [v for v in van_hanh_vien if v not in used_vhv]
                    vhv_index = 0
                    if group['vhv'] and group['vhv'] in vhv_options:
                        vhv_index = vhv_options.index(group['vhv'])
                    vhv = st.selectbox(f"VHV - Nhóm {i+1}", vhv_options, index=vhv_index, key=f"li_vhv_{i}")
                    
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
                        day_index = 0
                        if group['day'] and group['day'] in day_options:
                            day_index = day_options.index(group['day'])
                        day = st.selectbox(f"Ngày - Nhóm {i+1}", day_options, index=day_index, key=f"li_day_{i}")
                        
                        st.session_state.line_inspection[i] = {
                            'tk': tk if tk != "(Chọn)" else None, 
                            'vhv': vhv if vhv != "(Chọn)" else None, 
                            'day': day if day != "(Chọn)" else None
                        }
    
    with tab2:
        st.subheader("Tạo lịch trực tự động")
        
        col_create, col_info = st.columns([3, 1])
        with col_create:
            if st.button("🎯 Tạo/Xếp lại lịch trực", type="primary", use_container_width=True):
                with st.spinner("Đang xếp lịch với thuật toán phân bố đồng đều..."):
                    try:
                        line_inspection_groups = [g for g in st.session_state.line_inspection 
                                                if g['tk'] and g['vhv'] and g['day']]
                        
                        night_15_count = sum(1 for goal in st.session_state.night_shift_goals.values() 
                                           if goal == 15)
                        if night_15_count > 1:
                            st.error("❌ Chỉ được có tối đa 1 người chọn 15 ca đêm!")
                        else:
                            schedule, staff_data = generate_advanced_schedule(
                                month, year, training_day, 
                                st.session_state.day_off, 
                                st.session_state.business_trip,
                                line_inspection_groups,
                                st.session_state.night_shift_goals, 
                                balance_shifts, 
                                tk_substitute_vhv,
                                allow_overtime_global=False
                            )
                            
                            if schedule:
                                st.session_state.schedule_data = schedule
                                st.session_state.staff_stats = staff_data
                                st.session_state.staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                                    schedule, num_days, year, month, 
                                    line_inspection_groups,
                                    st.session_state.day_off, 
                                    st.session_state.business_trip, 
                                    training_day
                                )
                                st.session_state.schedule_created = True
                                st.session_state.original_schedule = schedule.copy()
                                st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
                                st.session_state.original_horizontal_schedule = st.session_state.staff_horizontal_schedule.copy()
                                
                                st.success(f"✅ Đã tạo lịch thành công cho tháng {month}/{year}!")
                                
                                # Kiểm tra phân bố
                                vhv_totals = [staff_data[staff]['current_total_credits'] for staff in van_hanh_vien]
                                tk_totals = [staff_data[staff]['current_total_credits'] for staff in truong_kiep]
                                
                                vhv_diff = max(vhv_totals) - min(vhv_totals)
                                tk_diff = max(tk_totals) - min(tk_totals)
                                
                                if vhv_diff <= 1 and tk_diff <= 1:
                                    st.success("✅ Phân bố công đồng đều giữa các nhân viên cùng vai trò!")
                                else:
                                    st.warning(f"⚠️ Chênh lệch công: VHV={vhv_diff}, TK={tk_diff}")
                                
                            else:
                                st.error("❌ Không thể tạo lịch! Vui lòng kiểm tra lại các ràng buộc.")
                                
                    except Exception as e:
                        st.error(f"❌ Lỗi khi tạo lịch: {str(e)}")
        
        with col_info:
            st.info("""
            **THUẬT TOÁN MỚI:**
            - Ưu tiên người ít công nhất
            - Ưu tiên người ít được chọn nhất
            - Đảm bảo công bằng giữa các nhân viên
            """)
        
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
                status = "✅" if total == 17 else "❌"
                if total > 17: 
                    status = "🔥 Tăng ca"
                elif total < 17:
                    status = "⚠️ Thiếu"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': data['role'] + (' (Thay VHV)' if data.get('is_substituting_vhv') else ''),
                    'Tổng công': total,
                    'Trạng thái': status,
                    'Số lần tăng ca': data.get('overtime_count', 0),
                    'Số lần được chọn': st.session_state.selection_counts.get(staff, 0),
                    'Đã trực': data['total_shifts'],
                    'Ca ngày': data['day_shifts'],
                    'Ca đêm': data['night_shifts'],
                    'Đào tạo': data['training_credits'],
                    'Kiểm tra': data['line_inspection_credits'],
                    'Công tác': data['business_credits']
                })
            
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(stats_df, use_container_width=True)
            
            # Phân tích phân bố
            st.markdown("### 📊 Phân tích phân bố công")
            col1, col2 = st.columns(2)
            
            with col1:
                vhv_data = [(staff, st.session_state.staff_stats[staff]['current_total_credits']) 
                           for staff in van_hanh_vien]
                vhv_df = pd.DataFrame(vhv_data, columns=['Vận hành viên', 'Tổng công'])
                st.write("**Vận hành viên (VHV):**")
                st.dataframe(vhv_df, use_container_width=True)
                
                vhv_totals = [total for _, total in vhv_data]
                if vhv_totals:
                    st.metric("Chênh lệch VHV", f"{max(vhv_totals) - min(vhv_totals)} công")
            
            with col2:
                tk_data = [(staff, st.session_state.staff_stats[staff]['current_total_credits']) 
                          for staff in truong_kiep]
                tk_df = pd.DataFrame(tk_data, columns=['Trưởng kiếp', 'Tổng công'])
                st.write("**Trưởng kiếp (TK):**")
                st.dataframe(tk_df, use_container_width=True)
                
                tk_totals = [total for _, total in tk_data]
                if tk_totals:
                    st.metric("Chênh lệch TK", f"{max(tk_totals) - min(tk_totals)} công")
            
            # Đánh giá phân bố
            st.markdown("### 📈 Đánh giá phân bố")
            if vhv_totals and tk_totals:
                vhv_balanced = max(vhv_totals) - min(vhv_totals) <= 1
                tk_balanced = max(tk_totals) - min(tk_totals) <= 1
                
                if vhv_balanced and tk_balanced:
                    st.success("✅ Phân bố đồng đều! Chênh lệch công ≤ 1 giữa các nhân viên cùng vai trò.")
                else:
                    st.warning(f"⚠️ Cần điều chỉnh: VHV cân bằng={vhv_balanced}, TK cân bằng={tk_balanced}")
                    
                    if not vhv_balanced:
                        st.error("VHV chưa cân bằng! Chênh lệch quá lớn giữa các vận hành viên.")
                    if not tk_balanced:
                        st.error("TK chưa cân bằng! Chênh lệch quá lớn giữa các trưởng kiếp.")
        else:
            st.info("ℹ️ Vui lòng tạo lịch ở Tab 2 trước để xem thống kê.")
    
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
                    "Ngày bắt đầu công tác", 
                    min_value=1, 
                    max_value=num_days, 
                    value=min(datetime.now().day + 1, num_days),
                    key="start_day"
                )
                end_day = st.number_input(
                    "Ngày kết thúc công tác", 
                    min_value=start_day, 
                    max_value=num_days, 
                    value=min(start_day + 2, num_days),
                    key="end_day"
                )
            
            st.info(f"⚠️ {emergency_staff} sẽ đi công tác từ ngày {start_day} đến {end_day}")
            st.info("📝 Lịch sẽ được tính lại từ đầu với tăng ca được phép.")
            
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button("🔄 Điều chỉnh & Tính tăng ca", type="primary", use_container_width=True):
                    with st.spinner("Đang điều chỉnh lịch..."):
                        try:
                            line_inspection_groups = [g for g in st.session_state.line_inspection 
                                                    if g['tk'] and g['vhv'] and g['day']]
                            
                            new_schedule, new_stats = adjust_schedule_for_emergency(
                                st.session_state.original_schedule,
                                st.session_state.original_stats,
                                emergency_staff,
                                start_day,
                                end_day,
                                st.session_state.day_off,
                                st.session_state.business_trip,
                                line_inspection_groups,
                                st.session_state.night_shift_goals,
                                balance_shifts,
                                tk_substitute_vhv,
                                month,
                                year,
                                training_day
                            )
                            
                            st.session_state.schedule_data = new_schedule
                            st.session_state.staff_stats = new_stats
                            st.session_state.staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                                new_schedule, num_days, year, month, 
                                line_inspection_groups,
                                st.session_state.day_off, 
                                st.session_state.business_trip, 
                                training_day
                            )
                            st.session_state.adjusted_horizontal_schedule = st.session_state.staff_horizontal_schedule
                            
                            st.success(f"✅ Đã điều chỉnh cho {emergency_staff} đi công tác từ ngày {start_day} đến {end_day}")
                            st.success("📊 Các nhân viên khác đã được xếp lịch thay thế (có tính tăng ca).")
                            
                        except Exception as e:
                            st.error(f"❌ Lỗi khi điều chỉnh: {str(e)}")

            with col_act2:
                if st.button("↩️ Khôi phục lịch gốc", use_container_width=True):
                    if st.session_state.original_schedule:
                        st.session_state.schedule_data = st.session_state.original_schedule.copy()
                        st.session_state.staff_stats = {k: v.copy() for k, v in st.session_state.original_stats.items()}
                        st.session_state.staff_horizontal_schedule = st.session_state.original_horizontal_schedule.copy()
                        st.session_state.adjusted_horizontal_schedule = None
                        
                        # Xóa ngày công tác đột xuất
                        for staff in all_staff:
                            st.session_state.business_trip[staff] = [
                                d for d in st.session_state.business_trip[staff] 
                                if not (start_day <= d <= end_day) or staff != emergency_staff
                            ]
                        
                        # Reset counts
                        for staff in all_staff:
                            st.session_state.overtime_counts[staff] = 0
                            st.session_state.selection_counts[staff] = 0
                        
                        st.success("✅ Đã khôi phục lịch gốc!")
                    else:
                        st.warning("Không có lịch gốc để khôi phục!")
            
            if st.session_state.adjusted_horizontal_schedule is not None:
                st.markdown("#### 📋 Lịch sau điều chỉnh")
                st.dataframe(
                    st.session_state.adjusted_horizontal_schedule, 
                    use_container_width=True, 
                    height=600
                )
        else:
            st.info("ℹ️ Vui lòng tạo lịch ở Tab 2 trước khi điều chỉnh.")

if __name__ == "__main__":
    main()
