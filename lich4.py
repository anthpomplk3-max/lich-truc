# ... (phần code trước vẫn giữ nguyên cho đến tab4) ...

with tab4:
    st.subheader("📱 Lịch trực dạng ngang (N - Ngày, Đ - Đêm)")
    
    if st.session_state.schedule_created and st.session_state.horizontal_schedule is not None:
        # Hiển thị lịch ngang với màu sắc
        df_horizontal = st.session_state.horizontal_schedule
        
        # Tạo style cho bảng ngang - SỬA LẠI PHẦN NÀY
        def highlight_cells(val):
            """Hàm tô màu cho từng ô"""
            if isinstance(val, str):
                if 'TẤT CẢ' in val:
                    return 'background-color: #ffffcc; font-weight: bold'
                elif val != '':
                    # Kiểm tra xem đây có phải là cột Thứ không
                    return ''
            return ''
        
        # Áp dụng style cho toàn bộ dataframe
        styled_horizontal = df_horizontal.style.applymap(highlight_cells)
        
        # Thêm style cho từng loại hàng
        def apply_row_styles(styler):
            """Áp dụng style cho từng hàng dựa trên chỉ mục"""
            # Lấy danh sách các hàng
            for i, idx in enumerate(styler.index):
                if 'ngày' in idx.lower() or '(N)' in idx:
                    # Màu cho hàng ca ngày
                    styler = styler.map(lambda x: 'background-color: #e6ffe6', subset=pd.IndexSlice[i, :])
                elif 'đêm' in idx.lower() or '(Đ)' in idx:
                    # Màu cho hàng ca đêm
                    styler = styler.map(lambda x: 'background-color: #ffe6e6', subset=pd.IndexSlice[i, :])
                elif 'Ghi chú' in idx:
                    # Màu cho hàng ghi chú
                    styler = styler.map(lambda x: 'background-color: #ffffcc', subset=pd.IndexSlice[i, :])
                elif idx == 'Thứ':
                    # Màu cho hàng thứ
                    styler = styler.map(lambda x: 'background-color: #f5f5f5; font-weight: bold', subset=pd.IndexSlice[i, :])
            return styler
        
        # Áp dụng style theo hàng
        styled_horizontal = apply_row_styles(styled_horizontal)
        
        # Thêm style cho cột Thứ (Chủ nhật, thứ 7)
        def highlight_weekend(val, col_name):
            """Tô màu cho thứ 7 và chủ nhật"""
            if col_name == 'Thứ' and isinstance(val, str):
                if val in ['T7', 'CN']:
                    return 'background-color: #fff0f0'
            return ''
        
        # Áp dụng style cho cột Thứ
        for col in df_horizontal.columns:
            if col == 'Thứ':
                styled_horizontal = styled_horizontal.map(
                    lambda x, col=col: highlight_weekend(x, col), 
                    subset=pd.IndexSlice[:, col]
                )
        
        # Hiển thị với thanh cuộn ngang
        st.markdown("""
        <style>
        .horizontal-scroll {
            overflow-x: auto;
            white-space: nowrap;
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
        }
        .stDataFrame {
            min-width: 100%;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="horizontal-scroll">', unsafe_allow_html=True)
        
        # Hiển thị DataFrame với chiều cao tự động
        st.dataframe(
            styled_horizontal,
            use_container_width=True,
            height=min(400, 100 + len(df_horizontal) * 35)
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Hiển thị chú thích
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            **Chú thích màu sắc:**
            - 🟩 **Xanh nhạt**: Ca ngày (N)
            - 🟥 **Hồng nhạt**: Ca đêm (Đ)
            - 🟨 **Vàng**: Ngày đào tạo
            - ⚪ **Xám**: Thứ trong tuần
            - 🟪 **Hồng đậm**: Thứ 7, Chủ nhật
            """)
        
        with col2:
            st.markdown("""
            **Ký hiệu:**
            - **N**: Ca ngày (6h-18h)
            - **Đ**: Ca đêm (18h-6h)
            - **TK**: Trưởng kiếp
            - **VHV**: Vận hành viên
            - **T7**: Thứ 7
            - **CN**: Chủ nhật
            """)
        
        with col3:
            st.markdown("""
            **Ghi chú:**
            - Thứ 7, Chủ nhật được tô màu hồng
            - "TẤT CẢ": Ngày đào tạo
            - Ô trống: Không có phân công
            """)
        
        # Hiển thị dạng xem thu gọn (chỉ hiển thị 10 ngày một lần)
        st.markdown("---")
        st.subheader("Xem theo nhóm ngày")
        
        # Chia thành các nhóm 10 ngày
        num_groups = (num_days + 9) // 10
        
        for group in range(num_groups):
            start_day = group * 10 + 1
            end_day = min((group + 1) * 10, num_days)
            
            with st.expander(f"📅 Ngày {start_day} đến {end_day}", expanded=(group == 0)):
                # Tạo dataframe cho nhóm này
                group_data = {}
                for idx in df_horizontal.index:
                    row_data = {}
                    for day in range(start_day, end_day + 1):
                        col_name = f"Ngày {day}"
                        if col_name in df_horizontal.columns:
                            row_data[col_name] = df_horizontal.loc[idx, col_name]
                    group_data[idx] = row_data
                
                df_group = pd.DataFrame(group_data).T
                
                # Thêm cột Thứ
                df_group.insert(0, 'Thứ', df_horizontal['Thứ'])
                
                # Áp dụng style tương tự
                styled_group = df_group.copy()
                
                # Hiển thị
                st.dataframe(
                    styled_group,
                    use_container_width=True,
                    height=min(300, 100 + len(df_group) * 35)
                )
        
        # Nút tải xuống lịch ngang
        st.markdown("---")
        csv_horizontal = df_horizontal.to_csv(encoding='utf-8-sig')
        st.download_button(
            label="📥 Tải lịch ngang (CSV)",
            data=csv_horizontal,
            file_name=f"lich_truc_ngang_TBA_500kV_{month}_{year}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("👈 Vui lòng tạo lịch trực ở Tab 2 trước")

# ... (phần code sau vẫn giữ nguyên) ...