import io, textwrap
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

RED, GREEN, ORANGE, BLUE = (205, 25, 35), (0, 130, 70), (195, 105, 0), (30, 70, 120)

def font(size=22):
    paths = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
             "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msyh.ttc",
             "C:/Windows/Fonts/simhei.ttf"]
    for path in paths:
        try: return ImageFont.truetype(path, size)
        except Exception: pass
    return ImageFont.load_default()

def _color(q):
    if q.get("needs_review") or q.get("status") == "需复核": return ORANGE
    return GREEN if q.get("status") == "正确" else RED

def _wrap(text, limit=62):
    text = str(text or "").replace("\\n", " ")
    return textwrap.wrap(text, width=limit, break_long_words=True, break_on_hyphens=False) or [""]

def annotate_original(image, result):
    """只在模型给出可信 bbox 时在原图画框；其余题目列入批注报告，不猜位置。"""
    source = image.convert("RGB")
    if source.width > 2400:
        r = 2400 / source.width
        source = source.resize((2400, int(source.height*r)))
    draw = ImageDraw.Draw(source)
    base_font = font(max(18, min(34, source.width//45)))
    small_font = font(max(16, min(25, source.width//60)))
    unlocated = []
    for q in result.get("questions", []):
        b = q.get("bbox")
        if not b:
            unlocated.append(q)
            continue
        x1,y1,x2,y2 = [int(v * (source.width if i%2==0 else source.height)) for i,v in enumerate(b)]
        color = _color(q)
        draw.rounded_rectangle((x1,y1,x2,y2), radius=8, outline=color, width=max(3,source.width//700))
        symbol = "✓" if q.get("status")=="正确" and not q.get("needs_review") else ("?" if q.get("needs_review") else "✗")
        draw.text((min(source.width-45,x2+5), max(0,y1)), symbol, font=base_font, fill=color,
                  stroke_width=2, stroke_fill="white")
        if q.get("status") in ("错误","部分正确") and q.get("expected_answer"):
            label = "正确答案：" + q["expected_answer"]
            label_w = min(source.width-12, max(230, int(draw.textlength(label,font=small_font))+20))
            label_h = small_font.size+18
            lx = min(max(4,x1), source.width-label_w-4)
            ly = y2+5 if y2+label_h+5 < source.height else max(2,y1-label_h-5)
            draw.rounded_rectangle((lx,ly,lx+label_w,ly+label_h), radius=6, fill="white", outline=RED, width=2)
            draw.text((lx+8,ly+5), label, font=small_font, fill=RED)
    out = io.BytesIO()
    source.save(out, "PNG")
    annotated = out.getvalue()
    if unlocated:
        panel = create_printable_report(image, {"questions":unlocated, "total_score":None, "max_score":None,
            "overall_comment":"以下题目未获得可靠坐标，避免错误定位。"}, "未定位题目", "")
        p = Image.open(io.BytesIO(panel)).convert("RGB")
        p = p.resize((source.width, int(p.height*source.width/p.width)))
        canvas = Image.new("RGB",(source.width,source.height+p.height),"white")
        canvas.paste(source,(0,0)); canvas.paste(p,(0,source.height))
        out=io.BytesIO(); canvas.save(out,"PNG"); annotated=out.getvalue()
    return annotated

def create_printable_report(original_image, result, subject="学科", grade_level=""):
    source = original_image.convert("RGB")
    W, margin = 1600, 64
    title_f, body_f, small_f = font(38), font(26), font(21)
    qlist = result.get("questions", [])
    source_w = 320
    source_h = max(100, int(source.height*source_w/source.width))
    cards = []
    for i,q in enumerate(qlist,1):
        no=q.get("question_no") or i
        score=q.get("score"); maximum=q.get("max_score")
        score_s=f"{score:g}/{maximum:g}" if score is not None and maximum is not None else "待复核"
        lines=[
            (f"第{no}题  {q.get('status','需复核')}  得分：{score_s}",body_f,_color(q)),
            ("题目："+(q.get("question_text") or "未可靠识别"),small_f,(35,35,35)),
            ("学生答案："+(q.get("student_answer") or "未识别"),small_f,(35,35,35)),
            ("正确答案："+(q.get("expected_answer") or "未确定"),small_f,RED if q.get("status") in ("错误","部分正确") else (35,35,35))
        ]
        for label,value in [("批改意见：",q.get("feedback")),("关键步骤：",q.get("reasoning"))]:
            if value:
                lines += [(line,small_f,(35,35,35)) for line in _wrap(label+str(value),68)]
        if q.get("needs_review"): lines.append(("请教师复核：题目或答案可能存在识别歧义。",small_f,ORANGE))
        height=24+sum(max(f.size+13,29) for _,f,_ in lines)+22
        cards.append((lines,height))
    header_h=130
    card_gap=18
    total_h=margin+header_h+source_h+30+sum(h for _,h in cards)+card_gap*len(cards)+180+margin
    total_h=max(total_h,900)
    canvas=Image.new("RGB",(W,total_h),"white")
    d=ImageDraw.Draw(canvas)
    d.rounded_rectangle((margin,margin,W-margin,margin+header_h-10),radius=16,fill=(237,244,252),outline=(120,160,205),width=3)
    d.text((margin+24,margin+12),"作业批改报告",font=title_f,fill=BLUE)
    d.text((margin+24,margin+72),f"学科：{subject}  年级：{grade_level or '未填写'}  时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",font=small_f,fill=(40,60,80))
    y=margin+header_h
    thumb=source.copy(); thumb.thumbnail((source_w,source_h))
    canvas.paste(thumb,(margin,y))
    x=margin+source_w+35
    d.text((x,y+5),"批改汇总",font=body_f,fill=BLUE)
    total=result.get("total_score"); maximum=result.get("max_score")
    d.text((x,y+48),f"总分：{total if total is not None else '待复核'} / {maximum if maximum is not None else '未确定'}",font=body_f,fill=(30,30,30))
    d.text((x,y+91),f"题目数：{len(qlist)}  需复核：{sum(1 for q in qlist if q.get('needs_review'))}",font=small_f,fill=(30,30,30))
    if result.get("overall_comment"):
        for j,line in enumerate(_wrap("总体评价："+result["overall_comment"],42)[:3]):
            d.text((x,y+132+j*30),line,font=small_f,fill=(40,60,80))
    y+=source_h+25
    for lines,height in cards:
        d.rounded_rectangle((margin,y,W-margin,y+height),radius=12,fill="white",outline=BLUE,width=2)
        yy=y+12
        for text,f,c in lines:
            for line in _wrap(text,70):
                d.text((margin+20,yy),line,font=f,fill=c)
                yy+=max(f.size+13,29)
        y+=height+card_gap
    footer=min(total_h-margin-115,y+5)
    d.rounded_rectangle((margin,footer,W-margin,footer+100),radius=12,fill=(245,248,252),outline=(170,190,210),width=2)
    d.text((margin+20,footer+12),"教师复核提示",font=body_f,fill=BLUE)
    d.text((margin+20,footer+55),"自动批改仅供参考；正式成绩请教师确认。",font=small_f,fill=(50,60,70))
    canvas=canvas.crop((0,0,W,min(canvas.height,footer+125)))
    out=io.BytesIO(); canvas.save(out,"PNG",dpi=(200,200)); return out.getvalue()
