import streamlit as st
import pandas as pd
import calendar
import numpy as np
from datetime import datetime, date
import random
import traceback

try:
    # Tiêu đề ứng dụng
    st.set_page_config(page_title="Xếp lịch trực TBA 500kV", layout="wide")
    st.title("🔄 Xếp lịch trực TBA 500kV - Có chế độ Tăng Ca")
    st.markdown("---")

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

    # Khởi tạo session state
    if 'schedule_created' not in st.session_state:
        st.session_state.schedule_created = False
    if 'schedule_data' not in st.session_state:
        st.session_state.schedule_data = None
    if 'staff_stats' not in st.session_state:
        st.session_state.staff_stats = None
    if 'horizontal_schedule' not in st.session_state:
        st.session_state.horizontal_schedule = None
    if 'staff_horizontal_schedule' not in st.session_state:
        st.session_state.staff_horizontal_schedule = None
    if 'day_off' not in st.session_state:
        st.session_state.day_off = {staff: [] for staff in all_staff}
    if 'business_trip' not in st.session_state:
        st.session_state.business_trip = {staff: [] for staff in all_staff}
    if 'line_inspection' not in st.session_state:
        st.session_state.line_inspection = []
    if 'night_shift_goals' not in st.session_state:
        st.session_state.night_shift_goals = {staff: 0 for staff in all_staff}
    if 'tk_substitute_vhv' not in st.session_state:
        st.session_state.tk_substitute_vhv = False
    if 'emergency_adjustment' not in st.session_state:
        st.session_state.emergency_adjustment = {
            'staff': None,
            'start_day': None,
            'end_day': None,
            'reason': ''
        }
    if 'original_schedule' not in st.session_state:
        st.session_state.original_schedule = None
    if 'original_stats' not in st.session_state:
        st.session_state.original_stats = None
    if 'original_horizontal_schedule' not in st.session_state:
        st.session_state.original_horizontal_schedule = None
    if 'adjusted_horizontal_schedule' not in st.session_state:
        st.session_state.adjusted_horizontal_schedule = None

    # Sidebar cho thông tin nhập
    with st.sidebar:
        st.header("Thông tin tháng")
        
        # Chọn tháng/năm
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1, key="sidebar_month_select")
        with col2:
            year = st.selectbox("Năm", range(2023, 2030), index=datetime.now().year-2023, key="sidebar_year_select")
        
        # Tính số ngày trong tháng
        num_days = calendar.monthrange(year, month)[1]
        st.markdown(f"**Tháng {month}/{year} có {num_days} ngày**")
        st.markdown("---")
        
        st.header("Ngày đào tạo nội bộ")
        training_day = st.slider("Chọn ngày đào tạo", 1, num_days, 15, key="sidebar_training_slider")
        
        st.markdown("---")
        st.header("Cài đặt phân công")
        
        # Thêm tùy chọn cân bằng ca trong sidebar
        balance_shifts_option = st.checkbox("Cân bằng ca ngày và ca đêm (chênh lệch ≤ 2)", value=True, key="sidebar_balance_checkbox")
        
        # Thêm tùy chọn cho phép TK thay thế VHV
        st.session_state.tk_substitute_vhv = st.checkbox(
            "Cho phép Trưởng kiếp thay thế Vận hành viên (chỉ khi khó khăn)", 
            value=False, 
            key="sidebar_tk_substitute_checkbox",
            help="Chỉ kích hoạt khi thiếu VHV trầm trọng, không thể xếp lịch được"
        )
        
        st.markdown("---")
        st.header("Quy tắc xếp lịch")
        st.info("""
        **QUY TẮC CỨNG:**
        1. Mỗi ca: 1 TK + 1 VHV
        2. **Tổng công chuẩn: 17 công/người**
        3. Không làm việc 24h liên tục (trừ ngày ĐT)
        4. Tối đa 3 ca đêm liên tiếp
        5. TK thay TK, VHV thay VHV (trừ khi cấp bách)
        
        **CÔNG TÁC ĐỘT XUẤT (TĂNG CA):**
        - Người đi công tác: tính công đi đường
        - Người ở nhà thay thế: **Được tính tăng ca** (Tổng công > 17)
        - Giữ nguyên lịch cũ, chỉ thay đổi từ ngày công tác
        """)

    # Hàm chuyển đổi lịch sang dạng ngang theo nhân viên
    def convert_to_staff_horizontal_schedule(schedule_data, num_days, year, month, line_inspection_groups, day_off_dict, business_trip_dict, training_day):
        """Chuyển lịch trực sang dạng ngang với cột dọc là nhân viên"""
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
            
            val_tk = "N" if 'Ngày' in shift_type else "Đ"
            val_vhv = "N" if 'Ngày' in shift_type else "Đ"
            
            if day == training_day:
                val_tk += " (ĐT)"
                val_vhv += " (ĐT)"
            
            # Chỉ điền nếu ô chưa có giá trị (ưu tiên giá trị KT, CT, Nghỉ đã điền trước nếu có lỗi logic, nhưng ở đây ta ghi đè nếu là lịch trực)
            # Tuy nhiên, logic đúng là lịch trực được ưu tiên hiển thị nếu đã xếp
            staff_schedule_df.loc[tk, col] = val_tk
            staff_schedule_df.loc[vhv, col] = val_vhv

        # Điền ngày đào tạo cho những người không trực
        training_col = f"Ngày {training_day}\n({day_to_weekday[training_day]})"
        for staff in all_staff:
            if pd.isna(staff_schedule_df.loc[staff, training_col]) or staff_schedule_df.loc[staff, training_col] == '':
                staff_schedule_df.loc[staff, training_col] = "ĐT"
        
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

    # Hàm tạo style cho lịch đã điều chỉnh
    def create_adjusted_schedule_style(original_df, adjusted_df):
        """Tạo style cho lịch đã điều chỉnh, tô màu các ô thay đổi"""
        styled_df = adjusted_df.copy()
        styles = {}
        
        for idx in adjusted_df.index:
            for col in adjusted_df.columns:
                if col == 'Vai trò':
                    continue
                original_val = str(original_df.loc[idx, col]) if idx in original_df.index and col in original_df.columns else ""
                adjusted_val = str(adjusted_df.loc[idx, col])
                
                if original_val != adjusted_val:
                    styles[(idx, col)] = 'background-color: #FFF9C4; color: #333; font-weight: bold' # Vàng
                elif any(x in adjusted_val for x in ['N', 'Đ']):
                    styles[(idx, col)] = 'background-color: #E8F5E9; color: #333' # Xanh
                elif 'KT' in adjusted_val:
                    styles[(idx, col)] = 'background-color: #FFE0B2; color: #333' # Cam
                elif 'CT' in adjusted_val:
                    styles[(idx, col)] = 'background-color: #FFEBEE; color: #333' # Đỏ
                elif 'Nghỉ' in adjusted_val:
                    styles[(idx, col)] = 'background-color: #F5F5F5; color: #999' # Xám
                elif 'ĐT' in adjusted_val:
                    styles[(idx, col)] = 'background-color: #F3E5F5; color: #333' # Tím
        
        def apply_styles(df):
            style_df = pd.DataFrame('', index=df.index, columns=df.columns)
            for (idx, col), style in styles.items():
                if idx in style_df.index and col in style_df.columns:
                    style_df.loc[idx, col] = style
            return style_df
        
        return styled_df.style.apply(apply_styles, axis=None)

    # =================================================================================
    # LOGIC CỐT LÕI ĐƯỢC CHỈNH SỬA
    # =================================================================================

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
        else:  # night
            return max(0, -diff)

    def update_staff_data(staff_data, staff, day, shift_type):
        """Cập nhật thông tin nhân viên sau khi phân công"""
        if shift_type == 'day':
            staff_data[staff]['total_shifts'] += 1
            staff_data[staff]['day_shifts'] += 1
            staff_data[staff]['consecutive_night'] = 0
        else:  # night
            staff_data[staff]['total_shifts'] += 1
            staff_data[staff]['night_shifts'] += 1
            staff_data[staff]['consecutive_night'] += 1
        
        staff_data[staff]['last_shift'] = shift_type
        staff_data[staff]['last_shift_day'] = day
        staff_data[staff]['day_night_diff'] = staff_data[staff]['day_shifts'] - staff_data[staff]['night_shifts']
        staff_data[staff]['last_assigned_day'] = day
        
        # Cập nhật tổng công hiện tại
        staff_data[staff]['current_total_credits'] = (
            staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
        )

    def select_staff_for_role(available_staff, staff_data, day, shift_type, role_type, balance_shifts=True, last_days_mode=False, is_training_day=False, allow_overtime=False):
        """
        Chọn nhân viên phù hợp.
        allow_overtime=True: Cho phép chọn người đã đủ hoặc thừa 17 công (chế độ tăng ca/khẩn cấp).
        allow_overtime=False: Chỉ chọn người chưa đủ 17 công.
        """
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
            if role_type == 'TK' and not data['is_tk']: continue
            if role_type == 'VHV' and not data['is_vhv']: continue
            if role_type == 'TK_AS_VHV' and not data['is_tk']: continue
            
            # QUAN TRỌNG: Kiểm tra giới hạn 17 công
            # Nếu KHÔNG cho phép tăng ca, và người này đã đủ công -> Bỏ qua
            if not allow_overtime and data['remaining_to_17'] <= 0:
                continue
            
            # Kiểm tra ca đêm liên tiếp (tối đa 3)
            if shift_type == 'night' and data['consecutive_night'] >= 3:
                continue
            
            # Kiểm tra không làm 24h liên tục (trừ ngày đào tạo)
            if shift_type == 'night' and not is_training_day and data['last_shift'] == 'day' and data['last_shift_day'] == day:
                continue
            
            # Kiểm tra cân bằng ca (nếu bật) - nới lỏng nếu đang cần gấp (overtime)
            if balance_shifts and not allow_overtime:
                if shift_type == 'day' and (data['day_shifts'] - data['night_shifts'] > 2): continue
                if shift_type == 'night' and (data['night_shifts'] - data['day_shifts'] > 2): continue
            
            filtered_staff.append(staff)
        
        if not filtered_staff:
            return None
        
        # Sắp xếp ưu tiên
        # Priority 1: -remaining_to_17 (Người còn thiếu nhiều công xếp trước. Người âm công (overtime) xếp sau)
        # Vì vậy, khi allow_overtime=True, nó vẫn ưu tiên lấp đầy người chưa đủ công trước.
        filtered_staff.sort(key=lambda x: (
            -staff_data[x]['remaining_to_17'],  # Quan trọng nhất: ưu tiên người thiếu công
            staff_data[x]['total_shifts'],      # Ưu tiên người ít ca
            calculate_night_shift_priority(staff_data[x], shift_type),
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            random.random()
        ))
        
        return filtered_staff[0]

    def adjust_schedule_for_emergency(schedule_data, staff_data, emergency_staff, start_day, end_day, day_off_dict, business_trip_dict, line_inspection_groups, night_shift_goals, balance_shifts=True, allow_tk_substitute_vhv=False):
        """
        Điều chỉnh lịch khi có công tác đột xuất.
        - Giữ nguyên lịch trước ngày start_day.
        - Xếp lại lịch từ start_day trở đi.
        - Người công tác sẽ nghỉ.
        - Những người còn lại sẽ chia nhau làm thay -> TĂNG CA (Overtime).
        """
        num_days = calendar.monthrange(year, month)[1]
        
        # Lưu bản gốc nếu chưa có
        if st.session_state.original_schedule is None:
            st.session_state.original_schedule = schedule_data.copy()
            st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
        
        # Cập nhật ngày công tác đột xuất cho người đi
        business_trip_dict[emergency_staff].extend(range(start_day, end_day + 1))
        
        # Lọc bỏ các ca cũ từ ngày start_day trở đi
        new_schedule = [shift for shift in schedule_data if shift['Ngày'] < start_day]
        
        # Reset thống kê và tính lại từ đầu dựa trên new_schedule (lịch quá khứ)
        for staff in all_staff:
            staff_data[staff]['total_shifts'] = 0
            staff_data[staff]['day_shifts'] = 0
            staff_data[staff]['night_shifts'] = 0
            staff_data[staff]['consecutive_night'] = 0
            staff_data[staff]['last_shift'] = None
            staff_data[staff]['last_shift_day'] = None
        
        # Replay lịch quá khứ
        for shift in new_schedule:
            day = shift['Ngày']
            shift_type = shift['Ca']
            tk = shift['Trưởng kiếp']
            vhv = shift['Vận hành viên']
            update_staff_data(staff_data, tk, day, 'day' if 'Ngày' in shift_type else 'night')
            update_staff_data(staff_data, vhv, day, 'day' if 'Ngày' in shift_type else 'night')
        
        # Cập nhật unavailable_days mới
        for staff in all_staff:
            staff_data[staff]['unavailable_days'] = set(day_off_dict.get(staff, []) + business_trip_dict.get(staff, []))
            staff_data[staff]['business_trip_days'] = set(business_trip_dict.get(staff, []))
            
            # Thêm ngày kiểm tra đường dây
            for group in line_inspection_groups:
                 if group['tk'] == staff or group['vhv'] == staff:
                     if group['day']: staff_data[staff]['unavailable_days'].add(group['day'])

            # Tính lại công hành chính
            training_credits = 1
            line_inspection_credits = len([g for g in line_inspection_groups if g['tk'] == staff or g['vhv'] == staff])
            business_credits = len(staff_data[staff]['business_trip_days'])
            admin_credits = training_credits + line_inspection_credits + business_credits
            
            staff_data[staff]['admin_credits'] = admin_credits
            staff_data[staff]['current_total_credits'] = admin_credits + staff_data[staff]['total_shifts']

        # Xếp lịch mới từ start_day
        for day in range(start_day, num_days + 1):
            if day == training_day: continue # Đã xử lý trong ngày đào tạo mặc định nếu có
            
            is_training_day = (day == training_day)
            last_days_mode = (day > num_days - 5)
            
            # --- CA NGÀY ---
            available_tk = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
            available_vhv = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
            
            # Chọn TK: Thử tìm người chưa đủ công (allow_overtime=False), nếu không có thì tìm người làm thêm (allow_overtime=True)
            sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_tk:
                sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
                
            # Chọn VHV: Tương tự
            sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_vhv:
                sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
            
            # Nếu thiếu VHV, thử dùng TK thay thế
            if not sel_vhv and allow_tk_substitute_vhv and sel_tk:
                avail_tk_sub = [s for s in available_tk if s != sel_tk]
                sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
                if not sel_vhv:
                    sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
                if sel_vhv:
                    staff_data[sel_vhv]['is_substituting_vhv'] = True

            if sel_tk and sel_vhv:
                update_staff_data(staff_data, sel_tk, day, 'day')
                update_staff_data(staff_data, sel_vhv, day, 'day')
                note = 'Điều chỉnh' + ('; TK thay VHV' if sel_vhv in truong_kiep else '')
                new_schedule.append({
                    'Ngày': day, 'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                    'Ca': 'Ngày (6h-18h)', 'Trưởng kiếp': sel_tk, 'Vận hành viên': sel_vhv, 'Ghi chú': note
                })

            # --- CA ĐÊM ---
            # Lọc người khả dụng cho ca đêm (tránh làm 24h liên tục)
            avail_tk_night = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days'] 
                              and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]
            avail_vhv_night = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days'] 
                               and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]

            # Chọn TK Đêm
            sel_tk_n = select_staff_for_role(avail_tk_night, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_tk_n:
                 sel_tk_n = select_staff_for_role(avail_tk_night, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)

            # Chọn VHV Đêm
            sel_vhv_n = select_staff_for_role(avail_vhv_night, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_vhv_n:
                sel_vhv_n = select_staff_for_role(avail_vhv_night, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)

            # Thay thế ban đêm
            if not sel_vhv_n and allow_tk_substitute_vhv and sel_tk_n:
                avail_tk_sub_n = [s for s in avail_tk_night if s != sel_tk_n]
                sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
                if not sel_vhv_n:
                    sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
                if sel_vhv_n:
                    staff_data[sel_vhv_n]['is_substituting_vhv'] = True

            if sel_tk_n and sel_vhv_n:
                update_staff_data(staff_data, sel_tk_n, day, 'night')
                update_staff_data(staff_data, sel_vhv_n, day, 'night')
                # Giới hạn 3 ca đêm
                if staff_data[sel_tk_n]['consecutive_night'] > 3: staff_data[sel_tk_n]['consecutive_night'] = 3
                if staff_data[sel_vhv_n]['consecutive_night'] > 3: staff_data[sel_vhv_n]['consecutive_night'] = 3
                
                note = 'Điều chỉnh' + ('; TK thay VHV' if sel_vhv_n in truong_kiep else '')
                new_schedule.append({
                    'Ngày': day, 'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                    'Ca': 'Đêm (18h-6h)', 'Trưởng kiếp': sel_tk_n, 'Vận hành viên': sel_vhv_n, 'Ghi chú': note
                })
        
        new_schedule.sort(key=lambda x: x['Ngày'])
        return new_schedule, staff_data

    def generate_advanced_schedule(month, year, training_day, day_off_dict, business_trip_dict, line_inspection_groups, night_shift_goals, balance_shifts=True, allow_tk_substitute_vhv=False):
        """Tạo lịch trực tự động - Chế độ chuẩn (Cố gắng đạt 17 công)"""
        num_days = calendar.monthrange(year, month)[1]
        schedule = []
        has_business_trip = any(len(days) > 0 for days in business_trip_dict.values())
        
        # Mapping ngày kiểm tra đường dây
        line_inspection_dict = {staff: set() for staff in all_staff}
        for group in line_inspection_groups:
            if group['tk'] and group['vhv'] and group['day']:
                line_inspection_dict[group['tk']].add(group['day'])
                line_inspection_dict[group['vhv']].add(group['day'])
        
        # Khởi tạo dữ liệu nhân viên
        staff_data = {}
        for staff in all_staff:
            training_credits = 1
            line_inspection_credits = len(line_inspection_dict.get(staff, set())) * 1
            business_days = len(business_trip_dict.get(staff, []))
            business_credits = business_days * 1
            admin_credits = training_credits + line_inspection_credits + business_credits
            required_shift_credits = max(0, 17 - admin_credits)
            
            staff_data[staff] = {
                'role': 'TK' if staff in truong_kiep else 'VHV',
                'total_shifts': 0, 'day_shifts': 0, 'night_shifts': 0, 'consecutive_night': 0,
                'last_shift': None, 'last_shift_day': None,
                'target_shifts': required_shift_credits,
                'night_shift_goal': night_shift_goals.get(staff, 0),
                'unavailable_days': set(day_off_dict.get(staff, []) + business_trip_dict.get(staff, [])),
                'business_trip_days': set(business_trip_dict.get(staff, [])),
                'line_inspection_days': line_inspection_dict.get(staff, set()),
                'day_night_diff': 0, 'last_assigned_day': None,
                'training_credits': training_credits,
                'line_inspection_credits': line_inspection_credits,
                'business_credits': business_credits, 'admin_credits': admin_credits,
                'current_total_credits': admin_credits,
                'is_tk': staff in truong_kiep, 'is_vhv': staff in van_hanh_vien,
            }
            staff_data[staff]['unavailable_days'].update(line_inspection_dict.get(staff, set()))

        # Xếp lịch từng ngày
        working_days = list(range(1, num_days + 1))
        for day in working_days:
            is_training_day = (day == training_day)
            last_days_mode = (day > num_days - 5)
            
            available_tk = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
            available_vhv = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
            
            # --- CA NGÀY ---
            # Thử chế độ chuẩn (không overtime)
            sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            # Nếu không tìm được và có người đi công tác (gây thiếu hụt), cho phép overtime
            if not sel_tk and has_business_trip:
                sel_tk = select_staff_for_role(available_tk, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
            
            sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_vhv and has_business_trip:
                sel_vhv = select_staff_for_role(available_vhv, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
            
            # Thay thế TK->VHV
            if not sel_vhv and allow_tk_substitute_vhv and sel_tk:
                avail_tk_sub = [s for s in available_tk if s != sel_tk]
                sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
                if not sel_vhv and has_business_trip:
                     sel_vhv = select_staff_for_role(avail_tk_sub, staff_data, day, 'day', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
                if sel_vhv: staff_data[sel_vhv]['is_substituting_vhv'] = True

            if sel_tk and sel_vhv:
                update_staff_data(staff_data, sel_tk, day, 'day')
                update_staff_data(staff_data, sel_vhv, day, 'day')
                note = ('Đào tạo + ' if is_training_day else '') + ('TK thay VHV' if sel_vhv in truong_kiep else '')
                schedule.append({
                    'Ngày': day, 'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                    'Ca': 'Ngày (6h-18h)', 'Trưởng kiếp': sel_tk, 'Vận hành viên': sel_vhv, 'Ghi chú': note
                })

            # --- CA ĐÊM ---
            if is_training_day:
                 avail_tk_n = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days']]
                 avail_vhv_n = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days']]
            else:
                 avail_tk_n = [s for s in truong_kiep if day not in staff_data[s]['unavailable_days'] and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]
                 avail_vhv_n = [s for s in van_hanh_vien if day not in staff_data[s]['unavailable_days'] and not (staff_data[s]['last_shift'] == 'day' and staff_data[s]['last_shift_day'] == day)]

            sel_tk_n = select_staff_for_role(avail_tk_n, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_tk_n and has_business_trip:
                sel_tk_n = select_staff_for_role(avail_tk_n, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)

            sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
            if not sel_vhv_n and has_business_trip:
                sel_vhv_n = select_staff_for_role(avail_vhv_n, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)

            if not sel_vhv_n and allow_tk_substitute_vhv and sel_tk_n:
                avail_tk_sub_n = [s for s in avail_tk_n if s != sel_tk_n]
                sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=False)
                if not sel_vhv_n and has_business_trip:
                     sel_vhv_n = select_staff_for_role(avail_tk_sub_n, staff_data, day, 'night', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day, allow_overtime=True)
                if sel_vhv_n: staff_data[sel_vhv_n]['is_substituting_vhv'] = True

            if sel_tk_n and sel_vhv_n:
                update_staff_data(staff_data, sel_tk_n, day, 'night')
                update_staff_data(staff_data, sel_vhv_n, day, 'night')
                if staff_data[sel_tk_n]['consecutive_night'] > 3: staff_data[sel_tk_n]['consecutive_night'] = 3
                if staff_data[sel_vhv_n]['consecutive_night'] > 3: staff_data[sel_vhv_n]['consecutive_night'] = 3
                
                note = ('Đào tạo + ' if is_training_day else '') + ('TK thay VHV' if sel_vhv_n in truong_kiep else '')
                schedule.append({
                    'Ngày': day, 'Thứ': calendar.day_name[calendar.weekday(year, month, day)],
                    'Ca': 'Đêm (18h-6h)', 'Trưởng kiếp': sel_tk_n, 'Vận hành viên': sel_vhv_n, 'Ghi chú': note
                })

        for staff in all_staff:
            staff_data[staff]['total_credits'] = staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
            
        return schedule, staff_data

    # UI Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Chọn ngày nghỉ & Công tác & Kiểm tra & Ca đêm", 
        "📊 Xếp lịch & Xem lịch ngang", 
        "📋 Thống kê", 
        "🚨 Điều chỉnh công tác đột xuất"
    ])

    with tab1:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Chọn ngày nghỉ & Công tác & Số ca đêm mong muốn")
            col_tk, col_vhv = st.columns(2)
            
            with col_tk:
                st.markdown("### Trưởng kiếp")
                for idx, tk in enumerate(truong_kiep):
                    with st.expander(f"**{tk}**", expanded=False):
                        days_off = st.multiselect(f"Ngày nghỉ - {tk}", list(range(1, num_days + 1)), default=st.session_state.day_off.get(tk, []), key=f"off_tk_{idx}_{month}")
                        if len(days_off) > 5: st.error("Quá 5 ngày nghỉ!"); days_off = days_off[:5]
                        st.session_state.day_off[tk] = days_off
                        
                        business_days = st.multiselect(f"Ngày công tác - {tk}", [d for d in range(1, num_days + 1) if d not in days_off and d != training_day], default=st.session_state.business_trip.get(tk, []), key=f"bus_tk_{idx}_{month}")
                        st.session_state.business_trip[tk] = business_days
                        
                        night_goal = st.slider(f"Mục tiêu ca đêm - {tk}", 0, 17, st.session_state.night_shift_goals.get(tk, 0), key=f"ng_tk_{idx}_{month}")
                        st.session_state.night_shift_goals[tk] = night_goal

            with col_vhv:
                st.markdown("### Vận hành viên")
                for idx, vhv in enumerate(van_hanh_vien):
                    with st.expander(f"**{vhv}**", expanded=False):
                        days_off = st.multiselect(f"Ngày nghỉ - {vhv}", list(range(1, num_days + 1)), default=st.session_state.day_off.get(vhv, []), key=f"off_vhv_{idx}_{month}")
                        if len(days_off) > 5: st.error("Quá 5 ngày nghỉ!"); days_off = days_off[:5]
                        st.session_state.day_off[vhv] = days_off
                        
                        business_days = st.multiselect(f"Ngày công tác - {vhv}", [d for d in range(1, num_days + 1) if d not in days_off and d != training_day], default=st.session_state.business_trip.get(vhv, []), key=f"bus_vhv_{idx}_{month}")
                        st.session_state.business_trip[vhv] = business_days
                        
                        night_goal = st.slider(f"Mục tiêu ca đêm - {vhv}", 0, 17, st.session_state.night_shift_goals.get(vhv, 0), key=f"ng_vhv_{idx}_{month}")
                        st.session_state.night_shift_goals[vhv] = night_goal

        with col2:
            st.subheader("🏞️ Kiểm tra đường dây 220kV")
            col_add, col_del = st.columns(2)
            if col_add.button("➕ Thêm nhóm"): st.session_state.line_inspection.append({'tk': None, 'vhv': None, 'day': None})
            if col_del.button("➖ Xóa nhóm") and len(st.session_state.line_inspection) > 0: st.session_state.line_inspection.pop()
            
            for i, group in enumerate(st.session_state.line_inspection):
                with st.expander(f"Nhóm {i+1}", expanded=True):
                    used_tk = [g['tk'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['tk']]
                    tk = st.selectbox(f"TK - Nhóm {i+1}", ["(Chọn)"] + [t for t in truong_kiep if t not in used_tk], index=0 if not group['tk'] else [t for t in truong_kiep if t not in used_tk].index(group['tk'])+1 if group['tk'] in [t for t in truong_kiep if t not in used_tk] else 0, key=f"li_tk_{i}")
                    
                    used_vhv = [g['vhv'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['vhv']]
                    vhv = st.selectbox(f"VHV - Nhóm {i+1}", ["(Chọn)"] + [v for v in van_hanh_vien if v not in used_vhv], index=0 if not group['vhv'] else [v for v in van_hanh_vien if v not in used_vhv].index(group['vhv'])+1 if group['vhv'] in [v for v in van_hanh_vien if v not in used_vhv] else 0, key=f"li_vhv_{i}")
                    
                    if tk != "(Chọn)" and vhv != "(Chọn)":
                        invalid_days = set(st.session_state.day_off.get(tk, []) + st.session_state.business_trip.get(tk, []) + st.session_state.day_off.get(vhv, []) + st.session_state.business_trip.get(vhv, []) + [training_day])
                        used_days = [g['day'] for j, g in enumerate(st.session_state.line_inspection) if j != i and g['day']]
                        avail_days = [d for d in range(1, num_days+1) if d not in invalid_days and d not in used_days]
                        day = st.selectbox(f"Ngày - Nhóm {i+1}", ["(Chọn)"] + avail_days, index=0 if not group['day'] else avail_days.index(group['day'])+1 if group['day'] in avail_days else 0, key=f"li_day_{i}")
                        st.session_state.line_inspection[i] = {'tk': tk if tk != "(Chọn)" else None, 'vhv': vhv if vhv != "(Chọn)" else None, 'day': day if day != "(Chọn)" else None}

    with tab2:
        st.subheader("Tạo lịch trực tự động")
        if st.button("🎯 Tạo lịch trực", type="primary"):
            with st.spinner("Đang xếp lịch..."):
                day_off_dict = st.session_state.day_off
                business_trip_dict = st.session_state.business_trip
                line_inspection_groups = [g for g in st.session_state.line_inspection if g['tk'] and g['vhv'] and g['day']]
                night_shift_goals = st.session_state.night_shift_goals
                
                schedule, staff_data = generate_advanced_schedule(
                    month, year, training_day, day_off_dict, business_trip_dict, 
                    line_inspection_groups, night_shift_goals, balance_shifts_option, st.session_state.tk_substitute_vhv
                )
                
                if schedule:
                    st.session_state.schedule_data = schedule
                    st.session_state.staff_stats = staff_data
                    st.session_state.staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                        schedule, num_days, year, month, line_inspection_groups, day_off_dict, business_trip_dict, training_day
                    )
                    st.session_state.schedule_created = True
                    st.session_state.original_schedule = schedule.copy()
                    st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
                    st.session_state.original_horizontal_schedule = st.session_state.staff_horizontal_schedule.copy()
                    st.success("✅ Đã tạo lịch thành công!")
                else:
                    st.error("❌ Không thể tạo lịch! Vui lòng kiểm tra lại các ràng buộc (quá nhiều ngày nghỉ/công tác).")

        if st.session_state.schedule_created and st.session_state.staff_horizontal_schedule is not None:
            st.dataframe(st.session_state.staff_horizontal_schedule, use_container_width=True, height=600)
            
            csv = st.session_state.staff_horizontal_schedule.to_csv(encoding='utf-8-sig')
            st.download_button("📥 Tải lịch (CSV)", csv, f"lich_truc_{month}_{year}.csv", "text/csv")

    with tab3:
        if st.session_state.schedule_created and st.session_state.staff_stats:
            st.subheader("📈 Thống kê chi tiết")
            stats_data = []
            for staff, data in st.session_state.staff_stats.items():
                total = data['current_total_credits']
                status = "✅" if total >= 17 else "❌"
                if total > 17: status = "🔥 Tăng ca"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': data['role'] + (' (Thay VHV)' if data.get('is_substituting_vhv') else ''),
                    'Tổng công': total,
                    'Trạng thái': status,
                    'Đã trực': data['total_shifts'],
                    'Ca ngày': data['day_shifts'],
                    'Ca đêm': data['night_shifts'],
                    'Đào tạo': data['training_credits'],
                    'Kiểm tra': data['line_inspection_credits'],
                    'Công tác': data['business_credits']
                })
            st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
            
            st.info("🔥 **Lưu ý**: 'Tăng ca' xuất hiện khi nhân viên phải trực thay người đi công tác đột xuất hoặc thiếu nhân sự.")

    with tab4:
        st.subheader("🚨 Điều chỉnh lịch khi có công tác đột xuất")
        if st.session_state.schedule_created:
            col1, col2 = st.columns(2)
            with col1:
                emergency_staff = st.selectbox("Chọn nhân viên đi đột xuất", all_staff)
            with col2:
                start_day = st.number_input("Ngày bắt đầu", 1, num_days, min(datetime.now().day + 1, num_days))
                end_day = st.number_input("Ngày kết thúc", start_day, num_days, min(start_day + 2, num_days))

            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button("🔄 Điều chỉnh & Tính tăng ca", type="primary"):
                    new_schedule, new_stats = adjust_schedule_for_emergency(
                        st.session_state.schedule_data, st.session_state.staff_stats, emergency_staff,
                        start_day, end_day, st.session_state.day_off, st.session_state.business_trip,
                        [g for g in st.session_state.line_inspection if g['tk'] and g['vhv'] and g['day']],
                        st.session_state.night_shift_goals, balance_shifts_option, st.session_state.tk_substitute_vhv
                    )
                    
                    st.session_state.schedule_data = new_schedule
                    st.session_state.staff_stats = new_stats
                    st.session_state.staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                        new_schedule, num_days, year, month, 
                        [g for g in st.session_state.line_inspection if g['tk'] and g['vhv'] and g['day']],
                        st.session_state.day_off, st.session_state.business_trip, training_day
                    )
                    st.session_state.adjusted_horizontal_schedule = st.session_state.staff_horizontal_schedule
                    st.success(f"✅ Đã điều chỉnh cho {emergency_staff}. Các nhân viên khác đã được xếp lịch thay thế (có tính tăng ca).")

            with col_act2:
                if st.button("↩️ Khôi phục lịch gốc"):
                    st.session_state.schedule_data = st.session_state.original_schedule.copy()
                    st.session_state.staff_stats = {k: v.copy() for k, v in st.session_state.original_stats.items()}
                    st.session_state.staff_horizontal_schedule = st.session_state.original_horizontal_schedule.copy()
                    st.session_state.adjusted_horizontal_schedule = None
                    st.success("Đã khôi phục!")
            
            if st.session_state.adjusted_horizontal_schedule is not None:
                st.markdown("#### Lịch sau điều chỉnh (Vàng: Thay đổi)")
                st.dataframe(create_adjusted_schedule_style(st.session_state.original_horizontal_schedule, st.session_state.adjusted_horizontal_schedule), use_container_width=True, height=600)
        else:
            st.info("Vui lòng tạo lịch ở Tab 2 trước.")

except Exception as e:
    st.error(f"Lỗi: {str(e)}")
    st.code(traceback.format_exc())