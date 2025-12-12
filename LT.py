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

# Thứ tự ưu tiên tăng ca (Theo yêu cầu: An, Lợi, Cuộng, Võ - Đồng, Việt, Tình, Nam)
overtime_priority_vhv = ["Trường Hoàng An", "Lê Vũ Yinh Lợi", "Nguyễn Cao Cuộng", "Tân Văn Võ"]
overtime_priority_tk = ["Nguyễn Minh Đồng", "Ngô Quang Việt", "Nguyễn Trọng Tình", "Đặng Nhiệt Nam"] 

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
        'emergency_staff': None,
        'emergency_start_day': None,
        'emergency_end_day': None,
        'emergency_adjustment_made': False
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
        # Ưu tiên người còn thiếu ca đêm so với mục tiêu
        night_diff = night_goal - staff_data['night_shifts']
        return -night_diff # Giá trị càng nhỏ (âm càng lớn) càng ưu tiên
    else:
        # Không có ưu tiên đặc biệt cho ca ngày liên quan đến mục tiêu ca đêm
        return 0

def calculate_shift_balance_score(staff_data, shift_type, balance_shifts):
    """Tính điểm cân bằng ca ngày/đêm - Hạn chế chênh lệch > 2"""
    if not balance_shifts:
        return 0
    day_shifts = staff_data['day_shifts']
    night_shifts = staff_data['night_shifts']
    diff = day_shifts - night_shifts
    if shift_type == 'day':
        # Nếu đang nhiều ca ngày hơn, điểm cao để né ca ngày
        return max(0, diff) 
    else:
        # Nếu đang ít ca ngày hơn (nhiều ca đêm hơn), điểm cao để né ca đêm
        return max(0, -diff) 

def get_max_consecutive_shifts(night_goal, shift_type):
    """Xác định số ca liên tiếp tối đa (3 hoặc 4)"""
    max_consecutive = 3
    if night_goal == 15:
        # 4 ca liên tiếp nếu chọn 15 ca đêm
        max_consecutive = 4
    
    # Trong điều kiện bình thường (không tăng ca/công tác), max_consecutive là 3
    # Khi xếp lịch, nếu có người chọn 15 ca đêm, cho phép 4
    return max_consecutive

def calculate_total_credits(data):
    """Tính tổng công hiện tại: Admin (KT, CT) + Training + Shifts"""
    return data['admin_credits'] + data['training_credit_final'] + data['total_shifts']

def update_staff_data(staff_data, staff, day, shift_type, is_training_day=False):
    """Cập nhật thông tin nhân viên sau khi phân công - ĐÃ SỬA LOGIC NGÀY ĐÀO TẠO"""
    
    # Đếm số công tăng ca hiện tại TRƯỚC khi cập nhật total_shifts
    overtime_before = staff_data[staff].get('overtime_count', 0)
    
    # NGÀY ĐÀO TẠO: Áp dụng logic tính công 17 chuẩn
    if is_training_day:
        if shift_type == 'day':
            # Trực ngày: 17 = 16 trực + 1 KT -> Tăng 1 công trực
            staff_data[staff]['total_shifts'] += 1 
            staff_data[staff]['day_shifts'] += 1
            staff_data[staff]['consecutive_night'] = 0
            staff_data[staff]['consecutive_day'] = staff_data[staff].get('consecutive_day', 0) + 1
            # training_credit_final KHÔNG TĂNG (giữ nguyên = 0)
            
        else: # shift_type == 'night'
            # Trực đêm: 17 = 15 trực + 1 ĐT + 1 KT -> Tăng 1 công trực + 1 công đào tạo
            staff_data[staff]['total_shifts'] += 1 # Tăng 1 công trực đêm
            staff_data[staff]['training_credit_final'] = 1 # Tăng 1 công đào tạo
            staff_data[staff]['night_shifts'] += 1
            staff_data[staff]['consecutive_night'] += 1
            staff_data[staff]['consecutive_day'] = 0
            
    else:
        # Các ngày khác: tính công bình thường
        staff_data[staff]['total_shifts'] += 1
        
        if shift_type == 'day':
            staff_data[staff]['day_shifts'] += 1
            staff_data[staff]['consecutive_night'] = 0
            staff_data[staff]['consecutive_day'] = staff_data[staff].get('consecutive_day', 0) + 1
        else:
            staff_data[staff]['night_shifts'] += 1
            staff_data[staff]['consecutive_night'] += 1
            staff_data[staff]['consecutive_day'] = 0
    
    # Cập nhật tổng công hiện tại
    staff_data[staff]['current_total_credits'] = calculate_total_credits(staff_data[staff])
        
    # Nếu tổng công sau khi cập nhật lớn hơn 17 VÀ KHÔNG PHẢI ca ngày ĐT, thì đây là ca tăng ca
    if staff_data[staff]['current_total_credits'] > 17:
        # Chỉ tăng overtime_count nếu ca này làm vượt 17 công.
        staff_data[staff]['overtime_count'] = staff_data[staff].get('overtime_count', 0) + 1
    
    # Luôn cập nhật thông tin lịch trình
    staff_data[staff]['last_shift'] = shift_type
    staff_data[staff]['last_shift_day'] = day
    staff_data[staff]['day_night_diff'] = staff_data[staff]['day_shifts'] - staff_data[staff]['night_shifts']
    staff_data[staff]['last_assigned_day'] = day


def select_staff_for_role(available_staff, staff_data, day, shift_type, role_type, 
                         balance_shifts=True, is_training_day=False, 
                         allow_overtime=False):
    """Chọn nhân viên phù hợp - ĐÃ SỬA ĐIỀU KIỆN KIỂM TRA TĂNG CA VÀ CÂN BẰNG"""
    if not available_staff:
        return None
    
    # Tính toán số công còn thiếu
    for staff in available_staff:
        data = staff_data[staff]
        current_credits = data['current_total_credits']
        remaining_to_17 = 17 - current_credits
        data['remaining_to_17'] = remaining_to_17

    filtered_staff = []
    for staff in available_staff:
        data = staff_data[staff]
        
        # Kiểm tra vai trò
        if role_type == 'TK' and not data['is_tk']: 
            continue
        if role_type == 'VHV' and not data['is_vhv']: 
            continue
        # TK_AS_VHV: TK thay thế VHV
        if role_type == 'TK_AS_VHV' and not data['is_tk']: 
            continue
        
        # QUAN TRỌNG: Kiểm tra điều kiện tăng ca
        if not allow_overtime and data['current_total_credits'] >= 17:
            # Đã đủ hoặc vượt 17 công, không được chọn khi không cho phép tăng ca
            continue
        
        night_goal = data.get('night_shift_goal', 0)
        max_consecutive = get_max_consecutive_shifts(night_goal, shift_type)
        
        # Kiểm tra ca đêm liên tiếp
        if shift_type == 'night':
            if data['consecutive_night'] >= max_consecutive:
                continue
        
        # Kiểm tra ca ngày liên tiếp (chỉ kiểm tra nếu max_consecutive là 4)
        if shift_type == 'day' and max_consecutive == 4:
            if data.get('consecutive_day', 0) >= 4:
                continue
        
        # Kiểm tra không làm 24h liên tục (trừ ngày đào tạo)
        if not is_training_day and shift_type == 'night' and data['last_shift'] == 'day' and data['last_shift_day'] == day:
            continue
        
        # Kiểm tra cân bằng ca (nếu bật)
        if balance_shifts and not allow_overtime:
            # Hạn chế người có chênh lệch quá lớn (vd: > 2) trong chế độ không tăng ca
            if shift_type == 'day' and (data['day_shifts'] - data['night_shifts'] > 2): 
                continue
            if shift_type == 'night' and (data['night_shifts'] - data['day_shifts'] > 2): 
                continue
        
        filtered_staff.append(staff)
    
    if not filtered_staff:
        return None
    
    # Sắp xếp ưu tiên
    if allow_overtime:
        # Ưu tiên tăng ca: ít tăng ca trước, theo thứ tự ưu tiên TĂNG CA, ít công trước
        filtered_staff.sort(key=lambda x: (
            staff_data[x].get('overtime_count', 0), # 1. Ít tăng ca nhất
            overtime_priority_map.get(x, 999),      # 2. Theo thứ tự ưu tiên tăng ca (0 là ưu tiên nhất)
            staff_data[x]['total_shifts'],          # 3. Ít công trực nhất
            calculate_night_shift_priority(staff_data[x], shift_type), # 4. Cân bằng mục tiêu ca đêm
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts), # 5. Cân bằng ngày/đêm
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']), # 6. Người đã lâu chưa được xếp lịch
            random.random()
        ))
    else:
        # Sắp xếp thông thường: công còn nhiều trước, ít công trước, cân bằng ca đêm
        filtered_staff.sort(key=lambda x: (
            -staff_data[x]['remaining_to_17'],      # 1. Công còn nhiều để đạt 17 (âm giá trị để ưu tiên người còn thiếu)
            staff_data[x]['total_shifts'],          # 2. Ít công trực nhất
            calculate_night_shift_priority(staff_data[x], shift_type), # 3. Cân bằng mục tiêu ca đêm
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts), # 4. Cân bằng ngày/đêm
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']), # 5. Người đã lâu chưa được xếp lịch
            random.random()
        ))
    
    return filtered_staff[0]

def convert_to_staff_horizontal_schedule(schedule_data, num_days, year, month, 
                                        line_inspection_groups, day_off_dict, 
                                        business_trip_dict, training_day):
    """Chuyển lịch trực sang dạng ngang - ĐÃ SỬA LOGIC HIỂN THỊ NGÀY ĐÀO TẠO"""
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
    staff_schedule_df = staff_schedule_df.fillna("-") # Điền "-" trước
    
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
            # Chỉ ghi "KT" nếu chưa bị Nghỉ/CT ghi đè
            if staff_schedule_df.loc[group['tk'], col] == "-":
                staff_schedule_df.loc[group['tk'], col] = "KT"
            if staff_schedule_df.loc[group['vhv'], col] == "-":
                staff_schedule_df.loc[group['vhv'], col] = "KT"
    
    # Điền ca trực vào lịch (Chỉ N hoặc Đ)
    for schedule in schedule_data:
        day = schedule['Ngày']
        shift_type = schedule['Ca']
        col = f"Ngày {day}\n({day_to_weekday[day]})"
        
        tk = schedule['Trưởng kiếp']
        vhv = schedule['Vận hành viên']
        
        # Xác định giá trị hiển thị
        val_tk = "N" if 'Ngày' in shift_type else "Đ"
        val_vhv = "N" if 'Ngày' in shift_type else "Đ"
        
        # Ghi đè chỉ khi là "-" (vì "Nghỉ", "CT", "KT" đã được ghi trước)
        if staff_schedule_df.loc[tk, col] == "-": staff_schedule_df.loc[tk, col] = val_tk
        if staff_schedule_df.loc[vhv, col] == "-": staff_schedule_df.loc[vhv, col] = val_vhv
    
    # Đặc biệt xử lý ngày đào tạo: THÊM (ĐT) cho TẤT CẢ nhân viên có mặt
    training_col = f"Ngày {training_day}\n({day_to_weekday[training_day]})"
    for staff in all_staff:
        current_val = staff_schedule_df.loc[staff, training_col]
        
        # Kiểm tra nếu ngày đó KHÔNG phải là Nghỉ hoặc CT (KT vẫn có thể được thêm (ĐT))
        is_unavailable_for_training = (
            training_day in day_off_dict.get(staff, []) or
            training_day in business_trip_dict.get(staff, [])
        )
        
        if not is_unavailable_for_training:
            if current_val == "-": # Người không trực/KT
                staff_schedule_df.loc[staff, training_col] = "ĐT"
            elif "(ĐT)" not in current_val:
                # Nếu đã trực N/Đ hoặc KT, thêm (ĐT)
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

def initialize_staff_data(month, year, training_day, day_off_dict, business_trip_dict, 
                         line_inspection_groups, night_shift_goals):
    """Khởi tạo dữ liệu nhân viên ban đầu - ĐÃ SỬA LOGIC CÔNG ĐÀO TẠO"""
    line_inspection_dict = {staff: set() for staff in all_staff}
    for group in line_inspection_groups:
        if group['tk'] and group['vhv'] and group['day']:
            line_inspection_dict[group['tk']].add(group['day'])
            line_inspection_dict[group['vhv']].add(group['day'])
            
    staff_data = {}
    for staff in all_staff:
        # training_credits được set = 0 ban đầu, sẽ được tính sau khi xếp lịch
        training_credit_final = 0 
        line_inspection_credits = len(line_inspection_dict.get(staff, set())) * 1
        business_days = len(business_trip_dict.get(staff, []))
        business_credits = business_days * 1
        
        # Admin credits chỉ còn KT và CT
        admin_credits = line_inspection_credits + business_credits
        
        staff_data[staff] = {
            'role': 'TK' if staff in truong_kiep else 'VHV',
            'total_shifts': 0, 'day_shifts': 0, 'night_shifts': 0, 
            'consecutive_night': 0, 'consecutive_day': 0,
            'last_shift': None, 'last_shift_day': None,
            'target_shifts': max(0, 17 - admin_credits), # Số ca trực cần để đạt 17 công (chưa tính công ĐT)
            'night_shift_goal': night_shift_goals.get(staff, 0),
            'unavailable_days': set(day_off_dict.get(staff, []) + business_trip_dict.get(staff, [])),
            'business_trip_days': set(business_trip_dict.get(staff, [])),
            'line_inspection_days': line_inspection_dict.get(staff, set()),
            'day_night_diff': 0, 'last_assigned_day': None,
            'training_credit_final': training_credit_final, # Sẽ được set = 1 nếu không vắng mặt ngày ĐT
            'line_inspection_credits': line_inspection_credits,
            'business_credits': business_credits, 
            'admin_credits': admin_credits, # Chỉ gồm KT và CT
            'current_total_credits': admin_credits, # Tổng công hiện tại (chưa có công ĐT)
            'is_tk': staff in truong_kiep, 
            'is_vhv': staff in van_hanh viên,
            'overtime_count': st.session_state.overtime_counts.get(staff, 0),
        }
        staff_data[staff]['unavailable_days'].update(line_inspection_dict.get(staff, set()))
        
    return staff_data

def rebuild_staff_data_from_schedule(initial_staff_data, original_schedule, rebuild_until_day):
    """Tái tạo dữ liệu nhân viên (stats) dựa trên lịch đã trực (trước ngày công tác)"""
    rebuilt_data = {k: v.copy() for k, v in initial_staff_data.items()}
    
    # Reset stats ca trực và liên tục (chỉ giữ lại admin_credits)
    for staff in all_staff:
        rebuilt_data[staff]['total_shifts'] = 0
        rebuilt_data[staff]['day_shifts'] = 0
        rebuilt_data[staff]['night_shifts'] = 0
        rebuilt_data[staff]['consecutive_night'] = 0
        rebuilt_data[staff]['consecutive_day'] = 0
        rebuilt_data[staff]['last_shift'] = None
        rebuilt_data[staff]['last_shift_day'] = None
        rebuilt_data[staff]['day_night_diff'] = 0
        rebuilt_data[staff]['last_assigned_day'] = None
        rebuilt_data[staff]['training_credit_final'] = 0 # Reset công đào tạo
        rebuilt_data[staff]['current_total_credits'] = rebuilt_data[staff]['admin_credits']
        rebuilt_data[staff]['overtime_count'] = 0 # Đếm lại từ đầu

    # Chạy lại logic update_staff_data cho các ngày đã trực
    schedule_to_rebuild = [s for s in original_schedule if s['Ngày'] < rebuild_until_day]
    
    training_day = st.session_state.training_day
    
    for schedule in schedule_to_rebuild:
        day = schedule['Ngày']
        is_training_day = (day == training_day)
        shift_type = 'day' if 'Ngày' in schedule['Ca'] else 'night'
        sel_tk = schedule['Trưởng kiếp']
        sel_vhv = schedule['Vận hành viên']
        
        update_staff_data(rebuilt_data, sel_tk, day, shift_type, is_training_day)
        update_staff_data(rebuilt_data, sel_vhv, day, shift_type, is_training_day)
    
    return rebuilt_data

# ==================== MAIN SCHEDULING FUNCTIONS ====================
def generate_advanced_schedule(month, year, training_day, day_off_dict, business_trip_dict, 
                              line_inspection_groups, night_shift_goals, balance_shifts=True, 
                              allow_tk_substitute_vhv=False, allow_overtime_global=False,
                              start_day=1, initial_staff_data=None):
    """Tạo lịch trực tự động - Có thể xếp lại từ start_day"""
    num_days = calendar.monthrange(year, month)[1]
    
    # Kiểm tra số ca đêm mục tiêu và giới hạn 15 ca đêm
    total_night_goals = sum(night_shift_goals.values())
    if total_night_goals > num_days:
        st.warning(f"Tổng số ca đêm mong muốn ({total_night_goals}) vượt quá số ca đêm có thể ({num_days})")
    
    night_15_count = sum(1 for goal in night_shift_goals.values() if goal == 15)
    if night_15_count > 1:
        st.error("Chỉ được có tối đa 1 người chọn 15 ca đêm!")
        return [], {}

    # Khởi tạo dữ liệu nhân viên
    if initial_staff_data is None:
        staff_data = initialize_staff_data(month, year, training_day, day_off_dict, 
                                           business_trip_dict, line_inspection_groups, 
                                           night_shift_goals)
        schedule = []
    else:
        # Nếu đã có dữ liệu khởi tạo (cho chế độ điều chỉnh)
        staff_data = initial_staff_data
        # Lấy lịch đã trực trước start_day
        schedule = [s for s in st.session_state.original_schedule if s['Ngày'] < start_day]


    # Xếp lịch từng ngày từ start_day
    for day in range(start_day, num_days + 1):
        is_training_day = (day == training_day)
        
        # Lọc nhân viên available
        # Ngày đào tạo: tất cả đều có thể trực ca ngày 
        available_tk = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
        available_vhv = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
        
        # --- CA NGÀY ---
        allow_overtime_today = allow_overtime_global
        
        # Ngày đào tạo: luôn được chọn (vì ca ngày không tính công đào tạo riêng)
        sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', 
                                      balance_shifts, is_training_day, allow_overtime=allow_overtime_today)  
        sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', 
                                       balance_shifts, is_training_day, allow_overtime=allow_overtime_today)  

        # Thay thế TK->VHV nếu cần (chỉ khi được phép thay thế và VHV thiếu)
        if not sel_vhv and allow_tk_substitute_vhv:
            avail_tk_sub = [s for s in available_tk if s != sel_tk]
            sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', 
                                           balance_shifts, is_training_day, allow_overtime=allow_overtime_today)
            if sel_vhv: 
                staff_data[sel_vhv]['is_substituting_vhv'] = True

        if sel_tk and sel_vhv:
            update_staff_data(staff_data, sel_tk, day, 'day', is_training_day)
            update_staff_data(staff_data, sel_vhv, day, 'day', is_training_day)
            note = ('Đào tạo' if is_training_day else '') + (' + TK thay VHV' if sel_vhv in truong_kiep else '')
            schedule.append({
                'Ngày': day, 
                'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                'Ca': 'Ngày (6h-18h)', 
                'Trưởng kiếp': sel_tk, 
                'Vận hành viên': sel_vhv, 
                'Ghi chú': note.strip().lstrip('+').strip()
            })
        else:
            # Cần cảnh báo nếu không xếp được lịch
            if day != training_day or not allow_overtime_today: # Nếu là ngày đào tạo, không bắt buộc nếu không tăng ca
                st.warning(f"Không thể xếp ca ngày cho ngày {day}. Vui lòng kiểm tra lại ràng buộc.")
            
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
                                        balance_shifts, is_training_day, 
                                        allow_overtime=allow_overtime_today)
        sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', 
                                         balance_shifts, is_training_day, 
                                         allow_overtime=allow_overtime_today)

        # Thay thế TK->VHV cho ca đêm
        if not sel_vhv_n and allow_tk_substitute_vhv:
            avail_tk_sub_n = [s for s in avail_tk_n if s != sel_tk_n]
            sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', 
                                             balance_shifts, is_training_day, 
                                             allow_overtime=allow_overtime_today)
            if sel_vhv_n: 
                staff_data[sel_vhv_n]['is_substituting_vhv'] = True

        if sel_tk_n and sel_vhv_n:
            update_staff_data(staff_data, sel_tk_n, day, 'night', is_training_day)
            update_staff_data(staff_data, sel_vhv_n, day, 'night', is_training_day)
            
            note = ('Đào tạo' if is_training_day else '') + (' + TK thay VHV' if sel_vhv_n in truong_kiep else '')
            schedule.append({
                'Ngày': day, 
                'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                'Ca': 'Đêm (18h-6h)', 
                'Trưởng kiếp': sel_tk_n, 
                'Vận hành viên': sel_vhv_n, 
                'Ghi chú': note.strip().lstrip('+').strip()
            })
        else:
            if day != training_day or not allow_overtime_today:
                st.warning(f"Không thể xếp ca đêm cho ngày {day}. Vui lòng kiểm tra lại ràng buộc.")

    # Giai đoạn cuối: Tính công đào tạo cho người KHÔNG trực trong ngày đào tạo và KHÔNG vắng mặt
    for staff in all_staff:
        data = staff_data[staff]
        
        # Nếu training_credit_final vẫn là 0
        if data['training_credit_final'] == 0:
            is_on_shift = any(s for s in schedule if s['Ngày'] == training_day and (s['Trưởng kiếp'] == staff or s['Vận hành viên'] == staff))
            
            # Nếu không trực vào ngày đào tạo VÀ ngày đó không phải ngày nghỉ/CT
            is_unavailable_for_training = (
                training_day in day_off_dict.get(staff, []) or
                training_day in business_trip_dict.get(staff, [])
            )
            
            if not is_on_shift and not is_unavailable_for_training:
                data['training_credit_final'] = 1
        
        # Cập nhật tổng công cuối cùng (Final Check)
        staff_data[staff]['total_credits'] = calculate_total_credits(staff_data[staff])
        staff_data[staff]['current_total_credits'] = staff_data[staff]['total_credits']
        
        # Cập nhật số lần tăng ca cho session state (dùng cho lần xếp lịch sau)
        st.session_state.overtime_counts[staff] = staff_data[staff].get('overtime_count', 0)
    
    # Cảnh báo nếu có tăng ca trong lịch gốc
    overtime_employees = [staff for staff, data in staff_data.items() 
                        if data['current_total_credits'] > 17]
    if overtime_employees and not allow_overtime_global:
        st.warning(f"⚠️ Có {len(overtime_employees)} nhân viên bị tăng ca: {', '.join(overtime_employees)}. Tổng công > 17. Vui lòng kiểm tra lại các ràng buộc (ngày nghỉ, công tác, kiểm tra đường dây).")
    
    # Cảnh báo nếu có người chưa đủ 17 công
    under_staff = [staff for staff, data in staff_data.items() 
                   if data['current_total_credits'] < 17]
    if under_staff:
        st.error(f"❌ CÔNG CHƯA CÂN BẰNG! Có {len(under_staff)} nhân viên chưa đủ 17 công: {', '.join(under_staff)}")

    return schedule, staff_data

def adjust_schedule_for_emergency(original_schedule, emergency_staff, 
                                 start_day, end_day, day_off_dict, original_business_trip_dict,
                                 line_inspection_groups, night_shift_goals, 
                                 balance_shifts=True, allow_tk_substitute_vhv=False,
                                 month=None, year=None, training_day=None):
    """Điều chỉnh lịch khi có công tác đột xuất - Chỉ xếp lại từ ngày công tác"""
    
    # 1. Khởi tạo lại thông tin tháng
    if month is None: month = st.session_state.month
    if year is None: year = st.session_state.year
    if training_day is None: training_day = st.session_state.training_day
    
    # 2. Tạo bản sao của dữ liệu công tác gốc
    business_trip_copy = {k: v.copy() for k, v in original_business_trip_dict.items()}
    
    # 3. Thêm ngày công tác đột xuất vào bản sao
    emergency_days = list(range(start_day, end_day + 1))
    business_trip_copy[emergency_staff].extend(emergency_days)
    business_trip_copy[emergency_staff] = sorted(list(set(business_trip_copy[emergency_staff])))
    
    # 4. Khởi tạo dữ liệu nhân viên gốc (với CT đột xuất)
    initial_staff_data = initialize_staff_data(month, year, training_day, day_off_dict, 
                                               business_trip_copy, line_inspection_groups, 
                                               night_shift_goals)
    
    # 5. Tái tạo trạng thái nhân viên dựa trên lịch đã trực trước ngày công tác
    rebuilt_staff_data = rebuild_staff_data_from_schedule(
        initial_staff_data, 
        original_schedule, 
        start_day
    )
    
    # 6. Chạy lại thuật toán xếp lịch từ ngày bắt đầu công tác (start_day)
    # *LUÔN CHO PHÉP TĂNG CA* trong chế độ điều chỉnh đột xuất
    new_schedule, new_stats = generate_advanced_schedule(
        month, year, training_day, day_off_dict, business_trip_copy,
        line_inspection_groups, night_shift_goals, balance_shifts, 
        allow_tk_substitute_vhv, allow_overtime_global=True,
        start_day=start_day, initial_staff_data=rebuilt_staff_data
    )
    
    return new_schedule, new_stats

# ==================== UI COMPONENTS ====================
def main():
    st.title("🔄 Xếp lịch trực TBA 500kV")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("📅 Thông tin tháng")
        
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("Tháng", range(1, 13), index=st.session_state.month-1)
        with col2:
            year = st.selectbox("Năm", range(2023, 2030), index=st.session_state.year-2023)
        
        num_days = calendar.monthrange(year, month)[1]
        st.info(f"**Tháng {month}/{year} có {num_days} ngày**")
        
        st.markdown("---")
        st.header("🎓 Ngày đào tạo")
        training_day = st.slider("Chọn ngày đào tạo", 1, num_days, st.session_state.training_day)
        
        st.markdown("---")
        st.header("⚙️ Cài đặt phân công")
        balance_shifts = st.checkbox(
            "Cân bằng ca ngày và ca đêm (chênh lệch ≤ 2)", 
            value=st.session_state.balance_shifts
        )
        
        tk_substitute_vhv = st.checkbox(
            "Cho phép Trưởng kiếp thay VHV (chỉ khi khó khăn)", 
            value=st.session_state.tk_substitute_vhv
        )
        
        st.markdown("---")
        st.header("📋 Quy tắc xếp lịch")
        st.info("""
        **QUY TẮC CHUNG:**
        1. Mỗi ca: 1 TK + 1 VHV
        2. **Tổng công chuẩn: 17 công/người/tháng** (Bắt buộc)
        3. Không làm 24h liên tục (trừ ngày đào tạo)
        4. Tối đa **3 ca đêm liên tiếp** (hoặc **4 ca** nếu có người chọn 15 ca đêm)
        5. Tối đa **4 ca ngày liên tiếp** nếu có người chọn 15 ca đêm
        
        **TÍNH CÔNG NGÀY ĐÀO TẠO (Đã cập nhật theo yêu cầu):**
        - **Trực ngày:** Công trực ngày ĐT tính vào **công trực** (không tính công ĐT riêng)
        - **Trực đêm:** Công trực đêm ĐT tính vào **công trực** + **công ĐT riêng**
        - **Không trực:** Tính **công ĐT riêng**
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
        "📈 Thống kê", 
        "🚨 Điều chỉnh đột xuất"
    ])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Chọn ngày nghỉ & Công tác & Mục tiêu ca đêm")
            col_tk, col_vhv = st.columns(2)
            
            # --- Input Trưởng kiếp ---
            with col_tk:
                st.markdown("### Trưởng kiếp")
                night_15_selected = sum(1 for staff in all_staff 
                                           if st.session_state.night_shift_goals.get(staff, 0) == 15)
                
                for idx, tk in enumerate(truong_kiep):
                    with st.expander(f"**{tk}**", expanded=False):
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {tk}", 
                            list(range(1, num_days + 1)), 
                            default=st.session_state.day_off.get(tk, []), 
                            key=f"off_tk_{idx}_{month}_{year}"
                        )
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
                        
                        # Đã có người khác chọn 15 ca đêm -> giới hạn người này tối đa 14
                        if night_15_selected == 1 and current_goal != 15:
                            max_goal = 14
                            st.info("Đã có người khác chọn 15 ca đêm")
                        elif night_15_selected > 1 and current_goal != 15:
                             max_goal = 14
                        
                        night_goal = st.slider(
                            f"Mục tiêu ca đêm - {tk}", 
                            0, max_goal, 
                            min(current_goal, max_goal), 
                            key=f"ng_tk_{idx}_{month}_{year}"
                        )
                        st.session_state.night_shift_goals[tk] = night_goal

            # --- Input Vận hành viên ---
            with col_vhv:
                st.markdown("### Vận hành viên")
                night_15_selected = sum(1 for staff in all_staff 
                                           if st.session_state.night_shift_goals.get(staff, 0) == 15)
                
                for idx, vhv in enumerate(van_hanh_vien):
                    with st.expander(f"**{vhv}**", expanded=False):
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {vhv}", 
                            list(range(1, num_days + 1)), 
                            default=st.session_state.day_off.get(vhv, []), 
                            key=f"off_vhv_{idx}_{month}_{year}"
                        )
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
                        
                        if night_15_selected == 1 and current_goal != 15:
                            max_goal = 14
                            st.info("Đã có người khác chọn 15 ca đêm")
                        elif night_15_selected > 1 and current_goal != 15:
                             max_goal = 14
                        
                        night_goal = st.slider(
                            f"Mục tiêu ca đêm - {vhv}", 
                            0, max_goal, 
                            min(current_goal, max_goal), 
                            key=f"ng_vhv_{idx}_{month}_{year}"
                        )
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
                            st.session_state.business_trip.get(vhv, [])
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
        
        if st.button("🎯 Tạo/Xếp lại lịch trực", type="primary", use_container_width=True):
            # Reset overtime counts cho chế độ xếp lịch bình thường
            st.session_state.overtime_counts = {staff: 0 for staff in all_staff}
            
            with st.spinner("Đang xếp lịch..."):
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
                            allow_overtime_global=False # Không cho phép tăng ca trong lịch gốc
                        )
                        
                        if schedule and all(data['current_total_credits'] == 17 for data in staff_data.values()):
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
                            # Lưu lịch gốc
                            st.session_state.original_schedule = schedule.copy()
                            st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
                            st.session_state.original_horizontal_schedule = st.session_state.staff_horizontal_schedule.copy()
                            st.session_state.adjusted_horizontal_schedule = None
                            st.session_state.emergency_adjustment_made = False
                            
                            st.success(f"✅ Đã tạo lịch thành công cho tháng {month}/{year}! **Tất cả nhân viên đạt 17 công chuẩn.**")
                            
                        else:
                            # Cảnh báo nếu không đạt 17 công chuẩn (do ràng buộc quá chặt)
                            under_staff = [staff for staff, data in staff_data.items() 
                                           if data['current_total_credits'] < 17]
                            overtime_staff = [staff for staff, data in staff_data.items() 
                                           if data['current_total_credits'] > 17]
                                           
                            if under_staff:
                                st.error(f"❌ Không thể tạo lịch hoàn hảo! Có {len(under_staff)} nhân viên chưa đủ 17 công: {', '.join(under_staff)}. Vui lòng nới lỏng ràng buộc.")
                            elif overtime_staff:
                                st.error(f"❌ Không thể tạo lịch hoàn hảo! Có {len(overtime_staff)} nhân viên bị tăng công: {', '.join(overtime_staff)}. Vui lòng kiểm tra lại ràng buộc.")
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
                status = "✅ 17 công" if total == 17 else "❌ Cần điều chỉnh"
                if total > 17: 
                    status = "🔥 Tăng ca"
                elif total < 17:
                    status = "⚠️ Thiếu công"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': data['role'] + (' (Thay VHV)' if data.get('is_substituting_vhv') else ''),
                    'Tổng công': total,
                    'Trạng thái': status,
                    'Số lần tăng ca': data.get('overtime_count', 0),
                    'Đã trực': data['total_shifts'],
                    'Ca ngày': data['day_shifts'],
                    'Ca đêm': data['night_shifts'],
                    'Công ĐT': data['training_credit_final'],
                    'Kiểm tra': data['line_inspection_credits'],
                    'Công tác': data['business_credits']
                })
            
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(stats_df, use_container_width=True)
            
            st.markdown("### 📋 Tổng hợp ngày đào tạo")
            col1, col2, col3 = st.columns(3)
            
            training_day_staff = {}
            if st.session_state.schedule_data:
                for staff in all_staff:
                    data = st.session_state.staff_stats[staff]
                    
                    # Xác định loại công đào tạo dựa trên logic tính công
                    if data['training_credit_final'] == 1:
                        # Trực đêm ĐT (1 công trực + 1 công ĐT) hoặc Không trực ĐT (chỉ 1 công ĐT)
                        is_night_shift = any(s for s in st.session_state.schedule_data if s['Ngày'] == training_day and 'Đêm' in s['Ca'] and (s['Trưởng kiếp'] == staff or s['Vận hành viên'] == staff))
                        training_day_staff[staff] = "Trực đêm" if is_night_shift else "Không trực"
                    elif training_day in data['line_inspection_days'] and data['training_credit_final'] == 0:
                        # KT ngày ĐT
                        training_day_staff[staff] = "Kiểm tra"
                    elif any(s for s in st.session_state.schedule_data if s['Ngày'] == training_day and 'Ngày' in s['Ca'] and (s['Trưởng kiếp'] == staff or s['Vận hành viên'] == staff)):
                        # Trực ngày ĐT (tính vào công trực)
                        training_day_staff[staff] = "Trực ngày"
                    elif training_day in data['unavailable_days']:
                        training_day_staff[staff] = "Vắng mặt"
                    
            
            with col1:
                st.metric("Trực ca ngày (ĐT)", f"{sum(1 for t in training_day_staff.values() if t == 'Trực ngày')} người")
            with col2:
                st.metric("Trực ca đêm (ĐT)", f"{sum(1 for t in training_day_staff.values() if t == 'Trực đêm')} người")
            with col3:
                st.metric("Không trực (ĐT)", f"{sum(1 for t in training_day_staff.values() if t == 'Không trực')} người")
            
            st.info("""
            **CHÚ THÍCH:**
            - Tổng công: Admin (KT, CT) + Công ĐT + Công Trực
            - ✅ 17 công: Tổng công bằng 17 (theo yêu cầu bắt buộc)
            - 🔥 Tăng ca: Tổng công > 17 (chỉ xảy ra khi có công tác đột xuất hoặc khó khăn)
            - ⚠️ Thiếu công: Tổng công < 17
            """)
        else:
            st.info("ℹ️ Vui lòng tạo lịch ở Tab 2 trước để xem thống kê.")
    
    with tab4:
        st.subheader("🚨 Điều chỉnh lịch khi có công tác đột xuất")
        
        if st.session_state.schedule_created:
            
            # Cập nhật emergency staff và ngày công tác
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
            
            st.session_state.emergency_staff = emergency_staff
            st.session_state.emergency_start_day = start_day
            st.session_state.emergency_end_day = end_day
            
            st.info(f"⚠️ **{emergency_staff}** sẽ đi công tác đột xuất từ **Ngày {start_day}** đến **Ngày {end_day}**")
            st.info("📝 Lịch sẽ được tính lại **từ ngày bắt đầu công tác** cho đến cuối tháng với **tăng ca được phép và luân phiên**.")
            
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button("🔄 Điều chỉnh & Tính tăng ca", type="primary", use_container_width=True):
                    
                    with st.spinner("Đang điều chỉnh lịch..."):
                        try:
                            line_inspection_groups = [g for g in st.session_state.line_inspection 
                                                    if g['tk'] and g['vhv'] and g['day']]
                            
                            new_schedule, new_stats = adjust_schedule_for_emergency(
                                st.session_state.original_schedule,
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
                            st.session_state.emergency_adjustment_made = True
                            
                            st.success(f"✅ Đã điều chỉnh cho {emergency_staff} đi công tác từ ngày {start_day} đến {end_day}")
                            st.success("📊 Các nhân viên khác đã được xếp lịch thay thế (có tính tăng ca).")
                            
                            # Cảnh báo tăng ca
                            overtime_employees = [staff for staff, data in new_stats.items() 
                                                if data['current_total_credits'] > 17]
                            if overtime_employees:
                                st.warning(f"⚠️ Có {len(overtime_employees)} nhân viên bị tăng ca: {', '.join(overtime_employees)}")
                            
                        except Exception as e:
                            st.error(f"❌ Lỗi khi điều chỉnh: {str(e)}")

            with col_act2:
                if st.button("↩️ Khôi phục lịch gốc", use_container_width=True):
                    if st.session_state.original_schedule and st.session_state.emergency_adjustment_made:
                        st.session_state.schedule_data = st.session_state.original_schedule.copy()
                        st.session_state.staff_stats = {k: v.copy() for k, v in st.session_state.original_stats.items()}
                        st.session_state.staff_horizontal_schedule = st.session_state.original_horizontal_schedule.copy()
                        st.session_state.adjusted_horizontal_schedule = None
                        st.session_state.emergency_adjustment_made = False
                        
                        # Reset overtime counts to original (0 for normal scheduling)
                        st.session_state.overtime_counts = {staff: 0 for staff in all_staff}
                        
                        st.success("✅ Đã khôi phục lịch gốc!")
                    elif not st.session_state.original_schedule:
                        st.warning("Không có lịch gốc để khôi phục!")
                    elif not st.session_state.emergency_adjustment_made:
                        st.warning("Chưa có điều chỉnh đột xuất nào được thực hiện.")

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
