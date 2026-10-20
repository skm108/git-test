import base64, json, os, re
from openai import OpenAI

def _extract_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise ValueError("模型没有返回可解析的 JSON。")
        return json.loads(m.group(0))

def _client():
    key = os.getenv("ARK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key or key.startswith("填写"):
        raise RuntimeError("缺少 API Key：请复制 .env.example 为 .env 并填写 ARK_API_KEY。")
    return OpenAI(api_key=key, base_url=os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))

def _model():
    model = os.getenv("ARK_MODEL", "").strip()
    if not model or model.startswith("填写"):
        raise RuntimeError("请在 .env 中填写 ARK_MODEL（模型名称或推理接入点 ID）。")
    return model

def _normalise(data):
    qs = data.get("questions", []) if isinstance(data, dict) else []
    clean, valid = [], {"正确", "错误", "部分正确", "需复核"}
    for i, q in enumerate(qs, 1):
        if not isinstance(q, dict):
            continue
        status = q.get("status", "需复核")
        if status not in valid:
            status = "需复核"
        review = bool(q.get("needs_review", status == "需复核"))
        def number(v):
            try: return float(v) if v is not None else None
            except (TypeError, ValueError): return None
        score, maximum = number(q.get("score")), number(q.get("max_score"))
        if score is not None and maximum is not None and (score < 0 or maximum < 0 or score > maximum):
            score, maximum, status, review = None, None, "需复核", True
        bbox = q.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                bbox = [max(0.0, min(1.0, float(v))) for v in bbox]
                if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]: bbox = None
            except (TypeError, ValueError): bbox = None
        else:
            bbox = None
        clean.append({
            "question_no": str(q.get("question_no", i)),
            "question_text": str(q.get("question_text", "")),
            "student_answer": str(q.get("student_answer", "")),
            "expected_answer": str(q.get("expected_answer", "")),
            "status": status, "score": score, "max_score": maximum,
            "feedback": str(q.get("feedback", "")),
            "reasoning": str(q.get("reasoning", "")),
            "needs_review": review,
            "image_region": str(q.get("image_region", "")),
            "bbox": bbox
        })
    total = sum(q["score"] for q in clean) if clean and all(q["score"] is not None for q in clean) else None
    maximum = sum(q["max_score"] for q in clean) if clean and all(q["max_score"] is not None for q in clean) else None
    return {"questions": clean, "total_score": round(total, 2) if total is not None else None,
            "max_score": round(maximum, 2) if maximum is not None else None,
            "overall_comment": str(data.get("overall_comment", "")),
            "general_warnings": data.get("general_warnings", []) if isinstance(data.get("general_warnings", []), list) else []}

def grade_homework(image_bytes, subject, grade_level, reference_answer="", rubric="",
                   strictness="严谨：不确定就标记复核", include_solution=True):
    client, model = _client(), _model()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    prompt = f"""
你是一名严谨的{subject}教师，批改{grade_level}作业。逐题识别图片并只返回合法 JSON。
规则：
1. 参考答案为空时先独立解题，绝不能仅因未提供参考答案就判错。
2. 数学题先准确转写题干，再计算；行列式必须明确识别矩阵行列，不能猜测 OCR 文本。
3. 若题干、公式、矩阵或学生答案有歧义，status=“需复核”、needs_review=true，并说明原因。
4. 选择题先解题再匹配选项；计算结果与选项不符时标记复核。
5. reasoning 写关键计算步骤，数学题尤其需要。
6. bbox 是题目在原图中的归一化坐标 [x1,y1,x2,y2]，范围 0~1，原点左上；仅在能可靠定位整道题时填写，否则 null。不要猜坐标。
7. 错题 feedback 简洁；expected_answer 写正确答案。状态只能是“正确”“错误”“部分正确”“需复核”。
8. {strictness}。{"请提供关键计算步骤。" if include_solution else "步骤简洁。"}
参考答案：{reference_answer or "未提供，请独立求解。"}
评分标准：{rubric or "未提供，合理评分；不确定时复核。"}
JSON 格式：
{{
 "questions":[{{"question_no":"1","question_text":"题目","student_answer":"学生答案",
 "expected_answer":"正确答案","status":"正确|错误|部分正确|需复核","score":1,"max_score":1,
 "feedback":"批改意见","reasoning":"关键计算步骤","needs_review":false,
 "image_region":"页面左上","bbox":[0.05,0.1,0.45,0.3]}}],
 "overall_comment":"总体评价","general_warnings":[]
}}
score/max_score 可为 null。bbox 不可靠则必须为 null。
"""
    response = client.chat.completions.create(
        model=model, temperature=0.1, response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
        ]}]
    )
    return _normalise(_extract_json(response.choices[0].message.content))
