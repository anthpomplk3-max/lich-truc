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
        4. Tối đa 3 ca đêm liên tiếp
        5. Ngày đào tạo: vẫn có ca trực bình thường
        6. Người công tác: không tham gia trực (1 công/ngày)
        7. Kiểm tra đường dây: 1 TK + 1 VHV (1 công/ngày)
        8. Cân bằng ca: chênh lệch ca ngày/đêm ≤ 2
        9. **TK chỉ thay TK, VHV chỉ thay VHV**
        10. **Chỉ khi khó khăn: TK có thể thay VHV**
        11. **Khi không có công tác: mọi người đều đủ 17 công**
        
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

    # Hàm điều chỉnh lịch khi có công tác đột xuất
    def adjust_schedule_for_emergency(schedule_data, staff_data, emergency_staff, start_day, end_day, day_off_dict, business_trip_dict, line_inspection_groups, night_shift_goals, balance_shifts=True, allow_tk_substitute_vhv=False):
        """Điều chỉnh lịch khi có công tác đột xuất - Giữ nguyên các ngày đã trực"""
        num_days = calendar.monthrange(year, month)[1]
        
        # Lưu lịch gốc trước khi điều chỉnh
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
                    
                    # Kiểm tra quá 3 ca đêm liên tiếp
                    if staff_data[selected_tk_night]['consecutive_night'] > 3:
                        staff_data[selected_tk_night]['consecutive_night'] = 3
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
            }
            
            # Thêm ngày kiểm tra đường dây vào unavailable_days
            staff_data[staff]['unavailable_days'].update(line_inspection_dict.get(staff, set()))
        
        # Tổng số ca cần cho tất cả nhân viên
        total_required_shifts = sum(data['target_shifts'] for data in staff_data.values())
        
        # Tính số ca có sẵn trong tháng
        # Mỗi ngày có 2 ca (ngày và đêm), không trừ ngày đào tạo
        total_available_shifts = num_days * 2
        
        # Nếu không có ai đi công tác, PHẢI đảm bảo mọi người đủ 17 công
        if not has_business_trip:
            # Tính tổng công hành chính của tất cả mọi người
            total_admin_credits = sum(data['admin_credits'] for data in staff_data.values())
            total_required_from_shifts = 17 * len(all_staff) - total_admin_credits
            
            if total_required_from_shifts > total_available_shifts:
                # KHẨN CẤP: Không đủ ca để đảm bảo 17 công
                # Cần điều chỉnh bằng cách tăng target_shifts hoặc cảnh báo
                st.warning("⚠️ CẢNH BÁO: Không đủ ca trực để đảm bảo mỗi người 17 công!")
                st.info("Giải pháp: Giảm số ngày nghỉ hoặc điều chỉnh ngày kiểm tra đường dây.")
            
            # Đảm bảo phân bổ đủ ca để mọi người đạt 17 công
            # Tính hệ số điều chỉnh để phân bổ ca trực
            if total_required_from_shifts > 0:
                adjustment_factor = min(1.0, total_available_shifts / total_required_from_shifts)
                
                # Điều chỉnh target_shifts cho mỗi nhân viên
                for staff in all_staff:
                    if staff_data[staff]['target_shifts'] > 0:
                        staff_data[staff]['target_shifts'] = max(1, int(
                            staff_data[staff]['target_shifts'] * adjustment_factor
                        ))
        
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
                
                # Kiểm tra quá 3 ca đêm liên tiếp
                if staff_data[selected_tk_night]['consecutive_night'] > 3:
                    staff_data[selected_tk_night]['consecutive_night'] = 3
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
                
                # Kiểm tra ca đêm liên tiếp
                if shift_type == 'night' and data['consecutive_night'] >= 4:  # Cho phép 4 ca đêm liên tiếp
                    continue
                
                # Trong ngày cuối, ưu tiên người còn thiếu công
                if data['remaining_to_17'] <= 0 and data['total_shifts'] >= data['target_shifts']:
                    # Nếu đã đủ 17 công và đã đạt target, giảm ưu tiên
                    pass
                
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
            
            # Ưu tiên người còn thiếu công để đạt 17
            if remaining_to_17 <= 0:
                # Nếu đã đủ 17 công, giảm ưu tiên (nhưng vẫn có thể được chọn nếu không còn ai)
                if data['total_shifts'] >= data['target_shifts'] + 2:  # Cho phép vượt target một chút
                    continue
            
            # Kiểm tra ca đêm liên tiếp
            if shift_type == 'night' and data['consecutive_night'] >= 3:
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

    # Tạo tabs với unique keys
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Chọn ngày nghỉ & Công tác & Kiểm tra & Ca đêm", 
        "📊 Xếp lịch tự động", 
        "📋 Thống kê", 
        "📱 Xem lịch ngang theo nhân viên",
        "🚨 Điều chỉnh công tác đột xuất"
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
                            max_value=10,
                            value=st.session_state.night_shift_goals.get(tk, 0),
                            key=night_goal_key,
                            help="Số ca đêm mong muốn trong tháng (nằm trong tổng 17 công)"
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
                            max_value=10,
                            value=st.session_state.night_shift_goals.get(vhv, 0),
                            key=night_goal_key,
                            help="Số ca đêm mong muốn trong tháng (nằm trong tổng 17 công)"
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
        st.subheader("Tạo lịch trực tự động")
        
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
                            st.info("""
                            **Nguyên nhân có thể:**
                            1. Quá nhiều ngày nghỉ/kiểm tra đường dây
                            2. Số ca trực trong tháng không đủ phân bổ
                            3. Xung đột lịch trình nghiêm trọng
                            
                            **Giải pháp khẩn cấp:**
                            - Giảm số ngày nghỉ
                            - Giảm số nhóm kiểm tra đường dây
                            - Bật chế độ TK thay thế VHV
                            """)
        
        if st.session_state.schedule_created and st.session_state.schedule_data:
            st.subheader("Lịch trực dạng dọc (chi tiết)")
            df_schedule = pd.DataFrame(st.session_state.schedule_data)
            
            # Tô màu cho các loại ca
            def color_ca(val):
                if 'Ngày' in str(val):
                    return 'background-color: #e6ffe6'
                elif 'Đêm' in str(val):
                    return 'background-color: #ffe6e6'
                elif 'Đào tạo' in str(val):
                    return 'background-color: #ffffcc'
                return ''
            
            styled_df = df_schedule.style.applymap(color_ca, subset=['Ca'])
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            # Nút tải xuống
            csv = df_schedule.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải lịch trực (CSV)",
                data=csv,
                file_name=f"lich_truc_TBA_500kV_{month}_{year}.csv",
                mime="text/csv",
                use_container_width=True,
                key="tab2_download_schedule_csv"
            )

    with tab3:
        st.subheader("Thống kê tổng quan")
        
        # Kiểm tra xem có ai đi công tác không
        has_business_trip = any(len(days) > 0 for days in st.session_state.business_trip.values())
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Tổng nhân sự", len(all_staff))
        
        with col2:
            st.metric("Trưởng kiếp", len(truong_kiep))
        
        with col3:
            st.metric("Vận hành viên", len(van_hanh_vien))
        
        with col4:
            st.metric("Công tác", "Có" if has_business_trip else "Không")
        
        # Thông báo đặc biệt khi không có công tác
        if not has_business_trip:
            st.info("📋 **CHẾ ĐỘ ĐẶC BIỆT**: Không có ai đi công tác - Hệ thống đảm bảo mỗi người đủ 17 công!")
        
        # Hiển thị thống kê nhóm kiểm tra
        if st.session_state.line_inspection:
            active_groups = [g for g in st.session_state.line_inspection 
                            if g['tk'] and g['vhv'] and g['day']]
            if active_groups:
                st.subheader("🏞️ Thống kê nhóm kiểm tra đường dây")
                groups_info = []
                for i, group in enumerate(active_groups):
                    groups_info.append({
                        'Nhóm': i+1,
                        'Trưởng kiếp': group['tk'],
                        'Vận hành viên': group['vhv'],
                        'Ngày kiểm tra': group['day'],
                        'Thứ': calendar.day_name[calendar.weekday(year, month, group['day'])]
                    })
                
                df_groups = pd.DataFrame(groups_info)
                st.dataframe(df_groups, use_container_width=True, hide_index=True)
        
        if st.session_state.schedule_created and st.session_state.staff_stats:
            st.subheader("📈 Thống kê phân công chi tiết")
            
            stats_data = []
            under_17_count = 0
            night_goal_achieved = 0
            tk_substitute_count = 0
            
            for staff, data in st.session_state.staff_stats.items():
                # Tính các loại công
                training_credits = data.get('training_credits', 1)
                line_inspection_credits = data.get('line_inspection_credits', 0)
                business_credits = data.get('business_credits', 0)
                shifts_done = data['total_shifts']
                day_shifts = data['day_shifts']
                night_shifts = data['night_shifts']
                night_goal = data.get('night_shift_goal', 0)
                
                # Kiểm tra đạt mục tiêu ca đêm
                night_goal_status = "✅" if night_shifts >= night_goal else "⚠️"
                if night_shifts >= night_goal:
                    night_goal_achieved += 1
                
                # Kiểm tra TK thay thế VHV
                if data.get('is_substituting_vhv', False):
                    tk_substitute_count += 1
                
                # Tổng công đã có
                total_credits = training_credits + line_inspection_credits + business_credits + shifts_done
                
                # Kiểm tra nếu dưới 17 công
                if total_credits < 17:
                    under_17_count += 1
                    status = "❌"
                else:
                    status = "✅"
                
                # Công còn lại cần đạt 17
                remaining_credits = 17 - total_credits
                
                diff = day_shifts - night_shifts
                diff_status = "✅" if abs(diff) <= 2 else "⚠️"
                
                # Kiểm tra vai trò thay thế
                role_info = data['role']
                if data.get('is_substituting_vhv', False):
                    role_info = f"{role_info} (thay VHV)"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': role_info,
                    'Mục tiêu': 17,
                    'Đào tạo': training_credits,
                    'Kiểm tra': line_inspection_credits,
                    'Công tác': business_credits,
                    'Đã trực': shifts_done,
                    'Ca ngày': day_shifts,
                    'Ca đêm': night_shifts,
                    'Mục tiêu ca đêm': night_goal,
                    'Đạt ca đêm': night_goal_status,
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
            
            # Tô màu cho trạng thái đạt ca đêm
            def color_night_goal(val):
                if val == "✅":
                    return 'background-color: #e6ffe6; color: green;'
                elif val == "⚠️":
                    return 'background-color: #fff0cc; color: #e68a00;'
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
                .applymap(color_night_goal, subset=['Đạt ca đêm']) \
                .applymap(color_diff, subset=['Chênh lệch (N-Đ)']) \
                .applymap(color_remaining, subset=['Còn thiếu'])
            
            st.dataframe(styled_stats, use_container_width=True)
            
            # Thống kê TK thay thế VHV
            if tk_substitute_count > 0:
                st.info(f"📌 **LƯU Ý**: Có {tk_substitute_count} Trưởng kiếp đã thay thế Vận hành viên do thiếu nhân sự.")
            
            # Thống kê mục tiêu ca đêm
            st.subheader("🌙 Thống kê mục tiêu ca đêm")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Đạt mục tiêu ca đêm", f"{night_goal_achieved}/{len(all_staff)}")
            with col2:
                total_night_goals = sum(data.get('night_shift_goal', 0) for data in st.session_state.staff_stats.values())
                total_night_shifts = sum(data['night_shifts'] for data in st.session_state.staff_stats.values())
                st.metric("Tổng ca đêm thực tế", f"{total_night_shifts}/{total_night_goals}")
            with col3:
                avg_night_goal = total_night_goals / len(all_staff) if len(all_staff) > 0 else 0
                avg_night_actual = total_night_shifts / len(all_staff) if len(all_staff) > 0 else 0
                st.metric("TB ca đêm/người", f"{avg_night_actual:.1f}/{avg_night_goal:.1f}")
            
            # Cảnh báo đặc biệt khi không có công tác nhưng có người chưa đủ 17 công
            if not has_business_trip and under_17_count > 0:
                st.error(f"❌ **LỖI HỆ THỐNG**: Không có ai đi công tác nhưng có {under_17_count} người chưa đạt 17 công!")
                st.info("""
                **Nguyên nhân:**
                1. Quá nhiều ngày nghỉ/kiểm tra đường dây
                2. Số ca trực trong tháng không đủ phân bổ
                3. Xung đột lịch trình nghiêm trọng
                
                **Giải pháp khẩn cấp:**
                - Giảm số ngày nghỉ (tối đa 5 ngày/người)
                - Giảm số nhóm kiểm tra đường dây
                - Bật chế độ TK thay thế VHV
                - Điều chỉnh ngày đào tạo
                """)
            elif under_17_count > 0:
                st.warning(f"⚠️ **CẢNH BÁO**: Có {under_17_count} người chưa đạt 17 công/tháng!")
            
            # Tính toán thống kê cân bằng
            st.subheader("📊 Thống kê cân bằng ca")
            
            balance_stats = []
            for staff, data in st.session_state.staff_stats.items():
                diff = abs(data['day_shifts'] - data['night_shifts'])
                balance_stats.append({
                    'Nhân viên': staff,
                    'Ca ngày': data['day_shifts'],
                    'Ca đêm': data['night_shifts'],
                    'Chênh lệch tuyệt đối': diff,
                    'Trạng thái': 'Cân bằng' if diff <= 2 else 'Chưa cân bằng'
                })
            
            df_balance = pd.DataFrame(balance_stats)
            
            # Đếm số người cân bằng
            balanced_count = sum(1 for stat in balance_stats if stat['Chênh lệch tuyệt đối'] <= 2)
            total_count = len(balance_stats)
            balance_percentage = (balanced_count / total_count) * 100 if total_count > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Người cân bằng", f"{balanced_count}/{total_count}")
            with col2:
                st.metric("Tỷ lệ cân bằng", f"{balance_percentage:.1f}%")
            with col3:
                avg_diff = sum(stat['Chênh lệch tuyệt đối'] for stat in balance_stats) / total_count
                st.metric("Chênh lệch TB", f"{avg_diff:.1f}")
            
            st.dataframe(df_balance, use_container_width=True)
            
            # Tóm tắt phân công
            st.subheader("📋 Tóm tắt phân công")
            col1, col2, col3, col4 = st.columns(4)
            
            total_shifts = sum(data['total_shifts'] for data in st.session_state.staff_stats.values())
            total_target = 17 * len(all_staff)
            total_training = len(all_staff)
            total_business = sum(len(data['business_trip_days']) for data in st.session_state.staff_stats.values())
            total_inspection = sum(len(data['line_inspection_days']) for data in st.session_state.staff_stats.values())
            total_day_shifts = sum(data['day_shifts'] for data in st.session_state.staff_stats.values())
            total_night_shifts = sum(data['night_shifts'] for data in st.session_state.staff_stats.values())
            
            # Tính tổng công thực tế
            total_business_credits = total_business * 1
            total_inspection_credits = total_inspection
            total_actual = total_shifts + total_training + total_business_credits + total_inspection_credits
            
            with col1:
                st.metric("Tổng ca trực", total_shifts)
            with col2:
                st.metric("Ngày công tác", f"{total_business} ({total_business_credits} công)")
            with col3:
                st.metric("Nhóm kiểm tra", f"{total_inspection} ({total_inspection_credits} công)")
            with col4:
                completion_rate = (total_actual / total_target) * 100 if total_target > 0 else 0
                status_color = "normal"
                if not has_business_trip and completion_rate < 100:
                    status_color = "off"
                elif has_business_trip and completion_rate < 95:
                    status_color = "off"
                st.metric("Hoàn thành mục tiêu", f"{completion_rate:.1f}%", delta=None, delta_color=status_color)
        else:
            st.info("👈 Vui lòng tạo lịch trực ở Tab 2")

    with tab4:
        st.subheader("📱 Lịch trực dạng ngang theo nhân viên")
        st.markdown("**Cột dọc: Nhân viên | Cột ngang: Ngày trong tháng**")
        
        if st.session_state.schedule_created and st.session_state.staff_horizontal_schedule is not None:
            # Hiển thị lịch ngang theo nhân viên
            df_staff_horizontal = st.session_state.staff_horizontal_schedule
            
            # Tạo một bản sao để hiển thị
            display_df = df_staff_horizontal.copy()
            
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
            
            # Hiển thị DataFrame với chiều cao tự động
            st.dataframe(
                display_df,
                use_container_width=True,
                height=min(600, 150 + len(display_df) * 35)
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Hiển thị chú thích
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Ký hiệu:**
                - **TK**: Trưởng kiếp
                - **VHV**: Vận hành viên
                - **N**: Ca ngày (6h-18h)
                - **Đ**: Ca đêm (18h-6h)
                - **ĐT**: Đào tạo nội bộ (hành chính)
                - **N (ĐT)**: Trực ca ngày + Đào tạo
                - **Đ (ĐT)**: Trực ca đêm + Đào tạo
                - **KT**: Kiểm tra đường dây
                - **CT**: Công tác
                - **Nghỉ**: Ngày nghỉ
                - **-**: Không có hoạt động
                - **T2-CN**: Thứ trong tuần
                """)
            
            with col2:
                st.markdown("""
                **QUY TẮC CỨNG:**
                - **Tổng công: 17 công/người/tháng (BẮT BUỘC)**
                - **TK chỉ thay TK, VHV chỉ thay VHV**
                - **Chỉ khi khó khăn: TK có thể thay VHV**
                - **Khi không có công tác: Mọi người đều đủ 17 công**
                - Công đào tạo: 1 công (ĐT) - tất cả đều có
                - Công kiểm tra: 1 công/ngày (KT)
                - Công công tác: 1 công/ngày (CT)
                - Công trực ca: 1 công/ca (N hoặc Đ)
                - Ngày đào tạo: vẫn có ca trực bình thường
                - Mỗi nhân viên nghỉ tối đa 5 ngày/tháng
                """)
            
            # Nút tải xuống lịch ngang
            st.markdown("---")
            csv_horizontal = df_staff_horizontal.to_csv(encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải lịch ngang theo nhân viên (CSV)",
                data=csv_horizontal,
                file_name=f"lich_truc_ngang_nhan_vien_TBA_500kV_{month}_{year}.csv",
                mime="text/csv",
                use_container_width=True,
                key="tab4_download_horizontal_csv"
            )
        else:
            st.info("👈 Vui lòng tạo lịch trực ở Tab 2 trước")

    with tab5:
        st.subheader("🚨 Điều chỉnh lịch khi có công tác đột xuất")
        st.markdown("**Giữ nguyên các ngày đã trực, chỉ thay đổi các ngày tiếp theo**")
        
        if st.session_state.schedule_created and st.session_state.schedule_data:
            # Hiển thị thông tin hiện tại
            st.info("📋 **LỊCH HIỆN TẠI ĐÃ ĐƯỢC TẠO**")
            
            # Chọn nhân viên đi công tác đột xuất
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Chọn nhân viên công tác đột xuất")
                emergency_staff = st.selectbox(
                    "Chọn nhân viên đi công tác đột xuất",
                    options=all_staff,
                    key="tab5_emergency_staff"
                )
                
                # Hiển thị thông tin nhân viên được chọn
                if emergency_staff in st.session_state.staff_stats:
                    data = st.session_state.staff_stats[emergency_staff]
                    st.info(f"""
                    **Thông tin {emergency_staff}:**
                    - Vai trò: {data['role']}
                    - Đã trực: {data['total_shifts']} ca
                    - Công đã có: {data['current_total_credits']}/17
                    - Ngày công tác hiện tại: {len(data['business_trip_days'])} ngày
                    """)
            
            with col2:
                st.subheader("Chọn thời gian công tác")
                
                # Xác định ngày bắt đầu (từ ngày mai)
                today = date.today()
                if month == today.month and year == today.year:
                    min_start = today.day + 1
                else:
                    min_start = 1
                
                start_day = st.number_input(
                    "Ngày bắt đầu công tác",
                    min_value=min_start,
                    max_value=num_days,
                    value=min_start,
                    key="tab5_start_day"
                )
                
                end_day = st.number_input(
                    "Ngày kết thúc công tác",
                    min_value=start_day,
                    max_value=num_days,
                    value=min(start_day + 2, num_days),
                    key="tab5_end_day"
                )
                
                # Kiểm tra xem ngày đã chọn có hợp lệ không
                if start_day <= end_day:
                    duration = end_day - start_day + 1
                    st.info(f"Thời gian công tác: {duration} ngày (từ ngày {start_day} đến ngày {end_day})")
                    
                    # Kiểm tra xem nhân viên đã có lịch trực trong khoảng thời gian này chưa
                    conflicts = []
                    for shift in st.session_state.schedule_data:
                        if start_day <= shift['Ngày'] <= end_day:
                            if shift['Trưởng kiếp'] == emergency_staff or shift['Vận hành viên'] == emergency_staff:
                                conflicts.append(f"Ngày {shift['Ngày']}: {shift['Ca']}")
                    
                    if conflicts:
                        st.error(f"⚠️ **XUNG ĐỘT LỊCH TRỰC**: {emergency_staff} đã có lịch trực trong các ngày:")
                        for conflict in conflicts:
                            st.error(f"- {conflict}")
                        st.warning("Vui lòng chọn khoảng thời gian khác hoặc điều chỉnh lịch trực.")
                    else:
                        st.success("✅ Khoảng thời gian công tác hợp lệ (không xung đột với lịch trực hiện tại)")
            
            # Nút điều chỉnh lịch
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Điều chỉnh lịch", type="primary", use_container_width=True, key="tab5_adjust_schedule_btn"):
                    # Kiểm tra xung đột
                    conflicts = []
                    for shift in st.session_state.schedule_data:
                        if start_day <= shift['Ngày'] <= end_day:
                            if shift['Trưởng kiếp'] == emergency_staff or shift['Vận hành viên'] == emergency_staff:
                                conflicts.append(f"Ngày {shift['Ngày']}: {shift['Ca']}")
                    
                    if conflicts:
                        st.error("Không thể điều chỉnh vì có xung đột lịch trực!")
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
                            
                            st.success(f"✅ Đã điều chỉnh lịch thành công cho {emergency_staff} đi công tác từ ngày {start_day} đến {end_day}!")
                            
                            # Hiển thị thay đổi
                            st.info(f"**THAY ĐỔI ĐÃ THỰC HIỆN:**")
                            st.write(f"- {emergency_staff} đi công tác từ ngày {start_day} đến {end_day}")
                            st.write(f"- Giữ nguyên lịch trực trước ngày {start_day}")
                            st.write(f"- Điều chỉnh lịch trực từ ngày {start_day} đến hết tháng")
                            
                            # Kiểm tra xem có người nào chưa đạt 17 công không
                            under_17 = []
                            for staff, data in new_stats.items():
                                total_credits = data['admin_credits'] + data['total_shifts']
                                if total_credits < 17:
                                    under_17.append((staff, total_credits))
                            
                            if under_17:
                                st.warning(f"⚠️ Sau khi điều chỉnh, có {len(under_17)} người chưa đạt 17 công:")
                                for staff, credits in under_17:
                                    st.warning(f"- {staff}: {credits}/17 công")
            
            with col2:
                if st.session_state.original_schedule is not None:
                    if st.button("↩️ Khôi phục lịch gốc", type="secondary", use_container_width=True, key="tab5_restore_schedule_btn"):
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
                        
                        st.success("✅ Đã khôi phục lịch gốc thành công!")
            
            # Hiển thị phần lịch bị ảnh hưởng
            st.markdown("---")
            st.subheader("📋 Lịch trực bị ảnh hưởng bởi điều chỉnh")
            
            if 'new_schedule' in locals():
                # Hiển thị các ca từ ngày bắt đầu điều chỉnh
                affected_shifts = [shift for shift in st.session_state.schedule_data if shift['Ngày'] >= start_day]
                
                if affected_shifts:
                    df_affected = pd.DataFrame(affected_shifts)
                    st.dataframe(df_affected, use_container_width=True, height=300)
                    
                    st.info(f"**Tổng cộng:** {len(affected_shifts)} ca đã được điều chỉnh từ ngày {start_day}")
                else:
                    st.info("Chưa có thay đổi nào được thực hiện.")
            
            # Hướng dẫn
            st.markdown("---")
            st.info("""
            **HƯỚNG DẪN ĐIỀU CHỈNH CÔNG TÁC ĐỘT XUẤT:**
            1. Chọn nhân viên đi công tác đột xuất
            2. Chọn ngày bắt đầu và kết thúc công tác
            3. Hệ thống tự động kiểm tra xung đột với lịch trực hiện tại
            4. Nhấn "Điều chỉnh lịch" để thực hiện thay đổi
            5. Hệ thống sẽ:
               - Giữ nguyên tất cả các ca trực trước ngày bắt đầu công tác
               - Xóa các ca trực của nhân viên đi công tác trong khoảng thời gian này
               - Tái xếp lịch từ ngày bắt đầu đến cuối tháng
               - Đảm bảo vẫn tuân thủ tất cả các quy tắc xếp lịch
            6. Có thể khôi phục về lịch gốc bất kỳ lúc nào
            """)
        else:
            st.info("👈 Vui lòng tạo lịch trực ở Tab 2 trước khi thực hiện điều chỉnh")

    # Footer
    st.markdown("---")
    st.caption("""
    **Hệ thống xếp lịch trực TBA 500kV - Phiên bản 12.0 - HỖ TRỢ ĐIỀU CHỈNH ĐỘT XUẤT**  
    *Mỗi người: 17 công/tháng = 1 công đào tạo + công kiểm tra + công công tác + công trực ca*  
    **QUY TẮC CỨNG:** TK chỉ thay TK, VHV chỉ thay VHV (trừ khi khó khăn)  
    **BẮT BUỘC:** Khi không có công tác, mọi người phải đủ 17 công  
    **ĐIỀU CHỈNH ĐỘT XUẤT:** Giữ nguyên các ngày đã trực, chỉ thay đổi các ngày tiếp theo  
    *Ngày đào tạo: vẫn có ca trực bình thường*  
    *Có thể đặt mục tiêu số ca đêm mong muốn*  
    *Ưu tiên đạt 17 công trước các yêu cầu khác*
    """)

except Exception as e:
    st.error(f"Đã xảy ra lỗi trong ứng dụng: {str(e)}")
    with st.expander("Chi tiết lỗi (dành cho nhà phát triển)"):
        st.code(traceback.format_exc())
    st.info("Vui lòng làm mới trang và thử lại. Nếu lỗi vẫn tiếp tục, hãy liên hệ với quản trị viên.")