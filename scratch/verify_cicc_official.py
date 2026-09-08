import pandas as pd
import numpy as np

# 19 Official Assets from CICC Research Slide
cicc_assets = [
    {"ticker": "TLT", "name": "美债-长端", "category": "🌐 跨资产与主流指数", "win_score": 0.64, "odds_score": 0.98, "price": 99.50, "star": "5星", "action": "核心进攻 / 超配长久期", "desc": "超长久期无风险利率债，处于历史估值极端洼地，降息周期最大弹性品种"},
    {"ticker": "SHY", "name": "美债-短端", "category": "🌐 跨资产与主流指数", "win_score": 0.71, "odds_score": 0.84, "price": 82.20, "star": "5星", "action": "稳健底仓 / 锁定5%+高票息", "desc": "短端无风险高票息，收益率曲线倒挂修复核心受益标的"},
    {"ticker": "MAGS", "name": "M7", "category": "💻 科技与半导体", "win_score": 0.71, "odds_score": 0.72, "price": 42.50, "star": "5星", "action": "核心进攻 / 巨头护城河", "desc": "科技七巨头 (NVDA, MSFT, AAPL, GOOGL, AMZN, META, TSLA)，强劲盈利消化估值"},
    {"ticker": "KWEB", "name": "恒生科技", "category": "🌐 跨资产与主流指数", "win_score": 0.58, "odds_score": 0.83, "price": 28.30, "star": "5星", "action": "积极进攻 / 估值历史洼地", "desc": "中国互联网核心资产，相比上期新纳入，估值分位数处于极端底部，盈利拐点确立"},
    {"ticker": "CYB50", "name": "创业板50", "category": "🌐 跨资产与主流指数", "win_score": 0.63, "odds_score": 0.65, "price": 0.85, "star": "4星", "action": "优选配置 / 弹性反弹", "desc": "成长龙头与新能源核心，经历深幅回调后赔率显著回升"},
    {"ticker": "GLD", "name": "黄金", "category": "🌐 跨资产与主流指数", "win_score": 0.66, "odds_score": 0.48, "price": 232.00, "star": "4星", "action": "战略标配 / 去美元化避险", "desc": "央行购金与主权信用风险对冲，胜率高，估值处于中位"},
    {"ticker": "QQQ", "name": "纳斯达克100", "category": "💻 科技与半导体", "win_score": 0.65, "odds_score": 0.45, "price": 480.00, "star": "4星", "action": "顺势持有 / 紧设止损", "desc": "全球科技创新旗舰，景气度高，静态估值偏高但动态增长健康"},
    {"ticker": "SOXX", "name": "费城半导体", "category": "💻 科技与半导体", "win_score": 0.78, "odds_score": 0.35, "price": 240.00, "star": "4星", "action": "动量顺势 / 严设止损防回调", "desc": "AI 算力硬件需求极度爆发，全场胜率最高(0.78)，但估值透支较重需防短期回调"},
    {"ticker": "MICRO", "name": "万得微盘", "category": "🌐 跨资产与主流指数", "win_score": 0.63, "odds_score": 0.40, "price": 1.00, "star": "3星", "action": "战术博弈 / 控制敞口", "desc": "小微盘高流动性因子，弹性较大，受流动性与资金面影响显著"},
    {"ticker": "CSI300", "name": "沪深300", "category": "🌐 跨资产与主流指数", "win_score": 0.57, "odds_score": 0.35, "price": 3400.00, "star": "3星", "action": "均衡观望 / 等待右侧", "desc": "A 股大盘蓝筹基准，处于震荡筑底阶段"},
    {"ticker": "SPY", "name": "标普500", "category": "🌐 跨资产与主流指数", "win_score": 0.61, "odds_score": 0.25, "price": 550.00, "star": "3星", "action": "标配持有 / 动态跟踪", "desc": "美股全市场基准，估值处于历史偏高分位，顺势持有但防范均线偏离"},
    {"ticker": "USO", "name": "原油", "category": "🏭 顺周期高端制造", "win_score": 0.52, "odds_score": 0.30, "price": 72.00, "star": "2星", "action": "偏空回避 / 逢高减持", "desc": "全球实体制造业总需求走弱，胜率与赔率均偏低"},
    {"ticker": "TWII", "name": "台湾加权", "category": "💻 科技与半导体", "win_score": 0.61, "odds_score": 0.21, "price": 22000.00, "star": "2星", "action": "逢高谨慎 / 防估值回调", "desc": "台积电权重极高，受益半导体景气，但估值分位数已处高位"},
    {"ticker": "STAR50", "name": "科创50", "category": "💻 科技与半导体", "win_score": 0.61, "odds_score": 0.19, "price": 750.00, "star": "2星", "action": "结构性跟踪", "desc": "芯片设计与硬科技制造，研发投入高，静态估值压力待释放"},
    {"ticker": "DIA", "name": "道琼斯", "category": "🏭 顺周期高端制造", "win_score": 0.53, "odds_score": 0.15, "price": 410.00, "star": "2星", "action": "逢高减持 / 结构调整", "desc": "传统周期与工业权重，动能偏弱，估值安全边际不足"},
    {"ticker": "HSI", "name": "恒生指数", "category": "🌐 跨资产与主流指数", "win_score": 0.57, "odds_score": 0.42, "price": 18000.00, "star": "3星", "action": "均衡配置", "desc": "港股大盘，高股息与中资互联网兼具，估值中位"},
    {"ticker": "CSI500", "name": "中证500", "category": "🌐 跨资产与主流指数", "win_score": 0.61, "odds_score": 0.08, "price": 4800.00, "star": "2星", "action": "减配观望", "desc": "中盘制造与医药成长，相对折价空间不足"},
    {"ticker": "KOSPI", "name": "韩国综指", "category": "💻 科技与半导体", "win_score": 0.68, "odds_score": 0.08, "price": 2600.00, "star": "2星", "action": "顺势短线 / 紧设止损", "desc": "存储芯片超级周期推动胜率达 0.68，但估值透支严重，赔率仅 0.08"},
    {"ticker": "DIVLOW", "name": "红利低波", "category": "🛡️ 防御内需与电力", "win_score": 0.47, "odds_score": 0.06, "price": 1.15, "star": "1星", "action": "坚决回避 / 获利了结", "desc": "前期大涨后估值创5年极值新高，股息率吸引力被抹平，胜率赔率全场双最低(0.47, 0.06)"}
]

df = pd.DataFrame(cicc_assets)
for item in cicc_assets:
    # Quadrant
    w = item["win_score"]
    o = item["odds_score"]
    if w >= 0.55 and o >= 0.50:
        item["quadrant"] = "第一象限: 戴维斯双击 (高胜率+高赔率)"
        item["q_code"] = "Q1"
    elif w >= 0.55 and o < 0.50:
        item["quadrant"] = "第二象限: 动量顺势 (高胜率+低赔率)"
        item["q_code"] = "Q2"
    elif w < 0.55 and o < 0.50:
        item["quadrant"] = "第三象限: 戴维斯双杀 (低胜率+低赔率)"
        item["q_code"] = "Q3"
    else:
        item["quadrant"] = "第四象限: 价值洼地反转 (低胜率+高赔率)"
        item["q_code"] = "Q4"
        
    # Composite score
    item["composite_score"] = round((w * 50.0 + o * 50.0), 1)

df_out = pd.DataFrame(cicc_assets)
print(df_out[['name', 'ticker', 'win_score', 'odds_score', 'q_code', 'composite_score']].to_string())
