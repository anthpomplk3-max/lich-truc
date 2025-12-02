import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
from collections import defaultdict

# Tiêu đề ứng dụng
st.set_page_config(page_title="Xếp lịch trực TBA 500kV", layout="wide")
st.title("🔄 Xếp lịch trực TBA 500kV")
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

# Sidebar cho thông tin nhập
with st.sidebar:
    st.header("Thông tin tháng")
    
    # Chọn tháng/năm
    col1, col2 = st.columns(2)
    with col1:
        month = st.selectbox("Tháng", range(1, 13), index=datetime.now().month-1)
    with col2:
        year = st.selectbox("Năm", range(2023, 2030), index=datetime.now().year-2023)
    
    # Tính số ngày trong tháng
    num_days = calendar.monthrange(year, month)[1]
    
    st.markdown(f"**Tháng {month}/{year} có {num_days} ngày**")
    st.markdown("---")
    
    st.header("Ngày đào tạo nội bộ")
    training_day = st.slider("Chọn ngày đào tạo", 1, num_days, 15)
    
    st.markdown("---")
    st.header("Hướng dẫn")
    st.info("""
    1. Mỗi người chọn tối đa 5 ngày nghỉ
    2. Mỗi người có 2 ngày hành chính
    3. Tổng công trong tháng: 17 công
    4. Ca ngày: 6h - 18h
    5. Ca đêm: 18h - 6h
    """)

# Main content
tab1, tab2, tab3 = st.tabs(["📅 Chọn ngày nghỉ", "📊 Xếp lịch", "📋 Thống kê"])

with tab1:
    st.subheader("Chọn ngày nghỉ cho từng nhân viên")
    st.warning("Mỗi người chọn tối đa 5 ngày nghỉ trong tháng")
    
    # Khởi tạo session state cho ngày nghỉ
    if 'day_off' not in st.session_state:
        st.session_state.day_off = {staff: [] for staff in all_staff}
    
    # Tạo layout cho từng nhân viên
    for i in range(0, len(all_staff), 2):
        cols = st.columns(2)
        
        for j in range(2):
            if i + j < len(all_staff):
                staff = all_staff[i + j]
                with cols[j]:
                    st.markdown(f"**{staff}**")
                    
                    # Chọn ngày nghỉ
                    days_off = st.multiselect(
                        f"Ngày nghỉ - {staff}",
                        options=list(range(1, num_days + 1)),
                        default=st.session_state.day_off.get(staff, []),
                        key=f"off_{staff}"
                    )
                    
                    # Kiểm tra số ngày nghỉ
                    if len(days_off) > 5:
                        st.error(f"{staff} chọn quá 5 ngày nghỉ!")
                        days_off = days_off[:5]
                    
                    st.session_state.day_off[staff] = days_off
                    
                    # Chọn 2 ngày hành chính
                    admin_days = st.multiselect(
                        f"Ngày hành chính - {staff}",
                        options=[d for d in range(1, num_days + 1) if d not in days_off and d != training_day],
                        max_selections=2,
                        key=f"admin_{staff}"
                    )
                    
                    st.caption(f"Ngày nghỉ: {len(days_off)}/5 | HC: {len(admin_days)}/2")

with tab2:
    st.subheader("Lịch trực tháng")
    
    if st.button("🎯 Tạo lịch trực tự động"):
        # Tạo lịch trực
        schedule = []
        
        # Ngày đào tạo - tất cả có mặt
        for day in range(1, num_days + 1):
            # Kiểm tra ngày đào tạo
            if day == training_day:
                schedule.append({
                    'Ngày': day,
                    'Ca': 'Đào tạo',
                    'Trưởng kiếp': 'Tất cả',
                    'Vận hành viên': 'Tất cả',
                    'Ghi chú': 'Đào tạo nội bộ'
                })
                continue
            
            # Ca ngày
            schedule.append({
                'Ngày': day,
                'Ca': 'Ngày (6h-18h)',
                'Trưởng kiếp': '',
                'Vận hành viên': '',
                'Ghi chú': ''
            })
            
            # Ca đêm
            schedule.append({
                'Ngày': day,
                'Ca': 'Đêm (18h-6h)',
                'Trưởng kiếp': '',
                'Vận hành viên': '',
                'Ghi chú': ''
            })
        
        df_schedule = pd.DataFrame(schedule)
        
        # Hiển thị lịch
        st.dataframe(df_schedule, use_container_width=True)
        
        # Thống kê
        st.subheader("Thống kê phân công")
        
        # Tính số công cho từng người
        work_stats = []
        for staff in all_staff:
            # Giả định phân công (trong thực tế cần thuật toán phức tạp hơn)
            total_shifts = 17  # Tổng số ca
            night_shifts = 8   # Số ca đêm
            day_shifts = 9     # Số ca ngày
            
            work_stats.append({
                'Nhân viên': staff,
                'Tổng ca': total_shifts,
                'Ca ngày': day_shifts,
                'Ca đêm': night_shifts,
                'Ngày nghỉ': len(st.session_state.day_off.get(staff, [])),
                'Ngày HC': 2
            })
        
        df_stats = pd.DataFrame(work_stats)
        st.dataframe(df_stats, use_container_width=True)
        
        # Nút tải xuống
        csv = df_schedule.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Tải lịch trực (CSV)",
            data=csv,
            file_name=f"lich_truc_{month}_{year}.csv",
            mime="text/csv"
        )
    else:
        st.info("Nhấn nút 'Tạo lịch trực tự động' để xếp lịch")

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
    
    # Hiển thị ngày nghỉ của từng người
    st.subheader("Danh sách ngày nghỉ")
    
    off_days_data = []
    for staff in all_staff:
        days_off = st.session_state.day_off.get(staff, [])
        off_days_data.append({
            'Nhân viên': staff,
            'Số ngày nghỉ': len(days_off),
            'Ngày nghỉ cụ thể': ', '.join(map(str, days_off)) if days_off else 'Không có'
        })
    
    df_off_days = pd.DataFrame(off_days_data)
    st.dataframe(df_off_days, use_container_width=True)
    
    # Kiểm tra vi phạm
    st.subheader("Kiểm tra ràng buộc")
    
    violations = []
    
    # Kiểm tra số ngày nghỉ
    for staff in all_staff:
        days_off = st.session_state.day_off.get(staff, [])
        if len(days_off) > 5:
            violations.append(f"{staff}: Chọn {len(days_off)} ngày nghỉ (vượt quá 5 ngày)")
    
    if violations:
        st.error("Các vi phạm:")
        for violation in violations:
            st.write(f"⚠️ {violation}")
    else:
        st.success("✓ Tất cả nhân viên đều chọn đúng số ngày nghỉ cho phép")

# Footer
st.markdown("---")
st.caption("Hệ thống xếp lịch trực TBA 500kV - Version 1.0")