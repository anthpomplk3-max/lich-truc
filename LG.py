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
    st.title("🔄 Xếp lịch trực TBA 500kV - Giao diện ngang")
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
    if 'original_schedule' not in st.session_state:
        st.session_state.original_schedule = None
    if 'original_stats' not in st.session_state:
        st.session_state.original_stats = None
    if 'original_horizontal_schedule' not in st.session_state:
        st.session_state.original_horizontal_schedule = None
    if 'adjusted_horizontal_schedule' not in st.session_state:
        st.session_state.adjusted_horizontal_schedule = None
    if 'comparison_data' not in st.session_state:
        st.session_state.comparison_data = None
    if 'emergency_staff' not in st.session_state:
        st.session_state.emergency_staff = None
    if 'emergency_start_day' not in st.session_state:
        st.session_state.emergency_start_day = None
    if 'emergency_end_day' not in st.session_state:
        st.session_state.emergency_end_day = None

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
        st.header("Hướng dẫn")
        st.info("""
        **QUY TẮC XẾP LỊCH CỨNG:**
        1. Mỗi ca: 1 Trưởng kiếp + 1 Vận hành viên
        2. **Tổng công: 17 công/người/tháng** (bắt buộc)
        3. Không làm việc 24h liên tục (trừ ngày đào tạo)
        4. **Tối đa 3 ca đêm liên tiếp** (trừ trường hợp đặc biệt)
        5. Ngày đào tạo: vẫn có ca trực bình thường
        6. Người công tác: không tham gia trực (1 công/ngày)
        7. Kiểm tra đường dây: 1 TK + 1 VHV (1 công/ngày)
        8. Cân bằng ca: chênh lệch ca ngày/đêm ≤ 2
        9. **TK chỉ thay TK, VHV chỉ thay VHV**
        10. **Chỉ khi khó khăn: TK có thể thay VHV**
        11. **Khi không có công tác: mọi người đều đủ 17 công**
        
        **TRƯỜNG HỢP ĐẶC BIỆT:**
        - Nếu có Trưởng kíp/VHV chọn 17 ca đêm:
          1. Người đó được phép làm nhiều ca đêm liên tiếp không giới hạn
          2. 13 ca đêm còn lại chia đều cho 3 người cùng vai trò
          3. Vẫn đảm bảo tổng 17 công/người
        
        **ĐIỀU CHỈNH CÔNG TÁC ĐỘT XUẤT:**
        - Giữ nguyên các ngày đã trực
        - Chỉ thay đổi các ngày tiếp theo
        - Đảm bảo các điều kiện trên vẫn được duy trì
        - Công tác đột xuất tính 1 công/ngày
        """)

    # Hàm chuyển đổi lịch sang dạng ngang theo nhân viên
    def convert_to_staff_horizontal_schedule(schedule_data, num_days, year, month, line_inspection_groups, day_off_dict, business_trip_dict, training_day):
        """Chuyển lịch trực sang dạng ngang với cột dọc là nhân viên"""
        # Tạo dictionary ánh xạ ngày -> thứ
        day_to_weekday = {}
        for day in range(1, num_days + 1):
            weekday = calendar.day_name[calendar.weekday(year, month, day)]
            vietnamese_days = {
                'Monday': 'T2', 'Tuesday': 'T3', 'Wednesday': 'T4',
                'Thursday': 'T5', 'Friday': 'T6', 'Saturday': 'T7', 'Sunday': 'CN'
            }
            day_to_weekday[day] = vietnamese_days.get(weekday, weekday)
        
        # Khởi tạo DataFrame với index là nhân viên, columns là các ngày
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
            
            if 'Ngày' in shift_type:
                tk = schedule['Trưởng kiếp']
                vhv = schedule['Vận hành viên']
                
                # Kiểm tra xem có phải ngày đào tạo không
                if day == training_day:
                    staff_schedule_df.loc[tk, col] = "N (ĐT)"
                    staff_schedule_df.loc[vhv, col] = "N (ĐT)"
                else:
                    # Chỉ điền nếu ô chưa có giá trị
                    if pd.isna(staff_schedule_df.loc[tk, col]) or staff_schedule_df.loc[tk, col] == '':
                        staff_schedule_df.loc[tk, col] = "N"
                    if pd.isna(staff_schedule_df.loc[vhv, col]) or staff_schedule_df.loc[vhv, col] == '':
                        staff_schedule_df.loc[vhv, col] = "N"
            elif 'Đêm' in shift_type:
                tk = schedule['Trưởng kiếp']
                vhv = schedule['Vận hành viên']
                
                # Kiểm tra xem có phải ngày đào tạo không
                if day == training_day:
                    staff_schedule_df.loc[tk, col] = "Đ (ĐT)"
                    staff_schedule_df.loc[vhv, col] = "Đ (ĐT)"
                else:
                    # Chỉ điền nếu ô chưa có giá trị
                    if pd.isna(staff_schedule_df.loc[tk, col]) or staff_schedule_df.loc[tk, col] == '':
                        staff_schedule_df.loc[tk, col] = "Đ"
                    if pd.isna(staff_schedule_df.loc[vhv, col]) or staff_schedule_df.loc[vhv, col] == '':
                        staff_schedule_df.loc[vhv, col] = "Đ"
        
        # Điền ngày đào tạo cho những người không trực
        training_col = f"Ngày {training_day}\n({day_to_weekday[training_day]})"
        for staff in all_staff:
            if pd.isna(staff_schedule_df.loc[staff, training_col]) or staff_schedule_df.loc[staff, training_col] == '':
                staff_schedule_df.loc[staff, training_col] = "ĐT"
        
        # Điền ô trống với dấu "-"
        staff_schedule_df = staff_schedule_df.fillna("-")
        
        # Thêm cột vai trò
        role_column = []
        for staff in all_staff:
            if staff in truong_kiep:
                role_column.append("TK")
            else:
                role_column.append("VHV")
        staff_schedule_df.insert(0, 'Vai trò', role_column)
        
        # Sắp xếp theo vai trò và tên
        staff_schedule_df = staff_schedule_df.sort_values('Vai trò', ascending=False)
        
        return staff_schedule_df

    # Hàm tạo style cho lịch đã điều chỉnh
    def create_adjusted_schedule_style(original_df, adjusted_df):
        """Tạo style cho lịch đã điều chỉnh, tô màu các ô thay đổi"""
        # Tạo bản sao để không ảnh hưởng đến dataframe gốc
        styled_df = adjusted_df.copy()
        
        # Tạo dictionary để lưu style
        styles = {}
        
        # So sánh từng ô
        for idx in adjusted_df.index:
            for col in adjusted_df.columns:
                if col == 'Vai trò':
                    continue
                    
                original_val = str(original_df.loc[idx, col]) if idx in original_df.index and col in original_df.columns else ""
                adjusted_val = str(adjusted_df.loc[idx, col])
                
                if original_val != adjusted_val:
                    # Tô màu vàng cho ô thay đổi
                    styles[(idx, col)] = 'background-color: #FFF9C4; color: #333; font-weight: bold'
                elif adjusted_val in ['N', 'Đ', 'N (ĐT)', 'Đ (ĐT)']:
                    # Tô màu xanh nhạt cho ca trực
                    styles[(idx, col)] = 'background-color: #E8F5E9; color: #333'
                elif adjusted_val in ['KT']:
                    # Tô màu cam nhạt cho kiểm tra đường dây
                    styles[(idx, col)] = 'background-color: #FFE0B2; color: #333'
                elif adjusted_val in ['CT']:
                    # Tô màu đỏ nhạt cho công tác
                    styles[(idx, col)] = 'background-color: #FFEBEE; color: #333'
                elif adjusted_val in ['Nghỉ']:
                    # Tô màu xám cho ngày nghỉ
                    styles[(idx, col)] = 'background-color: #F5F5F5; color: #999'
                elif adjusted_val in ['ĐT']:
                    # Tô màu tím nhạt cho đào tạo
                    styles[(idx, col)] = 'background-color: #F3E5F5; color: #333'
        
        # Áp dụng style
        def apply_styles(df):
            style_df = pd.DataFrame('', index=df.index, columns=df.columns)
            for (idx, col), style in styles.items():
                if idx in style_df.index and col in style_df.columns:
                    style_df.loc[idx, col] = style
            return style_df
        
        return styled_df.style.apply(apply_styles, axis=None)

    # Hàm xử lý trường hợp đặc biệt: người chọn 17 ca đêm
    def handle_special_night_shift_case(staff_list, night_shift_goals, staff_data):
        """Xử lý trường hợp đặc biệt khi có người chọn 17 ca đêm"""
        # Kiểm tra xem có ai chọn 17 ca đêm không
        night_17_staff = [staff for staff in staff_list if night_shift_goals.get(staff, 0) == 17]
        
        if night_17_staff:
            # Người chọn 17 ca đêm: không giới hạn ca đêm liên tiếp
            for staff in night_17_staff:
                staff_data[staff]['no_night_limit'] = True
            
            # Tính toán chia đều 13 ca đêm còn lại cho 3 người cùng vai trò
            other_staff = [staff for staff in staff_list if staff not in night_17_staff]
            if len(other_staff) == 3:
                # Tính toán phân chia
                base_nights = 13 // 3
                remainder = 13 % 3
                
                for i, staff in enumerate(other_staff):
                    extra = 1 if i < remainder else 0
                    target_nights = base_nights + extra
                    
                    # Cập nhật mục tiêu ca đêm cho các nhân viên còn lại
                    staff_data[staff]['night_shift_goal'] = target_nights
            
        return staff_data

    # Hàm điều chỉnh lịch khi có công tác đột xuất
    def adjust_schedule_for_emergency(schedule_data, staff_data, emergency_staff, start_day, end_day, day_off_dict, business_trip_dict, line_inspection_groups, night_shift_goals, balance_shifts=True, allow_tk_substitute_vhv=False):
        """Điều chỉnh lịch khi có công tác đột xuất - Giữ nguyên các ngày đã trực"""
        num_days = calendar.monthrange(year, month)[1]
        
        # Lưu lịch gốc trước khi điều chỉnh (nếu chưa có)
        if st.session_state.original_schedule is None:
            st.session_state.original_schedule = schedule_data.copy()
            st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
        
        # Thêm ngày công tác đột xuất
        business_trip_dict[emergency_staff].extend(range(start_day, end_day + 1))
        
        # Xóa các ca từ ngày bắt đầu công tác trở đi
        new_schedule = [shift for shift in schedule_data if shift['Ngày'] < start_day]
        
        # Cập nhật thống kê nhân viên từ các ca đã trực
        for staff in all_staff:
            # Reset thống kê ca trực
            staff_data[staff]['total_shifts'] = 0
            staff_data[staff]['day_shifts'] = 0
            staff_data[staff]['night_shifts'] = 0
            staff_data[staff]['consecutive_night'] = 0
            staff_data[staff]['last_shift'] = None
            staff_data[staff]['last_shift_day'] = None
        
        # Tính lại thống kê từ các ca đã trực
        for shift in new_schedule:
            day = shift['Ngày']
            shift_type = shift['Ca']
            tk = shift['Trưởng kiếp']
            vhv = shift['Vận hành viên']
            
            if 'Ngày' in shift_type:
                staff_data[tk]['total_shifts'] += 1
                staff_data[tk]['day_shifts'] += 1
                staff_data[tk]['last_shift'] = 'day'
                staff_data[tk]['last_shift_day'] = day
                staff_data[tk]['consecutive_night'] = 0
                
                staff_data[vhv]['total_shifts'] += 1
                staff_data[vhv]['day_shifts'] += 1
                staff_data[vhv]['last_shift'] = 'day'
                staff_data[vhv]['last_shift_day'] = day
                staff_data[vhv]['consecutive_night'] = 0
            elif 'Đêm' in shift_type:
                staff_data[tk]['total_shifts'] += 1
                staff_data[tk]['night_shifts'] += 1
                staff_data[tk]['last_shift'] = 'night'
                staff_data[tk]['last_shift_day'] = day
                staff_data[tk]['consecutive_night'] += 1
                
                staff_data[vhv]['total_shifts'] += 1
                staff_data[vhv]['night_shifts'] += 1
                staff_data[vhv]['last_shift'] = 'night'
                staff_data[vhv]['last_shift_day'] = day
                staff_data[vhv]['consecutive_night'] += 1
        
        # Cập nhật unavailable_days cho nhân viên đi công tác đột xuất
        for day in range(start_day, end_day + 1):
            if day not in staff_data[emergency_staff]['unavailable_days']:
                staff_data[emergency_staff]['unavailable_days'].add(day)
            if day not in staff_data[emergency_staff]['business_trip_days']:
                staff_data[emergency_staff]['business_trip_days'].add(day)
        
        # Tính lại target_shifts cho tất cả nhân viên
        for staff in all_staff:
            # Tính lại công hành chính (bao gồm công tác mới)
            training_credits = 1
            line_inspection_credits = len(staff_data[staff]['line_inspection_days'])
            business_credits = len(staff_data[staff]['business_trip_days'])
            admin_credits = training_credits + line_inspection_credits + business_credits
            
            # Công trực ca cần đạt để đủ 17 công
            required_shift_credits = max(0, 17 - admin_credits)
            
            # Trừ đi số ca đã trực
            remaining_shifts_needed = max(0, required_shift_credits - staff_data[staff]['total_shifts'])
            
            staff_data[staff]['target_shifts'] = remaining_shifts_needed
            staff_data[staff]['admin_credits'] = admin_credits
            staff_data[staff]['business_credits'] = business_credits
            staff_data[staff]['current_total_credits'] = admin_credits + staff_data[staff]['total_shifts']
        
        # Xử lý trường hợp đặc biệt: người chọn 17 ca đêm
        staff_data = handle_special_night_shift_case(truong_kiep, night_shift_goals, staff_data)
        staff_data = handle_special_night_shift_case(van_hanh_vien, night_shift_goals, staff_data)
        
        # Xếp lịch cho các ngày từ start_day đến cuối tháng
        for day in range(start_day, num_days + 1):
            # Bỏ qua ngày đào tạo (đã xử lý trong lịch cũ)
            if day == training_day:
                continue
            
            # Xác định xem có phải ngày cuối tháng không (5 ngày cuối)
            last_days_mode = (day > num_days - 5)
            
            # Xử lý ca ngày
            available_tk_day = [tk for tk in truong_kiep 
                              if day not in staff_data[tk]['unavailable_days']]
            available_vhv_day = [vhv for vhv in van_hanh_vien 
                               if day not in staff_data[vhv]['unavailable_days']]
            
            if available_tk_day and available_vhv_day:
                selected_tk = select_staff_for_role(
                    available_tk_day, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode, False
                )
                selected_vhv = select_staff_for_role(
                    available_vhv_day, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode, False
                )
                
                if selected_tk and selected_vhv:
                    # Cập nhật thông tin
                    update_staff_data(staff_data, selected_tk, day, 'day')
                    update_staff_data(staff_data, selected_vhv, day, 'day')
                    
                    weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                    new_schedule.append({
                        'Ngày': day,
                        'Thứ': weekday_name,
                        'Ca': 'Ngày (6h-18h)',
                        'Trưởng kiếp': selected_tk,
                        'Vận hành viên': selected_vhv,
                        'Ghi chú': 'Điều chỉnh'
                    })
            
            # Xử lý ca đêm
            available_tk_night = [tk for tk in truong_kiep 
                                if day not in staff_data[tk]['unavailable_days']
                                and not (staff_data[tk]['last_shift'] == 'day' and staff_data[tk]['last_shift_day'] == day)]
            
            available_vhv_night = [vhv for vhv in van_hanh_vien 
                                 if day not in staff_data[vhv]['unavailable_days']
                                 and not (staff_data[vhv]['last_shift'] == 'day' and staff_data[vhv]['last_shift_day'] == day)]
            
            if available_tk_night and available_vhv_night:
                selected_tk_night = select_staff_for_role(
                    available_tk_night, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode, False
                )
                selected_vhv_night = select_staff_for_role(
                    available_vhv_night, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode, False
                )
                
                if selected_tk_night and selected_vhv_night:
                    # Cập nhật thông tin
                    update_staff_data(staff_data, selected_tk_night, day, 'night')
                    update_staff_data(staff_data, selected_vhv_night, day, 'night')
                    
                    # Kiểm tra quá 3 ca đêm liên tiếp (trừ trường hợp đặc biệt)
                    if not staff_data[selected_tk_night].get('no_night_limit', False):
                        if staff_data[selected_tk_night]['consecutive_night'] > 3:
                            staff_data[selected_tk_night]['consecutive_night'] = 3
                    if not staff_data[selected_vhv_night].get('no_night_limit', False):
                        if staff_data[selected_vhv_night]['consecutive_night'] > 3:
                            staff_data[selected_vhv_night]['consecutive_night'] = 3
                    
                    weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                    new_schedule.append({
                        'Ngày': day,
                        'Thứ': weekday_name,
                        'Ca': 'Đêm (18h-6h)',
                        'Trưởng kiếp': selected_tk_night,
                        'Vận hành viên': selected_vhv_night,
                        'Ghi chú': 'Điều chỉnh'
                    })
        
        # Sắp xếp lại lịch theo ngày
        new_schedule.sort(key=lambda x: x['Ngày'])
        
        return new_schedule, staff_data

    # Thuật toán xếp lịch nâng cao - ĐẢM BẢO 17 CÔNG & PHÂN BIỆT VAI TRÒ
    def generate_advanced_schedule(month, year, training_day, day_off_dict, business_trip_dict, line_inspection_groups, night_shift_goals, balance_shifts=True, allow_tk_substitute_vhv=False):
        """Tạo lịch trực tự động với các ràng buộc nâng cao và cân bằng ca - ĐẢM BẢO 17 CÔNG/NGƯỜI"""
        num_days = calendar.monthrange(year, month)[1]
        schedule = []
        
        # Kiểm tra xem có nhân viên đi công tác không
        has_business_trip = any(len(days) > 0 for days in business_trip_dict.values())
        
        # Tạo dictionary cho ngày kiểm tra đường dây
        line_inspection_dict = {staff: set() for staff in all_staff}
        for group in line_inspection_groups:
            if group['tk'] and group['vhv'] and group['day']:
                tk = group['tk']
                vhv = group['vhv']
                day = group['day']
                line_inspection_dict[tk].add(day)
                line_inspection_dict[vhv].add(day)
        
        # Khởi tạo dữ liệu nhân viên
        staff_data = {}
        for staff in all_staff:
            # Tính các loại công cố định
            training_credits = 1  # Công đào tạo (hành chính)
            line_inspection_days = len(line_inspection_dict.get(staff, set()))
            line_inspection_credits = line_inspection_days * 1  # Mỗi ngày kiểm tra = 1 công
            business_days = len(business_trip_dict.get(staff, []))
            business_credits = business_days * 1  # Mỗi ngày công tác = 1 công
            
            # Tổng công hành chính (không trực)
            admin_credits = training_credits + line_inspection_credits + business_credits
            
            # Công trực ca cần đạt để đủ 17 công
            required_shift_credits = max(0, 17 - admin_credits)
            
            # Mục tiêu ca đêm
            night_shift_goal = night_shift_goals.get(staff, 0)
            
            staff_data[staff] = {
                'role': 'TK' if staff in truong_kiep else 'VHV',
                'total_shifts': 0,  # Tổng số ca đã trực
                'day_shifts': 0,
                'night_shifts': 0,
                'consecutive_night': 0,
                'last_shift': None,
                'last_shift_day': None,
                'target_shifts': required_shift_credits,  # Số ca trực cần để đủ 17 công
                'night_shift_goal': night_shift_goal,  # Số ca đêm mong muốn
                'unavailable_days': set(day_off_dict.get(staff, []) + business_trip_dict.get(staff, [])),
                'business_trip_days': set(business_trip_dict.get(staff, [])),
                'line_inspection_days': line_inspection_dict.get(staff, set()),
                'day_night_diff': 0,
                'last_assigned_day': None,
                'training_credits': training_credits,
                'line_inspection_credits': line_inspection_credits,
                'business_credits': business_credits,
                'admin_credits': admin_credits,
                'current_total_credits': admin_credits,  # Tổng công hiện tại (chưa có ca trực)
                'is_tk': staff in truong_kiep,
                'is_vhv': staff in van_hanh_vien,
                'no_night_limit': False,  # Mặc định có giới hạn ca đêm liên tiếp
            }
            
            # Thêm ngày kiểm tra đường dây vào unavailable_days
            staff_data[staff]['unavailable_days'].update(line_inspection_dict.get(staff, set()))
        
        # Xử lý trường hợp đặc biệt: người chọn 17 ca đêm
        staff_data = handle_special_night_shift_case(truong_kiep, night_shift_goals, staff_data)
        staff_data = handle_special_night_shift_case(van_hanh_vien, night_shift_goals, staff_data)
        
        # Tính tổng công trực có sẵn trong tháng
        # Mỗi ngày có 2 ca (ngày và đêm), mỗi ca có 2 người trực -> tổng công trực tối đa = num_days * 4
        total_available_shift_credits = num_days * 4
        
        # Nếu không có ai đi công tác, PHẢI đảm bảo mọi người đủ 17 công
        if not has_business_trip:
            # Tính tổng công hành chính của tất cả mọi người
            total_admin_credits = sum(data['admin_credits'] for data in staff_data.values())
            total_required_from_shifts = 17 * len(all_staff) - total_admin_credits
            
            if total_required_from_shifts > total_available_shift_credits:
                # KHẨN CẤP: Không đủ ca để đảm bảo 17 công
                st.error(f"❌ KHÔNG ĐỦ CÔNG TRỰC: Cần {total_required_from_shifts} công trực, nhưng chỉ có {total_available_shift_credits} công trực.")
                st.error("Vui lòng giảm số ngày nghỉ, giảm số nhóm kiểm tra đường dây, hoặc bật chế độ TK thay VHV.")
                # Trả về lịch rỗng và dữ liệu nhân viên
                return [], staff_data
        
        # Tạo danh sách ngày cần xếp lịch (bao gồm cả ngày đào tạo)
        working_days = list(range(1, num_days + 1))
        
        # Tạo lịch cho từng ngày làm việc
        for day in working_days:
            # Xác định xem có phải ngày đào tạo không
            is_training_day = (day == training_day)
            
            # Xác định xem có phải ngày cuối tháng không (5 ngày cuối)
            last_days_mode = (day > num_days - 5)
            
            # Xử lý ca ngày trước
            # Tách riêng danh sách TK và VHV có sẵn
            available_tk_day = [tk for tk in truong_kiep 
                              if day not in staff_data[tk]['unavailable_days']]
            available_vhv_day = [vhv for vhv in van_hanh_vien 
                               if day not in staff_data[vhv]['unavailable_days']]
            
            # Chọn TK cho ca ngày (CHỈ CHỌN TỪ DANH SÁCH TK)
            selected_tk = None
            if available_tk_day:
                selected_tk = select_staff_for_role(
                    available_tk_day, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode, is_training_day
                )
            
            # Chọn VHV cho ca ngày (CHỈ CHỌN TỪ DANH SÁCH VHV, TRỪ KHI KHÓ KHĂN)
            selected_vhv = None
            if available_vhv_day:
                selected_vhv = select_staff_for_role(
                    available_vhv_day, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode, is_training_day
                )
            
            # Nếu không chọn được VHV và được phép thay thế
            if not selected_vhv and allow_tk_substitute_vhv and selected_tk:
                # Tìm TK có thể thay thế VHV (không trùng với TK đã chọn)
                available_tk_for_vhv = [tk for tk in available_tk_day if tk != selected_tk]
                if available_tk_for_vhv:
                    selected_vhv = select_staff_for_role(
                        available_tk_for_vhv, staff_data, day, 'day', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day
                    )
                    if selected_vhv:
                        # Đánh dấu đây là TK thay thế VHV
                        staff_data[selected_vhv]['is_substituting_vhv'] = True
            
            if selected_tk and selected_vhv:
                # Cập nhật thông tin
                update_staff_data(staff_data, selected_tk, day, 'day')
                update_staff_data(staff_data, selected_vhv, day, 'day')
                
                weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                ca_type = 'Ngày (6h-18h)'
                ghi_chu = ''
                
                if is_training_day:
                    ghi_chu = 'Đào tạo + Trực ca ngày'
                if selected_vhv in truong_kiep and selected_vhv != selected_tk:
                    ghi_chu = f"{ghi_chu}; TK thay VHV" if ghi_chu else "TK thay VHV"
                
                schedule.append({
                    'Ngày': day,
                    'Thứ': weekday_name,
                    'Ca': ca_type,
                    'Trưởng kiếp': selected_tk,
                    'Vận hành viên': selected_vhv,
                    'Ghi chú': ghi_chu
                })
            
            # Xử lý ca đêm
            # Kiểm tra không làm 24h liên tục (trừ ngày đào tạo)
            if is_training_day:
                # Ngày đào tạo: cho phép làm 24h (tham gia đào tạo + trực ca đêm)
                available_tk_night = [tk for tk in truong_kiep 
                                    if day not in staff_data[tk]['unavailable_days']]
                available_vhv_night = [vhv for vhv in van_hanh_vien 
                                     if day not in staff_data[vhv]['unavailable_days']]
            else:
                # Ngày bình thường: không làm 24h liên tục
                available_tk_night = [tk for tk in truong_kiep 
                                    if day not in staff_data[tk]['unavailable_days']
                                    and not (staff_data[tk]['last_shift'] == 'day' and staff_data[tk]['last_shift_day'] == day)]
                
                available_vhv_night = [vhv for vhv in van_hanh_vien 
                                     if day not in staff_data[vhv]['unavailable_days']
                                     and not (staff_data[vhv]['last_shift'] == 'day' and staff_data[vhv]['last_shift_day'] == day)]
            
            # Chọn TK cho ca đêm (CHỈ CHỌN TỪ DANH SÁCH TK)
            selected_tk_night = None
            if available_tk_night:
                selected_tk_night = select_staff_for_role(
                    available_tk_night, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode, is_training_day
                )
            
            # Chọn VHV cho ca đêm (CHỈ CHỌN TỪ DANH SÁCH VHV, TRỪ KHI KHÓ KHĂN)
            selected_vhv_night = None
            if available_vhv_night:
                selected_vhv_night = select_staff_for_role(
                    available_vhv_night, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode, is_training_day
                )
            
            # Nếu không chọn được VHV và được phép thay thế
            if not selected_vhv_night and allow_tk_substitute_vhv and selected_tk_night:
                # Tìm TK có thể thay thế VHV (không trùng với TK đã chọn)
                available_tk_for_vhv_night = [tk for tk in available_tk_night if tk != selected_tk_night]
                if available_tk_for_vhv_night:
                    selected_vhv_night = select_staff_for_role(
                        available_tk_for_vhv_night, staff_data, day, 'night', 'TK_AS_VHV', balance_shifts, last_days_mode, is_training_day
                    )
                    if selected_vhv_night:
                        # Đánh dấu đây là TK thay thế VHV
                        staff_data[selected_vhv_night]['is_substituting_vhv'] = True
            
            if selected_tk_night and selected_vhv_night:
                # Cập nhật thông tin
                update_staff_data(staff_data, selected_tk_night, day, 'night')
                update_staff_data(staff_data, selected_vhv_night, day, 'night')
                
                # Kiểm tra quá 3 ca đêm liên tiếp (trừ trường hợp đặc biệt)
                if not staff_data[selected_tk_night].get('no_night_limit', False):
                    if staff_data[selected_tk_night]['consecutive_night'] > 3:
                        staff_data[selected_tk_night]['consecutive_night'] = 3
                if not staff_data[selected_vhv_night].get('no_night_limit', False):
                    if staff_data[selected_vhv_night]['consecutive_night'] > 3:
                        staff_data[selected_vhv_night]['consecutive_night'] = 3
                
                weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                ca_type = 'Đêm (18h-6h)'
                ghi_chu = ''
                
                if is_training_day:
                    ghi_chu = 'Đào tạo + Trực ca đêm'
                if selected_vhv_night in truong_kiep and selected_vhv_night != selected_tk_night:
                    ghi_chu = f"{ghi_chu}; TK thay VHV" if ghi_chu else "TK thay VHV"
                
                schedule.append({
                    'Ngày': day,
                    'Thứ': weekday_name,
                    'Ca': ca_type,
                    'Trưởng kiếp': selected_tk_night,
                    'Vận hành viên': selected_vhv_night,
                    'Ghi chú': ghi_chu
                })
        
        # Sau khi xếp xong, tính lại tổng công cho mỗi người
        for staff in all_staff:
            staff_data[staff]['total_credits'] = (
                staff_data[staff]['admin_credits'] + staff_data[staff]['total_shifts']
            )
        
        return schedule, staff_data

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

    def select_staff_for_role(available_staff, staff_data, day, shift_type, role_type, balance_shifts=True, last_days_mode=False, is_training_day=False):
        """Chọn nhân viên phù hợp cho ca làm việc - PHÂN BIỆT VAI TRÒ"""
        if not available_staff:
            return None
        
        # Tính toán số công còn thiếu so với mục tiêu 17
        for staff in available_staff:
            data = staff_data[staff]
            current_credits = data['current_total_credits']
            remaining_to_17 = 17 - current_credits
            data['remaining_to_17'] = remaining_to_17
        
        # Chế độ ngày cuối tháng: ưu tiên hoàn thành 17 công
        if last_days_mode:
            filtered_staff = []
            for staff in available_staff:
                data = staff_data[staff]
                
                # Kiểm tra vai trò: TK_AS_VHV là TK thay thế VHV
                if role_type == 'TK' and not data['is_tk']:
                    continue
                if role_type == 'VHV' and not data['is_vhv']:
                    continue
                if role_type == 'TK_AS_VHV' and not data['is_tk']:
                    continue
                
                # Kiểm tra không làm 24h liên tục (trừ ngày đào tạo)
                if shift_type == 'night' and not is_training_day and data['last_shift'] == 'day' and data['last_shift_day'] == day:
                    continue
                
                # Kiểm tra ca đêm liên tiếp (trừ trường hợp đặc biệt)
                if shift_type == 'night' and data['consecutive_night'] >= 4 and not data.get('no_night_limit', False):
                    continue
                
                # QUAN TRỌNG: Nếu đã đủ 17 công, KHÔNG được phân bổ thêm
                if data['remaining_to_17'] <= 0:
                    continue
                
                filtered_staff.append(staff)
            
            if filtered_staff:
                # Sắp xếp ưu tiên: người còn thiếu nhiều công nhất để đạt 17
                filtered_staff.sort(key=lambda x: (
                    -staff_data[x]['remaining_to_17'],  # Ưu tiên người còn thiếu nhiều công nhất
                    staff_data[x]['target_shifts'] - staff_data[x]['total_shifts'],  # Sau đó ưu tiên người còn thiếu ca
                    # Ưu tiên cho mục tiêu ca đêm
                    calculate_night_shift_priority(staff_data[x], shift_type),
                    staff_data[x]['total_shifts'],  # Sau đó ưu tiên người ít ca
                    random.random()
                ))
                return filtered_staff[0]
        
        # Chế độ bình thường
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
            
            # Tính số công còn thiếu để đạt 17
            remaining_to_17 = data['remaining_to_17']
            
            # QUAN TRỌNG: Nếu đã đủ 17 công, KHÔNG được phân bổ thêm ca trực
            if remaining_to_17 <= 0:
                continue
            
            # Kiểm tra ca đêm liên tiếp (trừ trường hợp đặc biệt)
            if shift_type == 'night' and data['consecutive_night'] >= 3 and not data.get('no_night_limit', False):
                continue
            
            # Kiểm tra không làm 24h liên tục (trừ ngày đào tạo)
            if shift_type == 'night' and not is_training_day and data['last_shift'] == 'day' and data['last_shift_day'] == day:
                continue
            
            # Kiểm tra cân bằng ca nếu được bật
            if balance_shifts:
                if shift_type == 'day':
                    # Nếu làm ca ngày, kiểm tra xem có quá nhiều ca ngày không
                    if data['day_shifts'] - data['night_shifts'] > 2:
                        continue
                else:  # shift_type == 'night'
                    # Nếu làm ca đêm, kiểm tra xem có quá nhiều ca đêm không
                    if data['night_shifts'] - data['day_shifts'] > 2:
                        continue
            
            filtered_staff.append(staff)
        
        if not filtered_staff:
            return None
        
        # Sắp xếp ưu tiên theo nhiều tiêu chí
        filtered_staff.sort(key=lambda x: (
            # Ưu tiên 1: Người còn thiếu nhiều công nhất để đạt 17
            -staff_data[x]['remaining_to_17'],
            # Ưu tiên 2: Người ít ca tổng nhất
            staff_data[x]['total_shifts'],
            # Ưu tiên 3: Còn cách target xa
            staff_data[x]['target_shifts'] - staff_data[x]['total_shifts'],
            # Ưu tiên 4: Ưu tiên mục tiêu ca đêm
            calculate_night_shift_priority(staff_data[x], shift_type),
            # Ưu tiên 5: Cân bằng ca
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            # Ưu tiên 6: Người lâu chưa được phân công nhất
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            # Ưu tiên 7: Ngẫu nhiên để tránh pattern cố định
            random.random()
        ))
        
        return filtered_staff[0]

    def calculate_night_shift_priority(staff_data, shift_type):
        """Tính điểm ưu tiên dựa trên mục tiêu ca đêm"""
        if shift_type == 'night':
            # Đối với ca đêm: ưu tiên người còn thiếu ca đêm so với mục tiêu
            night_goal = staff_data.get('night_shift_goal', 0)
            night_diff = night_goal - staff_data['night_shifts']
            # Ưu tiên người còn thiếu nhiều ca đêm (night_diff dương lớn)
            return -night_diff  # Âm để người có night_diff dương lớn lên đầu
        else:
            # Đối với ca ngày: ưu tiên người đã có nhiều ca đêm hơn mục tiêu
            night_goal = staff_data.get('night_shift_goal', 0)
            night_diff = staff_data['night_shifts'] - night_goal
            # Ưu tiên người đã vượt mục tiêu ca đêm (night_diff dương)
            return -night_diff

    def calculate_shift_balance_score(staff_data, shift_type, balance_shifts):
        """Tính điểm cân bằng ca ngày/đêm"""
        if not balance_shifts:
            return 0
        
        day_shifts = staff_data['day_shifts']
        night_shifts = staff_data['night_shifts']
        diff = day_shifts - night_shifts
        
        if shift_type == 'day':
            # Nếu đang chọn cho ca ngày, ưu tiên người có ít ca ngày hơn
            return max(0, diff)
        else:  # shift_type == 'night'
            # Nếu đang chọn cho ca đêm, ưu tiên người có ít ca đêm hơn
            return max(0, -diff)

    # Hàm tạo bảng so sánh trước-sau điều chỉnh
    def create_comparison_table(before_stats, after_stats):
        """Tạo bảng so sánh trước và sau khi điều chỉnh công tác"""
        comparison_data = []
        
        for staff in all_staff:
            before = before_stats.get(staff, {})
            after = after_stats.get(staff, {})
            
            # Tính công tăng thêm
            before_total = before.get('current_total_credits', 0)
            after_total = after.get('current_total_credits', 0)
            total_change = after_total - before_total
            
            # Tính ca ngày tăng thêm
            before_day = before.get('day_shifts', 0)
            after_day = after.get('day_shifts', 0)
            day_change = after_day - before_day
            
            # Tính ca đêm tăng thêm
            before_night = before.get('night_shifts', 0)
            after_night = after.get('night_shifts', 0)
            night_change = after_night - before_night
            
            # Tính công tác tăng thêm
            before_business = before.get('business_credits', 0)
            after_business = after.get('business_credits', 0)
            business_change = after_business - before_business
            
            comparison_data.append({
                'Nhân viên': staff,
                'Vai trò': 'TK' if staff in truong_kiep else 'VHV',
                'Công trước': before_total,
                'Công sau': after_total,
                'Công tăng': total_change,
                'Ca ngày trước': before_day,
                'Ca ngày sau': after_day,
                'Ca ngày tăng': day_change,
                'Ca đêm trước': before_night,
                'Ca đêm sau': after_night,
                'Ca đêm tăng': night_change,
                'Công tác trước': before_business,
                'Công tác sau': after_business,
                'Công tác tăng': business_change
            })
        
        return pd.DataFrame(comparison_data)

    # Tạo tabs với unique keys
    tab1, tab2, tab3 = st.tabs([
        "📅 Chọn ngày nghỉ & Công tác & Kiểm tra & Ca đêm", 
        "📊 Xếp lịch & Điều chỉnh & So sánh", 
        "📋 Thống kê chi tiết"
    ])

    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Chọn ngày nghỉ & Công tác & Số ca đêm mong muốn")
            
            # Tạo 2 cột cho 2 loại nhân viên
            col_tk, col_vhv = st.columns(2)
            
            with col_tk:
                st.markdown("### Trưởng kiếp")
                for idx, tk in enumerate(truong_kiep):
                    with st.expander(f"**{tk}**", expanded=False):
                        # Tạo key duy nhất cho mỗi widget
                        days_off_key = f"off_tk_{idx}_{month}_{year}"
                        business_key = f"business_tk_{idx}_{month}_{year}"
                        night_goal_key = f"night_goal_tk_{idx}_{month}_{year}"
                        
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {tk}",
                            options=list(range(1, num_days + 1)),
                            default=st.session_state.day_off.get(tk, []),
                            key=days_off_key
                        )
                        
                        if len(days_off) > 5:
                            st.error(f"{tk} chọn quá 5 ngày nghỉ!")
                            days_off = days_off[:5]
                        
                        st.session_state.day_off[tk] = days_off
                        
                        business_days = st.multiselect(
                            f"Ngày công tác - {tk}",
                            options=[d for d in range(1, num_days + 1) if d not in days_off and d != training_day],
                            default=st.session_state.business_trip.get(tk, []),
                            key=business_key
                        )
                        
                        st.session_state.business_trip[tk] = business_days
                        
                        # Thêm slider cho số ca đêm mong muốn
                        night_goal = st.slider(
                            f"Số ca đêm mong muốn - {tk}",
                            min_value=0,
                            max_value=17,
                            value=st.session_state.night_shift_goals.get(tk, 0),
                            key=night_goal_key,
                            help="Số ca đêm mong muốn trong tháng (0-17). Nếu chọn 17: được làm nhiều ca đêm liên tiếp không giới hạn, 13 ca đêm còn lại chia đều cho 3 TK khác."
                        )
                        st.session_state.night_shift_goals[tk] = night_goal
                        
                        st.caption(f"Ngày nghỉ: {len(days_off)}/5 | Công tác: {len(business_days)} | Ca đêm mong muốn: {night_goal}")
            
            with col_vhv:
                st.markdown("### Vận hành viên")
                for idx, vhv in enumerate(van_hanh_vien):
                    with st.expander(f"**{vhv}**", expanded=False):
                        # Tạo key duy nhất cho mỗi widget
                        days_off_key = f"off_vhv_{idx}_{month}_{year}"
                        business_key = f"business_vhv_{idx}_{month}_{year}"
                        night_goal_key = f"night_goal_vhv_{idx}_{month}_{year}"
                        
                        days_off = st.multiselect(
                            f"Ngày nghỉ - {vhv}",
                            options=list(range(1, num_days + 1)),
                            default=st.session_state.day_off.get(vhv, []),
                            key=days_off_key
                        )
                        
                        if len(days_off) > 5:
                            st.error(f"{vhv} chọn quá 5 ngày nghỉ!")
                            days_off = days_off[:5]
                        
                        st.session_state.day_off[vhv] = days_off
                        
                        business_days = st.multiselect(
                            f"Ngày công tác - {vhv}",
                            options=[d for d in range(1, num_days + 1) if d not in days_off and d != training_day],
                            default=st.session_state.business_trip.get(vhv, []),
                            key=business_key
                        )
                        
                        st.session_state.business_trip[vhv] = business_days
                        
                        # Thêm slider cho số ca đêm mong muốn
                        night_goal = st.slider(
                            f"Số ca đêm mong muốn - {vhv}",
                            min_value=0,
                            max_value=17,
                            value=st.session_state.night_shift_goals.get(vhv, 0),
                            key=night_goal_key,
                            help="Số ca đêm mong muốn trong tháng (0-17). Nếu chọn 17: được làm nhiều ca đêm liên tiếp không giới hạn, 13 ca đêm còn lại chia đều cho 3 VHV khác."
                        )
                        st.session_state.night_shift_goals[vhv] = night_goal
                        
                        st.caption(f"Ngày nghỉ: {len(days_off)}/5 | Công tác: {len(business_days)} | Ca đêm mong muốn: {night_goal}")
        
        with col2:
            st.subheader("🏞️ Kiểm tra đường dây 220kV")
            st.markdown("""
            **Quy định:**
            - Mỗi nhóm: 1 TK + 1 VHV
            - Mỗi nhóm đi 1 ngày trong tháng
            - Công kiểm tra tính 1 công hành chính (trong 17 công)
            - Không trùng ngày đào tạo, nghỉ, công tác
            - Trưởng kíp: 1 công, Vận hành viên: 1 công
            """)
            
            # Hiển thị số nhóm hiện có
            num_groups = len(st.session_state.line_inspection)
            
            # Cho phép thêm/xóa nhóm
            col_add, col_del = st.columns(2)
            with col_add:
                if st.button("➕ Thêm nhóm", use_container_width=True, key="tab1_add_group_btn"):
                    st.session_state.line_inspection.append({'tk': None, 'vhv': None, 'day': None})
            
            with col_del:
                if st.button("➖ Xóa nhóm cuối", use_container_width=True, key="tab1_remove_group_btn") and num_groups > 0:
                    st.session_state.line_inspection.pop()
            
            # Hiển thị các nhóm
            for i, group in enumerate(st.session_state.line_inspection):
                with st.expander(f"Nhóm kiểm tra {i+1}", expanded=(i == 0 and num_groups > 0)):
                    # Tạo key duy nhất cho mỗi widget trong nhóm
                    group_key = f"tab1_group_{i}_{month}_{year}"
                    tk_key = f"tab1_line_tk_{group_key}"
                    vhv_key = f"tab1_line_vhv_{group_key}"
                    day_key = f"tab1_line_day_{group_key}"
                    
                    # Chọn Trưởng kiếp
                    used_tk = [g['tk'] for j, g in enumerate(st.session_state.line_inspection) 
                              if j != i and g['tk'] is not None]
                    available_tk = [tk for tk in truong_kiep if tk not in used_tk]
                    
                    selected_tk = st.selectbox(
                        f"Trưởng kiếp - Nhóm {i+1}",
                        options=["(Chọn TK)"] + available_tk,
                        index=0 if group['tk'] is None else available_tk.index(group['tk']) + 1,
                        key=tk_key
                    )
                    if selected_tk == "(Chọn TK)":
                        selected_tk = None
                    
                    # Chọn Vận hành viên
                    used_vhv = [g['vhv'] for j, g in enumerate(st.session_state.line_inspection) 
                               if j != i and g['vhv'] is not None]
                    available_vhv = [vhv for vhv in van_hanh_vien if vhv not in used_vhv]
                    
                    selected_vhv = st.selectbox(
                        f"Vận hành viên - Nhóm {i+1}",
                        options=["(Chọn VHV)"] + available_vhv,
                        index=0 if group['vhv'] is None else available_vhv.index(group['vhv']) + 1,
                        key=vhv_key
                    )
                    if selected_vhv == "(Chọn VHV)":
                        selected_vhv = None
                    
                    # Chọn ngày kiểm tra
                    if selected_tk and selected_vhv:
                        # Lấy ngày nghỉ và công tác của cả hai
                        tk_off = st.session_state.day_off.get(selected_tk, [])
                        tk_business = st.session_state.business_trip.get(selected_tk, [])
                        vhv_off = st.session_state.day_off.get(selected_vhv, [])
                        vhv_business = st.session_state.business_trip.get(selected_vhv, [])
                        
                        # Ngày không được trùng
                        invalid_days = set(tk_off + tk_business + vhv_off + vhv_business + [training_day])
                        
                        # Ngày đã được chọn bởi nhóm khác
                        used_days = [g['day'] for j, g in enumerate(st.session_state.line_inspection) 
                                    if j != i and g['day'] is not None]
                        
                        available_days = [d for d in range(1, num_days + 1) 
                                         if d not in invalid_days and d not in used_days]
                        
                        if available_days:
                            selected_day = st.selectbox(
                                f"Ngày kiểm tra - Nhóm {i+1}",
                                options=["(Chọn ngày)"] + available_days,
                                index=0 if group['day'] is None else available_days.index(group['day']) + 1,
                                key=day_key
                            )
                            if selected_day == "(Chọn ngày)":
                                selected_day = None
                        else:
                            st.warning("Không còn ngày phù hợp cho nhóm này")
                            selected_day = None
                    else:
                        selected_day = None
                        st.info("Vui lòng chọn TK và VHV trước")
                    
                    # Cập nhật thông tin nhóm
                    st.session_state.line_inspection[i] = {
                        'tk': selected_tk,
                        'vhv': selected_vhv,
                        'day': selected_day
                    }
                    
                    # Hiển thị thông tin nhóm
                    if selected_tk and selected_vhv and selected_day:
                        st.success(f"Nhóm {i+1}: {selected_tk} + {selected_vhv} - Ngày {selected_day}")
            
            # Thống kê
            if st.session_state.line_inspection:
                st.markdown("### 📊 Thống kê nhóm kiểm tra")
                groups_data = []
                for i, group in enumerate(st.session_state.line_inspection):
                    if group['tk'] and group['vhv'] and group['day']:
                        groups_data.append({
                            'Nhóm': i+1,
                            'Trưởng kiếp': group['tk'],
                            'Vận hành viên': group['vhv'],
                            'Ngày': group['day'],
                            'Thứ': calendar.day_name[calendar.weekday(year, month, group['day'])]
                        })
                
                if groups_data:
                    df_groups = pd.DataFrame(groups_data)
                    st.dataframe(df_groups, use_container_width=True, hide_index=True)
                else:
                    st.info("Chưa có nhóm kiểm tra nào được thiết lập đầy đủ")
            
            # Thống kê mục tiêu ca đêm
            st.markdown("### 🌙 Thống kê mục tiêu ca đêm")
            night_goals_data = []
            total_night_goals = 0
            for staff in all_staff:
                goal = st.session_state.night_shift_goals.get(staff, 0)
                total_night_goals += goal
                night_goals_data.append({
                    'Nhân viên': staff,
                    'Vai trò': 'TK' if staff in truong_kiep else 'VHV',
                    'Ca đêm mong muốn': goal
                })
            
            df_night_goals = pd.DataFrame(night_goals_data)
            st.dataframe(df_night_goals, use_container_width=True, hide_index=True)
            st.caption(f"Tổng số ca đêm mong muốn: {total_night_goals}")

    with tab2:
        st.subheader("Tạo lịch trực tự động và điều chỉnh công tác đột xuất")
        
        # Sử dụng giá trị từ sidebar
        balance_shifts_value = balance_shifts_option
        allow_tk_substitute_vhv = st.session_state.tk_substitute_vhv
        
        # Kiểm tra xem có ai đi công tác không
        has_business_trip = any(len(days) > 0 for days in st.session_state.business_trip.values())
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🎯 Tạo lịch trực tự động", type="primary", use_container_width=True, key="tab2_generate_schedule_btn"):
                with st.spinner("Đang tạo lịch trực với cân bằng ca và kiểm tra đường dây..."):
                    day_off_dict = st.session_state.day_off
                    business_trip_dict = st.session_state.business_trip
                    line_inspection_groups = [g for g in st.session_state.line_inspection 
                                             if g['tk'] and g['vhv'] and g['day']]
                    night_shift_goals = st.session_state.night_shift_goals
                    
                    # Hiển thị thông báo về quy tắc
                    if not has_business_trip:
                        st.info("📋 **KHÔNG CÓ AI ĐI CÔNG TÁC**: Hệ thống sẽ đảm bảo mỗi người đủ 17 công!")
                    
                    schedule, staff_data = generate_advanced_schedule(
                        month, year, training_day, day_off_dict, 
                        business_trip_dict, line_inspection_groups, night_shift_goals, 
                        balance_shifts_value, allow_tk_substitute_vhv
                    )
                    
                    if not schedule and not has_business_trip:
                        # Lịch rỗng do không đủ ca
                        st.error("❌ KHÔNG THỂ TẠO LịCH: Không đủ ca trực để đảm bảo mỗi người 17 công!")
                        st.info("Vui lòng điều chỉnh: giảm ngày nghỉ, giảm nhóm kiểm tra, hoặc bật chế độ TK thay VHV.")
                        st.session_state.schedule_created = False
                    else:
                        # Tạo lịch ngang theo nhân viên
                        staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                            schedule, num_days, year, month, line_inspection_groups,
                            day_off_dict, business_trip_dict, training_day
                        )
                        
                        # Lưu vào session state
                        st.session_state.schedule_data = schedule
                        st.session_state.staff_stats = staff_data
                        st.session_state.staff_horizontal_schedule = staff_horizontal_schedule
                        st.session_state.schedule_created = True
                        
                        # Lưu bản gốc
                        st.session_state.original_schedule = schedule.copy()
                        st.session_state.original_stats = {k: v.copy() for k, v in staff_data.items()}
                        st.session_state.original_horizontal_schedule = staff_horizontal_schedule.copy()
                        st.session_state.adjusted_horizontal_schedule = None
                        st.session_state.comparison_data = None
                        st.session_state.emergency_staff = None
                        st.session_state.emergency_start_day = None
                        st.session_state.emergency_end_day = None
                        
                        st.success("✅ Đã tạo lịch trực thành công!")
                        
                        # Kiểm tra xem có người nào chưa đạt 17 công không
                        under_17 = []
                        for staff, data in staff_data.items():
                            total_credits = data['admin_credits'] + data['total_shifts']
                            if total_credits < 17:
                                under_17.append((staff, total_credits))
                        
                        if under_17:
                            st.warning(f"⚠️ Có {len(under_17)} người chưa đạt 17 công:")
                            for staff, credits in under_17:
                                st.warning(f"- {staff}: {credits}/17 công")
                            
                            if not has_business_trip:
                                st.error("❌ **LỖI NGHIÊM TRỌNG**: Không có ai đi công tác nhưng vẫn có người chưa đủ 17 công!")
        
        # Hiển thị lịch ngang sau khi tạo lịch
        if st.session_state.schedule_created and st.session_state.staff_horizontal_schedule is not None:
            st.markdown("---")
            st.subheader("📱 Lịch trực dạng ngang")
            st.markdown("**Cột dọc: Nhân viên | Cột ngang: Ngày trong tháng**")
            
            # Kiểm tra xem có lịch đã điều chỉnh không
            if st.session_state.adjusted_horizontal_schedule is not None:
                # Hiển thị lịch đã điều chỉnh với style so sánh với lịch gốc
                styled_schedule = create_adjusted_schedule_style(
                    st.session_state.original_horizontal_schedule,
                    st.session_state.adjusted_horizontal_schedule
                )
                df_to_display = styled_schedule
                st.info("🟨 **Các ô màu vàng**: Thay đổi sau khi điều chỉnh công tác")
            else:
                # Hiển thị lịch gốc (không style)
                df_to_display = st.session_state.staff_horizontal_schedule
            
            # Thêm CSS để cuộn ngang
            st.markdown("""
            <style>
            .horizontal-scroll {
                overflow-x: auto;
                white-space: nowrap;
                max-width: 100%;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                margin-bottom: 20px;
            }
            </style>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="horizontal-scroll">', unsafe_allow_html=True)
            st.dataframe(
                df_to_display,
                use_container_width=True,
                height=min(600, 150 + len(df_to_display) * 35)
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Hiển thị chú thích
            with st.expander("📋 Ký hiệu và quy tắc"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("""
                    **Ký hiệu:**
                    - **TK**: Trưởng kiếp
                    - **VHV**: Vận hành viên
                    - **N**: Ca ngày (6h-18h)
                    - **Đ**: Ca đêm (18h-6h)
                    - **ĐT**: Đào tạo nội bộ
                    - **N (ĐT)**: Trực ca ngày + Đào tạo
                    - **Đ (ĐT)**: Trực ca đêm + Đào tạo
                    - **KT**: Kiểm tra đường dây
                    - **CT**: Công tác
                    - **Nghỉ**: Ngày nghỉ
                    - **-**: Không có hoạt động
                    """)
                
                with col2:
                    st.markdown("""
                    **QUY TẮC:**
                    - **Tổng công: 17 công/người/tháng**
                    - **TK chỉ thay TK, VHV chỉ thay VHV**
                    - **Khi không có công tác: Mọi người đều đủ 17 công**
                    - Công đào tạo: 1 công (ĐT)
                    - Công kiểm tra: 1 công/ngày (KT)
                    - Công công tác: 1 công/ngày (CT)
                    - Công trực ca: 1 công/ca (N hoặc Đ)
                    """)
            
            # Nút tải xuống lịch ngang
            st.markdown("---")
            csv_horizontal = df_to_display.to_csv(encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải lịch ngang theo nhân viên (CSV)",
                data=csv_horizontal,
                file_name=f"lich_truc_ngang_nhan_vien_TBA_500kV_{month}_{year}.csv",
                mime="text/csv",
                use_container_width=True,
                key="tab2_download_horizontal_csv"
            )
            
            # Phần điều chỉnh công tác đột xuất
            st.markdown("---")
            st.subheader("🚨 Điều chỉnh công tác đột xuất")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Chọn nhân viên và thời gian công tác")
                
                # Chọn nhân viên - mặc định là N/A
                emergency_options = ["N/A"] + all_staff
                emergency_index = 0 if st.session_state.emergency_staff is None else emergency_options.index(st.session_state.emergency_staff)
                
                emergency_staff = st.selectbox(
                    "Chọn nhân viên đi công tác đột xuất",
                    options=emergency_options,
                    index=emergency_index,
                    key="tab2_emergency_staff"
                )
                
                if emergency_staff == "N/A":
                    emergency_staff = None
                    st.session_state.emergency_staff = None
                else:
                    st.session_state.emergency_staff = emergency_staff
                
                # Chọn ngày bắt đầu
                if st.session_state.emergency_start_day is None:
                    start_value = 1
                else:
                    start_value = st.session_state.emergency_start_day
                
                start_day = st.number_input(
                    "Ngày bắt đầu công tác",
                    min_value=1,
                    max_value=num_days,
                    value=start_value,
                    key="tab2_start_day"
                )
                st.session_state.emergency_start_day = start_day
                
                # Chọn ngày kết thúc
                if st.session_state.emergency_end_day is None:
                    end_value = min(start_day + 2, num_days)
                else:
                    end_value = st.session_state.emergency_end_day
                
                end_day = st.number_input(
                    "Ngày kết thúc công tác",
                    min_value=start_day,
                    max_value=num_days,
                    value=end_value,
                    key="tab2_end_day"
                )
                st.session_state.emergency_end_day = end_day
                
                # Kiểm tra hợp lệ
                if emergency_staff and start_day <= end_day:
                    duration = end_day - start_day + 1
                    st.info(f"**Thông tin công tác:** {emergency_staff} đi công tác {duration} ngày (từ ngày {start_day} đến {end_day})")
                    
                    # Kiểm tra xung đột
                    conflicts = []
                    for shift in st.session_state.schedule_data:
                        if start_day <= shift['Ngày'] <= end_day:
                            if shift['Trưởng kiếp'] == emergency_staff or shift['Vận hành viên'] == emergency_staff:
                                conflicts.append(f"Ngày {shift['Ngày']}: {shift['Ca']}")
                    
                    if conflicts:
                        st.warning(f"⚠️ {emergency_staff} đã có lịch trực trong các ngày sau:")
                        for conflict in conflicts:
                            st.warning(f"- {conflict}")
            
            with col2:
                st.markdown("#### Thao tác điều chỉnh")
                
                # Nút điều chỉnh lịch
                if st.button("🔄 Điều chỉnh lịch theo công tác", type="primary", use_container_width=True, key="tab2_adjust_schedule_btn"):
                    if not emergency_staff:
                        st.error("❌ Vui lòng chọn nhân viên đi công tác!")
                    elif start_day > end_day:
                        st.error("❌ Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc!")
                    else:
                        with st.spinner("Đang điều chỉnh lịch trực..."):
                            # Thực hiện điều chỉnh
                            day_off_dict = st.session_state.day_off
                            business_trip_dict = st.session_state.business_trip
                            line_inspection_groups = [g for g in st.session_state.line_inspection 
                                                     if g['tk'] and g['vhv'] and g['day']]
                            night_shift_goals = st.session_state.night_shift_goals
                            balance_shifts_value = balance_shifts_option
                            allow_tk_substitute_vhv = st.session_state.tk_substitute_vhv
                            
                            new_schedule, new_stats = adjust_schedule_for_emergency(
                                st.session_state.schedule_data,
                                st.session_state.staff_stats,
                                emergency_staff,
                                start_day,
                                end_day,
                                day_off_dict,
                                business_trip_dict,
                                line_inspection_groups,
                                night_shift_goals,
                                balance_shifts_value,
                                allow_tk_substitute_vhv
                            )
                            
                            # Cập nhật session state
                            st.session_state.schedule_data = new_schedule
                            st.session_state.staff_stats = new_stats
                            
                            # Tạo lịch ngang mới
                            staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                                new_schedule, num_days, year, month, line_inspection_groups,
                                day_off_dict, business_trip_dict, training_day
                            )
                            st.session_state.staff_horizontal_schedule = staff_horizontal_schedule
                            
                            # Lưu lịch đã điều chỉnh
                            st.session_state.adjusted_horizontal_schedule = staff_horizontal_schedule
                            
                            # Tạo bảng so sánh
                            st.session_state.comparison_data = create_comparison_table(
                                st.session_state.original_stats,
                                st.session_state.staff_stats
                            )
                            
                            st.success(f"✅ Đã điều chỉnh lịch thành công cho {emergency_staff} đi công tác!")
                
                # Nút khôi phục lịch gốc
                if st.session_state.original_schedule is not None:
                    if st.button("↩️ Khôi phục lịch gốc", type="secondary", use_container_width=True, key="tab2_restore_schedule_btn"):
                        # Khôi phục lịch gốc
                        st.session_state.schedule_data = st.session_state.original_schedule.copy()
                        st.session_state.staff_stats = {k: v.copy() for k, v in st.session_state.original_stats.items()}
                        
                        # Tạo lại lịch ngang
                        day_off_dict = st.session_state.day_off
                        business_trip_dict = st.session_state.business_trip
                        line_inspection_groups = [g for g in st.session_state.line_inspection 
                                                 if g['tk'] and g['vhv'] and g['day']]
                        
                        staff_horizontal_schedule = convert_to_staff_horizontal_schedule(
                            st.session_state.schedule_data, num_days, year, month, line_inspection_groups,
                            day_off_dict, business_trip_dict, training_day
                        )
                        st.session_state.staff_horizontal_schedule = staff_horizontal_schedule
                        st.session_state.adjusted_horizontal_schedule = None
                        st.session_state.comparison_data = None
                        st.session_state.emergency_staff = None
                        st.session_state.emergency_start_day = None
                        st.session_state.emergency_end_day = None
                        
                        st.success("✅ Đã khôi phục lịch gốc thành công!")
            
            # Hiển thị bảng so sánh nếu đã điều chỉnh
            if st.session_state.comparison_data is not None:
                st.markdown("---")
                st.subheader("📊 So sánh trước và sau điều chỉnh")
                
                df_comparison = st.session_state.comparison_data
                
                # Tạo style cho bảng so sánh
                def highlight_changes(val, column):
                    if 'tăng' in column:
                        if val > 0:
                            return 'background-color: #e6ffe6; color: green; font-weight: bold'
                        elif val < 0:
                            return 'background-color: #ffe6e6; color: red; font-weight: bold'
                    return ''
                
                # Áp dụng style cho các cột tăng
                styled_comparison = df_comparison.style
                for col in df_comparison.columns:
                    if 'tăng' in col:
                        styled_comparison = styled_comparison.apply(
                            lambda x: [highlight_changes(v, col) for v in x], 
                            subset=[col]
                        )
                
                st.dataframe(styled_comparison, use_container_width=True)
                
                # Tóm tắt thay đổi
                st.markdown("#### 📈 Tóm tắt thay đổi")
                
                total_credits_change = df_comparison['Công tăng'].sum()
                total_business_change = df_comparison['Công tác tăng'].sum()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Tổng công tăng", f"{total_credits_change}")
                with col2:
                    st.metric("Công tác tăng", f"{total_business_change}")
                with col3:
                    affected_people = len(df_comparison[df_comparison['Công tăng'] != 0])
                    st.metric("Người bị ảnh hưởng", affected_people)
                
                # Hiển thị chi tiết thay đổi của người đi công tác
                if emergency_staff:
                    staff_change = df_comparison[df_comparison['Nhân viên'] == emergency_staff].iloc[0]
                    st.info(f"""
                    **Thay đổi của {emergency_staff}:**
                    - Công tác tăng: {staff_change['Công tác tăng']} công
                    - Tổng công tăng: {staff_change['Công tăng']} công
                    - Ca ngày thay đổi: {staff_change['Ca ngày tăng']} ca
                    - Ca đêm thay đổi: {staff_change['Ca đêm tăng']} ca
                    """)
        else:
            st.info("👈 Vui lòng nhấn nút 'Tạo lịch trực tự động' để tạo lịch")

    with tab3:
        st.subheader("Thống kê chi tiết")
        
        if st.session_state.schedule_created and st.session_state.staff_stats:
            # Hiển thị thông tin tổng quan
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Tổng nhân sự", len(all_staff))
            
            with col2:
                st.metric("Trưởng kiếp", len(truong_kiep))
            
            with col3:
                st.metric("Vận hành viên", len(van_hanh_vien))
            
            total_business_days = sum(len(st.session_state.business_trip[staff]) for staff in all_staff)
            with col4:
                st.metric("Ngày công tác", total_business_days)
            
            # Thống kê chi tiết từng nhân viên
            st.markdown("---")
            st.subheader("📈 Thống kê phân công chi tiết")
            
            stats_data = []
            for staff, data in st.session_state.staff_stats.items():
                # Tính các loại công
                training_credits = data.get('training_credits', 1)
                line_inspection_credits = data.get('line_inspection_credits', 0)
                business_credits = data.get('business_credits', 0)
                shifts_done = data['total_shifts']
                day_shifts = data['day_shifts']
                night_shifts = data['night_shifts']
                night_goal = data.get('night_shift_goal', 0)
                
                # Tổng công đã có
                total_credits = training_credits + line_inspection_credits + business_credits + shifts_done
                
                # Kiểm tra nếu dưới 17 công
                status = "✅" if total_credits >= 17 else "❌"
                
                # Công còn lại cần đạt 17
                remaining_credits = 17 - total_credits
                
                diff = day_shifts - night_shifts
                diff_status = "✅" if abs(diff) <= 2 else "⚠️"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': 'TK' if staff in truong_kiep else 'VHV',
                    'Đào tạo': training_credits,
                    'Kiểm tra': line_inspection_credits,
                    'Công tác': business_credits,
                    'Đã trực': shifts_done,
                    'Ca ngày': day_shifts,
                    'Ca đêm': night_shifts,
                    'Mục tiêu ca đêm': night_goal,
                    'Tổng công': total_credits,
                    'Đạt 17 công': status,
                    'Chênh lệch (N-Đ)': f"{diff} {diff_status}",
                    'Còn thiếu': remaining_credits if remaining_credits > 0 else 0,
                })
            
            df_stats = pd.DataFrame(stats_data)
            
            # Tô màu cho trạng thái đạt 17 công
            def color_17_status(val):
                if val == "✅":
                    return 'background-color: #e6ffe6; color: green; font-weight: bold'
                elif val == "❌":
                    return 'background-color: #ffe6e6; color: red; font-weight: bold'
                return ''
            
            # Tô màu chênh lệch
            def color_diff(val):
                if isinstance(val, str):
                    if '✅' in val:
                        return 'background-color: #e6ffe6'
                    elif '⚠️' in val:
                        return 'background-color: #fff0cc'
                return ''
            
            # Tô màu cho cột "Còn thiếu"
            def color_remaining(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        return 'background-color: #fff0cc; color: #e68a00; font-weight: bold'
                return ''
            
            styled_stats = df_stats.style \
                .applymap(color_17_status, subset=['Đạt 17 công']) \
                .applymap(color_diff, subset=['Chênh lệch (N-Đ)']) \
                .applymap(color_remaining, subset=['Còn thiếu'])
            
            st.dataframe(styled_stats, use_container_width=True)
            
            # Tóm tắt phân công
            st.markdown("---")
            st.subheader("📋 Tóm tắt phân công")
            
            col1, col2, col3, col4 = st.columns(4)
            
            total_shifts = sum(data['total_shifts'] for data in st.session_state.staff_stats.values())
            total_target = 17 * len(all_staff)
            total_training = len(all_staff)
            total_business = sum(data['business_credits'] for data in st.session_state.staff_stats.values())
            total_inspection = sum(data['line_inspection_credits'] for data in st.session_state.staff_stats.values())
            total_day_shifts = sum(data['day_shifts'] for data in st.session_state.staff_stats.values())
            total_night_shifts = sum(data['night_shifts'] for data in st.session_state.staff_stats.values())
            
            # Tính tổng công thực tế
            total_actual = total_shifts + total_training + total_business + total_inspection
            
            with col1:
                st.metric("Tổng ca trực", total_shifts)
            with col2:
                st.metric("Ngày công tác", f"{total_business} công")
            with col3:
                st.metric("Nhóm kiểm tra", f"{total_inspection} công")
            with col4:
                completion_rate = (total_actual / total_target) * 100 if total_target > 0 else 0
                st.metric("Hoàn thành mục tiêu", f"{completion_rate:.1f}%")
        else:
            st.info("👈 Vui lòng tạo lịch trực ở Tab 2")

    # Footer
    st.markdown("---")
    st.caption("""
    **Hệ thống xếp lịch trực TBA 500kV - Phiên bản 16.0 - LỊCH NGANG & ĐIỀU CHỈNH TRỰC TIẾP**  
    *Mỗi người: 17 công/tháng = 1 công đào tạo + công kiểm tra + công công tác + công trực ca*  
    **QUY TẮC CỨNG:** TK chỉ thay TK, VHV chỉ thay VHV (trừ khi khó khăn)  
    **BẮT BUỘC:** Khi không có công tác, mọi người phải đủ 17 công  
    **KIỂM TRA ĐƯỜNG DÂY:** TK 1 công, VHV 1 công  
    **CA ĐÊM MONG MUỐN:** Có thể đặt từ 0 đến 17 ca đêm  
    **TRƯỜNG HỢP ĐẶC BIỆT:** Nếu chọn 17 ca đêm: được làm nhiều ca đêm liên tiếp không giới hạn  
    **ĐIỀU CHỈNH ĐỘT XUẤT:** Giữ nguyên các ngày đã trực, chỉ thay đổi các ngày tiếp theo  
    *Ngày đào tạo: vẫn có ca trực bình thường*  
    *So sánh trực tiếp trước và sau điều chỉnh*  
    *Hiển thị số công tăng thêm của mỗi người*
    """)

except Exception as e:
    st.error(f"Đã xảy ra lỗi trong ứng dụng: {str(e)}")
    with st.expander("Chi tiết lỗi (dành cho nhà phát triển)"):
        st.code(traceback.format_exc())
    st.info("Vui lòng làm mới trang và thử lại. Nếu lỗi vẫn tiếp tục, hãy liên hệ với quản trị viên.")