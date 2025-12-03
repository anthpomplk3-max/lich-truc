import streamlit as st
import pandas as pd
import calendar
import numpy as np
from datetime import datetime
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
    if 'day_off' not in st.session_state:
        st.session_state.day_off = {staff: [] for staff in all_staff}
    if 'business_trip' not in st.session_state:
        st.session_state.business_trip = {staff: [] for staff in all_staff}
    if 'line_inspection' not in st.session_state:
        st.session_state.line_inspection = []

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
        
        st.markdown("---")
        st.header("Hướng dẫn")
        st.info("""
        **Quy tắc xếp lịch:**
        1. Mỗi ca: 1 Trưởng kiếp + 1 Vận hành viên
        2. Tổng công: 17 công/người/tháng (bao gồm công đào tạo, kiểm tra, công tác và trực ca)
        3. Không làm việc 24h liên tục
        4. Tối đa 3 ca đêm liên tiếp
        5. Ngày đào tạo: tất cả có mặt (tính 1 công hành chính)
        6. Người công tác: không tham gia trực (mỗi ngày công tác = 1 công)
        7. Kiểm tra đường dây: 1 TK + 1 VHV đi 1 ngày (tính 1 công hành chính)
        8. Cân bằng ca: chênh lệch ca ngày/đêm ≤ 2
        9. Người đi công tác khi về vẫn có thể tăng ca bình thường
        """)

    # Hàm chuyển đổi lịch sang dạng ngang
    def convert_to_horizontal_schedule(schedule_data, num_days, year, month, line_inspection_groups):
        """Chuyển lịch trực từ dạng dọc sang dạng ngang"""
        horizontal_data = {}
        
        # Tạo dictionary để tra cứu ngày kiểm tra đường dây
        line_inspection_days = {}
        for group in line_inspection_groups:
            if group['tk'] and group['vhv'] and group['day']:
                day = group['day']
                if day not in line_inspection_days:
                    line_inspection_days[day] = []
                line_inspection_days[day].append(f"{group['tk']} & {group['vhv']}")
        
        # Khởi tạo cấu trúc dữ liệu
        for day in range(1, num_days + 1):
            day_key = f"Ngày {day}"
            horizontal_data[day_key] = {
                'Ca ngày (N) - TK': '',
                'Ca ngày (N) - VHV': '',
                'Ca đêm (Đ) - TK': '',
                'Ca đêm (Đ) - VHV': '',
                'Ghi chú': ''
            }
            
            # Thêm ghi chú cho ngày kiểm tra đường dây
            if day in line_inspection_days:
                groups_info = ", ".join(line_inspection_days[day])
                horizontal_data[f"Ngày {day}"]['Ghi chú'] = f"Kiểm tra: {groups_info}"
        
        # Điền dữ liệu vào bảng ngang
        for schedule in schedule_data:
            day = schedule['Ngày']
            shift_type = schedule['Ca']
            
            if shift_type == 'Đào tạo':
                horizontal_data[f"Ngày {day}"]['Ghi chú'] = 'ĐÀO TẠO'
                horizontal_data[f"Ngày {day}"]['Ca ngày (N) - TK'] = 'TẤT CẢ'
                horizontal_data[f"Ngày {day}"]['Ca ngày (N) - VHV'] = 'TẤT CẢ'
                horizontal_data[f"Ngày {day}"]['Ca đêm (Đ) - TK'] = 'TẤT CẢ'
                horizontal_data[f"Ngày {day}"]['Ca đêm (Đ) - VHV'] = 'TẤT CẢ'
            elif 'Ngày' in shift_type:
                horizontal_data[f"Ngày {day}"]['Ca ngày (N) - TK'] = schedule['Trưởng kiếp']
                horizontal_data[f"Ngày {day}"]['Ca ngày (N) - VHV'] = schedule['Vận hành viên']
            elif 'Đêm' in shift_type:
                horizontal_data[f"Ngày {day}"]['Ca đêm (Đ) - TK'] = schedule['Trưởng kiếp']
                horizontal_data[f"Ngày {day}"]['Ca đêm (Đ) - VHV'] = schedule['Vận hành viên']
        
        # Chuyển đổi sang DataFrame
        df_horizontal = pd.DataFrame(horizontal_data).T
        
        # Thêm cột Thứ
        days_of_week = []
        for day in range(1, num_days + 1):
            weekday = calendar.day_name[calendar.weekday(year, month, day)]
            # Viết tắt tên thứ
            vietnamese_days = {
                'Monday': 'T2', 'Tuesday': 'T3', 'Wednesday': 'T4',
                'Thursday': 'T5', 'Friday': 'T6', 'Saturday': 'T7', 'Sunday': 'CN'
            }
            days_of_week.append(vietnamese_days.get(weekday, weekday))
        
        df_horizontal.insert(0, 'Thứ', days_of_week)
        df_horizontal.index.name = 'Ngày'
        
        return df_horizontal

    # Thuật toán xếp lịch nâng cao với cân bằng ca và kiểm tra đường dây
    def generate_advanced_schedule(month, year, training_day, day_off_dict, business_trip_dict, line_inspection_groups, balance_shifts=True):
        """Tạo lịch trực tự động với các ràng buộc nâng cao và cân bằng ca"""
        num_days = calendar.monthrange(year, month)[1]
        schedule = []
        
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
            staff_data[staff] = {
                'role': 'TK' if staff in truong_kiep else 'VHV',
                'total_shifts': 0,
                'day_shifts': 0,
                'night_shifts': 0,
                'consecutive_night': 0,
                'last_shift': None,
                'last_shift_day': None,
                'target_shifts': 0,  # Sẽ được tính lại dựa trên các loại công
                'unavailable_days': set(day_off_dict.get(staff, []) + business_trip_dict.get(staff, [])),
                'business_trip_days': set(business_trip_dict.get(staff, [])),
                'line_inspection_days': line_inspection_dict[staff],
                'day_night_diff': 0,
                'last_assigned_day': None,
                'training_day_present': True,  # Tất cả đều có mặt ngày đào tạo
            }
            
            # Thêm ngày kiểm tra đường dây vào unavailable_days
            staff_data[staff]['unavailable_days'].update(line_inspection_dict[staff])
        
        # Điều chỉnh mục tiêu dựa trên các loại công
        for staff in all_staff:
            # Các loại công cố định
            training_credits = 1  # Công đào tạo (hành chính)
            
            # Công kiểm tra đường dây
            line_inspection_days = len(staff_data[staff]['line_inspection_days'])
            line_inspection_credits = line_inspection_days * 1  # Mỗi ngày kiểm tra = 1 công
            
            # Công đi công tác (CHỈ TÍNH 1 CÔNG/NGÀY)
            business_days = len(staff_data[staff]['business_trip_days'])
            business_credits = business_days * 1  # Mỗi ngày công tác = 1 công (thay vì 2)
            
            # Tổng công hành chính (không trực)
            admin_credits = training_credits + line_inspection_credits + business_credits
            
            # Công trực ca cần đạt
            # Tổng 17 công = công hành chính + công trực ca
            # Vậy công trực ca cần = 17 - công hành chính
            required_shift_credits = 17 - admin_credits
            
            # Đảm bảo không âm (trong trường hợp công hành chính đã đủ 17)
            staff_data[staff]['target_shifts'] = max(0, required_shift_credits)
            
            # Lưu thông tin để hiển thị
            staff_data[staff]['training_credits'] = training_credits
            staff_data[staff]['line_inspection_credits'] = line_inspection_credits
            staff_data[staff]['business_credits'] = business_credits
            staff_data[staff]['admin_credits'] = admin_credits
        
        # Phân bổ thêm công trực cho những người không đi công tác
        # Nếu có người đi công tác, những người cùng vai trò sẽ tăng ca
        for role_group, role_name in [(truong_kiep, 'TK'), (van_hanh_vien, 'VHV')]:
            # Tính tổng công trực cần của nhóm
            total_required_shifts = sum(staff_data[staff]['target_shifts'] for staff in role_group)
            
            # Tính số ca trực có sẵn trong tháng (trừ ngày đào tạo, nghỉ, công tác, kiểm tra)
            available_days = []
            for day in range(1, num_days + 1):
                if day != training_day:  # Ngày đào tạo không trực
                    # Đếm số người trong nhóm có thể trực ngày này
                    available_count = 0
                    for staff in role_group:
                        if day not in staff_data[staff]['unavailable_days']:
                            available_count += 1
                    if available_count >= 1:  # Cần ít nhất 1 người để trực
                        # Có 2 ca mỗi ngày
                        available_days.append(day)
            
            total_available_shifts = len(available_days) * 2  # 2 ca mỗi ngày
            
            # Nếu tổng công trực cần > số ca có sẵn, cần điều chỉnh
            if total_required_shifts > total_available_shifts:
                # Giảm công trực của từng người theo tỷ lệ
                for staff in role_group:
                    if staff_data[staff]['target_shifts'] > 0:
                        staff_data[staff]['target_shifts'] = int(
                            staff_data[staff]['target_shifts'] * total_available_shifts / total_required_shifts
                        )
            
            # Nếu có người đi công tác, những người còn lại tăng ca
            staff_with_business_trip = [s for s in role_group if len(staff_data[s]['business_trip_days']) > 0]
            if staff_with_business_trip:
                # Tính tổng công trực cần bù (vẫn là 2 ca cho mỗi ngày công tác vì không thể trực)
                total_shift_deficit = 0
                for staff in staff_with_business_trip:
                    # Mỗi ngày công tác làm giảm 2 ca trực (ngày + đêm)
                    business_days = len(staff_data[staff]['business_trip_days'])
                    total_shift_deficit += business_days * 2
                
                # Phân bổ cho những người không đi công tác
                staff_without_business = [s for s in role_group if len(staff_data[s]['business_trip_days']) == 0]
                if staff_without_business and total_shift_deficit > 0:
                    additional_shifts_per_person = max(1, total_shift_deficit // len(staff_without_business))
                    for staff in staff_without_business:
                        staff_data[staff]['target_shifts'] += additional_shifts_per_person
        
        # Tạo danh sách ngày cần xếp lịch (trừ ngày đào tạo)
        working_days = [day for day in range(1, num_days + 1) if day != training_day]
        
        # Thêm ngày đào tạo vào lịch
        weekday_name = calendar.day_name[calendar.weekday(year, month, training_day)]
        schedule.append({
            'Ngày': training_day,
            'Thứ': weekday_name,
            'Ca': 'Đào tạo',
            'Trưởng kiếp': 'Tất cả',
            'Vận hành viên': 'Tất cả',
            'Ghi chú': 'Đào tạo nội bộ'
        })
        
        # Tạo lịch cho từng ngày làm việc
        for day in working_days:
            # Xác định xem có phải ngày cuối tháng không (3 ngày cuối)
            last_days_mode = (day > num_days - 3)
            
            # Xử lý ca ngày trước
            available_tk_day = [tk for tk in truong_kiep 
                              if day not in staff_data[tk]['unavailable_days']]
            available_vhv_day = [vhv for vhv in van_hanh_vien 
                               if day not in staff_data[vhv]['unavailable_days']]
            
            if available_tk_day and available_vhv_day:
                selected_tk = select_staff_for_shift(
                    available_tk_day, staff_data, day, 'day', 'TK', balance_shifts, last_days_mode
                )
                selected_vhv = select_staff_for_shift(
                    available_vhv_day, staff_data, day, 'day', 'VHV', balance_shifts, last_days_mode
                )
                
                if selected_tk and selected_vhv:
                    # Cập nhật thông tin
                    update_staff_data(staff_data, selected_tk, day, 'day')
                    update_staff_data(staff_data, selected_vhv, day, 'day')
                    
                    weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                    schedule.append({
                        'Ngày': day,
                        'Thứ': weekday_name,
                        'Ca': 'Ngày (6h-18h)',
                        'Trưởng kiếp': selected_tk,
                        'Vận hành viên': selected_vhv,
                        'Ghi chú': ''
                    })
                elif last_days_mode:
                    # Trong ngày cuối tháng, nếu không xếp được ca ngày, thử với chế độ khẩn cấp
                    selected_tk = select_staff_for_shift_emergency(
                        available_tk_day, staff_data, day, 'day', 'TK'
                    )
                    selected_vhv = select_staff_for_shift_emergency(
                        available_vhv_day, staff_data, day, 'day', 'VHV'
                    )
                    if selected_tk and selected_vhv:
                        update_staff_data(staff_data, selected_tk, day, 'day')
                        update_staff_data(staff_data, selected_vhv, day, 'day')
                        weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                        schedule.append({
                            'Ngày': day,
                            'Thứ': weekday_name,
                            'Ca': 'Ngày (6h-18h)',
                            'Trưởng kiếp': selected_tk,
                            'Vận hành viên': selected_vhv,
                            'Ghi chú': '(Khẩn cấp)'
                        })
            
            # Xử lý ca đêm
            # Kiểm tra không làm 24h liên tục
            available_tk_night = [tk for tk in truong_kiep 
                                if day not in staff_data[tk]['unavailable_days']
                                and not (staff_data[tk]['last_shift'] == 'day' and staff_data[tk]['last_shift_day'] == day)]
            
            available_vhv_night = [vhv for vhv in van_hanh_vien 
                                 if day not in staff_data[vhv]['unavailable_days']
                                 and not (staff_data[vhv]['last_shift'] == 'day' and staff_data[vhv]['last_shift_day'] == day)]
            
            if available_tk_night and available_vhv_night:
                selected_tk_night = select_staff_for_shift(
                    available_tk_night, staff_data, day, 'night', 'TK', balance_shifts, last_days_mode
                )
                selected_vhv_night = select_staff_for_shift(
                    available_vhv_night, staff_data, day, 'night', 'VHV', balance_shifts, last_days_mode
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
                    schedule.append({
                        'Ngày': day,
                        'Thứ': weekday_name,
                        'Ca': 'Đêm (18h-6h)',
                        'Trưởng kiếp': selected_tk_night,
                        'Vận hành viên': selected_vhv_night,
                        'Ghi chú': ''
                    })
                elif last_days_mode:
                    # Trong ngày cuối tháng, nếu không xếp được ca đêm, thử với chế độ khẩn cấp
                    selected_tk_night = select_staff_for_shift_emergency(
                        available_tk_night, staff_data, day, 'night', 'TK'
                    )
                    selected_vhv_night = select_staff_for_shift_emergency(
                        available_vhv_night, staff_data, day, 'night', 'VHV'
                    )
                    if selected_tk_night and selected_vhv_night:
                        update_staff_data(staff_data, selected_tk_night, day, 'night')
                        update_staff_data(staff_data, selected_vhv_night, day, 'night')
                        weekday_name = calendar.day_name[calendar.weekday(year, month, day)]
                        schedule.append({
                            'Ngày': day,
                            'Thứ': weekday_name,
                            'Ca': 'Đêm (18h-6h)',
                            'Trưởng kiếp': selected_tk_night,
                            'Vận hành viên': selected_vhv_night,
                            'Ghi chú': '(Khẩn cấp)'
                        })
        
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

    def select_staff_for_shift(available_staff, staff_data, day, shift_type, role, balance_shifts=True, last_days_mode=False):
        """Chọn nhân viên phù hợp cho ca làm việc với cân bằng ca ngày/đêm"""
        if not available_staff:
            return None
        
        # Chế độ ngày cuối tháng: ưu tiên hoàn thành mục tiêu
        if last_days_mode:
            filtered_staff = []
            for staff in available_staff:
                data = staff_data[staff]
                
                # Kiểm tra không làm 24h liên tục (vẫn phải giữ)
                if shift_type == 'night' and data['last_shift'] == 'day' and data['last_shift_day'] == day:
                    continue
                
                # Trong ngày cuối, cho phép vượt mục tiêu một chút nếu cần
                if data['total_shifts'] >= data['target_shifts'] + 2:  # Cho phép vượt tối đa 2 ca
                    continue
                
                # Kiểm tra ca đêm liên tiếp (nới lỏng trong ngày cuối)
                if shift_type == 'night' and data['consecutive_night'] >= 4:  # Cho phép 4 ca đêm liên tiếp
                    continue
                
                filtered_staff.append(staff)
            
            if filtered_staff:
                # Sắp xếp ưu tiên: người còn thiếu nhiều công nhất
                filtered_staff.sort(key=lambda x: (
                    staff_data[x]['target_shifts'] - staff_data[x]['total_shifts'],  # Ưu tiên người còn thiếu nhiều
                    staff_data[x]['total_shifts'],  # Sau đó ưu tiên người ít ca
                    random.random()
                ))
                return filtered_staff[0]
        
        # Chế độ bình thường
        filtered_staff = []
        for staff in available_staff:
            data = staff_data[staff]
            
            # Kiểm tra đã đạt mục tiêu chưa
            if data['total_shifts'] >= data['target_shifts']:
                continue
            
            # Kiểm tra ca đêm liên tiếp
            if shift_type == 'night' and data['consecutive_night'] >= 3:
                continue
            
            # Kiểm tra không làm 24h liên tục
            if shift_type == 'night' and data['last_shift'] == 'day' and data['last_shift_day'] == day:
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
            # Nếu không có ai phù hợp, thử lại mà không kiểm tra cân bằng ca
            for staff in available_staff:
                data = staff_data[staff]
                
                if data['total_shifts'] >= data['target_shifts']:
                    continue
                
                if shift_type == 'night' and data['consecutive_night'] >= 3:
                    continue
                
                if shift_type == 'night' and data['last_shift'] == 'day' and data['last_shift_day'] == day:
                    continue
                
                filtered_staff.append(staff)
        
        if not filtered_staff:
            return None
        
        # Sắp xếp ưu tiên theo nhiều tiêu chí
        filtered_staff.sort(key=lambda x: (
            # Ưu tiên 1: Người ít ca tổng nhất
            staff_data[x]['total_shifts'],
            # Ưu tiên 2: Còn cách mục tiêu xa
            -abs(staff_data[x]['target_shifts'] - staff_data[x]['total_shifts']),
            # Ưu tiên 3: Cân bằng ca
            calculate_shift_balance_score(staff_data[x], shift_type, balance_shifts),
            # Ưu tiên 4: Người lâu chưa được phân công nhất
            0 if staff_data[x]['last_assigned_day'] is None else (day - staff_data[x]['last_assigned_day']),
            # Ưu tiên 5: Ngẫu nhiên để tránh pattern cố định
            random.random()
        ))
        
        return filtered_staff[0]

    def select_staff_for_shift_emergency(available_staff, staff_data, day, shift_type, role):
        """Chọn nhân viên trong trường hợp khẩn cấp (ngày cuối tháng)"""
        if not available_staff:
            return None
        
        # Trong trường hợp khẩn cấp, chỉ giữ điều kiện không làm 24h liên tục
        filtered_staff = []
        for staff in available_staff:
            data = staff_data[staff]
            
            # Chỉ kiểm tra không làm 24h liên tục
            if shift_type == 'night' and data['last_shift'] == 'day' and data['last_shift_day'] == day:
                continue
            
            filtered_staff.append(staff)
        
        if not filtered_staff:
            return None
        
        # Ưu tiên người ít ca nhất
        filtered_staff.sort(key=lambda x: (
            staff_data[x]['total_shifts'],
            random.random()
        ))
        
        return filtered_staff[0]

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
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Chọn ngày nghỉ & Công tác & Kiểm tra", 
        "📊 Xếp lịch tự động", 
        "📋 Thống kê", 
        "📱 Xem lịch ngang"
    ])

    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Chọn ngày nghỉ & Công tác")
            
            # Tạo 2 cột cho 2 loại nhân viên
            col_tk, col_vhv = st.columns(2)
            
            with col_tk:
                st.markdown("### Trưởng kiếp")
                for idx, tk in enumerate(truong_kiep):
                    with st.expander(f"**{tk}**", expanded=False):
                        # Tạo key duy nhất cho mỗi widget
                        days_off_key = f"off_tk_{idx}_{month}_{year}"
                        business_key = f"business_tk_{idx}_{month}_{year}"
                        
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
                        
                        st.caption(f"Ngày nghỉ: {len(days_off)}/5 | Công tác: {len(business_days)}")
            
            with col_vhv:
                st.markdown("### Vận hành viên")
                for idx, vhv in enumerate(van_hanh_vien):
                    with st.expander(f"**{vhv}**", expanded=False):
                        # Tạo key duy nhất cho mỗi widget
                        days_off_key = f"off_vhv_{idx}_{month}_{year}"
                        business_key = f"business_vhv_{idx}_{month}_{year}"
                        
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
                        
                        st.caption(f"Ngày nghỉ: {len(days_off)}/5 | Công tác: {len(business_days)}")
        
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

    with tab2:
        st.subheader("Tạo lịch trực tự động")
        
        # Sử dụng giá trị từ sidebar
        balance_shifts_value = balance_shifts_option
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🎯 Tạo lịch trực tự động", type="primary", use_container_width=True, key="tab2_generate_schedule_btn"):
                with st.spinner("Đang tạo lịch trực với cân bằng ca và kiểm tra đường dây..."):
                    day_off_dict = st.session_state.day_off
                    business_trip_dict = st.session_state.business_trip
                    line_inspection_groups = [g for g in st.session_state.line_inspection 
                                             if g['tk'] and g['vhv'] and g['day']]
                    
                    schedule, staff_data = generate_advanced_schedule(
                        month, year, training_day, day_off_dict, 
                        business_trip_dict, line_inspection_groups, balance_shifts_value
                    )
                    
                    # Tạo lịch ngang
                    horizontal_schedule = convert_to_horizontal_schedule(
                        schedule, num_days, year, month, line_inspection_groups
                    )
                    
                    # Lưu vào session state
                    st.session_state.schedule_data = schedule
                    st.session_state.staff_stats = staff_data
                    st.session_state.horizontal_schedule = horizontal_schedule
                    st.session_state.schedule_created = True
                    
                    st.success("✅ Đã tạo lịch trực thành công!")
        
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
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Tổng nhân sự", len(all_staff))
        
        with col2:
            st.metric("Trưởng kiếp", len(truong_kiep))
        
        with col3:
            st.metric("Vận hành viên", len(van_hanh_vien))
        
        with col4:
            st.metric("Ngày đào tạo", f"Ngày {training_day}")
        
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
            for staff, data in st.session_state.staff_stats.items():
                # Tính các loại công
                training_credits = data.get('training_credits', 1)  # Công đào tạo
                line_inspection_credits = data.get('line_inspection_credits', 0)  # Công kiểm tra
                business_credits = data.get('business_credits', 0)  # Công công tác (1 công/ngày)
                shifts_done = data['total_shifts']  # Công trực ca
                day_shifts = data['day_shifts']
                night_shifts = data['night_shifts']
                
                # Tổng công đã có
                total_credits = training_credits + line_inspection_credits + business_credits + shifts_done
                
                # Công còn lại cần đạt 17
                remaining_credits = 17 - total_credits
                
                diff = day_shifts - night_shifts
                diff_status = "✅" if abs(diff) <= 2 else "⚠️"
                
                stats_data.append({
                    'Nhân viên': staff,
                    'Vai trò': data['role'],
                    'Mục tiêu': 17,
                    'Đào tạo': training_credits,
                    'Kiểm tra': line_inspection_credits,
                    'Công tác': business_credits,
                    'Đã trực': shifts_done,
                    'Ca ngày': day_shifts,
                    'Ca đêm': night_shifts,
                    'Tổng công': total_credits,
                    'Chênh lệch (N-Đ)': f"{diff} {diff_status}",
                    'Còn thiếu': remaining_credits if remaining_credits > 0 else 0,
                    'Vượt công': -remaining_credits if remaining_credits < 0 else 0
                })
            
            df_stats = pd.DataFrame(stats_data)
            
            # Tô màu chênh lệch
            def color_diff(val):
                if isinstance(val, str):
                    if '✅' in val:
                        return 'background-color: #e6ffe6'
                    elif '⚠️' in val:
                        return 'background-color: #fff0cc'
                return ''
            
            # Tô màu cho cột "Còn thiếu" và "Vượt công"
            def color_remaining(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        return 'background-color: #fff0cc'
                    elif val < 0:
                        return 'background-color: #ffe6e6'
                return ''
            
            styled_stats = df_stats.style \
                .applymap(color_diff, subset=['Chênh lệch (N-Đ)']) \
                .applymap(color_remaining, subset=['Còn thiếu', 'Vượt công'])
            
            st.dataframe(styled_stats, use_container_width=True)
            
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
            total_training = len(all_staff)  # Mỗi người 1 công đào tạo
            total_business = sum(len(data['business_trip_days']) for data in st.session_state.staff_stats.values())
            total_inspection = sum(len(data['line_inspection_days']) for data in st.session_state.staff_stats.values())
            total_day_shifts = sum(data['day_shifts'] for data in st.session_state.staff_stats.values())
            total_night_shifts = sum(data['night_shifts'] for data in st.session_state.staff_stats.values())
            
            # Tính tổng công thực tế
            total_business_credits = total_business * 1  # Mỗi ngày công tác = 1 công (thay vì 2)
            total_inspection_credits = total_inspection  # Mỗi ngày kiểm tra = 1 công
            total_actual = total_shifts + total_training + total_business_credits + total_inspection_credits
            
            with col1:
                st.metric("Tổng ca trực", total_shifts)
            with col2:
                st.metric("Ngày công tác", f"{total_business} ({total_business_credits} công)")
            with col3:
                st.metric("Nhóm kiểm tra", f"{total_inspection} ({total_inspection_credits} công)")
            with col4:
                st.metric("Tổng công thực", f"{total_actual}/{total_target}")
        else:
            st.info("👈 Vui lòng tạo lịch trực ở Tab 2")

    with tab4:
        st.subheader("📱 Lịch trực dạng ngang (N - Ngày, Đ - Đêm)")
        
        if st.session_state.schedule_created and st.session_state.horizontal_schedule is not None:
            # Hiển thị lịch ngang với màu sắc
            df_horizontal = st.session_state.horizontal_schedule
            
            # Tạo một bản sao để hiển thị
            display_df = df_horizontal.copy()
            
            # Hiển thị với CSS đơn giản
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
                height=min(400, 100 + len(display_df) * 35)
            )
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Hiển thị chú thích
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("""
                **Ký hiệu:**
                - **N**: Ca ngày (6h-18h)
                - **Đ**: Ca đêm (18h-6h)
                - **TK**: Trưởng kiếp
                - **VHV**: Vận hành viên
                - **T7**: Thứ 7
                - **CN**: Chủ nhật
                """)
            
            with col2:
                st.markdown("""
                **Ghi chú:**
                - "TẤT CẢ": Ngày đào tạo
                - "Kiểm tra": Đi kiểm tra đường dây
                - Ô trống: Không có phân công
                - Mỗi cột là một ngày trong tháng
                - ✅: Chênh lệch ca ≤ 2
                - ⚠️: Chênh lệch ca > 2
                - **Công tối thiểu: 17 công/tháng**
                - Công đào tạo: 1 công
                - Công kiểm tra: 1 công/ngày
                - **Công công tác: 1 công/ngày** (thay vì 2)
                - Người đi công tác khi về vẫn có thể tăng ca bình thường
                """)
            
            # Nút tải xuống lịch ngang
            st.markdown("---")
            csv_horizontal = df_horizontal.to_csv(encoding='utf-8-sig')
            st.download_button(
                label="📥 Tải lịch ngang (CSV)",
                data=csv_horizontal,
                file_name=f"lich_truc_ngang_TBA_500kV_{month}_{year}.csv",
                mime="text/csv",
                use_container_width=True,
                key="tab4_download_horizontal_csv"
            )
        else:
            st.info("👈 Vui lòng tạo lịch trực ở Tab 2 trước")

    # Footer
    st.markdown("---")
    st.caption("""
    **Hệ thống xếp lịch trực TBA 500kV - Phiên bản 8.2 - Điều chỉnh công công tác**  
    *Mỗi người: 17 công/tháng = 1 công đào tạo + công kiểm tra + công công tác + công trực ca*  
    *Công công tác: 1 công/ngày (thay vì 2 công)*  
    *Tự động điều chỉnh công khi có người công tác: người cùng vai trò tăng ca*  
    *Đảm bảo các ngày cuối tháng đều có người trực*
    """)

except Exception as e:
    st.error(f"Đã xảy ra lỗi trong ứng dụng: {str(e)}")
    with st.expander("Chi tiết lỗi (dành cho nhà phát triển)"):
        st.code(traceback.format_exc())
    st.info("Vui lòng làm mới trang và thử lại. Nếu lỗi vẫn tiếp tục, hãy liên hệ với quản trị viên.")