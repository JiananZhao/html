"""
Three.js 3D Cyber Crystal Quadrant Radar Component
Provides an ultra-high-end WebGL 3D visualization for CICC Tactical Asset Allocation.
Features:
- PBR physics lighting with crystal/glass translucent spheres
- Dynamic mouse hover effects (elastic scale bounce, glowing flare, expanding shockwave ring, focus dimming)
- Interactive cyberpunk glassmorphic HUD card following cursor
- Zero-gravity breathing floating animation at 60 FPS
- Rotating planetary energy rings on top 5-star assets
- Smooth category filtering animation
"""
import json
import streamlit as st
import pandas as pd


def get_threejs_quadrant_html(df_quadrant: pd.DataFrame, height: int = 760) -> str:
    if df_quadrant is None or df_quadrant.empty:
        return "<div>暂无四象限数据</div>"

    payload = df_quadrant.to_dict(orient="records")
    data_json = json.dumps(payload, ensure_ascii=False)

    html_code = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CICC 3D Cyber Quadrant Radar</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
        body, html {{
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #050814;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        }}
        #radar-wrapper {{
            position: relative;
            width: 100%;
            height: 100vh;
            background: radial-gradient(circle at 50% 50%, #0a1128 0%, #050814 85%);
            overflow: hidden;
            cursor: grab;
        }}
        #radar-wrapper.grabbing {{
            cursor: grabbing;
        }}
        #webgl-canvas {{
            width: 100%;
            height: 100%;
            display: block;
        }}

        /* 顶部毛玻璃导航与板块过滤器 */
        #top-bar {{
            position: absolute;
            top: 14px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 50;
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 9px 20px;
            border-radius: 30px;
            border: 1.5px solid rgba(255, 255, 255, 0.20);
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.65);
        }}
        .filter-btn {{
            background: transparent;
            border: 1px solid transparent;
            color: #94a3b8;
            padding: 8px 18px;
            font-size: 15px;
            font-weight: 700;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.25s ease;
            white-space: nowrap;
        }}
        .filter-btn:hover {{
            color: #ffffff;
            background: rgba(255, 255, 255, 0.14);
        }}
        .filter-btn.active {{
            color: #00f59b;
            background: rgba(0, 245, 155, 0.18);
            border-color: rgba(0, 245, 155, 0.6);
            box-shadow: 0 0 16px rgba(0, 245, 155, 0.4);
        }}
        .reset-btn {{
            color: #38bdf8;
            border: 1.5px solid rgba(56, 189, 248, 0.45);
            background: rgba(56, 189, 248, 0.12);
            margin-left: 6px;
        }}
        .reset-btn:hover {{
            color: #ffffff;
            background: rgba(56, 189, 248, 0.30);
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.5);
        }}

        /* 状态栏与操作指引 (底部 Tier 2 右侧) */
        #status-pill {{
            position: absolute;
            bottom: 10px;
            right: 20px;
            z-index: 45;
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(14px);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 18px;
            padding: 5px 14px;
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 7px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
        }}
        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00f59b;
            box-shadow: 0 0 10px #00f59b;
            animation: pulse-dot 1.8s infinite;
        }}
        @keyframes pulse-dot {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(0.85); }}
        }}

        /* 类别图例栏 (底部 Tier 2 左侧) */
        #legend-pill {{
            position: absolute;
            bottom: 10px;
            left: 20px;
            z-index: 45;
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(14px);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 18px;
            padding: 5px 14px;
            color: #cbd5e1;
            font-size: 12px;
            font-weight: 700;
            display: flex;
            gap: 12px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
        }}
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .legend-color {{ width: 10px; height: 10px; border-radius: 50%; }}

        /* 鼠标悬停全息 HUD 悬浮卡片 */
        #hud-card {{
            position: absolute;
            display: none;
            pointer-events: none;
            z-index: 100;
            width: 350px;
            background: rgba(15, 23, 42, 0.96);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 2px solid rgba(0, 245, 155, 0.65);
            border-radius: 16px;
            padding: 18px 20px;
            color: #f8fafc;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.85), 0 0 35px rgba(0, 245, 155, 0.3);
            transform: none;
            transition: opacity 0.15s ease;
        }}
        .hud-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 1px solid rgba(255, 255, 255, 0.14);
            padding-bottom: 10px;
            margin-bottom: 12px;
        }}
        .hud-title {{ font-size: 20px; font-weight: 800; color: #ffffff; }}
        .hud-ticker {{ font-size: 16px; color: #38bdf8; font-family: monospace; font-weight: 700; }}
        .hud-badge {{
            font-size: 13.5px;
            padding: 3px 10px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.14);
            font-weight: 700;
        }}
        .hud-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 12px;
        }}
        .hud-stat {{
            background: rgba(255, 255, 255, 0.06);
            padding: 8px 11px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.10);
        }}
        .hud-stat-label {{ font-size: 12.5px; font-weight: 600; color: #94a3b8; margin-bottom: 3px; }}
        .hud-stat-val {{ font-size: 17px; font-weight: 800; color: #f1f5f9; }}
        .hud-action {{
            background: rgba(0, 245, 155, 0.14);
            border-left: 4px solid #00f59b;
            padding: 8px 12px;
            font-size: 14px;
            font-weight: 700;
            color: #86efac;
            line-height: 1.45;
            border-radius: 0 8px 8px 0;
            margin-bottom: 8px;
        }}
        .hud-desc {{ font-size: 12.5px; font-weight: 500; color: #94a3b8; line-height: 1.45; }}

        /* 象限固定水印指示文字 (轻量精致毛玻璃徽章，字号 13px 粗体) */
        .quadrant-tag {{
            position: absolute;
            pointer-events: none;
            z-index: 20;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.5px;
            padding: 6px 14px;
            border-radius: 10px;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
        }}
        #tag-q1 {{ top: 68px; right: 20px; color: #4ade80; background: rgba(34, 197, 94, 0.18); border: 1.5px solid rgba(74, 222, 128, 0.45); }}
        #tag-q2 {{ bottom: 72px; right: 20px; color: #c084fc; background: rgba(168, 85, 247, 0.18); border: 1.5px solid rgba(192, 132, 252, 0.45); }}
        #tag-q3 {{ bottom: 72px; left: 24px; color: #f87171; background: rgba(239, 68, 68, 0.18); border: 1.5px solid rgba(248, 113, 113, 0.45); }}
        #tag-q4 {{ top: 68px; left: 24px; color: #fbbf24; background: rgba(245, 158, 11, 0.18); border: 1.5px solid rgba(251, 191, 36, 0.45); }}

        /* 坐标轴说明文字 (独立悬浮胶囊，严谨避让全部角落与工具栏) */
        #axis-x-label {{
            position: absolute;
            bottom: 58px;
            left: 50%;
            transform: translateX(-50%);
            color: #ffffff;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(16px);
            padding: 5px 18px;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.22);
            font-size: 12.5px;
            font-weight: 800;
            pointer-events: none;
            letter-spacing: 0.6px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
            white-space: nowrap;
            z-index: 40;
        }}
        #axis-y-label {{
            position: absolute;
            top: 50%;
            left: 28px;
            transform: translate(-50%, -50%) rotate(-90deg);
            transform-origin: center center;
            color: #ffffff;
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(16px);
            padding: 5px 16px;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.22);
            font-size: 12px;
            font-weight: 800;
            pointer-events: none;
            letter-spacing: 0.6px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
            white-space: nowrap;
            z-index: 40;
        }}
    </style>
    <!-- Three.js CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="radar-wrapper">
        <!-- 顶部板块分类快捷过滤胶囊 + 视角复位按钮 -->
        <div id="top-bar">
            <button class="filter-btn active" data-cat="all">🏛️ 全部核心标的</button>
            <button class="filter-btn" data-cat="tech">💻 科技与半导体</button>
            <button class="filter-btn" data-cat="cyclical">🏭 顺周期高端制造</button>
            <button class="filter-btn" data-cat="defensive">🛡️ 防御内需与电力</button>
            <button class="filter-btn" data-cat="macro">🌐 跨资产与宏观</button>
            <button class="filter-btn reset-btn" id="reset-cam-btn" title="双击任意空白区域亦可复位">🔄 视角复位</button>
        </div>

        <!-- 四象限战略水印指示牌 (对齐中金原版研报) -->
        <div id="tag-q1" class="quadrant-tag">Q1 戴维斯双击 (高胜率 + 高赔率 ｜ 核心超配)</div>
        <div id="tag-q2" class="quadrant-tag">Q2 动量顺势 (高胜率 + 低赔率 ｜ 紧设止损)</div>
        <div id="tag-q3" class="quadrant-tag">Q3 戴维斯双杀 (低胜率 + 低赔率 ｜ 坚决回避)</div>
        <div id="tag-q4" class="quadrant-tag">Q4 价值洼地反转 (低胜率 + 高赔率 ｜ 左侧潜伏)</div>

        <!-- 独立分层坐标轴指示栏 (严谨避让全部角落与工具栏) -->
        <div id="axis-x-label">◄ 胜率偏低 (逆风) ──【横轴: 战术胜率 (Win Rate) 空间】(中金中枢 0.55) ── 胜率偏高 (顺风) ►</div>
        <div id="axis-y-label">◄ 低赔率 (估值高) ──【纵轴: 战术赔率 (Odds) 空间】(中金中枢 0.50) ── 高赔率 (低估) ►</div>

        <!-- 底部图例与状态指示 (Tier 2 左右独立) -->
        <div id="legend-pill">
            <div class="legend-item"><div class="legend-color" style="background:#00e5ff"></div><span>科技硬件半导体</span></div>
            <div class="legend-item"><div class="legend-color" style="background:#ff7a00"></div><span>顺周期制造</span></div>
            <div class="legend-item"><div class="legend-color" style="background:#b388ff"></div><span>防御内需电力</span></div>
            <div class="legend-item"><div class="legend-color" style="background:#00e676"></div><span>全球大类/跨资产</span></div>
        </div>

        <div id="status-pill">
            <div class="status-dot"></div>
            <span>🖱️ 滚轮以鼠标为中心缩放 ｜ 拖拽平移 ｜ 悬停聚焦 ｜ 双击复位</span>
        </div>

        <!-- 鼠标悬浮全息 HUD 数据卡 -->
        <div id="hud-card">
            <div class="hud-header">
                <div>
                    <div id="hud-title" class="hud-title">标的名称</div>
                    <div id="hud-ticker" class="hud-ticker">TICKER · $0.00</div>
                </div>
                <div id="hud-badge" class="hud-badge">⭐⭐⭐⭐⭐</div>
            </div>
            <div class="hud-grid">
                <div class="hud-stat">
                    <div class="hud-stat-label">综合投资评分</div>
                    <div id="hud-composite" class="hud-stat-val" style="color:#38bdf8">0.0 分</div>
                </div>
                <div class="hud-stat">
                    <div class="hud-stat-label">中金赔率 (估值空间)</div>
                    <div id="hud-odds" class="hud-stat-val">0.00 (合理)</div>
                </div>
                <div class="hud-stat">
                    <div class="hud-stat-label">中金胜率 (景气动量)</div>
                    <div id="hud-win" class="hud-stat-val">0.00 (0%)</div>
                </div>
                <div class="hud-stat">
                    <div class="hud-stat-label">相对大盘 5Y 分位</div>
                    <div id="hud-rel-pct" class="hud-stat-val" style="color:#a7f3d0">0.0%</div>
                </div>
            </div>
            <div id="hud-action" class="hud-action">中金战术配置策略建议</div>
            <div id="hud-desc" class="hud-desc">核心龙头说明</div>
        </div>

        <canvas id="webgl-canvas"></canvas>
    </div>

    <script>
        const assetData = {data_json};

        // 基础调色板与分类映射
        const catMap = {{
            "💻 科技硬件与互联网": {{ key: "tech", hex: 0x00e5ff, colorStr: "#00e5ff" }},
            "💻 科技与半导体": {{ key: "tech", hex: 0x00e5ff, colorStr: "#00e5ff" }},
            "🏭 顺周期与高端制造": {{ key: "cyclical", hex: 0xff7a00, colorStr: "#ff7a00" }},
            "🛡️ 防御、电力与内需": {{ key: "defensive", hex: 0xb388ff, colorStr: "#b388ff" }},
            "🛡️ 防御内需与电力": {{ key: "defensive", hex: 0xb388ff, colorStr: "#b388ff" }},
            "🌐 宏观大类资产": {{ key: "macro", hex: 0x00e676, colorStr: "#00e676" }},
            "🌐 宏观与大类资产": {{ key: "macro", hex: 0x00e676, colorStr: "#00e676" }},
            "🌐 跨资产与宏观": {{ key: "macro", hex: 0x00e676, colorStr: "#00e676" }},
            "🌐 跨资产与主流指数": {{ key: "macro", hex: 0x00e676, colorStr: "#00e676" }}
        }};

        function resolveCatInfo(category) {{
            if (!category) return catMap["🌐 宏观大类资产"];
            if (catMap[category]) return catMap[category];
            const c = String(category);
            if (c.includes("科技") || c.includes("半导体") || c.includes("互联网") || c.includes("软件")) return catMap["💻 科技与半导体"];
            if (c.includes("周期") || c.includes("制造") || c.includes("金融") || c.includes("材料") || c.includes("能源")) return catMap["🏭 顺周期与高端制造"];
            if (c.includes("防御") || c.includes("电力") || c.includes("消费") || c.includes("医疗") || c.includes("内需") || c.includes("房")) return catMap["🛡️ 防御、电力与内需"];
            return catMap["🌐 宏观大类资产"];
        }}

        const container = document.getElementById('radar-wrapper');
        const canvas = document.getElementById('webgl-canvas');
        const hud = document.getElementById('hud-card');

        // Three.js 场景、相机与渲染器 (相机默认 Z=125)
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x050814, 0.0028);

        const width = container.clientWidth;
        const height = container.clientHeight;
        const camera = new THREE.PerspectiveCamera(45, width / height, 1, 1000);
        camera.position.set(0, -1.5, 142);

        const renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: true }});
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.35;

        // -------------------------------------------------------------
        // 1. 光照体系 (PBR 晶体高光与边缘泛光)
        // -------------------------------------------------------------
        const ambientLight = new THREE.AmbientLight(0x1e293b, 1.8);
        scene.add(ambientLight);

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 2.8);
        dirLight1.position.set(60, 80, 70);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xa855f7, 1.6);
        dirLight2.position.set(-70, -60, 50);
        scene.add(dirLight2);

        const dirLight3 = new THREE.DirectionalLight(0x00f59b, 1.2);
        dirLight3.position.set(0, -80, -30);
        scene.add(dirLight3);

        // -------------------------------------------------------------
        // 2. 坐标网格与十字基准线 (严格对齐中金: 横轴=胜率 Win Rate, 纵轴=赔率 Odds)
        // -------------------------------------------------------------
        // 胜率基准中枢 0.55 位于 X=0 (范围 0.40 ~ 0.80)
        // 赔率基准中枢 0.50 位于 Y=0 (范围 0.00 ~ 1.00)
        function mapCoords(win, odds) {{
            const x = ((win - 0.55) / 0.25) * 68.0;
            const y = ((odds - 0.50) / 0.50) * 52.0;
            return {{ x, y }};
        }}

        // 中心十字基准线
        const axisMat = new THREE.LineBasicMaterial({{ color: 0x475569, transparent: true, opacity: 0.65 }});
        const gridGeomX = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(-86, 0, -2), new THREE.Vector3(86, 0, -2)
        ]);
        const gridGeomY = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, -60, -2), new THREE.Vector3(0, 60, -2)
        ]);
        scene.add(new THREE.Line(gridGeomX, axisMat));
        scene.add(new THREE.Line(gridGeomY, axisMat));

        // 中心原点发光靶环
        const originGeom = new THREE.RingGeometry(1.2, 1.8, 32);
        const originMat = new THREE.MeshBasicMaterial({{ color: 0xffffff, transparent: true, opacity: 0.5, side: THREE.DoubleSide }});
        const originRing = new THREE.Mesh(originGeom, originMat);
        originRing.position.set(0, 0, -2);
        scene.add(originRing);

        // -------------------------------------------------------------
        // 2.1 绘制中金官方严谨坐标轴刻度线与刻度标牌 (0.40~0.80 & 0.00~1.00)
        // -------------------------------------------------------------
        function createTickSprite(text, isCenter) {{
            const c = document.createElement('canvas');
            c.width = 256;
            c.height = 64;
            // Enhanced tick sprite with neon glow and larger, high‑contrast text
            const ctx = c.getContext('2d');
            ctx.clearRect(0, 0, 256, 64);
            // Larger fonts for readability
            ctx.font = isCenter ? '900 48px monospace' : '700 42px monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            // Neon glow effect
            ctx.shadowColor = '#00ffff';
            ctx.shadowBlur = 12;
            // Dark stroke for contrast
            ctx.lineWidth = 8;
            ctx.strokeStyle = 'rgba(5, 8, 20, 0.95)';
            ctx.strokeText(text, 128, 32);
            // Fill with vivid color
            ctx.fillStyle = isCenter ? '#38bdf8' : '#cbd5e1';
            ctx.fillText(text, 128, 32);
            const texture = new THREE.CanvasTexture(c);
            const mat = new THREE.SpriteMaterial({{ map: texture, transparent: true, opacity: 0.95, depthWrite: false }});
            const sprite = new THREE.Sprite(mat);
            sprite.scale.set(8.8, 2.2, 1.0);
            return sprite;
        }}

        const tickLineMat = new THREE.LineBasicMaterial({{ color: 0x64748b, transparent: true, opacity: 0.5 }});
        // X 轴刻度 (胜率 0.40 ~ 0.80)
        const xTicks = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80];
        xTicks.forEach(val => {{
            const pos = mapCoords(val, 0.50);
            const isCenter = (Math.abs(val - 0.55) < 0.001);
            const tickGeom = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(pos.x, -1.2, -2), new THREE.Vector3(pos.x, 1.2, -2)
            ]);
            scene.add(new THREE.Line(tickGeom, tickLineMat));
            const tickStr = isCenter ? "0.55(中枢)" : val.toFixed(2);
            const sprite = createTickSprite(tickStr, isCenter);
            sprite.position.set(pos.x, -3.2, -1.5);
            scene.add(sprite);
        }});

        // Y 轴刻度 (赔率 0.10 ~ 1.00)
        const yTicks = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00];
        yTicks.forEach(val => {{
            const pos = mapCoords(0.55, val);
            const isCenter = (Math.abs(val - 0.50) < 0.001);
            const tickGeom = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(-1.2, pos.y, -2), new THREE.Vector3(1.2, pos.y, -2)
            ]);
            scene.add(new THREE.Line(tickGeom, tickLineMat));
            const tickStr = isCenter ? "0.50(中枢)" : val.toFixed(2);
            const sprite = createTickSprite(tickStr, isCenter);
            sprite.position.set(-5.6, pos.y, -1.5);
            scene.add(sprite);
        }});

        // -------------------------------------------------------------
        // 3. 背景星空流光粒子 (Deep Space Nebula Dust)
        // -------------------------------------------------------------
        const starCount = 350;
        const starGeom = new THREE.BufferGeometry();
        const starPos = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount * 3; i += 3) {{
            starPos[i] = (Math.random() - 0.5) * 260;
            starPos[i + 1] = (Math.random() - 0.5) * 180;
            starPos[i + 2] = (Math.random() - 0.5) * 80 - 15;
        }}
        starGeom.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
        const starMat = new THREE.PointsMaterial({{
            color: 0x94a3b8,
            size: 1.2,
            transparent: true,
            opacity: 0.45
        }});
        const starField = new THREE.Points(starGeom, starMat);
        scene.add(starField);

        // -------------------------------------------------------------
        // 4. 创建 3D 赛博琉璃球体与超清超大代码标牌 (含微排斥防重叠解耦算法)
        // -------------------------------------------------------------
        const bubbleMeshes = [];
        const sphereGroup = new THREE.Group();
        scene.add(sphereGroup);

        // 动态文字 Sprite 生成器 (512x140 紧凑画布 + 110px 超大超粗字体 + 20px 暗黑重描边)
        function createTextSprite(text) {{
            const c = document.createElement('canvas');
            c.width = 512;
            c.height = 140;
            const ctx = c.getContext('2d');
            ctx.clearRect(0, 0, 512, 140);

            ctx.font = '900 110px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';

            // 20px 纯深色粗描边，保证在任何背景与高光下都能极致清晰突出
            ctx.lineWidth = 20;
            ctx.strokeStyle = 'rgba(2, 6, 23, 0.98)';
            ctx.strokeText(text, 256, 70);

            // 纯白高光填充
            ctx.fillStyle = '#ffffff';
            ctx.fillText(text, 256, 70);

            const texture = new THREE.CanvasTexture(c);
            const mat = new THREE.SpriteMaterial({{ map: texture, transparent: true, opacity: 0.96, depthWrite: false }});
            const sprite = new THREE.Sprite(mat);
            // 放大世界尺寸为 16.5 x 4.5，彻底解决字体太小问题
            sprite.scale.set(16.5, 4.5, 1.0);
            return sprite;
        }}

        // 预处理所有气泡的坐标与半径
        const bubbleInitList = assetData.map((item, idx) => {{
            const pos = mapCoords(item.win_score, item.odds_score);
            const catInfo = resolveCatInfo(item.category);
            const normScore = Math.max(0.0, Math.min(1.0, (item.composite_score - 20.0) / 75.0));
            const rWorld = 1.8 + normScore * 1.6;
            return {{
                item,
                idx,
                catInfo,
                rWorld,
                x: pos.x,
                y: pos.y,
                origX: pos.x,
                origY: pos.y
            }};
        }});

        // 【视觉微排斥解耦算法 (Visual Relaxation)】:
        // 彻底解决如 XLRE / XLU / XLP 极其接近时物理重合遮挡的问题。
        // 数据底层（userData.data 中的赔率与胜率）100% 保持绝对精确不变，仅在三维空间中通过微排斥将重合球体推至相切清晰视距。
        for (let iter = 0; iter < 20; iter++) {{
            for (let i = 0; i < bubbleInitList.length; i++) {{
                for (let j = i + 1; j < bubbleInitList.length; j++) {{
                    const p1 = bubbleInitList[i];
                    const p2 = bubbleInitList[j];
                    const dx = p2.x - p1.x;
                    const dy = p2.y - p1.y;
                    const dist = Math.hypot(dx, dy) || 0.001;
                    const minDist = (p1.rWorld + p2.rWorld) * 1.20;
                    if (dist < minDist) {{
                        const overlap = (minDist - dist) * 0.52;
                        const nx = dx / dist;
                        const ny = dy / dist;
                        p1.x -= nx * overlap;
                        p1.y -= ny * overlap;
                        p2.x += nx * overlap;
                        p2.y += ny * overlap;
                    }}
                }}
            }}
        }}

        bubbleInitList.forEach((b) => {{
            const item = b.item;
            const catInfo = b.catInfo;
            const rWorld = b.rWorld;

            // 纯粹晶体琉璃材质 (PBR MeshStandardMaterial)
            const sphereGeom = new THREE.SphereGeometry(rWorld, 32, 32);
            const sphereMat = new THREE.MeshStandardMaterial({{
                color: catInfo.hex,
                roughness: 0.20,
                metalness: 0.15,
                emissive: catInfo.hex,
                emissiveIntensity: 0.25,
                transparent: true,
                opacity: 0.88,
                depthWrite: true
            }});

            const mesh = new THREE.Mesh(sphereGeom, sphereMat);
            mesh.position.set(b.x, b.y, 0);

            // 挂载数据到 Mesh
            mesh.userData = {{
                data: item,
                catKey: catInfo.key,
                basePos: {{ x: b.x, y: b.y, z: 0 }},
                origPos: {{ x: b.origX, y: b.origY, z: 0 }},
                baseRadius: rWorld,
                baseEmissive: 0.25,
                currentScale: 1.0,
                catInfo: catInfo
            }};

            // 贴附醒目超大代码标牌 (位于球体正上方)
            const sprite = createTextSprite(item.ticker);
            sprite.position.set(0, rWorld + 2.5, 0);
            mesh.add(sprite);
            mesh.userData.sprite = sprite;

            sphereGroup.add(mesh);
            bubbleMeshes.push(mesh);
        }});

        // -------------------------------------------------------------
        // 5. 鼠标光标移动与射线拾取 (Raycaster & Hover Dynamics)
        // -------------------------------------------------------------
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2(-999, -999);
        let hoveredMesh = null;

        function updatePointer(e) {{
            const clientX = e.clientX !== undefined ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
            const clientY = e.clientY !== undefined ? e.clientY : (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
            const rect = canvas.getBoundingClientRect();
            mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1;

            const hudW = 350;
            const hudH = 290;
            let hudX = clientX - rect.left + 22;
            let hudY = clientY - rect.top - 20;

            if (hudX + hudW > rect.width) {{
                hudX = clientX - rect.left - hudW - 22;
            }}
            if (hudY + hudH > rect.height) {{
                hudY = clientY - rect.top - hudH - 16;
            }}
            hudX = Math.max(12, Math.min(rect.width - hudW - 12, hudX));
            hudY = Math.max(12, Math.min(rect.height - hudH - 12, hudY));

            hud.style.left = hudX + 'px';
            hud.style.top = hudY + 'px';
        }}

        window.addEventListener('mousemove', updatePointer);
        window.addEventListener('pointermove', updatePointer);

        window.addEventListener('mouseleave', () => {{
            mouse.x = -999;
            mouse.y = -999;
            hud.style.display = 'none';
        }});

        // -------------------------------------------------------------
        // 6. 鼠标滚轮以光标位置为中心缩放 + 鼠标拖拽画布平移
        // -------------------------------------------------------------
        const DEFAULT_CAM_POS = new THREE.Vector3(0, -1.5, 142);

        // 滚轮缩放：以鼠标所在世界位置为中心缩放
        container.addEventListener('wheel', (e) => {{
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const ndcX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            const ndcY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            // 将屏幕鼠标射线投影至 Z=0 象限数据平面
            const mouseVec = new THREE.Vector3(ndcX, ndcY, 0.5).unproject(camera);
            const dir = mouseVec.sub(camera.position).normalize();
            if (Math.abs(dir.z) < 1e-4) return;
            const dist = -camera.position.z / dir.z;
            const mouseWorld = camera.position.clone().add(dir.multiplyScalar(dist));

            // 计算缩放比例与相机位置迭代
            const zoomFactor = e.deltaY < 0 ? 0.85 : 1.18;
            const currentZ = camera.position.z;
            const nextZ = Math.max(28, Math.min(220, currentZ * zoomFactor));
            const ratio = nextZ / currentZ;

            camera.position.x = mouseWorld.x + (camera.position.x - mouseWorld.x) * ratio;
            camera.position.y = mouseWorld.y + (camera.position.y - mouseWorld.y) * ratio;
            camera.position.z = nextZ;
        }}, {{ passive: false }});

        // 鼠标拖拽平移 (Pan)
        let isDragging = false;
        let prevClientX = 0;
        let prevClientY = 0;

        canvas.addEventListener('mousedown', (e) => {{
            if (e.button === 0 || e.button === 1) {{
                isDragging = true;
                prevClientX = e.clientX;
                prevClientY = e.clientY;
                container.classList.add('grabbing');
            }}
        }});

        window.addEventListener('mousemove', (e) => {{
            if (isDragging) {{
                const dx = e.clientX - prevClientX;
                const dy = e.clientY - prevClientY;
                const factor = (camera.position.z / 125.0) * 0.15;
                camera.position.x -= dx * factor;
                camera.position.y += dy * factor;
                prevClientX = e.clientX;
                prevClientY = e.clientY;
            }}
        }});

        window.addEventListener('mouseup', () => {{
            isDragging = false;
            container.classList.remove('grabbing');
        }});

        // 视角复位功能
        function resetCamera() {{
            camera.position.copy(DEFAULT_CAM_POS);
        }}

        // 双击空白处直接视角复位
        canvas.addEventListener('dblclick', () => {{
            resetCamera();
        }});

        // 点击顶部视角复位按钮
        const resetCamBtn = document.getElementById('reset-cam-btn');
        if (resetCamBtn) {{
            resetCamBtn.addEventListener('click', () => {{
                resetCamera();
            }});
        }}

        // -------------------------------------------------------------
        // 7. 板块过滤交互逻辑
        // -------------------------------------------------------------
        let currentFilter = 'all';
        const filterBtns = document.querySelectorAll('.filter-btn[data-cat]');
        filterBtns.forEach(btn => {{
            btn.addEventListener('click', () => {{
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.getAttribute('data-cat');
            }});
        }});

        // -------------------------------------------------------------
        // 8. 渲染循环 (静态绝对稳定；仅光标悬停时产生聚焦微光与平滑放大)
        // -------------------------------------------------------------
        function animate() {{
            requestAnimationFrame(animate);

            // 射线碰撞检测 (递归检测子元素以支持直接命中文字标牌)
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(bubbleMeshes, true);

            let targetBubble = null;
            if (intersects.length > 0) {{
                let hitObj = intersects[0].object;
                // 递归回溯至主球体 Mesh
                while (hitObj && (!hitObj.userData || !hitObj.userData.data) && hitObj.parent) {{
                    hitObj = hitObj.parent;
                }}
                if (hitObj && hitObj.userData && hitObj.userData.data) {{
                    targetBubble = hitObj;
                }}
            }}

            if (targetBubble) {{
                if (hoveredMesh !== targetBubble) {{
                    hoveredMesh = targetBubble;
                    document.body.style.cursor = 'pointer';

                    // 填充并展示 HUD 卡片
                    const d = targetBubble.userData.data;
                    document.getElementById('hud-title').innerText = d.name;
                    document.getElementById('hud-ticker').innerText = `${{d.ticker}} · $${{d.price.toFixed(2)}}`;
                    document.getElementById('hud-badge').innerText = d.star || "⭐⭐⭐⭐";
                    document.getElementById('hud-composite').innerText = d.composite_score.toFixed(1) + " 分";
                    document.getElementById('hud-odds').innerText = `${{d.odds_score.toFixed(2)}} (${{(d.odds_score * 100).toFixed(0)}}%) · ${{d.valuation_tag.split(' ')[1] || '合理'}}`;
                    document.getElementById('hud-win').innerText = `${{d.win_score.toFixed(2)}} (${{(d.win_score * 100).toFixed(0)}}%)`;
                    document.getElementById('hud-rel-pct').innerText = d.rel_percentile_5y.toFixed(1) + "%";
                    document.getElementById('hud-action').innerText = "💡 " + d.action;
                    document.getElementById('hud-desc').innerText = d.desc;

                    hud.style.borderColor = targetBubble.userData.catInfo.colorStr;
                    hud.style.boxShadow = `0 15px 35px rgba(0,0,0,0.7), 0 0 25px ${{targetBubble.userData.catInfo.colorStr}}40`;
                    hud.style.display = 'block';
                }}
            }} else {{
                if (hoveredMesh) {{
                    hoveredMesh = null;
                    document.body.style.cursor = 'default';
                    hud.style.display = 'none';
                }}
            }}

            // 遍历所有气泡：静态时绝对静止稳定；仅在悬停时对指定气泡施加平滑缩放与聚焦光晕
            bubbleMeshes.forEach(mesh => {{
                const u = mesh.userData;
                const isHovered = (mesh === hoveredMesh);
                const isMatchFilter = (currentFilter === 'all' || u.catKey === currentFilter);

                // 1. 目标缩放：仅悬停气泡平滑放大 1.30 倍；未选中分类收缩至 0.25 倍
                let targetScale = 1.0;
                if (!isMatchFilter) {{
                    targetScale = 0.25;
                }} else if (isHovered) {{
                    targetScale = 1.30;
                }}
                u.currentScale += (targetScale - u.currentScale) * 0.16;
                mesh.scale.set(u.currentScale, u.currentScale, u.currentScale);

                // 2. 仅悬停气泡在 Z 轴前置 4.0 并将渲染次序置顶，彻底压倒所有临近遮挡
                const targetZ = isHovered ? 4.0 : 0.0;
                mesh.position.z += (targetZ - mesh.position.z) * 0.18;
                mesh.renderOrder = isHovered ? 999 : 0;

                // 3. 静态时位置绝对锁定！绝对无任何自发漂移或晃动
                mesh.position.x = u.basePos.x;
                mesh.position.y = u.basePos.y;

                // 4. 动态光晕：仅悬停气泡爆发柔和高光 (0.85)，其余保持沉静 (0.22)
                const targetEmissive = isHovered ? 0.85 : (isMatchFilter ? 0.22 : 0.04);
                mesh.material.emissiveIntensity += (targetEmissive - mesh.material.emissiveIntensity) * 0.16;

                // 5. 聚光景深：悬停时其他气泡轻微淡化 (0.35)，未悬停时全景清透 (0.88)
                let targetOpacity = 0.88;
                if (!isMatchFilter) {{
                    targetOpacity = 0.15;
                }} else if (hoveredMesh && !isHovered) {{
                    targetOpacity = 0.35;
                }} else if (isHovered) {{
                    targetOpacity = 1.0;
                }}
                mesh.material.opacity += (targetOpacity - mesh.material.opacity) * 0.16;

                // 6. 文字标牌：清晰醒目，悬停标牌进一步放大高亮
                if (u.sprite) {{
                    const spriteOpacity = isHovered ? 1.0 : (hoveredMesh ? 0.40 : (isMatchFilter ? 0.96 : 0.15));
                    u.sprite.material.opacity += (spriteOpacity - u.sprite.material.opacity) * 0.16;
                    const baseW = 16.5;
                    const baseH = 4.5;
                    const scaleMul = isHovered ? 1.30 : 1.0;
                    u.sprite.scale.set(baseW * scaleMul, baseH * scaleMul, 1.0);
                    u.sprite.renderOrder = isHovered ? 1000 : 1;
                }}
            }});

            renderer.render(scene, camera);
        }}

        animate();

        // 窗口大小响应自适应
        window.addEventListener('resize', () => {{
            const newW = container.clientWidth;
            const newH = container.clientHeight;
            camera.aspect = newW / newH;
            camera.updateProjectionMatrix();
            renderer.setSize(newW, newH);
        }});
    </script>
</body>
</html>
"""
    return html_code


def render_threejs_cicc_quadrant_ui(df_quadrant: pd.DataFrame, height: int = 760):
    """
    在 Streamlit 中直接呈现 WebGL / Three.js 3D 赛博琉璃雷达视口
    """
    html_code = get_threejs_quadrant_html(df_quadrant, height=height)
    st.components.v1.html(html_code, height=height, scrolling=False)
