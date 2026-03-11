import streamlit as st
from openai import OpenAI
import json
import pandas as pd
import time
from io import BytesIO

# ================= 页面全局配置 =================
st.set_page_config(page_title="品牌舆情智能定级系统", page_icon="🚨", layout="wide")

# ================= 核心变更：从云端保密柜静默读取 Key =================
# 这样不仅同事看不到 Key，网页上也没有任何输入框，做到真正的“开箱即用”
try:
    API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except KeyError:
    st.error("⚠️ 系统配置异常：未在云端 Secrets 中找到 API Key。请联系管理员配置。")
    st.stop()  # 如果没配置 Key，直接停止渲染后续页面

# ================= 终极版 Prompt =================
SYSTEM_PROMPT = """
# Role
你是一个极其严谨的资深舆情研判专家。你的唯一任务是阅读输入的【舆情文本】，并在庞大的知识库中，精准锁定【唯一一个】最核心的二级标签。

# Rules (核心定级法则)
1. 【绝对精准，字码不差】：输出的“二级标签”必须与下方知识库完全一致，绝对禁止生造。
2. 【最高风险优先】：遇到多个槽点，按 S > A > B > C > D 降维打击。
3. 【特殊升级规则】：食品安全事件中，明确提及已投诉到“12315”、“消费保”或“黑猫投诉”，原A级直接升级为【S级】。
4. 【防误判机制（极其重要）】：包含敏感词（如“加盟商”、“警察”）不代表发生了敏感事件。必须进行【事实核查】：
   - 网友的主观好奇、吃瓜、调侃、疑问，属于无实质负面的常规讨论，必须归为【常规/其他】。
   - 注意：以“为什么...”等疑问句式来表达对产品、包装、收费、服务等方面不满的（例如：“为什么收打包费却不给保温袋？”），属于隐性客诉，必须按实质负面内容进行定级，不能算作常规疑问！
   - 高危标签（S/A级）必须对应“已发生的客观严重事件”。

# Few-Shot Examples (研判示例)
用户输入：“益禾堂搞这么大优惠加盟商还真的赚钱吗，一个产品动不动就降价这么多[笑哭R]成本会不会很低啊”
你的输出应为：一级标签：常规无负面，二级标签：网友调侃/常规询问，风险等级：D

# Knowledge Base (此处为了代码展示简略，请将你完整的知识库贴回这里)
# Knowledge Base (舆情定级标准知识库)
## 1. 产品评价
- 难喝 -> D
- 难吃 -> D
- 口味（过甜） -> D
- 口味（香精味重） -> D
- 口味（不够甜） -> D
- 口味（味道变淡） -> D
- 异味（烂菜叶味） -> D
- 异味（臭虫虫味） -> D
- 异味 -> D
- 口感（西瓜籽） -> D
- 口感（百香果籽） -> D
- 健康质疑（可下钻） -> C
- 失眠/睡不着 -> D
- 供应管理（产品缺货） -> D

## 2. 服务规范
- 未按要求出品（糖度/温度/小料/杯型/吸管） -> B
- 未按规则发放周边（蒜鸟） -> B
- 未按规则包装产品 -> B
- 拒绝取消订单 -> B
- 拒绝退款 -> B
- 攻击消费者（辱骂） -> S
- 攻击消费者（上门辱骂） -> S
- 攻击消费者（言语威胁） -> S
- 跳单漏单 -> B
- 给错产品 -> B
- 外卖员冲突 -> S

## 3. 服务体验
- 出餐慢 -> C
- 服务态度差 -> C
- 配送速度慢 -> C
- 配送费涨价/配送费贵 -> C
- 联名活动体验差 -> C
- 冰块过多 -> C
- 温度太烫 -> C
- 点单选项不合理 -> C
- 不满门店装修（吐槽无暖气） -> C

## 4. 行业商业
- 竞品对比 -> C
- 竞对拉踩 -> B
- 行业曝光 -> C
- 泄露商业机密 -> A

## 5. 食品安全
- 饮用后身体不适（晕厥/腹泻/上吐下泻） -> A
- 异物 -> A
- 异物（头发/木屑/苍蝇/虫子腿和黑色絮状物/虫子） -> A

## 6. 违法违规
- 拒收现金 -> S
- 拒开发票 -> S
- 容量短缺 -> S
- 产品效期不合格 -> S
- 食安检查不合格 -> S
- 违反劳动法 -> S

## 7. 道德伦理
- 道德败坏 -> S
- 职场性骚扰 -> S

## 8. 物料品控
- 联名周边吐槽（周边质量差/周边瑕疵） -> A
- 产品原料吐槽（烂薄荷/臭水/发霉/植脂末） -> A
- 材料降级 -> A
- 包装质量差 -> A

## 9. 人事纠纷
- 职场问题吐槽（门店） -> B
- 拖欠薪资/追讨薪资/五险一金/辞退员工 -> S
- 虚假信息 -> C

## 10. 招商加盟
- 提及真假商标 -> C
- 吐槽加盟劣势/吐槽加盟制度/投资亏损/门店缩减/门店增长乏力/加盟商不满 -> S

## 11. 营销及品牌向
- 联名周边吐槽（贵/丑/备货不足/活动机制/品类太多） -> B
- 吐槽周边 -> B
- 负面归属（辱女） -> S
- 品牌泛泛吐槽 -> C
- 不如竞品（活动机制） -> B

## 12. 门店设计 & 门店管理
- 主题店设计吐槽 -> B
- 伪造健康证（应付领导） -> A
- 违规收款 -> B
- 吐槽老板 -> C
- 应聘吐槽（对HR不满） -> C

## 13. 活动管理
- 物料偷跑/联名偷跑/物料倒卖 -> S
- 线下活动吐槽（态度差/拥挤踩踏/管理混乱/体验差/布景丑/抽奖纠纷） -> B

## 14. 小程序
- 系统崩溃/系统卡顿/显示错误 -> A
- 优惠券吐槽（抢不到） -> B
- 优惠券吐槽（无法核销/无法领取/使用规则） -> A
- 活动吐槽（机制） -> B
- 活动吐槽（虚假宣传） -> A

## 15. 外卖活动
- 优惠券/免单券吐槽（抢不到） -> B
- 优惠券/免单券吐槽（无法核销/用不了） -> A
- 优惠券/免单券吐槽（抢不到/无法领取） -> B
- 优惠券/免单券吐槽（使用规则） -> A
- 活动吐槽（虚假宣传） -> A
- 活动吐槽（机制不合理） -> A
- 活动吐槽（门店压力大/等待太久/门店没货） -> B

## 16. 常规无负面 (防误判安全区)
- 网友调侃/常规询问 -> D
- 无效/无关内容 -> D

(注：为保持代码简洁，此处省略了部分不相关的知识库条目，请将你之前的知识库完整补充进来，但务必保留第16条【常规无负面】)

【特殊情况判定与输出规则】
在进行标签匹配前，必须先进行“负面/敏感度”判定。
如果研判发现该舆情事件仅为网友的主观疑问、玩梗调侃、正面评价或常规询问，且【无客观负面事实】、【无敏感内容】、【未触发预警分类表中的任何实质性负面情形】：
1. 绝对禁止生搬硬套或生造预警图表中的标签。
2. 必须立即终止常规预警匹配，并严格按照以下 JSON 格式输出：

{
  "事实核查": "对内容的客观描述，说明为何不属于负面或敏感内容",
  "候选推演": "说明为何排除负面标签的理由（如：仅为网友调侃，无实际客诉发生）",
  "一级标签": "无",
  "二级标签": "无",
  "风险等级": "R"
}
# Output Format (输出格式)
【极其重要】：你必须严格按照以下 JSON 格式输出，且必须先输出“事实核查”，最后再输出标签。
{
  "事实核查": "一句话分析：这是已发生的客观负面事实，还是网友的主观调侃、吃瓜或疑问？",
  "候选推演": "说明你考虑了哪几个标签，为什么排除了高危标签？",
  "一级标签": "最终提取的一级标签",
  "二级标签": "严格匹配的唯一二级标签",
  "风险等级": "最终判定的等级(S/A/B/C/D)"
}
"""


# ================= 核心请求函数 =================
def analyze_text(text, api_key):
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={'type': 'json_object'},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}


# ================= 主界面 UI =================
st.title("🚨 品牌舆情智能研判中心")
st.markdown("本系统已接入 DeepSeek 深度思考引擎，严格按照品牌现行标准进行 S/A/B/C/D 降维定级。")

# 使用 Tab 划分功能区
tab1, tab2 = st.tabs(["💬 单条文本实时研判", "📊 Excel 自动化报表批量处理"])

# --- Tab 1: 单条研判 ---
with tab1:
    st.subheader("文本实时诊断")
    user_input = st.text_area(
        "请在此粘贴需要核查的客诉或网帖内容：",
        height=150,
        placeholder="例如：益禾堂搞这么大优惠加盟商还真的赚钱吗，一个产品动不动就降价这么多[笑哭R]成本会不会很低啊"
    )

    if st.button("开始研判", type="primary", use_container_width=True):
        if user_input.strip() == "":
            st.warning("👈 请先输入内容后再点击研判！")
        else:
            with st.spinner("专家引擎正在深度分析中，请稍候..."):
                result = analyze_text(user_input, API_KEY)

                if "error" in result:
                    st.error(f"接口调用失败: {result['error']}")
                else:
                    st.success("研判完成！")
                    # 优美地展示结果
                    col1, col2, col3 = st.columns(3)
                    col1.metric("风险等级", result.get("风险等级", "未知"))
                    col2.metric("一级标签", result.get("一级标签", "未知"))
                    col3.metric("二级标签", result.get("二级标签", "未知"))

                    st.markdown("#### 🧠 决策逻辑推演")
                    st.info(f"**事实核查：** {result.get('事实核查', '')}")
                    st.warning(f"**候选推演：** {result.get('候选推演', '')}")

                    # 保留原始 JSON 查看选项
                    with st.expander("查看原始 JSON 数据格式"):
                        st.json(result)

# --- Tab 2: 批量研判 ---
with tab2:
    st.subheader("自动化报表处理")
    st.info("💡 请上传包含舆情文本的 Excel 表格。系统将自动新增列并填入研判结果，生成后可直接下载。")
    uploaded_file = st.file_uploader("上传您的 Excel 文件 (.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        st.markdown("**数据预览（前3行）：**")
        st.dataframe(df.head(3))

        text_column = st.selectbox("👉 请选择包含『舆情文本内容』的列名：", df.columns)

        if st.button("🚀 启动全量自动化研判", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            results_list = []
            total_rows = len(df)

            for index, row in df.iterrows():
                text = str(row[text_column])
                status_text.text(f"正在全速处理中... 进度：第 {index + 1} / {total_rows} 条")

                if pd.isna(text) or text.strip() == "" or text.strip() == "nan":
                    results_list.append({
                        "事实核查": "空文本",
                        "候选推演": "无",
                        "一级标签": "无",
                        "二级标签": "无",
                        "风险等级": "无"
                    })
                else:
                    res = analyze_text(text, API_KEY)
                    # 为了防止请求过快触发 API 限制，稍微暂停
                    time.sleep(0.3)

                    if "error" in res:
                        results_list.append({
                            "事实核查": "API报错",
                            "候选推演": res["error"],
                            "一级标签": "Error",
                            "二级标签": "Error",
                            "风险等级": "Error"
                        })
                    else:
                        results_list.append({
                            "事实核查": res.get("事实核查", ""),
                            "候选推演": res.get("候选推演", ""),
                            "一级标签": res.get("一级标签", ""),
                            "二级标签": res.get("二级标签", ""),
                            "风险等级": res.get("风险等级", "")
                        })

                progress_bar.progress((index + 1) / total_rows)

            status_text.text("✅ 所有数据处理完毕！")

            # 将结果合并回原表格
            result_df = pd.concat([df, pd.DataFrame(results_list)], axis=1)
            st.dataframe(result_df)

            # 提供下载按钮，转换流以防乱码并适应云端环境
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False, sheet_name='研判结果')
            processed_data = output.getvalue()

            st.download_button(
                label="📥 点击下载最终研判报表",
                data=processed_data,
                file_name="舆情智能研判自动化结果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
