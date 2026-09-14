import streamlit as st


def render_sidebar_vision_result() -> None:
    st.divider()
    st.subheader("👁️ 视觉结构化结果")
    latest_vision = st.session_state.get("latest_vision_result", {})
    if latest_vision:
        st.caption(
            f"图片: {latest_vision.get('image_name', '-')}"
            f" | 模式: {latest_vision.get('mode', '-')}"
        )
        if latest_vision.get("raw_summary"):
            st.write(f"摘要: {latest_vision['raw_summary']}")
        if latest_vision.get("ocr_text"):
            st.caption("OCR 文本")
            st.code(latest_vision["ocr_text"])
        if latest_vision.get("key_points"):
            st.caption("关键点")
            for item in latest_vision["key_points"]:
                st.write(f"- {item}")
        if latest_vision.get("chart_insights"):
            st.caption("图表洞察")
            for item in latest_vision["chart_insights"]:
                st.write(f"- {item}")
        if latest_vision.get("uncertainties"):
            st.caption("不确定项")
            for item in latest_vision["uncertainties"]:
                st.write(f"- {item}")
    else:
        st.caption("暂无视觉结构化结果")


def render_vision_input_section(vision_enabled: bool, analyze_image_bytes_func) -> None:
    if not vision_enabled:
        return

    st.divider()
    st.subheader("🖼️ 图片输入")
    st.toggle(
        "自动解析图片",
        key="vision_auto_analyze",
        help="开启后，上传图片后可直接一键生成视觉上下文。",
    )
    image_file = st.file_uploader(
        "上传图片（png/jpg/jpeg/webp）",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
    )
    vision_mode_label = st.selectbox(
        "解析模式",
        options=["通用理解", "OCR提取", "图表摘要"],
        index=0,
        help="通用理解：场景与对象；OCR提取：文字优先；图表摘要：趋势与结论优先。",
    )
    vision_mode_map = {
        "通用理解": "general",
        "OCR提取": "ocr",
        "图表摘要": "chart",
    }
    vision_mode = vision_mode_map[vision_mode_label]
    vision_note = st.text_input(
        "图片分析提示（可选）",
        value="",
        placeholder="可选补充要求，例如：重点识别图中性能对比结论。",
    )
    if image_file is None:
        return

    image_token = f"{image_file.name}:{image_file.size}"
    st.image(image_file, caption=f"已上传: {image_file.name}", use_container_width=True)
    should_analyze = st.button("解析图片并用于本轮提问", use_container_width=True)
    if st.session_state.vision_auto_analyze and st.session_state.last_vision_token != image_token:
        should_analyze = True
    if not should_analyze:
        return

    with st.spinner("正在解析图片（Vision）..."):
        vision_result = analyze_image_bytes_func(
            image_bytes=image_file.getvalue(),
            mime_type=image_file.type or "image/png",
            prompt=vision_note,
            mode=vision_mode,
        )
    if vision_result["ok"]:
        st.session_state.last_vision_token = image_token
        st.session_state.pending_vision_context = vision_result["text"]
        st.session_state.pending_vision_image_name = image_file.name
        st.session_state.pending_vision_mode = vision_mode
        st.session_state.pending_vision_ocr_text = vision_result.get("ocr_text", "")
        st.session_state.pending_vision_key_points = vision_result.get("key_points", [])
        st.session_state.pending_vision_chart_insights = vision_result.get("chart_insights", [])
        st.session_state.pending_vision_uncertainties = vision_result.get("uncertainties", [])
        st.session_state.latest_vision_result = {
            "image_name": image_file.name,
            "mode": vision_result.get("mode", vision_mode),
            "raw_summary": vision_result.get("raw_summary", ""),
            "ocr_text": vision_result.get("ocr_text", ""),
            "key_points": vision_result.get("key_points", []),
            "chart_insights": vision_result.get("chart_insights", []),
            "uncertainties": vision_result.get("uncertainties", []),
        }
        st.success("图片解析成功，已加入本轮上下文。")
        st.caption(f"视觉摘要：{vision_result['text'][:200]}...")
    else:
        st.error(f"图片解析失败：{vision_result['error']}")
