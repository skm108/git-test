# 豆包作业批改助手 V3

## 功能
- 上传作业图片并调用 Ark 视觉模型批改。
- 参考答案可选；缺少参考答案时要求模型独立解题。
- 在模型提供可信归一化坐标时，直接在原图题目周围画框并标注 ✓、✗ 或 ?。
- 错题附近标注正确答案；数学关键步骤显示在详情和打印报告中。
- 生成适合打印的批改报告 PNG/PDF，并导出 JSON/CSV。

## 安装
Python 3.10+。

Windows PowerShell:
```powershell
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置与启动
复制 `.env.example` 为 `.env`，填写 Ark API Key、模型/推理接入点 ID 和 Base URL，然后运行：
```bash
streamlit run app.py
```

## 定位准确性说明
程序仅在模型返回可信 `bbox=[x1,y1,x2,y2]` 归一化坐标时画框。若模型未返回坐标，程序将题目列在补充批注或打印报告中，不会猜位置。要进一步提高精度，可接入 OCR/版面检测，或增加手动框选校准功能。

## 注意
需使用支持视觉输入的模型/接入点；接口的 JSON 模式支持情况请以火山引擎实际配置为准。自动评分可能出错，正式成绩请教师复核。




二次提交测试