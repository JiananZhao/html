# macro_tab.py
# 宏观流动性与经济全景指标 Tab 渲染模块
# 升级重构版：
# 1. 顶部全局宏观核心体温驾驶舱 (Executive KPI Cockpit)
# 2. 六大逻辑主题子标签分页 (Sub-tabs) 彻底告别长页面滚动疲劳
# 3. 补齐全球流动性锚点：商业银行准备金 (Bank Reserves)、高收益债利差 (HY OAS)、美元指数 (DXY)
# 4. 补齐信贷周期与硬着陆雷达：银行信贷紧缩调查 (SLOOS)、工商业贷款增速、四周移动平均初请失业金
# 5. 新增第六大板块：⚡ AI 算力供应链、瓶颈传导与电力基建 (聚焦四大瓶颈与领先指标)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from macro_data_engine import fetch_all_macro_data, get_latest_kpi_summary


def _plot_dual_axis_chart(df1, df2, name1, name2, title, unit1="", unit2="", color1="#2563EB", color2="#DC2626", hlines=None):
    """绘制双Y轴或同轴对比折线图"""
    fig = go.Figure()

    if not df1.empty:
        fig.add_trace(go.Scatter(
            x=df1["date"], y=df1["value"],
            name=f"{name1} ({unit1})" if unit1 else name1,
            line=dict(color=color1, width=2.2),
            yaxis="y1"
        ))

    if not df2.empty:
        fig.add_trace(go.Scatter(
            x=df2["date"], y=df2["value"],
            name=f"{name2} ({unit2})" if unit2 else name2,
            line=dict(color=color2, width=2.0, dash="dot" if unit1 == unit2 else "solid"),
            yaxis="y1" if unit1 == unit2 else "y2"
        ))

    if hlines:
        for h in hlines:
            fig.add_hline(
                y=h.get("y", 0),
                line_dash=h.get("dash", "dash"),
                line_color=h.get("color", "gray"),
                annotation_text=h.get("text", ""),
                annotation_position="top left"
            )

    layout_kwargs = dict(
        title=dict(text=title, font=dict(size=15)),
        hovermode="x unified",
        height=390,
        margin=dict(l=20, r=20, t=45, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title=unit1)
    )

    if unit1 != unit2 and not df2.empty:
        layout_kwargs["yaxis2"] = dict(
            title=unit2,
            overlaying="y",
            side="right",
            showgrid=False
        )

    fig.update_layout(**layout_kwargs)
    return fig


def _plot_single_series(df_sub, title, unit="", color="#2563EB", hlines=None, fill_to_zero=False):
    """绘制单序列专业图表，支持多条阈值警戒线与零轴填充"""
    if df_sub.empty:
        return None
    fig = go.Figure()
    trace_kwargs = dict(
        x=df_sub["date"],
        y=df_sub["value"],
        name=title,
        line=dict(color=color, width=2.2)
    )
    if fill_to_zero:
        trace_kwargs["fill"] = "tozeroy"
        # 半透明填充色
        if color.startswith("#") and len(color) == 7:
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            trace_kwargs["fillcolor"] = f"rgba({r},{g},{b},0.12)"

    fig.add_trace(go.Scatter(**trace_kwargs))

    if hlines:
        for h in hlines:
            fig.add_hline(
                y=h.get("y", 0),
                line_dash=h.get("dash", "dash"),
                line_color=h.get("color", "red"),
                annotation_text=h.get("text", ""),
                annotation_position=h.get("pos", "top left")
            )

    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        xaxis_title="",
        yaxis_title=unit,
        hovermode="x unified",
        height=370,
        margin=dict(l=20, r=20, t=45, b=20),
        showlegend=False
    )
    return fig


def _get_metric_snapshot(df_long, metric_name):
    """提取单个指标的最新值、前值、差值与日期"""
    sub = df_long[df_long["metric_name"] == metric_name].sort_values("date")
    if sub.empty:
        return None
    latest = sub.iloc[-1]
    prev = sub.iloc[-2] if len(sub) > 1 else latest
    val = float(latest["value"])
    delta = val - float(prev["value"])
    date_str = latest["date"].strftime("%Y-%m-%d")
    return {"val": val, "delta": delta, "date": date_str}


def _render_kpi_cockpit(df_long: pd.DataFrame):
    """顶部全局宏观核心体温驾驶舱 (Executive KPI Cockpit)"""
    st.markdown("#### 🎛️ 全局宏观核心体温驾驶舱 (Executive Macro Vital Signs)")

    net_liq = _get_metric_snapshot(df_long, "Fed Net Liquidity (WALCL - TGA - RRP)")
    sofr_spread = _get_metric_snapshot(df_long, "SOFR - IORB Spread (隔夜资金面利差)")
    vix = _get_metric_snapshot(df_long, "CBOE VIX (标普500波动率恐慌指数)")
    move = _get_metric_snapshot(df_long, "ICE BofA MOVE (美债波动率恐慌指数)")
    sahm = _get_metric_snapshot(df_long, "Sahm Rule Recession Indicator (萨姆法则衰退指标)")
    spread_10_2 = _get_metric_snapshot(df_long, "10Y-2Y Treasury Spread (10年-2年美债利差)")
    erp = _get_metric_snapshot(df_long, "SP500 Dynamic ERP (标普500动态股权风险溢价)")
    fpe = _get_metric_snapshot(df_long, "SP500 Forward PE (标普500预期市盈率)")
    hy_oas = _get_metric_snapshot(df_long, "US High Yield OAS (高收益债信用利差)")
    nfci = _get_metric_snapshot(df_long, "Chicago Fed NFCI (芝加哥联储全国金融条件指数)")

    cols = st.columns(5)

    # 卡片 1：净流动性与隔夜资金面
    with cols[0]:
        with st.container(border=True):
            st.caption("💧 美联储净流动性 | SOFR利差")
            if net_liq:
                st.metric(
                    label=f"净流动性 ({net_liq['date']})",
                    value=f"${net_liq['val']:,.2f} B",
                    delta=f"{net_liq['delta']:+.2f} B"
                )
            else:
                st.metric("净流动性", "N/A")
            if sofr_spread:
                status = "🟢 充裕" if sofr_spread["val"] <= 0 else ("🟡 摩擦" if sofr_spread["val"] <= 5 else "🔴 紧缺")
                st.caption(f"SOFR-IORB: **{sofr_spread['val']:+.1f} bps** ({status})")

    # 卡片 2：股债双杀/恐慌温度计
    with cols[1]:
        with st.container(border=True):
            st.caption("⚡ 股市 VIX | 债市 MOVE 恐慌")
            if vix:
                st.metric(
                    label=f"CBOE VIX ({vix['date']})",
                    value=f"{vix['val']:.2f}",
                    delta=f"{vix['delta']:+.2f}",
                    delta_color="inverse"
                )
            else:
                st.metric("CBOE VIX", "N/A")
            if move:
                m_status = "🟢 平稳" if move["val"] < 100 else ("🟡 偏高" if move["val"] < 120 else "🔴 剧烈动荡")
                st.caption(f"债市 MOVE: **{move['val']:.1f}** ({m_status})")

    # 卡片 3：衰退与曲线形态
    with cols[2]:
        with st.container(border=True):
            st.caption("🛡️ 萨姆法则 | 10Y-2Y 曲线")
            if sahm:
                st.metric(
                    label=f"萨姆衰退指标 ({sahm['date']})",
                    value=f"{sahm['val']:.2f}%",
                    delta=f"{sahm['delta']:+.2f}%",
                    delta_color="inverse"
                )
            else:
                st.metric("萨姆衰退指标", "N/A")
            if spread_10_2:
                c_status = "⚠️ 倒挂" if spread_10_2["val"] < 0 else "📈 正斜率/陡峭化"
                st.caption(f"10Y-2Y 利差: **{spread_10_2['val']:+.2f}%** ({c_status})")

    # 卡片 4：跨资产风险溢价与估值
    with cols[3]:
        with st.container(border=True):
            st.caption("🎯 标普 500 ERP | Forward PE")
            if erp:
                st.metric(
                    label=f"动态 ERP ({erp['date']})",
                    value=f"{erp['val']:.2f}%",
                    delta=f"{erp['delta']:+.2f}%"
                )
            else:
                st.metric("动态 ERP", "N/A")
            if fpe:
                st.caption(f"Forward PE: **{fpe['val']:.2f}x** (变化 {fpe['delta']:+.2f}x)")

    # 卡片 5：企业信用利差与金融条件
    with cols[4]:
        with st.container(border=True):
            st.caption("🏦 高收益债利差 | 金融条件 NFCI")
            if hy_oas:
                st.metric(
                    label=f"HY OAS 利差 ({hy_oas['date']})",
                    value=f"{hy_oas['val']:.2f}%",
                    delta=f"{hy_oas['delta']:+.2f}%",
                    delta_color="inverse"
                )
            else:
                st.metric("HY OAS 利差", "N/A")
            if nfci:
                n_status = "🟢 宽松(<0)" if nfci["val"] < 0 else "🔴 收紧(>0)"
                st.caption(f"芝加哥 NFCI: **{nfci['val']:+.2f}** ({n_status})")


# ==============================================================================
# 新增核心导航组件：🧭 宏观流动性五维诊断作战地图与全站位置速查表
# ==============================================================================
def _render_liquidity_navigation_map(df_long: pd.DataFrame):
    """渲染全站流动性指标位置速查表、实时读数与 5 步实战诊断 SOP"""
    with st.expander("🧭 宏观流动性「五维诊断作战地图」与全站指标位置速查表 (点击展开：一表看懂去哪看、怎么看、如何联动定仓)", expanded=False):
        st.markdown(
            "💡 **为什么要按「五层传导链」看流动性？** 市场大跌往往不是因为单一指标恶化，而是沿着 "
            "**「① 央行底池抽水/隔夜摩擦 $\\rightarrow$ ② 美债抵押品波动率 (MOVE) 飙升 $\\rightarrow$ ③ 期限溢价与实际利率杀估值 $\\rightarrow$ ④ 高收益债利差 (HY OAS) 传染至实体企业 $\\rightarrow$ ⑤ 触发反身性趋势破位」** 逐级传导。"
        )

        def _fmt_snap(metric_name, unit="", decimals=2, signed=False):
            snap = _get_metric_snapshot(df_long, metric_name)
            if not snap:
                return "N/A"
            fmt = f"{{:+.{decimals}f}}" if signed else f"{{:,.{decimals}f}}"
            val_s = fmt.format(snap["val"])
            del_s = f"{snap['delta']:+.{decimals}f}"
            return f"{val_s}{unit} ({del_s} | {snap['date']})"

        nav_rows = [
            {
                "传导层级": "第 1 层：央行水源与隔夜管道",
                "核心监控指标": "美联储净流动性 (WALCL - TGA - RRP) & 银行准备金 (WRESBAL)",
                "当前实时读数 (变动 | 日期)": f"净流动性: {_fmt_snap('Fed Net Liquidity (WALCL - TGA - RRP)', 'B')} | 准备金: {_fmt_snap('US Bank Reserves (商业银行准备金余额)', 'B')}",
                "所在页面精确路径": "Tab 1 ➔ 💧 子标签 1 (左上方双轴图) & 顶部卡片 1",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 准备金 > $3.2T 且净流动性回升 | 🟡 准备金逼近 $3.0T~$3.2T | 🔴 跌破 $3.0T LCLoR 红线",
                "实战核心含义": "全市场基础货币总水源，通常领先美股 1~2 周；ON RRP 耗尽后 TGA 抽水将 1:1 消耗银行准备金。"
            },
            {
                "传导层级": "第 1 层：央行水源与隔夜管道",
                "核心监控指标": "SOFR - IORB 隔夜资金面利差 (回购管道摩擦计)",
                "当前实时读数 (变动 | 日期)": _fmt_snap("SOFR - IORB Spread (隔夜资金面利差)", " bps", decimals=1, signed=True),
                "所在页面精确路径": "Tab 1 ➔ 💧 子标签 1 (右上方面积图) & 顶部卡片 1",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 <= 0 bps (现金充裕) | 🟡 0 ~ +5 bps (发债/季末摩擦) | 🔴 > +10~15 bps (钱荒/回购挤兑)",
                "实战核心含义": "最敏锐的日频管道听诊器：一旦持续转正飙升，说明场内机构宁付溢价也在抢隔夜现金。"
            },
            {
                "传导层级": "第 2 层：债市抵押品与买方去杠杆",
                "核心监控指标": "ICE BofA MOVE (美债波动率) & CBOE VIX / SKEW / DIX",
                "当前实时读数 (变动 | 日期)": f"MOVE: {_fmt_snap('ICE BofA MOVE (美债波动率恐慌指数)', '', 1)} | VIX: {_fmt_snap('CBOE VIX (标普500波动率恐慌指数)', '', 2)}",
                "所在页面精确路径": "Tab 1 ➔ ⚡ 子标签 2 (左图 VIX vs MOVE / 右图 SKEW vs DIX) & 顶部卡片 2",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 MOVE < 100, VIX < 18 | 🟡 MOVE 110~125, VIX 20~28 | 🔴 MOVE > 130 (抵押品折价强制平仓)",
                "实战核心含义": "MOVE 是「流动性恐慌之母」（领先 VIX 1~2 周）；MOVE 飙升会调高美债抵押品折扣率，迫使 Risk Parity 与 CTA 被动砍仓。"
            },
            {
                "传导层级": "第 3 层：贴现率分母与跨资产风偏",
                "核心监控指标": "纽约联储 ACM 10Y 期限溢价 & 10Y TIPS 实际利率",
                "当前实时读数 (变动 | 日期)": f"ACM期限溢价: {_fmt_snap('NY Fed ACM 10Y Term Premium (纽约联储10年期美债期限溢价)', '%')} | TIPS实际利率: {_fmt_snap('10Y Real Interest Rate (10年期TIPS实际利率)', '%')}",
                "所在页面精确路径": "Tab 1 ➔ 🎯 子标签 3 (第一排左/右图)",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 期限溢价 < 0%, TIPS < 1.8% | 🟡 期限溢价 0~0.5%, TIPS 2.0% | 🔴 期限溢价 > +0.8% 或 TIPS 60日急升 > 35bps",
                "实战核心含义": "区分「好加息（经济增长）」与「坏加息（长债供需失衡/期限溢价飙升）」，后者纯杀科技股与 Neocloud 估值。"
            },
            {
                "传导层级": "第 3 层：贴现率分母与跨资产风偏",
                "核心监控指标": "标普 500 动态 ERP & 跨资产风偏比率 (HYG/TLT & 铜金比)",
                "当前实时读数 (变动 | 日期)": f"ERP: {_fmt_snap('SP500 Dynamic ERP (标普500动态股权风险溢价)', '%')} | HYG/TLT: {_fmt_snap('HYG/TLT Ratio (高收益债与长债风偏比率)', '', 3)}",
                "所在页面精确路径": "Tab 1 ➔ 🎯 子标签 3 (第二排左/右图) & 顶部卡片 4",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 ERP > 1.5%, HYG/TLT 上行 | 🟡 ERP 0~1.0% | 🔴 ERP <= 0% 且 HYG/TLT 高位破位下行",
                "实战核心含义": "当股指还在高位但 HYG/TLT 率先向下破位，说明债市聪明钱已先于股市撤离信用风险。"
            },
            {
                "传导层级": "第 4 层：企业信用利差与银行信贷",
                "核心监控指标": "高收益债信用利差 (HY OAS) & 芝加哥联储 NFCI & 银行惜贷 SLOOS",
                "当前实时读数 (变动 | 日期)": f"HY OAS: {_fmt_snap('US High Yield OAS (高收益债信用利差)', '%')} | NFCI: {_fmt_snap('Chicago Fed NFCI (芝加哥联储全国金融条件指数)', '', 2, True)}",
                "所在页面精确路径": "Tab 1 ➔ 🏦 子标签 4 (左图 HY OAS vs NFCI / 右图 SLOOS vs 工商业贷款) & 顶部卡片 5",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 HY OAS < 3.5%, NFCI < -0.3 | 🟡 HY OAS 3.6%~4.4% 或 60日走阔 >50bps | 🔴 HY OAS > 4.5%~5.0% (再融资冻结)",
                "实战核心含义": "决定二线算力租赁商 (CoreWeave 等) 与高负债企业生死；注意 NFCI 为周频滞后综合指标，盯拐点斜率而非绝对正负。"
            },
            {
                "传导层级": "第 5 层：全球美元阀门与反身性定仓",
                "核心监控指标": "美元指数 (DXY) + HYG 均线体系 (MA50/MA200) + QQQ/SPY 双轨反身性雷达",
                "当前实时读数 (变动 | 日期)": f"DXY: {_fmt_snap('US Dollar Index (美元指数 DXY / 贸易加权美元)', '', 2)} | 萨姆指标: {_fmt_snap('Sahm Rule Recession Indicator (萨姆法则衰退指标)', '%')}",
                "所在页面精确路径": "Tab 1 ➔ 🛡️ 子标签 5 (右下 DXY 图) & 顶部导航切换至 【🦅 索罗斯反身性大类配置 (Tab 5)】",
                "🟢 健康 / 🟡 摩擦 / 🔴 警报阈值": "🟢 站稳 MA50 & HYG>MA50 (100%仓位) | 🟡 跌破 MA20/HYG<MA50 (80%仓位) | 🟠 跌破 MA50+信用承压 (50%仓位) | 🔴 跌破 MA200+信用恶化 (0%清仓)",
                "实战核心含义": "将全部宏观流动性信号转化为 QQQ/SPY 具体仓位百分比 (100% / 80% / 50% / 0%) 的终极执行中枢。"
            }
        ]

        st.dataframe(pd.DataFrame(nav_rows), use_container_width=True, hide_index=True)

        st.info(
            "⏱️ **3 分钟标准看盘顺序（实战 SOP）**：\n"
            "1. **先扫一眼顶部 5 张核心体温卡片**：确认 `SOFR-IORB` 是否 > +5 bps（管道抢钱）、`MOVE` 是否 > 120（债市剧震）、`HY OAS` 是否突破 3.8%~4.0%（信用传染）。\n"
            "2. **若市场大跌但 `NFCI` 仍为负数（如 -0.46）**：切勿被周频滞后的 NFCI 麻痹！立即点开 **⚡ 子标签 2 (MOVE)** 与 **🎯 子标签 3 (10Y 期限溢价 & HYG/TLT)**，90% 的中期流动性退潮都先从长债期限溢价飙升和 `HYG/TLT` 破位开始。\n"
            "3. **决定具体买卖仓位**：切换到顶部主导航 **🦅 索罗斯反身性大类配置 (Tab 5)**，查看修复后的 `QQQ / SPY` 均线体系 (`MA20 / MA50 / MA200`) 与 `HYG / BAA10Y` 联动给出的多档仓位指令（`100%` / `80%` / `50%` / `0%`）。"
        )


# ==============================================================================
# 子主题 1：💧 流动性总闸门与央行水库 (Fed Plumbing & Global Liquidity)
# ==============================================================================
def _render_theme_liquidity(df_long: pd.DataFrame):
    st.markdown("### 💧 一、 流动性总闸门与央行水库 (Fed Plumbing & Money Supply)")
    st.caption("核心逻辑：**美联储净流动性 = 美联储总资产 (WALCL) - 财政部 TGA 账户 - 隔夜逆回购 (ON RRP)**。但决定商业银行能否真正放贷扩张风险资产的底层物理约束，是**商业银行准备金余额 (Bank Reserves)** 与**隔夜回购摩擦 (SOFR-IORB)**。")

    col_a, col_b = st.columns(2)

    with col_a:
        df_net_liq = df_long[df_long["metric_name"] == "Fed Net Liquidity (WALCL - TGA - RRP)"]
        df_reserves = df_long[df_long["metric_name"] == "US Bank Reserves (商业银行准备金余额)"]
        if not df_net_liq.empty:
            fig_liq = _plot_dual_axis_chart(
                df_net_liq, df_reserves,
                "美联储净流动性", "商业银行准备金 (WRESBAL)",
                "美联储净流动性 vs 商业银行准备金余额 (十亿美元)",
                unit1="USD Billion", unit2="USD Billion",
                color1="#059669", color2="#2563EB",
                hlines=[{"y": 3000, "color": "orange", "dash": "dash", "text": "准备金充裕度LCLoR警戒线 (~$3.0T)"}]
            )
            st.plotly_chart(fig_liq, use_container_width=True)
            with st.expander("📖 核心指标解读：美联储净流动性与银行准备金 LCLoR 红线", expanded=False):
                st.markdown("""
                - **净流动性公式**：$\\text{Net Liquidity} = \\text{WALCL} - \\text{TGA} - \\text{ON RRP}$。
                - **为什么必须同时盯住商业银行准备金 (WRESBAL)**：当逆回购（ON RRP）耗尽后，财政部发债回补 TGA 或美联储继续缩表（QT），将1:1直接抽干商业银行准备金。
                - **3万亿美元警戒线**：华尔街与美联储理事普遍认为，美国银行体系「最低舒适准备金水平 (LCLoR)」约在 **3.0万亿 ~ 3.2万亿美元**。一旦跌破该阈值，隔夜回购市场将随时爆发类似 2019 年 9 月的钱荒，迫使美联储停止 QT 甚至重启扩表（RMP）。
                """)

    with col_b:
        df_sofr_spread = df_long[df_long["metric_name"] == "SOFR - IORB Spread (隔夜资金面利差)"]
        df_sofr = df_long[df_long["metric_name"] == "SOFR (担保隔夜融资利率)"]
        df_iorb = df_long[df_long["metric_name"] == "IORB (准备金余额利率)"]
        if not df_sofr_spread.empty:
            fig_sofr = _plot_single_series(
                df_sofr_spread,
                "SOFR - IORB 隔夜资金面紧缺度利差 (bps)",
                unit="bps (基点)",
                color="#E11D48",
                fill_to_zero=True,
                hlines=[
                    {"y": 0, "color": "green", "dash": "dot", "text": "0 bps (流动性充裕)"},
                    {"y": 5, "color": "orange", "dash": "dash", "text": "+5 bps (季末/发债摩擦)"},
                    {"y": 15, "color": "red", "dash": "dash", "text": "+15 bps (钱荒警报/回购挤兑)"}
                ]
            )
            st.plotly_chart(fig_sofr, use_container_width=True)
            with st.expander("📖 核心指标解读：SOFR - IORB 管道摩擦温度计", expanded=False):
                st.markdown("""
                - **机制原理**：**IORB** 是美联储给商业银行存放准备金的无风险利息；**SOFR** 是机构用美债做抵押在回购市场借入隔夜现金的成本。
                - **实战信号**：正常充裕状态下，SOFR 应略低于 IORB（利差为负）。一旦 `SOFR - IORB` **持续转为正值并突破 +5 ~ +15 bps**，说明场内现金极度匮乏，中小银行与对冲基金宁可支付高于央行基准的溢价也在抢夺隔夜头寸，是金融管道堵塞的最直接高频信号。
                """)

    col_c, col_d = st.columns(2)
    with col_c:
        df_walcl = df_long[df_long["metric_name"] == "Fed Total Assets (美联储总资产 WALCL)"]
        df_m2_yoy = df_long[df_long["metric_name"] == "US M2 YoY (美国M2同比增速)"]
        if not df_walcl.empty or not df_m2_yoy.empty:
            fig_m2 = _plot_dual_axis_chart(
                df_walcl, df_m2_yoy,
                "美联储总资产 (WALCL)", "美国 M2 同比增速",
                "美联储资产负债表规模 vs 广义货币 M2 同比增速 (%)",
                unit1="USD Billion", unit2="%",
                color1="#1D4ED8", color2="#D97706",
                hlines=[{"y": 0, "color": "gray", "dash": "dot", "text": "M2 零增长线"}]
            )
            st.plotly_chart(fig_m2, use_container_width=True)
            with st.expander("📖 核心指标解读：央行扩缩表 (WALCL) 与广义货币 M2 增速", expanded=False):
                st.markdown("""
                - **WALCL（美联储总资产）**：衡量 QE（扩表印钞）与 QT（量化紧缩）的总量轨迹。
                - **M2 同比增速**：衡量实体经济中的广义货币派生能力。M2 同比触底回升并重返 **3%~5%** 温和扩张区间，说明银行信贷派生与财政支出正在对冲高利率压力，为风险资产提供温和名义 GDP 支撑。
                """)

    with col_d:
        df_2y = df_long[df_long["metric_name"] == "2Y Treasury Yield (2年期美债收益率)"]
        df_10y = df_long[df_long["metric_name"] == "10Y Treasury Yield (10年期美债收益率)"]
        df_30y = df_long[df_long["metric_name"] == "30Y Treasury Yield (30年期美债收益率)"]
        fig_yield = go.Figure()
        for d, name, col in [
            (df_2y, "2Y 美债 (政策预期锚)", "#10B981"),
            (df_10y, "10Y 美债 (资产定价锚)", "#2563EB"),
            (df_30y, "30Y 美债 (长端通胀与赤字锚)", "#9333EA")
        ]:
            if not d.empty:
                fig_yield.add_trace(go.Scatter(x=d["date"], y=d["value"], name=name, line=dict(width=2, color=col)))
        fig_yield.update_layout(
            title=dict(text="美国国债收益率曲线结构 (2Y / 10Y / 30Y)", font=dict(size=15)),
            yaxis_title="%", hovermode="x unified", height=390,
            margin=dict(l=20, r=20, t=45, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_yield, use_container_width=True)
        with st.expander("📖 核心指标解读：2Y / 10Y / 30Y 美债收益率联动机制", expanded=False):
            st.markdown("""
            - **2年期美债 (2Y)**：对美联储未来 12~24 个月降息/加息路径最敏感。
            - **10年期与30年期美债 (10Y/30Y)**：全球风险资产折现率分母。若美联储降息（2Y下降），但 10Y/30Y 因财政赤字发债洪峰或二次通胀预期而逆势上行（**熊市陡峭化 Bear Steepening**），会对科技股高估值形成严厉压制。
            """)


# ==============================================================================
# 子主题 2：⚡ 恐慌波动率与极端博弈 (Volatility, Tail Risk & Dark Pool)
# ==============================================================================
def _render_theme_volatility(df_long: pd.DataFrame):
    st.markdown("### ⚡ 二、 恐慌波动率与极端博弈 (Volatility, Tail Risk & Dark Pool)")
    st.caption("核心逻辑：**债市波动率 (MOVE) 是股市波动率 (VIX) 的先行母指标**。当 VIX 与 MOVE 同步飙升时，代表抵押品折价率上升触发跨资产去杠杆；而 SKEW 与暗池 DIX 则揭示聪明钱在期权尾部与场外暗池的真实底牌。")

    col1, col2 = st.columns(2)
    with col1:
        df_vix = df_long[df_long["metric_name"] == "CBOE VIX (标普500波动率恐慌指数)"]
        df_move = df_long[df_long["metric_name"] == "ICE BofA MOVE (美债波动率恐慌指数)"]
        if not df_vix.empty or not df_move.empty:
            fig_vm = _plot_dual_axis_chart(
                df_vix, df_move,
                "CBOE VIX (左轴)", "ICE BofA MOVE (右轴)",
                "股市恐慌指数 (VIX) vs 债市恐慌指数 (MOVE)",
                unit1="Index", unit2="Move Index",
                color1="#DC2626", color2="#7C3AED",
                hlines=[
                    {"y": 20, "color": "orange", "dash": "dot", "text": "VIX 20 (高波动分水岭)"},
                    {"y": 30, "color": "red", "dash": "dash", "text": "VIX 30 (恐慌抛售/左侧击球区)"}
                ]
            )
            st.plotly_chart(fig_vm, use_container_width=True)
            with st.expander("📖 核心指标解读：VIX 与 MOVE 股债恐慌共振", expanded=False):
                st.markdown("""
                - **ICE BofA MOVE 指数**：美债期权隐含波动率，被称为「流动性恐慌之母」。因为美债是全球金融体系最高等级的底层抵押品，当 **MOVE > 120~130** 时，美债抵押品折扣率（Haircut）被动调升，迫使风险平价基金（Risk Parity）与 CTA 基金无差别抛售股票与债券降杠杆。
                - **黄金买点规律**：当 VIX 飙升突破 **30~35**，随后 MOVE 率先见顶回落（说明美联储或财政部出面安抚债市），往往对应美股黄金坑底部的确认。
                """)

    with col2:
        df_skew = df_long[df_long["metric_name"] == "CBOE SKEW (黑天鹅尾部风险偏度指数)"]
        df_dix = df_long[df_long["metric_name"] == "SqueezeMetrics DIX (暗池买盘指数)"]
        if not df_skew.empty or not df_dix.empty:
            fig_sd = _plot_dual_axis_chart(
                df_skew, df_dix,
                "CBOE SKEW (黑天鹅指数)", "SqueezeMetrics DIX (暗池买盘%)",
                "CBOE SKEW 尾部风险偏度 vs 暗池买盘指标 (DIX)",
                unit1="Index", unit2="%",
                color1="#D97706", color2="#059669",
                hlines=[{"y": 145, "color": "red", "dash": "dash", "text": "SKEW 145 (机构密集抢购虚值Put防黑天鹅)"}]
            )
            st.plotly_chart(fig_sd, use_container_width=True)
            with st.expander("📖 核心指标解读：SKEW 黑天鹅防线与 DIX 暗池吸筹", expanded=False):
                st.markdown("""
                - **CBOE SKEW（偏度指数）**：衡量标普 500 深度虚值看跌期权（OTM Put）相对看涨期权的隐含波动率溢价。
                  - **危险背离**：若大盘连创新高、**VIX 处于 12~14 的极低位，但 SKEW 却飙升至 > 145~155**，说明表面风平浪静，但大型机构正在期权市场偷偷买入极端暴跌保险。
                - **SqueezeMetrics DIX（暗池指数）**：统计场外暗池交易中做市商短仓（对应机构真实买盘）占比。
                  - **底部吸筹**：当指数大跌或横盘，但 **DIX 连续多日 > 45%**，表明主权基金与长线机构正在暗池大举逢低吸筹。
                """)


# ==============================================================================
# 子主题 3：🎯 利率微观、期限溢价与跨资产估值 (Term Premium, ERP & Risk Appetite)
# ==============================================================================
def _render_theme_rates_valuation(df_long: pd.DataFrame):
    st.markdown("### 🎯 三、 利率微观、期限溢价与跨资产估值 (Term Premium, ERP & Risk Appetite)")
    st.caption("核心逻辑：拆解名义美债收益率背后的三大推手（**实际利率、通胀预期、期限溢价**），并通过**动态股权风险溢价 (ERP)** 与**跨资产风偏比率 (HYG/TLT、铜金比)** 评估股市估值性价比。")

    col1, col2 = st.columns(2)
    with col1:
        df_tp = df_long[df_long["metric_name"] == "NY Fed ACM 10Y Term Premium (纽约联储10年期美债期限溢价)"]
        df_10y = df_long[df_long["metric_name"] == "10Y Treasury Yield (10年期美债收益率)"]
        if not df_tp.empty:
            fig_tp = _plot_dual_axis_chart(
                df_tp, df_10y,
                "ACM 10Y 期限溢价", "10Y 美债名义收益率",
                "纽约联储 ACM 10年期期限溢价 vs 10Y美债收益率 (%)",
                unit1="%", unit2="%",
                color1="#9333EA", color2="#2563EB",
                hlines=[{"y": 0, "color": "gray", "dash": "dash", "text": "0% 期限溢价中枢"}]
            )
            st.plotly_chart(fig_tp, use_container_width=True)
            with st.expander("📖 核心指标解读：纽约联储 ACM 期限溢价 (Term Premium)", expanded=False):
                st.markdown("""
                - **拆解公式**：$10\\text{Y 名义利率} = \\text{未来短期实际利率预期} + \\text{通胀预期} + \\text{期限溢价 (Term Premium)}$。
                - **为什么期限溢价飙升对股市最致命**：
                  - 如果 10Y 利率上升是因为经济强劲（实际利率温和上升），企业盈利（EPS）增长可以抵消分母压力；
                  - 但如果是因为**财政赤字失控、长债拍卖无人接盘或美债供需失衡导致「期限溢价」飙升转正（如突破 +0.5% ~ +1.0%）**，这属于纯粹的「无风险资产要求更高风险补偿」，会直接抽干股市流动性并杀估值。
                """)

    with col2:
        df_real = df_long[df_long["metric_name"] == "10Y Real Interest Rate (10年期TIPS实际利率)"]
        df_bei = df_long[df_long["metric_name"] == "10Y Breakeven Inflation (10年期盈亏平衡通胀率)"]
        if not df_real.empty or not df_bei.empty:
            fig_rb = _plot_dual_axis_chart(
                df_real, df_bei,
                "10Y TIPS 实际利率", "10Y 盈亏平衡通胀预期",
                "10年期美债拆解：TIPS 实际利率 vs 盈亏平衡通胀预期 (%)",
                unit1="%", unit2="%",
                color1="#0284C7", color2="#EA580C",
                hlines=[{"y": 2.0, "color": "red", "dash": "dot", "text": "2.0% 高实际利率压制线"}]
            )
            st.plotly_chart(fig_rb, use_container_width=True)
            with st.expander("📖 核心指标解读：10Y TIPS 实际利率与通胀预期", expanded=False):
                st.markdown("""
                - **10Y TIPS 实际利率 (DFII10)**：剔除通胀后的真实资金成本，是黄金、比特币及高估值成长股（纳斯达克）的直接反函数分母。当实际利率持续高于 **2.0% ~ 2.2%** 时，无风险吃息资产极具吸引力，高估值资产容错率大幅下降。
                - **10Y 盈亏平衡通胀率 (T10YIE)**：债市交易员真金白银交易出来的长期通胀预期。锚定在 **2.1% ~ 2.4%** 属于健康再通胀；若突破 **2.6%** 则引发二次通胀恐慌，若跌破 **1.8%** 则交易通缩衰退。
                """)

    col3, col4 = st.columns(2)
    with col3:
        df_erp = df_long[df_long["metric_name"] == "SP500 Dynamic ERP (标普500动态股权风险溢价)"]
        df_fpe = df_long[df_long["metric_name"] == "SP500 Forward PE (标普500预期市盈率)"]
        if not df_erp.empty or not df_fpe.empty:
            fig_erp = _plot_dual_axis_chart(
                df_erp, df_fpe,
                "标普 500 动态 ERP (%)", "标普 500 Forward PE (倍)",
                "标普 500 动态股权风险溢价 (ERP) vs 预期市盈率 (Forward PE)",
                unit1="%", unit2="x (倍)",
                color1="#DC2626", color2="#1D4ED8",
                hlines=[
                    {"y": 0, "color": "red", "dash": "dash", "text": "ERP = 0% (股票相对美债零溢价警戒)"},
                    {"y": 1.0, "color": "green", "dash": "dot", "text": "ERP = 1.0% (中等性价比)"}
                ]
            )
            st.plotly_chart(fig_erp, use_container_width=True)
            with st.expander("📖 核心指标解读：标普 500 动态 ERP 与股债性价比", expanded=False):
                st.markdown("""
                - **计算公式**：$\\text{Dynamic ERP} = \\frac{1}{\\text{Forward PE}} \\times 100\\% - 10\\text{Y Nominal Treasury Yield}$。
                - **实战定仓意义**：
                  - 当 **ERP <= 0%**（例如 Forward PE 达 22x 对应盈利收益率 4.55%，而 10Y 美债高达 4.5%），意味着持有股票的风险补偿为零，股指完全依赖 EPS 超预期增长驱动，一旦财报季指引瑕疵极易发生 10% 级别的均值回归回调。
                  - 当 **ERP > 2.0% ~ 3.0%** 时，股票相对债券具备极高安全边际，是长线重仓击球区。
                """)

    with col4:
        df_hyg_tlt = df_long[df_long["metric_name"] == "HYG/TLT Ratio (高收益债与长债风偏比率)"]
        df_cu_au = df_long[df_long["metric_name"] == "Copper/Gold Ratio (铜金比 x1000)"]
        if not df_hyg_tlt.empty or not df_cu_au.empty:
            fig_cross = _plot_dual_axis_chart(
                df_hyg_tlt, df_cu_au,
                "HYG/TLT 信用风偏比", "铜金比 (x1000)",
                "跨资产真实风险偏好：HYG/TLT 比率 vs 铜金比 (Copper/Gold)",
                unit1="Ratio", unit2="Ratio x1000",
                color1="#059669", color2="#D97706"
            )
            st.plotly_chart(fig_cross, use_container_width=True)
            with st.expander("📖 核心指标解读：HYG/TLT 与铜金比跨资产验真", expanded=False):
                st.markdown("""
                - **HYG/TLT（垃圾债/长端国债比）**：趋势向上代表资金追逐企业信用风险、抛售避险国债（Risk-On）；若标普 500 创新高但 **HYG/TLT 率先掉头向下破位**，说明债券市场聪明钱已在提前撤退避险。
                - **铜金比（Copper/Gold Ratio）**：「铜博士」反映全球工业与 AI 电力基建实体需求，「黄金」反映避险与法币信用对冲。铜金比企稳上行是周期复苏与再通胀交易最坚实的物理验证。
                """)


# ==============================================================================
# 子主题 4：🏦 商业银行、信贷周期与金融条件 (Credit Cycle, SLOOS & NFCI)
# ==============================================================================
def _render_theme_credit_banking(df_long: pd.DataFrame):
    st.markdown("### 🏦 四、 商业银行、信贷周期与金融条件 (Credit Cycle, SLOOS & NFCI)")
    st.caption("核心逻辑：央行货币政策必须通过**商业银行信贷窗口**与**企业信用债市场**才能传导至实体经济。**高收益债利差 (HY OAS)** 是企业违约风险的高频听诊器，而 **SLOOS 银行信贷紧缩标准** 则是企业违约潮与工商业贷款周期的领先指标。")

    col1, col2 = st.columns(2)
    with col1:
        df_hy = df_long[df_long["metric_name"] == "US High Yield OAS (高收益债信用利差)"]
        df_nfci = df_long[df_long["metric_name"] == "Chicago Fed NFCI (芝加哥联储全国金融条件指数)"]
        if not df_hy.empty or not df_nfci.empty:
            fig_credit = _plot_dual_axis_chart(
                df_hy, df_nfci,
                "高收益债利差 HY OAS (%)", "芝加哥联储 NFCI",
                "美国高收益债信用利差 (HY OAS) vs 芝加哥联储金融条件指数 (NFCI)",
                unit1="%", unit2="Index",
                color1="#DC2626", color2="#2563EB",
                hlines=[
                    {"y": 3.5, "color": "green", "dash": "dot", "text": "HY OAS 3.5% (信用环境健康)"},
                    {"y": 5.0, "color": "red", "dash": "dash", "text": "HY OAS 5.0% (信用危机/违约传染警戒)"}
                ]
            )
            st.plotly_chart(fig_credit, use_container_width=True)
            with st.expander("📖 核心指标解读：高收益债利差 (HY OAS) 与芝加哥联储 NFCI", expanded=False):
                st.markdown("""
                - **US High Yield OAS (BAMLH0A0HYM2)**：垃圾债相对美债的期权调整利差，是企业融资环境的「生死线」。
                  - **< 3.5%**：信用极度宽松，哪怕高负债企业也能轻松发债滚续，股市无系统性崩盘风险。
                  - **突破 4.5% ~ 5.5%**：信用利差非线性走阔，低评级企业再融资冻结，往往伴随美股戴维斯双杀。
                - **芝加哥联储 NFCI**：综合货币市场、债市、股市和影子银行的 105 项指标。**< 0 代表金融环境宽松**，**> 0 代表进入紧缩压力区**。
                """)

    with col2:
        df_sloos = df_long[df_long["metric_name"] == "Fed SLOOS Tightening Standards (银行收紧工商业贷款标准净比例)"]
        df_loans = df_long[df_long["metric_name"] == "US Commercial & Industrial Loans YoY (工商业贷款同比增速)"]
        if not df_sloos.empty or not df_loans.empty:
            fig_sloos = _plot_dual_axis_chart(
                df_sloos, df_loans,
                "SLOOS 银行收紧信贷净比例 (%)", "工商业贷款同比增速 (%)",
                "美联储银行信贷紧缩调查 (SLOOS) vs 工商业贷款同比增速 (%)",
                unit1="%", unit2="%",
                color1="#EA580C", color2="#059669",
                hlines=[
                    {"y": 0, "color": "gray", "dash": "dot", "text": "0% 枯荣分界线"},
                    {"y": 20, "color": "red", "dash": "dash", "text": "SLOOS > 20% (商业银行普遍惜贷)"}
                ]
            )
            st.plotly_chart(fig_sloos, use_container_width=True)
            with st.expander("📖 核心指标解读：SLOOS 信贷调查与工商业贷款周期", expanded=False):
                st.markdown("""
                - **美联储高级信贷员意见调查 (SLOOS - DRTSCILM)**：统计商业银行收紧对大中型企业工商业贷款（C&I Loans）标准的净百分比。
                - **领先传导规律**：**SLOOS 信贷收紧通常领先企业违约率和工商业贷款增速约 2~4 个季度**。当 SLOOS 从高位显著回落并重新接近 **0% 甚至转负（放宽信贷）**，同时工商业贷款同比增速触底回升，标志着实体经济信贷周期正式迈入新一轮扩张。
                """)


# ==============================================================================
# 子主题 5：🛡️ 衰退定量、实体经济与居民韧性 (Recession Radar, Macro & Dollar)
# ==============================================================================
def _render_theme_recession_economy(df_long: pd.DataFrame):
    st.markdown("### 🛡️ 五、 衰退定量、实体经济与全球美元脉冲 (Recession Radar, Macro & DXY)")
    st.caption("核心逻辑：用**萨姆法则 + 10Y-2Y 曲线解除倒挂 + 四周平滑初请失业金**构建硬着陆三道防线；用**零售销售 vs 核心 PCE** 检验美国消费引擎（占 GDP 70%）的真实抗通胀韧性；用**美元指数 (DXY)** 监控全球美元流动性总阀门。")

    col1, col2 = st.columns(2)
    with col1:
        df_sahm = df_long[df_long["metric_name"] == "Sahm Rule Recession Indicator (萨姆法则衰退指标)"]
        df_10_2 = df_long[df_long["metric_name"] == "10Y-2Y Treasury Spread (10年-2年美债利差)"]
        if not df_sahm.empty or not df_10_2.empty:
            fig_rec = _plot_dual_axis_chart(
                df_sahm, df_10_2,
                "萨姆法则衰退指标 (%)", "10Y-2Y 收益率利差 (%)",
                "硬着陆定量预警：萨姆法则 (Sahm Rule) vs 10Y-2Y 收益率曲线",
                unit1="%", unit2="%",
                color1="#DC2626", color2="#2563EB",
                hlines=[
                    {"y": 0.50, "color": "red", "dash": "dash", "text": "萨姆法则 0.50% 衰退触发阈值"},
                    {"y": 0.0, "color": "gray", "dash": "dot", "text": "0% (10Y-2Y 倒挂解除线)"}
                ]
            )
            st.plotly_chart(fig_rec, use_container_width=True)
            with st.expander("📖 核心指标解读：萨姆法则与 10Y-2Y「解除倒挂」的真相", expanded=False):
                st.markdown("""
                - **萨姆法则 (Sahm Rule)**：当美国失业率 3 个月移动平均值相对于过去 12 个月最低点上升 **>= 0.50 个百分点**时，历史上标志着衰退开始（若由移民/劳动力供给激增导致，则需结合初请失业金交叉验证）。
                - **10Y-2Y 曲线「倒挂解除 (Un-inversion)」规律**：历史上经济衰退往往不是发生在曲线深幅倒挂期间，而是发生在**曲线从倒挂重新转正（陡峭化）的阶段**。
                  - **牛市陡峭化 (Bull Steepening)**：因经济恶化迫使美联储紧急大幅降息导致 2Y 暴跌，属于衰退确认信号；
                  - **软着陆陡峭化**：失业率温和可控、萨姆法则稳居 0.5% 以下时的预防性降息转正，则支持周期与成长股共振向上。
                """)

    with col2:
        df_icsa = df_long[df_long["metric_name"] == "US Initial Jobless Claims (美国初请失业金人数)"]
        df_icsa_ma = df_long[df_long["metric_name"] == "US 4-Week MA Initial Claims (初请失业金四周均值)"]
        if not df_icsa.empty or not df_icsa_ma.empty:
            fig_job = _plot_dual_axis_chart(
                df_icsa, df_icsa_ma,
                "单周初请失业金人数", "四周移动平均初请 (平滑噪音)",
                "美国就业高频防线：单周初请失业金 vs 四周移动均值 (人)",
                unit1="Persons", unit2="Persons",
                color1="#94A3B8", color2="#E11D48",
                hlines=[
                    {"y": 240000, "color": "orange", "dash": "dot", "text": "24万人 (就业边际降温)"},
                    {"y": 280000, "color": "red", "dash": "dash", "text": "28万人 (裁员潮/实质衰退警报)"}
                ]
            )
            st.plotly_chart(fig_job, use_container_width=True)
            with st.expander("📖 核心指标解读：初请失业金四周均值 (IC4WSA)", expanded=False):
                st.markdown("""
                - **为什么看四周均值**：单周初请数据极易受飓风、节假日、汽车厂停工等季节性噪音干扰，**四周移动平均值 (IC4WSA)** 是美联储判断真实裁员趋势的核心高频锚点。
                - **阈值判断**：**< 24万** 代表劳动力市场依然处于「低招聘、低裁员」的稳态；一旦四周均值持续突破 **26万 ~ 28万**，则验证企业利润受损开始实质性裁员。
                """)

    col3, col4 = st.columns(2)
    with col3:
        df_retail = df_long[df_long["metric_name"] == "US Retail Sales YoY (美国零售销售同比增速)"]
        df_pce = df_long[df_long["metric_name"] == "US Core PCE YoY (美国核心PCE物价同比-美联储锚)"]
        if not df_retail.empty or not df_pce.empty:
            fig_rp = _plot_dual_axis_chart(
                df_retail, df_pce,
                "零售销售同比增速 (%)", "核心 PCE 物价同比 (%)",
                "美国消费韧性与通胀粘性：零售销售同比 vs 核心 PCE 同比 (%)",
                unit1="%", unit2="%",
                color1="#059669", color2="#D97706",
                hlines=[{"y": 2.0, "color": "red", "dash": "dot", "text": "美联储 2.0% 通胀目标锚"}]
            )
            st.plotly_chart(fig_rp, use_container_width=True)
            with st.expander("📖 核心指标解读：实际零售消费韧性 (Retail Sales - Core PCE)", expanded=False):
                st.markdown("""
                - **核心看点**：美国零售销售公布的是「名义值」（包含物价上涨）。只有当 **零售销售同比增速 > 核心 PCE 同比增速** 时，才说明美国居民的「实际购买量」仍在正增长，软着陆根基稳固。
                """)

    with col4:
        df_dxy = df_long[df_long["metric_name"] == "US Dollar Index (美元指数 DXY / 贸易加权美元)"]
        df_unrate = df_long[df_long["metric_name"] == "US Unemployment Rate (美国失业率)"]
        if not df_dxy.empty or not df_unrate.empty:
            fig_dxy = _plot_dual_axis_chart(
                df_dxy, df_unrate,
                "美元指数 (DXY)", "美国失业率 (%)",
                "全球流动性阀门：美元指数 (DXY) vs 美国失业率 (%)",
                unit1="Index", unit2="%",
                color1="#1D4ED8", color2="#DC2626"
            )
            st.plotly_chart(fig_dxy, use_container_width=True)
            with st.expander("📖 核心指标解读：美元指数 (DXY) 与跨国巨头 EPS 汇兑效应", expanded=False):
                st.markdown("""
                - **全球流动性阀门**：美元是全球贸易融资与离岸美元债的计价货币。DXY 急速飙升（如突破 106~108）会造成全球美元流动性紧缩，同时由于标普 500 科技巨头约 **40%~50% 营收来自海外**，强美元会直接造成财报汇兑损失并压制海外需求。
                """)


# ==============================================================================
# 子主题 6：⚡ AI 算力供应链、物理瓶颈与电力基建 (AI Supply Chain & Power Grid)
# ==============================================================================
def _render_theme_ai_supply_chain(df_long: pd.DataFrame):
    st.markdown("### ⚡ 六、 AI 算力供应链、物理瓶颈传导与电力基建 (AI Supply Chain & Power Grid)")
    st.caption("核心逻辑：穿透半导体与数据中心基建全链条，聚焦**「晶圆先进封装 (CoWoS) ➔ 高带宽存储 (HBM) ➔ 光互连 (800G/1.6T) ➔ 电网变压器与液冷温控 (Power & Cooling)」**四大物理刚性瓶颈，结合宏观工业产出与交货周期验证硬件景气度。")

    # 1. 全链条四大物理瓶颈与核心卡位矩阵 (结构化交互卡片)
    st.markdown("#### 🔬 1. AI 算力基建四大物理瓶颈与领先观测指标矩阵")
    b_cols = st.columns(4)

    with b_cols[0]:
        with st.container(border=True):
            st.markdown("##### 🧱 瓶颈一：CoWoS 与先进制程")
            st.caption("**物理卡位**：台积电 3nm/2nm 晶圆与 CoWoS-L/S 先进封装中介层产能。")
            st.markdown("""
            - **核心标的**：`TSM`, `ASML`, `AMAT`, `KLAC`
            - **高频先行指标**：
              1. **每月 10 日**：台积电月度合并营收 YoY/MoM；
              2. **台积电法说会**：全年 CoWoS 产能翻倍指引与设备交期；
              3. **ASML 季报**：极紫外光刻机 (EUV/High-NA) 新增订单 (Net Bookings)。
            """)

    with b_cols[1]:
        with st.container(border=True):
            st.markdown("##### 🧠 瓶颈二：HBM 存储墙与良率")
            st.caption("**物理卡位**：HBM3e / HBM4 堆叠良率、硅通孔 (TSV) 产能与标准 DRAM 挤出效应。")
            st.markdown("""
            - **核心标的**：`SK Hynix`, `MU`, `Samsung`
            - **高频先行指标**：
              1. **每月 1 日**：韩国产业通商资源部公布月度半导体出口额 YoY；
              2. **次年产能售罄率**：海力士/美光季报披露次年 HBM 锁单排期；
              3. **DRAMeXchange**：DDR5 与企业级 eSSD 合约价环比涨幅。
            """)

    with b_cols[2]:
        with st.container(border=True):
            st.markdown("##### 🌐 瓶颈三：高速光互连与组网")
            st.caption("**物理卡位**：万卡/十万卡集群无损以太网交换机、800G/1.6T 光模块、DSP 芯片与激光器 (EML/CW)。")
            st.markdown("""
            - **核心标的**：`AVGO`, `ANET`, `MRVL`, `COHR`, `LITE`, `CRDO`
            - **高频先行指标**：
              1. **每月 5~10 日**：台湾服务器 ODM 四大天王（鸿海/广达/纬颖/纬创）与 BMC 龙头**信骅 (5274.TW)** 月度营收；
              2. **交换机端口升级**：博通 Tomahawk 5/6 与 1.6T 光模块出货放量节奏。
            """)

    with b_cols[3]:
        with st.container(border=True):
            st.markdown("##### ⚡ 瓶颈四：电力变压器与液冷")
            st.caption("**物理卡位**：单机柜功耗从 40kW 跃升至 120kW+ (GB200/Rubin)，电网并网排队、大功率变压器与液冷 CDU 成为终极硬约束。")
            st.markdown("""
            - **核心标的**：`VRT` (维谛), `ETN` (伊顿), `GEV` (GE Vernova), `CEG`, `VST` (核电/独立发电)
            - **高频先行指标**：
              1. **Vertiv / Eaton 季报**：在手订单 (Backlog) 规模与 **订单出货比 (Book-to-Bill > 1.2x)**；
              2. **北美电网 PPA 电价**：云厂签署核电/燃气长期购电协议溢价。
            """)

    st.markdown("---")

    # 2. 算力基建与半导体周期的宏观硬数据验证图
    st.markdown("#### 📈 2. 半导体与算力硬件周期的宏观硬数据交叉验证")
    col1, col2 = st.columns(2)

    with col1:
        df_ind = df_long[df_long["metric_name"] == "US Industrial Production YoY (美国工业产出同比增速)"]
        df_cu_au = df_long[df_long["metric_name"] == "Copper/Gold Ratio (铜金比 x1000)"]
        if not df_ind.empty or not df_cu_au.empty:
            fig_ind = _plot_dual_axis_chart(
                df_ind, df_cu_au,
                "美国工业产出同比 (%)", "铜金比 (x1000)",
                "实体制造业与电力基建脉搏：美国工业产出同比 vs 铜金比",
                unit1="%", unit2="Ratio x1000",
                color1="#2563EB", color2="#D97706",
                hlines=[{"y": 0, "color": "gray", "dash": "dot", "text": "工业产出 0% 荣枯线"}]
            )
            st.plotly_chart(fig_ind, use_container_width=True)
            with st.expander("📖 核心指标解读：工业产出与「铜博士」对数据中心基建的映射", expanded=False):
                st.markdown("""
                - **AI 数据中心本质是重工业基建**：一座吉瓦（GW）级 AI 数据中心需要消耗海量的铜缆、母线排、配电开关柜与冷却管道。
                - 当**美国工业产出同比转正上行**且**铜金比企稳抬升**时，印证云厂商的 CapEx 预算正在真实转化为物理世界的电网改造与机房交付。
                """)

    with col2:
        df_capex_proxy = df_long[df_long["metric_name"] == "US Commercial & Industrial Loans YoY (工商业贷款同比增速)"]
        df_real = df_long[df_long["metric_name"] == "10Y Real Interest Rate (10年期TIPS实际利率)"]
        if not df_capex_proxy.empty or not df_real.empty:
            fig_cap = _plot_dual_axis_chart(
                df_capex_proxy, df_real,
                "工商业贷款同比增速 (%)", "10Y TIPS 实际利率 (%)",
                "企业资本开支金融环境：工商业贷款增速 vs 10Y 实际资金成本",
                unit1="%", unit2="%",
                color1="#059669", color2="#DC2626"
            )
            st.plotly_chart(fig_cap, use_container_width=True)
            with st.expander("📖 核心指标解读：二线云厂 (Neocloud) 与企业 AI 部署的融资约束", expanded=False):
                st.markdown("""
                - **四巨头 vs 算力租赁商 (CoreWeave 等)**：微软、谷歌等超级云厂主要靠自身经营现金流（OCF）支撑 CapEx；但大量二线算力租赁商（Neoclouds）与传统企业采购 GPU 高度依赖债务融资（GPU 抵押贷款）与工商业信贷。
                - 若 **10Y 实际利率居高不下** 且 **商业银行工商业贷款持续萎缩**，二线算力买家将面临资金链断裂风险，导致算力需求向头部四巨头过度集中。
                """)

    # 3. 产业链上下游传导时滞与预警信号速查表
    st.markdown("#### 🗓️ 3. AI 算力全链条传导时滞与见顶/见底信号速查表")
    ai_chain_summary = pd.DataFrame([
        {
            "传导层级": "第一棒：终端金主预算",
            "核心环节": "四大云厂 (MSFT / META / GOOGL / AMZN)",
            "核心观测指标": "季度 CapEx 指引上调幅度、云业务 AI 贡献占比、服务器折旧年限变更",
            "领先/滞后关系": "全链条总水源 (领先硬件出货 2~3 个季度)",
            "🟢 景气扩张信号": "CapEx 连续上调且自由现金流可覆盖 >70%",
            "🔴 周期见顶预警": "云厂宣布延长 GPU 折旧年限、严控 CapEx 或下调 ROI 预期"
        },
        {
            "传导层级": "第二棒：产能物理锁死",
            "核心环节": "晶圆代工与存储 (TSMC / SK Hynix / MU)",
            "核心观测指标": "TSMC 每月10日营收、CoWoS 扩产倍增率、HBM 次年产能售罄状态",
            "领先/滞后关系": "领先 GPU 实际交付 1~2 个季度",
            "🟢 景气扩张信号": "CoWoS 供不应求、HBM 次年产能提前半年 100% 锁死",
            "🔴 周期见顶预警": "客户推迟 CoWoS 机器进场 (Pull-in 变 Push-out)、标准 DRAM 跌价"
        },
        {
            "传导层级": "第三棒：主芯片与网络",
            "核心环节": "GPU / ASIC / 光互连 (NVDA / AVGO / ANET)",
            "核心观测指标": "数据中心单季环比增量 ($B)、毛利率 (>73%)、800G/1.6T 光模块出货",
            "领先/滞后关系": "同步核心指标 (季度财报确认)",
            "🟢 景气扩张信号": "新一代架构 (Blackwell/Rubin) 放量带动 ASP 与毛利率双升",
            "🔴 周期见顶预警": "毛利率连续两个季度下滑、存货周转天数 (DIO) 异常飙升"
        },
        {
            "传导层级": "第四棒：整机组装交付",
            "核心环节": "台湾 ODM 与液冷电源 (鸿海 / 广达 / 纬颖 / VRT / 信骅)",
            "核心观测指标": "台厂每月5~10日营收 YoY/MoM、Vertiv 订单出货比 (Book-to-Bill)",
            "领先/滞后关系": "高频月度验钞机 (提前 1 个月预判 NVDA 季报)",
            "🟢 景气扩张信号": "广达/鸿海/信骅月度营收连续创历史新高、液冷订单 Book-to-Bill > 1.2x",
            "🔴 周期见顶预警": "ODM 月度营收环比连续两个月失速、机柜良率卡壳导致交付顺延"
        },
        {
            "传导层级": "第五棒：电力与土地硬约束",
            "核心环节": "电网设备与核电/燃气 PPA (ETN / GEV / CEG / VST)",
            "核心观测指标": "高压变压器交货周期 (Lead Time)、云厂核电 PPA 签约电价 ($/MWh)",
            "领先/滞后关系": "中长期物理天花板 (决定 2026~2030 算力扩张上限)",
            "🟢 景气扩张信号": "云厂溢价包揽核电重启产能、电网设备商积压订单排至 3 年后",
            "🔴 周期见顶预警": "监管机构否决数据中心并网协议 (如 FERC 驳回共址供电) 或电力审批冻结"
        }
    ])
    st.dataframe(ai_chain_summary, use_container_width=True, hide_index=True)


# ==============================================================================
# 子主题 7：🤖 AI 产业链「验证期」五层高频监控与融资反身性 (Zhou Mo / 丰搭 AI 体系)
# ==============================================================================
def _render_theme_ai_verification(df_long: pd.DataFrame):
    st.markdown("### 🤖 七、 AI 产业链「验证期」五层高频监控与宏观融资反身性全景看板")
    st.caption(
        "核心框架来源：梳理自 **周默（丰搭 AI 创始人）《AI 投资进入验证期》** 全产业链实证拆解体系（[视频原片链接](http://www.youtube.com/watch?v=MIUNgTlyjXw)）。"
        "当 AI 叙事从「盲目扩产期」进入「商业化与现金流验证期」，必须穿透 **前沿模型层 ➔ 企业 Token 路由微观层 ➔ 四大云厂 CapEx/FCF 账本 ➔ 应用层留存与单用户经济模型 ➔ 硬件 ODM 出货与 Neocloud 债务反身性** 五个维度交叉验真。"
    )

    # 1. 顶部实时宏观利率/信用与 AI 融资链反身性联动仪表盘
    y10 = _get_metric_snapshot(df_long, "10Y Treasury Yield (10年期美债收益率)")
    real10 = _get_metric_snapshot(df_long, "10Y Real Interest Rate (10年期TIPS实际利率)")
    hy_oas = _get_metric_snapshot(df_long, "US High Yield OAS (高收益债信用利差)")
    sofr_sp = _get_metric_snapshot(df_long, "SOFR - IORB Spread (隔夜资金面利差)")

    st.markdown("#### 🔗 实时宏观资金成本对 AI 算力资本链（Neocloud 债务 & CSP 自由现金流）反身性传导监控")
    k_cols = st.columns(4)
    with k_cols[0]:
        with st.container(border=True):
            st.caption("🏦 10Y 美债名义利率 (Neocloud 重定价锚)")
            if y10:
                y_state = "🔴 破5%高危" if y10["val"] >= 4.8 else ("🟡 偏紧(>4.2%)" if y10["val"] >= 4.2 else "🟢 温和")
                st.metric(f"10Y 美债 ({y10['date']})", f"{y10['val']:.2f}%", f"{y10['delta']:+.2f}%", delta_color="inverse")
                st.caption(f"状态: **{y_state}** (决定 CoreWeave 等 GPU 抵押贷利率)")
            else:
                st.metric("10Y 美债", "N/A")
    with k_cols[1]:
        with st.container(border=True):
            st.caption("💎 10Y TIPS 实际利率 (长久期 AI 估值分母)")
            if real10:
                r_state = "🔴 严厉杀估值(>2.0%)" if real10["val"] >= 2.0 else ("🟡 中性偏紧" if real10["val"] >= 1.5 else "🟢 宽松")
                st.metric(f"10Y TIPS ({real10['date']})", f"{real10['val']:.2f}%", f"{real10['delta']:+.2f}%", delta_color="inverse")
                st.caption(f"状态: **{r_state}** (压制 200x~2000x P/S 无收入 Neolabs)")
            else:
                st.metric("10Y TIPS", "N/A")
    with k_cols[2]:
        with st.container(border=True):
            st.caption("⚠️ 高收益债利差 HY OAS (算力债发债生死线)")
            if hy_oas:
                h_state = "🔴 再融资冻结(>4.5%)" if hy_oas["val"] >= 4.5 else ("🟡 利差走阔(>3.5%)" if hy_oas["val"] >= 3.5 else "🟢 发债顺畅")
                st.metric(f"HY OAS ({hy_oas['date']})", f"{hy_oas['val']:.2f}%", f"{hy_oas['delta']:+.2f}%", delta_color="inverse")
                st.caption(f"状态: **{h_state}** (监控 Neocloud 净债务/EBITDA 违约传染)")
            else:
                st.metric("HY OAS", "N/A")
    with k_cols[3]:
        with st.container(border=True):
            st.caption("🔥 AI 资本链最脆弱环节警示")
            st.markdown(
                "**CoreWeave 等算力租赁商 (Neocloud)** 约 **20% 增量算力**租给无收入 Neolabs。"
                "若 **高利率维持 + GPU 时租下跌** 导致 EBITDA 缩水，将触发债权人收紧信贷的**索罗斯负向反身性螺旋**。"
            )

    # 2. 五大产业链层级 + 个人实操日历 交互分页
    layer_tabs = st.tabs([
        "1️⃣ 前沿模型层 (S-1/ARR/算力拆分)",
        "2️⃣ 企业 Token 路由与需求微观",
        "3️⃣ 四大云厂 CSP (CapEx/FCF/ASIC)",
        "4️⃣ 应用层 (Copilot/Agent单用户账本/广告)",
        "5️⃣ 硬件供应链、Neocloud债务与2028电力",
        "🗓️ 个人高频跟踪SOP与官方信源索引"
    ])

    # --------------------------------------------------------------------------
    # Layer 1: 前沿模型层 (Anthropic / OpenAI / Neolabs)
    # --------------------------------------------------------------------------
    with layer_tabs[0]:
        st.markdown("#### 🧠 一、 前沿模型层（Anthropic / OpenAI / Neolabs）核心验证指标")
        st.info(
            "💡 **核心验证逻辑**：打破华尔街过去「按数据中心机房容量线性外推模型公司收入」的粗放假设！"
            "重点核查 **付费推理算力占比是否下降**、**RPO 长单锁定期是否过低**，以及 **7500 亿美元刚性算力承诺下的营业利润率弹性**。"
        )
        df_l1 = pd.DataFrame([
            {
                "核心指标名称": "1. ARR（年度经常性收入）及月度环比增速",
                "验证期核心基准与数值实证": "Anthropic 9月底 ARR 约 700 亿美元 ➔ 10月底约 800 亿美元；月度环比增速边际放缓直接引发二级市场算力链抛售。",
                "验证逻辑与多空分水岭": "衡量需求侧真实景气度及头部厂商价格战「跷跷板效应」的首要温度计；在刚性算力成本下，ARR 增速放缓会直接转化为亏损扩大。",
                "官方获取渠道与直达方式": "SEC EDGAR Form S-1 / S-1/A 招股书 (Anthropic CIK: 0002130357)；WSJ / The Information 月度私募财务追踪。"
            },
            {
                "核心指标名称": "2. 付费推理算力 vs. 训练算力成本占比",
                "验证期核心基准与数值实证": "Anthropic Q3 仅 30% 算力用于付费推理、70% 用于训练；推理算力成本占比首次出现下降！",
                "验证逻辑与多空分水岭": "直接证伪或证实模型公司是否仍处于「推理算力受限 (Capacity-constrained)」状态；推理占比下降打破了按机房容量线性外推收入的假设。",
                "官方获取渠道与直达方式": "SEC Form S-1 招股书 MD&A 及 Cost of Revenue / R&D 章节中的算力支出 (Compute Costs) 拆分明细。"
            },
            {
                "核心指标名称": "3. RPO（剩余履约义务）占 ARR 比重",
                "验证期核心基准与数值实证": "Anthropic RPO 仅约 100 亿美元（占 ARR 略超 10%），远低于成熟 SaaS 公司（如 Snowflake 约 50%）及云巨头。",
                "验证逻辑与多空分水岭": "衡量未来 12 个月收入确定性与企业长单锁定期；RPO 占比仅 ~10% 说明目前仍以按量 API 调用为主，收入能见度与客户粘性偏低。",
                "官方获取渠道与直达方式": "SEC Form S-1 / 10-Q / 10-K 财报附注 Note on Revenue Recognition — Remaining Performance Obligations。"
            },
            {
                "核心指标名称": "4. 长期算力采购承诺 (Long-term Compute Commitments)",
                "验证期核心基准与数值实证": "Anthropic 签署约 7500 亿美元长期不可撤销算力租赁与采购承诺。",
                "验证逻辑与多空分水岭": "衡量刚性成本压力与对 AGI 时间表的激进押注；在支出端完全刚性的前提下，ARR 增速直接决定营业利润率 (Operating Margin) 的生死。",
                "官方获取渠道与直达方式": "SEC Form S-1 / 10-Q 财报附注 Commitments and Contingencies（承诺与或有事项）及 MD&A 流动性章节。"
            },
            {
                "核心指标名称": "5. 毛利率 (Gross Margin) 与新旧模型收入占比",
                "验证期核心基准与数值实证": "闭源头部模型毛利率已达 85% 以上（开源模型部署毛利率 20%~70%）；头部模型公司约 80% 收入来自最新一代模型。",
                "验证逻辑与多空分水岭": "虽然单代推理毛利高达 85%+，但 80% 收入依赖最新模型迫使厂商无法停下高昂的边际训练投入（「停训即失速」）。",
                "官方获取渠道与直达方式": "SEC Form S-1 损益表与业务章节、云厂商 (AWS/GCP) 重谈芯片租赁合同后的季度毛利披露、买方企业账单抽样。"
            },
            {
                "核心指标名称": "6. 模型自我迭代加速度 (AI R&D Acceleration / RSI)",
                "验证期核心基准与数值实证": "追踪 AI 辅助研发对模型迭代周期的压缩幅度及任务时间跨度 (Time Horizons) 指数级跃迁。",
                "验证逻辑与多空分水岭": "评估 AI 自我迭代能否显著拉大闭源代际差距并降低单位边际训练成本，是支撑高估值叙事的技术底座。",
                "官方获取渠道与直达方式": "METR 官方报告 (https://metr.org)：《Independent Assessment of AI R&D Acceleration at Anthropic》与 AECI 基准。"
            },
            {
                "核心指标名称": "7. 市销率 (P/S) 与一级市场估值倍数",
                "验证期核心基准与数值实证": "成熟 AI 软件（如 Palantir 约 20x P/S） vs. 新兴实验室（Neolabs 高达 200x ~ 2000x P/S）。",
                "验证逻辑与多空分水岭": "识别高估值、无收入实验室（Pre-revenue Neolabs）的一级市场融资泡沫；一旦二级市场杀估值，Neolabs 断融将直接冲击上游 Neocloud。",
                "官方获取渠道与直达方式": "PitchBook、CB Insights、Crunchbase 一级市场估值库；二级市场终端 (Bloomberg / FactSet / Koyfin)。"
            }
        ])
        st.dataframe(df_l1, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Layer 2: 企业 Token 消费与需求侧微观结构指标
    # --------------------------------------------------------------------------
    with layer_tabs[1]:
        st.markdown("#### 🔀 二、 企业 Token 消费与需求侧微观结构指标")
        st.info(
            "💡 **核心验证逻辑**：企业端正通过 **Router（模型路由）** 把简单任务分流给开源/小模型（预算占比从 `5%~10%` 升至 `20%~25%`）；"
            "但闭源大厂通过 **封禁 Signature API + 引入 Loop Transformer** 迫使开源模型蒸馏猜测推理步数时消耗更多 Token，重新拉大实际推理成本差距。"
        )
        df_l2 = pd.DataFrame([
            {
                "核心指标名称": "1. 企业 Router（模型路由）Token 预算分配比例",
                "验证期核心基准与数值实证": "企业分配给开源及小模型的 Token 预算占比正从 5%~10% 快速攀升至 20%~25%。",
                "验证逻辑与多空分水岭": "企业通过网关 Router 将复杂推理交给闭源旗舰模型、简单高频任务分流给开源/小模型以严控账单；监测闭源模型定价权是否被侵蚀。",
                "官方获取渠道与直达方式": "OpenRouter 全球调用排行 (https://openrouter.ai/rankings)；丰搭 AI 等机构针对全球 ~100 家跨国企业 CIO/CTO 季度调研。"
            },
            {
                "核心指标名称": "2. 单次任务推理 Token 消耗量（Loop Transformer 效率）",
                "验证期核心基准与数值实证": "闭源厂商封禁 Signature API 迁移并引入 Loop Transformer 后，开源模型猜测推理步骤需消耗数倍 Token。",
                "验证逻辑与多空分水岭": "对比「单位 Token 单价」毫无意义，必须看「完成单次复杂任务的端到端总 Token 成本」；开源模型 Token 膨胀使其实际推理成本反超预期。",
                "官方获取渠道与直达方式": "Artificial Analysis 端到端评测 (https://artificialanalysis.ai)；LMSYS Chatbot Arena 与 Stanford HELM。"
            },
            {
                "核心指标名称": "3. 三层传统客群（AI Startups / Tech / 传统企业）预算上限",
                "验证期核心基准与数值实证": "科技巨头（如 Apple）开始限制员工内部 Token 预算导致用量降速；AI 初创取决于 VC 融资；传统企业处于上半年采购后的部署消化期。",
                "验证逻辑与多空分水岭": "解释为何 Q3/Q4 模型 API 环比增速出现阶段性换挡：大厂控费 + 传统企业消化库存，短期增量需看明年新一轮 IT 预算释放。",
                "官方获取渠道与直达方式": "硅谷 VC 季度报告 (Carta / PitchBook)、Morgan Stanley CIO Survey、Gartner IT Spending Forecast。"
            },
            {
                "核心指标名称": "4. 非传统客群（量化金融、生物医药、机器人）算力与数据采购",
                "验证期核心基准与数值实证": "头部量化基金直接锁定机房与存储产能；具身智能（Robotics）近一季度训练数据采购预算迎来陡峭拐点。",
                "验证逻辑与多空分水岭": "这类硬核买家的算力消耗**短期完全不体现在 OpenAI/Anthropic 的 ARR 中**，但在底层真实拉动服务器、存储与合成数据需求。",
                "官方获取渠道与直达方式": "数据标注与合成数据商（Scale AI、具身智能采集商）订单动态、丰搭 AI 专项行业采购报告。"
            }
        ])
        st.dataframe(df_l2, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Layer 3: 四大科技巨头（CSP）云业务与资本支出（CapEx）指标
    # --------------------------------------------------------------------------
    with layer_tabs[2]:
        st.markdown("#### ☁️ 三、 四大科技巨头（CSP：MSFT / GOOGL / AMZN / META）云业务与资本开支账本")
        st.warning(
            "⚠️ **财报排雷核心**：重点警惕 **① 谷歌 GCP 高增速中「直接卖 TPU 一次性确认 5 年收入」的会计乘数**、"
            "**② 微软 $6770 亿 RPO 中「长单注水 vs 1 年内 cRPO 仅增 29%」的交付背离**，以及 **③ 三大巨头自由现金流 (FCF) 转负后大举发债/表外租赁引发的资产负债表恶化**！"
        )

        csp_cols = st.columns(4)
        with csp_cols[0]:
            with st.container(border=True):
                st.markdown("##### 🟦 Microsoft (MSFT)")
                st.markdown(
                    "- **Azure 增速**：Q3 **+48%**（下季指引 **49%~50%**），其中约 **40% 增速由 OpenAI 贡献**。\n"
                    "- **RPO vs cRPO 背离**：在手合同高达 **6770 亿美元 (+73% YoY)**，但 **1 年内确认的 cRPO 仅增 +29%**（受长期 OpenAI 合同拉高但短期受交付限制）。\n"
                    "- **现金流状态**：四巨头中**唯一保持正 FCF (+186 亿美元)**，但已同步开启债务与租赁融资。"
                )
        with csp_cols[1]:
            with st.container(border=True):
                st.markdown("##### 🟥 Google (GOOGL)")
                st.markdown(
                    "- **GCP 增速拆解**：Q3 暴增 **+103%**，但高度依赖**向客户直接出售 TPU（一次性确认 5 年收入，每多卖 10 万张卡拉动 GCP 增速约 10~12 pct）**。\n"
                    "- **TPU 良率下修**：明年 TPU 产量因供应商良率问题从 **1000 万张下调至 850 万张**，被迫高价外租算力。\n"
                    "- **现金流状态**：FCF **-91 亿美元**，已停止股票回购并发债约 **410 亿美元**。"
                )
        with csp_cols[2]:
            with st.container(border=True):
                st.markdown("##### 🟧 Amazon (AMZN)")
                st.markdown(
                    "- **AWS 增速与指引**：Q3 增长 **+39%**，管理层给出**未来两年维持 40% 增速**的强力指引。\n"
                    "- **自研芯片空窗**：Q3 处于 **Trainium 2 向 Trainium 3 过渡的换代空窗期**，计划 2027 年底开始对外销售自研芯片。\n"
                    "- **现金流状态**：近 12 个月累计 FCF 为负，债务规模翻倍，本季度暂停新增融资。"
                )
        with csp_cols[3]:
            with st.container(border=True):
                st.markdown("##### 🟪 Meta (META)")
                st.markdown(
                    "- **CapEx 强度极限**：单季 CapEx 高达 **349 亿美元（占营收 54%）**，**首次超过经营现金流 (OCF)**！\n"
                    "- **表外融资与稀释**：通过外部融资支撑算力扩张，引发市场对**每年 4%~5% 股权稀释**的深度担忧。\n"
                    "- **广告基本盘支撑**：软广 CPM 大涨带动北美广告增速跳升 **+10 pct**，成为唯一的内部输血机。"
                )

        df_l3 = pd.DataFrame([
            {
                "核心指标名称": "1. AI 收入与 CapEx 绝对值缺口及短期 ROI",
                "验证期核心基准与数值实证": "自今年 Q1 以来，受供应链全线涨价与前沿模型训练成本占比提升影响，AI 收入与 CapEx 的绝对值差距持续拉大。",
                "验证逻辑与多空分水岭": "短期 ROI 越来越难算清；一旦云厂无法用云增速或广告增量向华尔街证明算力投资回报，将触发 CapEx 指引下修。",
                "官方获取渠道与直达方式": "四大云厂季度 10-Q 现金流量表 Additions to Property and Equipment 对比 Earnings Call 披露的 AI 年化收入 (Run-rate)。"
            },
            {
                "核心指标名称": "2. 云业务同比增速及核心驱动拆解 (Azure/AWS/GCP)",
                "验证期核心基准与数值实证": "Azure +48% (下季 49%-50%, OpenAI 贡献 ~40%)；AWS +39% (未来两年维系 40%)；GCP +103% (每卖10万张TPU拉动10-12 pct)。",
                "验证逻辑与多空分水岭": "必须剔除「关联方左口袋倒右口袋」与「一次性硬件销售确认 5 年收入」的会计噪音，还原真实可持续的企业云消费增速。",
                "官方获取渠道与直达方式": "季度 Earnings Release、10-Q 分部报告 (Segment Reporting) 及财报电话会问答实录 (Transcript)。"
            },
            {
                "核心指标名称": "3. 云厂商在手合同余额 (Backlog/RPO) 及 1 年内确认比例 (cRPO)",
                "验证期核心基准与数值实证": "微软在手合同达 6770 亿美元 (+73% YoY)，但 1 年内可确认的 cRPO 仅增长 +29%。",
                "验证逻辑与多空分水岭": "OpenAI 等超长期合同大幅虚增了总 RPO，而短期能转化为真金白银营收的 cRPO 受制于机房/电力交付瓶颈，增速差揭示真实落地速度。",
                "官方获取渠道与直达方式": "季度 10-Q 附注 Unearned Revenue 及 Remaining Performance Obligations (RPO) 期限结构表 (Maturity Schedule)。"
            },
            {
                "核心指标名称": "4. 自由现金流 (FCF)、CapEx/营收比与债务/股权稀释率",
                "验证期核心基准与数值实证": "MSFT 唯一正 FCF (+$18.6B)；GOOGL FCF -$9.1B、停回购、发债 ~$41B；AMZN TTM FCF 为负、债务翻倍；META CapEx $34.9B (占营收54% > OCF)，面临 4%-5% 年稀释。",
                "验证逻辑与多空分水岭": "标志着硅谷巨头从「账上净现金印钞机」正式切换为「重资产举债基建商」，资产负债表健康度与信用利差开始直接约束 CapEx 上限。",
                "官方获取渠道与直达方式": "10-Q 现金流量表、资产负债表 Long-term Debt、附注 Uncommenced Leases（未开始执行租赁承诺）及 Form 8-K / 424B 债券募集书。"
            },
            {
                "核心指标名称": "5. 自研 ASIC 芯片 (TPU / Trainium) 排产、良率与换代空窗期",
                "验证期核心基准与数值实证": "谷歌明年 TPU 因供应商良率从 1000 万张下调至 850 万张，被迫高价外租算力；AWS Q3 处 Trainium 2➔3 空窗，拟 2027 年底外售。",
                "验证逻辑与多空分水岭": "自研 ASIC 是云厂降低对英伟达依赖、改善毛利率的核心武器；一旦 ASIC 良率卡壳被迫外租 GPU，将双重挤压云厂毛利与 FCF。",
                "官方获取渠道与直达方式": "博通 (AVGO)、Marvell (MRVL) 财报电话会；TrendForce 与 SemiAnalysis 的台积电 CoWoS 封装排产追踪。"
            },
            {
                "核心指标名称": "6. 云厂商模型分发渠道占比 (AWS Bedrock / GCP Vertex AI)",
                "验证期核心基准与数值实证": "企业出于数据安全与合规考虑倾向通过云大厂采购模型 API；Anthropic Q3 新增 ARR 绝大部分来自 AWS Bedrock 分发。",
                "验证逻辑与多空分水岭": "云巨头掌握着企业级分发渠道霸权，模型实验室沦为「底层算力打工方 + 渠道分成方」。",
                "官方获取渠道与直达方式": "Anthropic S-1 招股书渠道集中度披露；YipitData、M Science、Datadog 云消费追踪报告。"
            }
        ])
        st.dataframe(df_l3, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Layer 4: AI 应用层（Copilot / Personal Agent / 广告 / 企业软件）
    # --------------------------------------------------------------------------
    with layer_tabs[3]:
        st.markdown("#### 📱 四、 AI 应用层（Copilot / Personal Agent / 广告重构 / 企业软件）核心验证指标")
        st.info(
            "💡 **应用层残酷真相（单用户盈亏账本）**：当前个人智能体（Personal Agent）必须跨过 **14 日留存率 >= 20%~25%** 的奇点才值得买量推广；"
            "且目前 **单 DAU 月均推理成本高达 $30~$60**，而 **月均变现仅 $15~$20（约 $5 订阅 + $10~$15 广告增量）**，在推理成本大幅下降前，盲目扩用户等于扩大亏损！"
        )
        df_l4 = pd.DataFrame([
            {
                "核心指标名称": "1. 办公套件 (Copilot) 付费席位渗透率与交付周期",
                "验证期核心基准与数值实证": "微软披露超 3000 万席位后停止公布具体数字；微软自带权限打通，企业交付周期比模型商快 3~4 周。",
                "验证逻辑与多空分水岭": "核心紧盯跨国大企业采购比例能否跨过 **50% 的「Must-have（必选品）」奇点门槛**；一旦突破 50%，企业软件商业化将全面跑通。",
                "官方获取渠道与直达方式": "微软季度财报电话会、核心软件代理商 (LSP/CSP，如 CDW、Softchoice) 季度渠道调研报告。"
            },
            {
                "核心指标名称": "2. 个人智能体 (Personal Agent) 14日留存率与单用户盈亏 (Unit Economics)",
                "验证期核心基准与数值实证": "留存门槛：14日留存 >= 20%-25%（OpenAI 花近2年从 10% 提至 25%；Meta AI 助手留存仅 15%-16%，DAU ~400万）。单用户账本：单 DAU 月推理成本 $30-$60 vs 月变现 $15-$20（~$5订阅 + $10-$15广告），净亏 $10-$45/月。",
                "验证逻辑与多空分水岭": "解释为何大厂不敢在留存未达 25% 且推理未降本前激进投放推广 Personal Agent——单元经济模型（Unit Economics）仍处于深度水下。",
                "官方获取渠道与直达方式": "Sensor Tower、data.ai (App Annie)、Similarweb 移动与网页端活跃度及留存追踪数据。"
            },
            {
                "核心指标名称": "3. 搜索与社交广告核心指标 (广告 ARR、Ad Load、CPM、ROAS)",
                "验证期核心基准与数值实证": "搜索分流：OpenAI 广告 ARR 在 Q3 从 1 亿美元跃升至 10 亿美元，分流谷歌预算；谷歌向 AI Mode 迁移短期无法提升加载率 (Ad Load)。社交抢份额：Meta 软广 CPM 大涨，北美广告增速跳升 +10 pct（抢占旅游/金融/汽车）。",
                "验证逻辑与多空分水岭": "广告是 AI 应用层最快见效的现金牛：Meta 靠 AI 推荐直接拉高 CPM 与转化率，而谷歌必须在 Ad Load 受限下证明 AI Mode 的 ROAS 溢价。",
                "官方获取渠道与直达方式": "Google 与 Meta 10-Q 财报、四大广告代理集团 (WPP GroupM / Publicis / Omnicom) 及数字营销机构 (Tinuiti) 季度报告。"
            },
            {
                "核心指标名称": "4. 短剧类超级应用 (Short-drama Apps) 用户时长与留存率",
                "验证期核心基准与数值实证": "追踪美区短剧应用（如 ReelShort、DramaBox）是否复刻国内「红果短剧」的高留存闭环生态。",
                "验证逻辑与多空分水岭": "若美区短剧从单纯的「买量投流大户」演化为高留存超级 App，将从 Meta/Google 的广告金主变成争夺全网注意力的「广告预算黑洞」。",
                "官方获取渠道与直达方式": "Sensor Tower、QuestMobile、第三方移动归因平台 (AppsFlyer、Adjust) 行业基准报告。"
            },
            {
                "核心指标名称": "5. 企业软件 FDE（前线部署工程师）产能与网络安全漏洞倍增数",
                "验证期核心基准与数值实证": "传统企业 AI 转型极度依赖 FDE 驻场定制（如 Palantir 模式）；同时 AI 自动化攻击使网络安全漏洞与攻击量扩大 10 倍！",
                "验证逻辑与多空分水岭": "FDE 招聘规模直接限制企业 AI 软件交付上限；而 10 倍攻击量使网络安全（CrowdStrike、Cloudflare、Palo Alto）成为软件层确定性最高的刚需。",
                "官方获取渠道与直达方式": "LinkedIn 头部软件商 FDE 岗位招聘数量追踪；美国国家漏洞数据库 (NIST NVD) 月度 CVE 漏洞披露统计。"
            }
        ])
        st.dataframe(df_l4, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Layer 5: 硬件供应链、半导体与宏观/基建融资链指标
    # --------------------------------------------------------------------------
    with layer_tabs[4]:
        st.markdown("#### ⚙️ 五、 硬件供应链、半导体与宏观/基建融资链（含 2028 电力并网与 BTM 离网发电）")
        st.success(
            "🎯 **硬件噪音过滤器**：二级市场频繁流传的「砍单传闻」往往源于**光模块或 CPU 前期超额拉货后的节奏微调**；"
            "只要**台湾服务器整机代工厂（鸿海、广达、纬创、纬颖）每月 10 日前披露的月度营收零砍单**、台积电维持 ~60% 毛利率、HBM 维持 ~80% 毛利率，硬件主周期就依然稳固！"
        )
        df_l5 = pd.DataFrame([
            {
                "核心指标名称": "1. ODM/OEM 服务器出货量 vs. 零组件（CPU/光模块）拉货节奏",
                "验证期核心基准与数值实证": "台湾服务器代工厂（鸿海、广达、纬创、纬颖）及超微 (SMCI) 整机订单零砍单；市场传言仅源于光模块/CPU 前期超额备货后的微调。",
                "验证逻辑与多空分水岭": "整机 ODM 出货量是过滤供应链假消息的终极验钞机：芯片与光模块最终必须组装成机柜交付，盯紧台厂月度营收即可免疫噪音。",
                "官方获取渠道与直达方式": "台湾证券交易所「公开资讯观测站」(https://mops.twse.com.tw) 每月 10 日前强制披露的代工厂月度合并营收；Coherent / Lumentum / 中际旭创财报。"
            },
            {
                "核心指标名称": "2. 晶圆代工指引、光刻机排期与存储芯片毛利率",
                "验证期核心基准与数值实证": "台积电今年已三次上调全年指引，毛利率维持 ~60%；ASML 光刻机订单排至 2029~2030 年；存储/HBM 毛利率高达 80%。",
                "验证逻辑与多空分水岭": "60% 的代工毛利与 80% 的存储毛利证明上游物理产能依然处于极度卖方市场，远期扩产能见度直达 2029 年。",
                "官方获取渠道与直达方式": "台积电 (TSM) 月度营收与法说会、ASML 季度在手订单 (Backlog)、SK 海力士 / 美光 (MU) / 三星季报及 DRAMeXchange 报价。"
            },
            {
                "核心指标名称": "3. 算力租赁商（Neocloud，如 CoreWeave）净债务/EBITDA、GPU 租金与宏观利率",
                "验证期核心基准与数值实证": "CoreWeave 等约 20% 增量算力租给无收入 Neolabs；债权人核心考核 Net Debt / EBITDA 杠杆倍数。",
                "验证逻辑与多空分水岭": "整条 AI 资金链最脆弱的一环！若美联储维持高息（10Y 美债破 5.0%）或 GPU 现货租金下跌导致 EBITDA 缩水，将触发「缩减购卡 ➔ 冲击上游」的负向反身性。",
                "官方获取渠道与直达方式": "CoreWeave 等招股书/季报与高收益债评级报告 (Moody's / S&P)；算力比价平台 (https://www.shadeform.ai / vast.ai / Lambda) H100/B200 时租；FRED 10Y 美债与 HY OAS。"
            },
            {
                "核心指标名称": "4. 2028 年数据中心电网并网容量 (GW) 与 100% 离网发电 (Behind-the-Meter) 占比",
                "验证期核心基准与数值实证": "2027 年电力指标已锁定；州长换届影响 2028 年全美约 60GW 申请（德州 ERCOT 占 18GW，市场担忧砍掉 15GW 导致 2028 年 CapEx 走平）。外加 2028 年约 1GW 太空算力补充。",
                "验证逻辑与多空分水岭": "由于美国电力审批采取县级自下而上博弈，承诺**不推高居民电价的「100% 离网自建电源 (Behind-the-Meter，燃气轮机/燃料电池)」项目获批最快**！",
                "官方获取渠道与直达方式": "德州电网月度大负荷并网报告 (https://www.ercot.com Large Load Interconnection Status Update)、PJM 队列；GE Vernova (GEV)、Bloom Energy (BE)、康明斯 (CMI) 燃气轮机/燃料电池订单。"
            }
        ])
        st.dataframe(df_l5, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # Layer 6: 个人实操高频跟踪 SOP 与官方信源直达索引
    # --------------------------------------------------------------------------
    with layer_tabs[5]:
        st.markdown("#### 🗓️ 六、 个人投资者「AI 验证期」极简高频跟踪 SOP（抓大放小实战手册）")
        s_cols = st.columns(3)
        with s_cols[0]:
            with st.container(border=True):
                st.markdown("##### 📅 1. 月度必看（过滤砍单噪音）")
                st.markdown(
                    "- **每月 1 日**：韩国月度半导体出口数据（验证 HBM/DRAM 景气）。\n"
                    "- **每月 10 日前**：登录 [台湾证交所 MOPS](https://mops.twse.com.tw) 查 **台积电 (2330)、鸿海 (2317)、广达 (2382)、纬颖 (6669)** 月度营收——只要整机厂营收不降，一切光模块/组件砍单传闻皆为噪音。\n"
                    "- **每月中旬**：查 [OpenRouter Rankings](https://openrouter.ai/rankings) 与 [Artificial Analysis](https://artificialanalysis.ai) 跟踪开源分流比例与单位任务推理总成本。"
                )
        with s_cols[1]:
            with st.container(border=True):
                st.markdown("##### 📊 2. 季度必看（核查现金流与长单水分）")
                st.markdown(
                    "- **四大云厂 10-Q 三张表**：\n"
                    "  1. `CapEx` vs `AI 年化收入 (Run-rate)` 缺口是否收敛；\n"
                    "  2. `总 RPO` vs `1 年内确认 cRPO` 增速差（剔除 OpenAI 长单水分与 GCP 卖 TPU 一次性确认 5 年收入的噪音）；\n"
                    "  3. `自由现金流 (FCF)` 与表外未开始执行租赁 (`Uncommenced Leases`)。\n"
                    "- **Neocloud 季报**：紧盯 CoreWeave 等 `Net Debt / EBITDA` 与 [Shadeform](https://www.shadeform.ai) GPU 时租价格。"
                )
        with s_cols[2]:
            with st.container(border=True):
                st.markdown("##### 🚨 3. 事件与宏观必看（盯住反身性奇点）")
                st.markdown(
                    "- **Anthropic Form S-1 (CIK: `0002130357`)**：紧盯 **付费推理算力占比（基准 30%）** 与 **RPO/ARR 比重（基准 ~10%）** 是否回升。\n"
                    "- **应用层奇点**：微软 Copilot 大企业渗透率是否突破 **50%**；Personal Agent 14 日留存率是否突破 **20%~25%**。\n"
                    "- **2028 电力与宏观阀门**：[德州 ERCOT](https://www.ercot.com) 18GW 队列审批率、100% 离网发电 (GEV/BE) 订单，以及本页顶部 **10Y 美债 (<4.5%) 与 HY OAS (<4.0%)**。"
                )


# ==============================================================================
# 主入口函数：render_macro_tab()
# ==============================================================================
def render_macro_tab():
    st.subheader("🌐 宏观流动性、利率定价、金融条件与 AI 算力基建全景监测")
    st.caption(
        "整合 **FRED 美联储官方经济数据库**、**纽约联储 ACM 期限溢价模型**、**芝加哥联储 NFCI**、**SqueezeMetrics 暗池 DIX** 与 **CBOE/Yahoo Finance** 跨资产高频数据。"
        "通过顶部全局驾驶舱与六大专题子标签页，一屏掌握从央行货币管道到 AI 物理算力瓶颈的完整传导链。"
    )

    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1.2, 2.0, 2.8])
    with col_ctrl1:
        force_refresh = st.button("🔄 强制刷新宏观数据", key="btn_refresh_macro")
    with col_ctrl2:
        view_mode = st.radio(
            "📑 页面浏览模式",
            options=["🗂️ 专题分页模式 (推荐·免滚动)", "📜 全景长图平铺模式"],
            index=0,
            horizontal=True,
            key="macro_view_mode_radio"
        )
    with col_ctrl3:
        st.caption(f"⏱️ 页面渲染时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (本地缓存有效期 6 小时)")

    with st.spinner("正在拉取并合成 FRED / NY Fed / CBOE / Yahoo 跨资产宏观全景数据..."):
        df_long = fetch_all_macro_data(force_refresh=force_refresh)

    if df_long is None or df_long.empty:
        st.error("未能获取到宏观数据，请检查网络连接或稍后重试。")
        return

    # 1. 渲染顶部全局核心体温驾驶舱与流动性五维作战地图
    _render_kpi_cockpit(df_long)
    _render_liquidity_navigation_map(df_long)
    st.markdown("---")

    # 2. 根据用户选择的浏览模式渲染七大核心板块
    if "专题分页模式" in view_mode:
        sub_tabs = st.tabs([
            "💧 1. 流动性总闸门与央行水库",
            "⚡ 2. 恐慌波动率与极端博弈",
            "🎯 3. 利率微观、期限溢价与估值",
            "🏦 4. 商业银行、信贷周期与金融条件",
            "🛡️ 5. 衰退定量、实体经济与居民韧性",
            "🚀 6. AI 算力供应链与电力基建",
            "🤖 7. AI 产业链「验证期」五层高频监控"
        ])
        with sub_tabs[0]:
            _render_theme_liquidity(df_long)
        with sub_tabs[1]:
            _render_theme_volatility(df_long)
        with sub_tabs[2]:
            _render_theme_rates_valuation(df_long)
        with sub_tabs[3]:
            _render_theme_credit_banking(df_long)
        with sub_tabs[4]:
            _render_theme_recession_economy(df_long)
        with sub_tabs[5]:
            _render_theme_ai_supply_chain(df_long)
        with sub_tabs[6]:
            _render_theme_ai_verification(df_long)
    else:
        _render_theme_liquidity(df_long)
        st.markdown("---")
        _render_theme_volatility(df_long)
        st.markdown("---")
        _render_theme_rates_valuation(df_long)
        st.markdown("---")
        _render_theme_credit_banking(df_long)
        st.markdown("---")
        _render_theme_recession_economy(df_long)
        st.markdown("---")
        _render_theme_ai_supply_chain(df_long)
        st.markdown("---")
        _render_theme_ai_verification(df_long)

    st.markdown("---")

    # 3. 底部折叠区：全量指标最新数值汇总表与 CSV 导出
    with st.expander("📋 展开查看：全部宏观指标最新数值汇总表 & 原始 CSV 导出", expanded=False):
        summary_df = get_latest_kpi_summary(df_long)
        if not summary_df.empty:
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

        csv_bytes = df_long.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 下载完整宏观历史序列数据 (CSV)",
            data=csv_bytes,
            file_name=f"macro_liquidity_series_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="btn_download_macro_csv"
        )
