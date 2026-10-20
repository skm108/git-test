import io, json
import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from grader import grade_homework
from annotate import annotate_original, create_printable_report

load_dotenv()
st.set_page_config(page_title="豆包作业批改助手 V3", page_icon="📝", layout="wide")
st.title("📝 豆包作业批改助手 V3")
st.caption("原图逐题批注 · 错题红框与正确答案 · 数学关键步骤 · 可打印批改报告")

with st.sidebar:
    st.header("批改设置")
    subject = st.selectbox("学科", ["数学", "语文", "英语", "物理", "化学", "其他"])
    grade_level = st.text_input("年级/学段", "初中")
    strictness = st.selectbox("批改策略", ["严谨：不确定就标记复核", "标准", "宽松：允许等价表达"])
    include_solution = st.checkbox("要求给出关键解题步骤", True)

uploaded = st.file_uploader("上传作业图片", type=["jpg", "jpeg", "png", "webp"])
reference_answer = st.text_area("参考答案（可选；留空则尝试独立解题）", height=90)
rubric = st.text_area("评分标准（可选）", height=90)

if uploaded and st.button("开始批改", type="primary", use_container_width=True):
    try:
        original_bytes = uploaded.getvalue()
        original_image = Image.open(io.BytesIO(original_bytes)).convert("RGB")
        with st.spinner("正在识别、求解并生成批注……"):
            result = grade_homework(original_bytes, subject, grade_level, reference_answer.strip(),
                                    rubric.strip(), strictness, include_solution)
            annotated = annotate_original(original_image, result)
            report = create_printable_report(original_image, result, subject, grade_level)
            st.session_state["result"] = result
            st.session_state["annotated_bytes"] = annotated
            st.session_state["report_bytes"] = report
    except Exception as exc:
        st.error(f"批改失败：{exc}")

result = st.session_state.get("result")
if result:
    questions = result.get("questions", [])
    st.divider()
    st.subheader("批改汇总")
    cols = st.columns(4)
    cols[0].metric("题目数", len(questions))
    cols[1].metric("总分", "待复核" if result.get("total_score") is None else result["total_score"])
    cols[2].metric("满分", "未确定" if result.get("max_score") is None else result["max_score"])
    cols[3].metric("需复核", sum(1 for q in questions if q.get("needs_review")))
    if result.get("overall_comment"):
        st.info(result["overall_comment"])
    for warning in result.get("general_warnings", []):
        st.warning(warning)

    st.subheader("逐题批改详情")
    for i, q in enumerate(questions, 1):
        with st.expander(f"第 {q.get('question_no', i)} 题 · {q.get('status', '需复核')}", expanded=(i == 1)):
            st.write("**题目：**", q.get("question_text") or "未可靠识别")
            st.write("**学生答案：**", q.get("student_answer") or "未识别")
            st.write("**正确/推导答案：**", q.get("expected_answer") or "未确定")
            st.write("**批改意见：**", q.get("feedback") or "")
            if q.get("reasoning"):
                st.markdown("**关键计算步骤/判断依据：**\n\n" + q["reasoning"])
            st.write("**得分：**", "待复核" if q.get("score") is None else f"{q['score']} / {q.get('max_score')}")
            if q.get("needs_review"):
                st.warning("该题无法可靠判断，请人工复核。")

    st.subheader("1. 原图批注版")
    st.caption("只在模型返回题目坐标时直接标注；坐标不可靠的题目会进入下方批注摘要，避免错误圈画。")
    annotated = st.session_state.get("annotated_bytes")
    if annotated:
        st.image(annotated, use_container_width=True)
        st.download_button("下载原图批注版 PNG", annotated, "homework_annotated.png", "image/png")

    st.subheader("2. 可打印批改报告")
    report = st.session_state.get("report_bytes")
    if report:
        st.image(report, caption="打印报告预览", use_container_width=True)
        st.download_button("下载批改报告 PNG", report, "homework_grading_report.png", "image/png", type="primary")
        st.download_button("下载批改报告 PDF", create_pdf_report(report), "homework_grading_report.pdf", "application/pdf")

    st.subheader("3. 数据导出")
    st.download_button("下载 JSON", json.dumps(result, ensure_ascii=False, indent=2),
                       "grading_result.json", "application/json")
    rows = [{"题号": q.get("question_no"), "题目": q.get("question_text"),
             "学生答案": q.get("student_answer"), "正确答案": q.get("expected_answer"),
             "状态": q.get("status"), "得分": q.get("score"), "满分": q.get("max_score"),
             "批改意见": q.get("feedback"), "关键步骤": q.get("reasoning"),
             "需复核": q.get("needs_review")} for q in questions]
    st.download_button("下载 CSV", pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
                       "grading_result.csv", "text/csv")

def create_pdf_report(png_bytes):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    ratio = min((page_w - 36) / image.width, (page_h - 36) / image.height)
    w, h = image.width * ratio, image.height * ratio
    pdf.drawImage(ImageReader(image), (page_w-w)/2, (page_h-h)/2, width=w, height=h)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
