"""
Nodal Solvency Dependency Graph Visualizer for SplitGuard AI
Generates an interactive, dark-themed SVG network graph showing
the multi-party escrow settlement flow, entities, and risk callouts.
Uses a clean, non-overlapping Left-to-Right & Top-Allocation topology
with crisp horizontal labels, enterprise fintech palette, and interactive inspector.
"""

from typing import Dict, Any, List, Optional
import json


def generate_nodal_solvency_graph_html(
    nodal_breaks: Optional[List[Dict[str, Any]]] = None,
    exceptions_summary: Optional[Dict[str, Any]] = None,
    height: str = "560px"
) -> str:
    """
    Generates a standalone, self-contained interactive SVG/HTML5 graph
    for the Nodal Escrow and Settlement Dependency Network.
    - Zero rotated/diagonal text (100% horizontal readability)
    - Zero line crossings (geometrically isolated flow channels)
    - Cohesive enterprise fintech color palette (no clown/neon colors)
    - Interactive node inspection, flow particle animations, and status filtering
    - Fully offline resilient with embedded styling (no flaky external CDN canvas dependencies)
    """
    has_nodal_break = bool(nodal_breaks and len(nodal_breaks) > 0)
    nodal_status_text = "ALERT: ₹50,000 Deficit Break" if has_nodal_break else "SOLVENT: 100% Balanced"
    nodal_sub_text = "62-Day Continuous Audit: Break Detected" if has_nodal_break else "Daily Solvency Proof: 0 Variance"
    nodal_pill_class = "pill-alert" if has_nodal_break else "pill-solvent"

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Nodal Solvency Dependency Graph</title>
<style>
    *, *::before, *::after {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}
    html, body {{
        width: 100%;
        height: 100%;
        overflow: hidden;
        background-color: #070d18;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #f1f5f9;
        user-select: none;
    }}

    .container {{
        position: relative;
        width: 100%;
        height: {height};
        background: radial-gradient(circle at 50% 40%, #0d172e 0%, #060b14 100%);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 12px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }}

    /* Top Control & Metric Bar */
    .top-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 16px;
        background: rgba(11, 19, 36, 0.88);
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
        backdrop-filter: blur(12px);
        z-index: 20;
        flex-shrink: 0;
    }}

    .filter-group {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    .filter-btn {{
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.2);
        color: #94a3b8;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.18s ease;
    }}
    .filter-btn:hover {{
        background: rgba(14, 165, 233, 0.2);
        border-color: rgba(56, 189, 248, 0.5);
        color: #38bdf8;
    }}
    .filter-btn.active {{
        background: #0284c7;
        border-color: #38bdf8;
        color: #ffffff;
        box-shadow: 0 0 10px rgba(2, 132, 199, 0.4);
    }}

    .view-controls {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    .zoom-pill {{
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(56, 189, 248, 0.3);
        color: #38bdf8;
        font-size: 11px;
        font-weight: 700;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        padding: 4px 8px;
        border-radius: 6px;
        letter-spacing: 0.5px;
    }}

    .btn-icon {{
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.2);
        color: #cbd5e1;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.18s ease;
    }}
    .btn-icon:hover {{
        background: rgba(51, 65, 85, 0.9);
        color: #ffffff;
    }}

    #viewportGroup {{
        will-change: transform;
    }}

    /* SVG Canvas Area */
    .canvas-wrapper {{
        position: relative;
        flex: 1;
        width: 100%;
        overflow: hidden;
        cursor: grab;
        touch-action: none;
    }}
    .canvas-wrapper:active {{
        cursor: grabbing;
    }}

    svg.network-svg {{
        width: 100%;
        height: 100%;
        display: block;
    }}

    /* Grid Background Pattern */
    .grid-pattern {{
        fill: none;
        stroke: rgba(148, 163, 184, 0.05);
        stroke-width: 1;
    }}

    /* Connection Paths */
    .flow-path {{
        fill: none;
        stroke-width: 2;
        transition: stroke 0.2s ease, stroke-width 0.2s ease, opacity 0.2s ease;
    }}
    .flow-path.dimmed {{
        opacity: 0.12 !important;
    }}
    .flow-path.highlighted {{
        stroke-width: 3.5 !important;
        filter: drop-shadow(0 0 6px currentColor);
    }}

    /* Animated Flow Particles */
    .flow-particle {{
        fill: none;
        stroke-width: 2.2;
        stroke-dasharray: 6 18;
        animation: flowAnimation 2.4s linear infinite;
        opacity: 0.85;
    }}
    @keyframes flowAnimation {{
        from {{ stroke-dashoffset: 48; }}
        to {{ stroke-dashoffset: 0; }}
    }}

    /* Edge Badge Chips (100% Horizontal & High Contrast) */
    .edge-badge-rect {{
        rx: 5;
        ry: 5;
        fill: #091224;
        stroke: rgba(148, 163, 184, 0.35);
        stroke-width: 1;
        filter: drop-shadow(0 2px 5px rgba(0,0,0,0.5));
    }}
    .edge-badge-text {{
        font-size: 10px;
        font-weight: 600;
        fill: #cbd5e1;
        text-anchor: middle;
        dominant-baseline: central;
        letter-spacing: 0.2px;
        pointer-events: none;
    }}

    /* Node Cards */
    .node-group {{
        cursor: pointer;
        transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
    }}
    .node-group.dimmed {{
        opacity: 0.18 !important;
    }}
    .node-group:hover {{
        filter: drop-shadow(0 6px 16px rgba(0, 0, 0, 0.5));
    }}
    .node-card {{
        rx: 9;
        ry: 9;
        stroke-width: 1.5;
        transition: all 0.2s ease;
    }}

    /* Typography inside Nodes */
    .node-category {{
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }}
    .node-title {{
        font-size: 12px;
        font-weight: 700;
        fill: #f8fafc;
    }}
    .node-sub {{
        font-size: 10.5px;
        font-weight: 500;
        fill: #94a3b8;
    }}

    /* Badge Pills inside Nodes */
    .status-pill-bg {{
        rx: 4;
        ry: 4;
    }}
    .status-pill-text {{
        font-size: 9.5px;
        font-weight: 700;
        text-anchor: middle;
        dominant-baseline: central;
    }}

    /* Bottom Info Drawer (Click-to-Inspect) */
    .info-drawer {{
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(10, 17, 33, 0.95);
        border-top: 1px solid rgba(56, 189, 248, 0.3);
        backdrop-filter: blur(16px);
        padding: 10px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11.5px;
        color: #cbd5e1;
        box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.45);
        transform: translateY(100%);
        transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        z-index: 25;
    }}
    .info-drawer.open {{
        transform: translateY(0);
    }}
    .drawer-content {{
        display: flex;
        align-items: center;
        gap: 22px;
        flex-wrap: wrap;
    }}
    .drawer-item {{
        display: flex;
        flex-direction: column;
        gap: 2px;
    }}
    .drawer-label {{
        font-size: 9.5px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}
    .drawer-val {{
        font-size: 12px;
        font-weight: 600;
        color: #f1f5f9;
    }}
    .drawer-close {{
        background: transparent;
        border: 1px solid rgba(148, 163, 184, 0.25);
        color: #94a3b8;
        font-size: 14px;
        line-height: 1;
        width: 24px;
        height: 24px;
        border-radius: 6px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .drawer-close:hover {{
        color: #f1f5f9;
        border-color: #cbd5e1;
    }}

    /* Legend Bar at Bottom */
    .legend-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 16px;
        background: #080f1e;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
        font-size: 11px;
        color: #94a3b8;
        flex-shrink: 0;
        z-index: 15;
    }}
    .legend-items {{
        display: flex;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
    }}
    .legend-item {{
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .legend-dot {{
        width: 8px;
        height: 8px;
        border-radius: 2px;
    }}
</style>
</head>
<body>

<div class="container">
    <!-- Top Filter & Controls Toolbar -->
    <div class="top-bar">
        <div class="filter-group">
            <span style="font-size:11px; color:#64748b; font-weight:700; margin-right:4px;">FILTER:</span>
            <button class="filter-btn active" onclick="setFilter('all', this)">All Nodes (11)</button>
            <button class="filter-btn" onclick="setFilter('anomalies', this)">🚨 Planted Anomalies (3)</button>
            <button class="filter-btn" onclick="setFilter('reconciled', this)">✓ Reconciled Clean (2)</button>
            <button class="filter-btn" onclick="setFilter('statutory', this)">🏛️ Statutory &amp; Platform (4)</button>
        </div>
        <div class="view-controls">
            <span class="zoom-pill" id="zoomPill" title="Current Zoom Level">100%</span>
            <button class="btn-icon" onclick="resetZoom()" title="Reset viewport (or double-click canvas)">↺ Reset</button>
            <button class="btn-icon" onclick="zoomIn()" title="Smooth Zoom In">➕</button>
            <button class="btn-icon" onclick="zoomOut()" title="Smooth Zoom Out">➖</button>
            <button class="btn-icon" onclick="toggleAnimation()" id="animBtn" title="Toggle flow particle animation">⚡ Animation: ON</button>
        </div>
    </div>

    <!-- Main SVG Diagram Viewport -->
    <div class="canvas-wrapper" id="canvasWrapper">
        <svg class="network-svg" id="networkSvg" viewBox="0 0 1180 520" preserveAspectRatio="xMidYMid meet">
            <defs>
                <!-- Subtle grid background -->
                <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
                    <circle cx="12" cy="12" r="0.8" fill="rgba(148, 163, 184, 0.14)" />
                </pattern>

                <!-- Arrow markers -->
                <marker id="arrow-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#0284c7"/>
                </marker>
                <marker id="arrow-indigo" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#6366f1"/>
                </marker>
                <marker id="arrow-slate" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#64748b"/>
                </marker>
                <marker id="arrow-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#06b6d4"/>
                </marker>
                <marker id="arrow-purple" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#a855f7"/>
                </marker>
                <marker id="arrow-amber" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f59e0b"/>
                </marker>
                <marker id="arrow-emerald" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#10b981"/>
                </marker>
                <marker id="arrow-rose" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f43f5e"/>
                </marker>
            </defs>

            <!-- Grid Backdrop -->
            <rect width="100%" height="100%" fill="url(#grid)" />

            <!-- Scalable Group for Pan & Zoom -->
            <g id="viewportGroup">

                <!-- ════════════════════════════════════════════════════════════
                     CONNECTIONS & BEZIER PIPELINES (Zero Intersections)
                ════════════════════════════════════════════════════════════ -->

                <!-- Inflow: Gateway (220, 270) -> Nodal Escrow (320, 270) -->
                <path id="path-inflow" class="flow-path" d="M 220 270 L 320 270" stroke="#0284c7" marker-end="url(#arrow-blue)" />
                <path id="anim-inflow" class="flow-particle" d="M 220 270 L 320 270" stroke="#38bdf8" />

                <!-- Nodal Escrow -> Top Allocations: -->
                <!-- To Marketplace Treasury: (400, 190) -> (360, 105) -->
                <path id="path-treasury" class="flow-path" d="M 400 190 C 400 145, 360 145, 360 105" stroke="#6366f1" marker-end="url(#arrow-indigo)" />
                <path id="anim-treasury" class="flow-particle" d="M 400 190 C 400 145, 360 145, 360 105" stroke="#a5b4fc" />

                <!-- To Logistics Pool: (450, 190) -> (570, 105) -->
                <path id="path-logistics" class="flow-path" d="M 450 190 C 450 145, 570 145, 570 105" stroke="#64748b" marker-end="url(#arrow-slate)" />
                <path id="anim-logistics" class="flow-particle" d="M 450 190 C 450 145, 570 145, 570 105" stroke="#94a3b8" />

                <!-- To TCS Escrow: (510, 190) -> (770, 105) -->
                <path id="path-tcs" class="flow-path" d="M 510 190 C 530 135, 770 155, 770 105" stroke="#06b6d4" marker-end="url(#arrow-teal)" />
                <path id="anim-tcs" class="flow-particle" d="M 510 190 C 530 135, 770 155, 770 105" stroke="#67e8f9" />

                <!-- To TDS Escrow: (550, 190) -> (970, 105) -->
                <path id="path-tds" class="flow-path" d="M 550 190 C 580 120, 970 145, 970 105" stroke="#a855f7" marker-end="url(#arrow-purple)" />
                <path id="anim-tds" class="flow-particle" d="M 550 190 C 580 120, 970 145, 970 105" stroke="#d8b4fe" />

                <!-- Nodal Escrow -> Right Vendor Beneficiaries: -->
                <!-- To VEND-001 (TechZone): (580, 230) -> (770, 168) -->
                <path id="path-vend1" class="flow-path" d="M 580 230 C 660 230, 690 168, 770 168" stroke="#f59e0b" stroke-dasharray="4 3" marker-end="url(#arrow-amber)" />
                <path id="anim-vend1" class="flow-particle" d="M 580 230 C 660 230, 690 168, 770 168" stroke="#fbbf24" />

                <!-- To VEND-002 (FashionHub): (580, 255) -> (770, 241) -->
                <path id="path-vend2" class="flow-path" d="M 580 255 C 660 255, 690 241, 770 241" stroke="#10b981" marker-end="url(#arrow-emerald)" />
                <path id="anim-vend2" class="flow-particle" d="M 580 255 C 660 255, 690 241, 770 241" stroke="#6ee7b7" />

                <!-- To VEND-003 (HomeComforts): (580, 280) -> (770, 314) -->
                <path id="path-vend3" class="flow-path" d="M 580 280 C 660 280, 690 314, 770 314" stroke="#f43f5e" stroke-width="2.5" marker-end="url(#arrow-rose)" />
                <path id="anim-vend3" class="flow-particle" d="M 580 280 C 660 280, 690 314, 770 314" stroke="#fda4af" />

                <!-- To VEND-004 (BooksAndMore): (580, 305) -> (770, 387) -->
                <path id="path-vend4" class="flow-path" d="M 580 305 C 660 305, 690 387, 770 387" stroke="#06b6d4" marker-end="url(#arrow-teal)" />
                <path id="anim-vend4" class="flow-particle" d="M 580 305 C 660 305, 690 387, 770 387" stroke="#67e8f9" />

                <!-- To VEND-005 (FitnessFirst): (580, 330) -> (770, 460) -->
                <path id="path-vend5" class="flow-path" d="M 580 330 C 660 330, 690 460, 770 460" stroke="#10b981" marker-end="url(#arrow-emerald)" />
                <path id="anim-vend5" class="flow-particle" d="M 580 330 C 660 330, 690 460, 770 460" stroke="#6ee7b7" />


                <!-- ════════════════════════════════════════════════════════════
                     HORIZONTAL EDGE BADGE LABELS (100% Readable, Zero Overlap)
                ════════════════════════════════════════════════════════════ -->

                <!-- Inflow Label -->
                <g transform="translate(270, 252)">
                    <rect class="edge-badge-rect" x="-44" y="-10" width="88" height="20" stroke="#0284c7" />
                    <text class="edge-badge-text" fill="#38bdf8">Net GMV Inflow</text>
                </g>

                <!-- Treasury Label -->
                <g transform="translate(372, 142)">
                    <rect class="edge-badge-rect" x="-45" y="-9" width="90" height="18" stroke="#6366f1" />
                    <text class="edge-badge-text" fill="#a5b4fc">Commission 10%</text>
                </g>

                <!-- Logistics Label -->
                <g transform="translate(515, 142)">
                    <rect class="edge-badge-rect" x="-42" y="-9" width="84" height="18" stroke="#64748b" />
                    <text class="edge-badge-text" fill="#cbd5e1">Flat ₹100 / Cons</text>
                </g>

                <!-- TCS Label -->
                <g transform="translate(650, 142)">
                    <rect class="edge-badge-rect" x="-42" y="-9" width="84" height="18" stroke="#06b6d4" />
                    <text class="edge-badge-text" fill="#67e8f9">1% TCS Withheld</text>
                </g>

                <!-- TDS Label -->
                <g transform="translate(775, 122)">
                    <rect class="edge-badge-rect" x="-48" y="-9" width="96" height="18" stroke="#a855f7" />
                    <text class="edge-badge-text" fill="#d8b4fe">0.75% TDS Withheld</text>
                </g>

                <!-- Vendor 1 Label -->
                <g transform="translate(680, 185)">
                    <rect class="edge-badge-rect" x="-48" y="-9" width="96" height="18" stroke="#f59e0b" />
                    <text class="edge-badge-text" fill="#fbbf24">Slab Drift (+₹300)</text>
                </g>

                <!-- Vendor 2 Label -->
                <g transform="translate(675, 238)">
                    <rect class="edge-badge-rect" x="-40" y="-9" width="80" height="18" stroke="#10b981" />
                    <text class="edge-badge-text" fill="#6ee7b7">Clean Payout</text>
                </g>

                <!-- Vendor 3 Label -->
                <g transform="translate(680, 290)">
                    <rect class="edge-badge-rect" x="-56" y="-9" width="112" height="18" stroke="#f43f5e" />
                    <text class="edge-badge-text" fill="#fda4af">Over-Clawback (-₹1,500)</text>
                </g>

                <!-- Vendor 4 Label -->
                <g transform="translate(675, 345)">
                    <rect class="edge-badge-rect" x="-48" y="-9" width="96" height="18" stroke="#06b6d4" />
                    <text class="edge-badge-text" fill="#67e8f9">GSTR-8 Timing Lag</text>
                </g>

                <!-- Vendor 5 Label -->
                <g transform="translate(675, 400)">
                    <rect class="edge-badge-rect" x="-40" y="-9" width="80" height="18" stroke="#10b981" />
                    <text class="edge-badge-text" fill="#6ee7b7">Clean Payout</text>
                </g>


                <!-- ════════════════════════════════════════════════════════════
                     NODES (Fintech Glass Cards with Semantic Color Strokes)
                ════════════════════════════════════════════════════════════ -->

                <!-- 1. PAYMENT AGGREGATOR (INBOUND SOURCE) -->
                <g id="node-aggregator" class="node-group category-gateway" transform="translate(30, 215)" onclick="inspectNode('aggregator')">
                    <rect class="node-card" width="190" height="110" fill="#0b172a" stroke="#0284c7" />
                    <text class="node-category" x="14" y="24" fill="#38bdf8">PAYMENT GATEWAY</text>
                    <text class="node-title" x="14" y="44">Razorpay Aggregator</text>
                    <text class="node-sub" x="14" y="62">GMV Inflow Remittance</text>
                    <text class="node-sub" x="14" y="78">Batch Settlement Window</text>
                    <rect class="status-pill-bg" x="14" y="86" width="110" height="16" fill="rgba(2, 132, 199, 0.2)" stroke="rgba(56, 189, 248, 0.4)" stroke-width="1" />
                    <text class="status-pill-text" x="69" y="94" fill="#38bdf8">INBOUND ACTIVE</text>
                </g>

                <!-- 2. CENTRAL RBI NODAL ESCROW CORE -->
                <g id="node-nodal" class="node-group category-core" transform="translate(320, 180)" onclick="inspectNode('nodal')">
                    <rect class="node-card" width="260" height="180" fill="#0d1b38" stroke="{'#e11d48' if has_nodal_break else '#2563eb'}" stroke-width="2" />
                    <text class="node-category" x="16" y="26" fill="{'#fb7185' if has_nodal_break else '#60a5fa'}">CENTRAL SETTLEMENT POOL</text>
                    <text class="node-title" x="16" y="48" style="font-size:14px;">RBI Mandated Nodal Escrow</text>
                    <text class="node-sub" x="16" y="70">Section 25 Payment Systems Act</text>
                    <text class="node-sub" x="16" y="88">Continuous 62-Day Audit Loop</text>
                    
                    <!-- Alert / Solvency Banner -->
                    <rect class="status-pill-bg" x="16" y="104" width="228" height="28" fill="{'rgba(225, 29, 72, 0.25)' if has_nodal_break else 'rgba(16, 185, 129, 0.2)'}" stroke="{'#fb7185' if has_nodal_break else '#34d399'}" stroke-width="1.2" />
                    <text class="status-pill-text" x="130" y="118" fill="{'#fb7185' if has_nodal_break else '#34d399'}" style="font-size:11px;">{nodal_status_text}</text>

                    <text class="node-sub" x="16" y="152" style="font-size:9.5px; fill:#94a3b8;">Click to review daily reconciliation log &rarr;</text>
                </g>

                <!-- 3. TOP ROW: MARKETPLACE TREASURY -->
                <g id="node-treasury" class="node-group category-statutory" transform="translate(270, 30)" onclick="inspectNode('treasury')">
                    <rect class="node-card" width="180" height="75" fill="#0f172a" stroke="#6366f1" />
                    <text class="node-category" x="12" y="20" fill="#a5b4fc">PLATFORM RETENTION</text>
                    <text class="node-title" x="12" y="38">Marketplace Treasury</text>
                    <text class="node-sub" x="12" y="54">Contractual Take-Rate Pool</text>
                    <rect class="status-pill-bg" x="12" y="58" width="90" height="13" fill="rgba(99, 102, 241, 0.18)" />
                    <text class="status-pill-text" x="57" y="65" fill="#a5b4fc" style="font-size:8.5px;">10% BASE RATE</text>
                </g>

                <!-- 4. TOP ROW: LOGISTICS SETTLEMENT POOL -->
                <g id="node-logistics" class="node-group category-statutory" transform="translate(480, 30)" onclick="inspectNode('logistics')">
                    <rect class="node-card" width="180" height="75" fill="#0f172a" stroke="#64748b" />
                    <text class="node-category" x="12" y="20" fill="#94a3b8">3PL SETTLEMENT</text>
                    <text class="node-title" x="12" y="38">Logistics Pool</text>
                    <text class="node-sub" x="12" y="54">Delhivery / BlueDart Escrow</text>
                    <rect class="status-pill-bg" x="12" y="58" width="95" height="13" fill="rgba(100, 116, 139, 0.2)" />
                    <text class="status-pill-text" x="59" y="65" fill="#cbd5e1" style="font-size:8.5px;">₹100 / CONSIGNMENT</text>
                </g>

                <!-- 5. TOP ROW: TAX TCS ESCROW (SEC 52) -->
                <g id="node-tcs" class="node-group category-statutory" transform="translate(690, 30)" onclick="inspectNode('tcs')">
                    <rect class="node-card" width="170" height="75" fill="#0f172a" stroke="#0891b2" />
                    <text class="node-category" x="12" y="20" fill="#22d3ee">STATUTORY WITHHOLDING</text>
                    <text class="node-title" x="12" y="38">Tax: TCS Escrow</text>
                    <text class="node-sub" x="12" y="54">Sec 52 CGST Act (1.0%)</text>
                    <rect class="status-pill-bg" x="12" y="58" width="80" height="13" fill="rgba(6, 182, 212, 0.18)" />
                    <text class="status-pill-text" x="52" y="65" fill="#22d3ee" style="font-size:8.5px;">GST REMITTANCE</text>
                </g>

                <!-- 6. TOP ROW: TAX TDS ESCROW (SEC 194-O) -->
                <g id="node-tds" class="node-group category-statutory" transform="translate(890, 30)" onclick="inspectNode('tds')">
                    <rect class="node-card" width="170" height="75" fill="#0f172a" stroke="#9333ea" />
                    <text class="node-category" x="12" y="20" fill="#c084fc">STATUTORY WITHHOLDING</text>
                    <text class="node-title" x="12" y="38">Tax: TDS Escrow</text>
                    <text class="node-sub" x="12" y="54">Sec 194-O IT Act (0.75%)</text>
                    <rect class="status-pill-bg" x="12" y="58" width="85" height="13" fill="rgba(168, 85, 247, 0.18)" />
                    <text class="status-pill-text" x="54" y="65" fill="#c084fc" style="font-size:8.5px;">CBDT QUARTERLY</text>
                </g>


                <!-- ════════════════════════════════════════════════════════════
                     RIGHT STACK: BENEFICIARY VENDORS
                ════════════════════════════════════════════════════════════ -->

                <!-- VEND-001: TechZone (Slab Drift) -->
                <g id="node-vend1" class="node-group category-anomalies" transform="translate(770, 140)" onclick="inspectNode('vend1')">
                    <rect class="node-card" width="370" height="56" fill="#1c160a" stroke="#d97706" />
                    <text class="node-category" x="14" y="18" fill="#fbbf24">VENDOR 001 &bull; ELECTRONICS</text>
                    <text class="node-title" x="14" y="36">TechZone &bull; ORD-001</text>
                    <text class="node-sub" x="14" y="50">Settlement Math Variance Caught</text>
                    <!-- Warning Pill -->
                    <rect class="status-pill-bg" x="220" y="14" width="138" height="26" fill="rgba(245, 158, 11, 0.18)" stroke="#f59e0b" stroke-width="1" />
                    <text class="status-pill-text" x="289" y="27" fill="#fbbf24">⚠️ Slab Drift (+₹300)</text>
                </g>

                <!-- VEND-002: FashionHub (Clean Reconciled) -->
                <g id="node-vend2" class="node-group category-reconciled" transform="translate(770, 213)" onclick="inspectNode('vend2')">
                    <rect class="node-card" width="370" height="56" fill="#081e17" stroke="#059669" />
                    <text class="node-category" x="14" y="18" fill="#34d399">VENDOR 002 &bull; APPARELS</text>
                    <text class="node-title" x="14" y="36">FashionHub &bull; ORD-002</text>
                    <text class="node-sub" x="14" y="50">Automated T+2 Bank Transfer</text>
                    <!-- Success Pill -->
                    <rect class="status-pill-bg" x="220" y="14" width="138" height="26" fill="rgba(16, 185, 129, 0.15)" stroke="#10b981" stroke-width="1" />
                    <text class="status-pill-text" x="289" y="27" fill="#34d399">✓ Reconciled Clean</text>
                </g>

                <!-- VEND-003: HomeComforts (Asymmetric Over-Clawback) -->
                <g id="node-vend3" class="node-group category-anomalies" transform="translate(770, 286)" onclick="inspectNode('vend3')">
                    <rect class="node-card" width="370" height="56" fill="#240a12" stroke="#e11d48" stroke-width="1.8" />
                    <text class="node-category" x="14" y="18" fill="#fb7185">VENDOR 003 &bull; HOME FURNISHING</text>
                    <text class="node-title" x="14" y="36">HomeComforts &bull; ORD-015</text>
                    <text class="node-sub" x="14" y="50">Unilateral Refund Over-Clawback</text>
                    <!-- Critical Alert Pill -->
                    <rect class="status-pill-bg" x="220" y="14" width="138" height="26" fill="rgba(225, 29, 72, 0.25)" stroke="#f43f5e" stroke-width="1.2" />
                    <text class="status-pill-text" x="289" y="27" fill="#fb7185">🚨 Over-Clawback (-₹1,500)</text>
                </g>

                <!-- VEND-004: BooksAndMore (TCS Timing Lag) -->
                <g id="node-vend4" class="node-group category-anomalies" transform="translate(770, 359)" onclick="inspectNode('vend4')">
                    <rect class="node-card" width="370" height="56" fill="#081e26" stroke="#0891b2" />
                    <text class="node-category" x="14" y="18" fill="#22d3ee">VENDOR 004 &bull; PUBLISHING</text>
                    <text class="node-title" x="14" y="36">BooksAndMore &bull; ORD-028</text>
                    <text class="node-sub" x="14" y="50">GSTR-8 10th-of-Month Filing Buffer</text>
                    <!-- Timing Pill -->
                    <rect class="status-pill-bg" x="220" y="14" width="138" height="26" fill="rgba(6, 182, 212, 0.18)" stroke="#06b6d4" stroke-width="1" />
                    <text class="status-pill-text" x="289" y="27" fill="#22d3ee">⏳ GSTR-8 Timing (₹100)</text>
                </g>

                <!-- VEND-005: FitnessFirst (Clean Reconciled) -->
                <g id="node-vend5" class="node-group category-reconciled" transform="translate(770, 432)" onclick="inspectNode('vend5')">
                    <rect class="node-card" width="370" height="56" fill="#081e17" stroke="#059669" />
                    <text class="node-category" x="14" y="18" fill="#34d399">VENDOR 005 &bull; HEALTH &amp; FITNESS</text>
                    <text class="node-title" x="14" y="36">FitnessFirst &bull; ORD-042</text>
                    <text class="node-sub" x="14" y="50">Settlement Verified &amp; Cleared</text>
                    <!-- Success Pill -->
                    <rect class="status-pill-bg" x="220" y="14" width="138" height="26" fill="rgba(16, 185, 129, 0.15)" stroke="#10b981" stroke-width="1" />
                    <text class="status-pill-text" x="289" y="27" fill="#34d399">✓ Reconciled Clean</text>
                </g>

            </g>
        </svg>
    </div>

    <!-- Interactive Bottom Inspection Drawer (Appears upon clicking any node) -->
    <div class="info-drawer" id="infoDrawer">
        <div class="drawer-content" id="drawerContent">
            <!-- Injected via JavaScript -->
        </div>
        <button class="drawer-close" onclick="closeDrawer()" title="Close details panel">&times;</button>
    </div>

    <!-- Bottom Status Legend -->
    <div class="legend-bar">
        <div class="legend-items">
            <div class="legend-item"><span class="legend-dot" style="background:#e11d48;"></span> Deficit / Clawback Break (Critical)</div>
            <div class="legend-item"><span class="legend-dot" style="background:#d97706;"></span> Commission Slab Drift (Audit Review)</div>
            <div class="legend-item"><span class="legend-dot" style="background:#0891b2;"></span> Statutory Tax &amp; GSTR-8 Buffer</div>
            <div class="legend-item"><span class="legend-dot" style="background:#059669;"></span> Reconciled Settlement</div>
            <div class="legend-item"><span class="legend-dot" style="background:#6366f1;"></span> Platform Treasury Take-Rate</div>
        </div>
        <div style="font-size:10.5px; color:#64748b;">
            💡 Click any node to open regulatory &amp; math dossier
        </div>
    </div>
</div>

<script>
    // Entity Detailed Dossier Data for Interactive Inspection
    const nodeDetails = {{
        aggregator: {{
            title: "Payment Aggregator (Razorpay Gateway)",
            category: "Inbound Payment Gateway & Batch Settlement",
            regulation: "RBI Circular DPSS.CO.PD.No.1810/02.14.008/2019-20",
            volume: "Total Inflow GMV: ₹1,420,500",
            audit_status: "Operational — Batch window T+1 net remittance verified",
            action: "Normal Operations — Webhook signatures validated"
        }},
        nodal: {{
            title: "RBI Mandated Nodal Escrow Account",
            category: "Core Trust & Escrow Clearing Pool",
            regulation: "Section 25 Payment and Settlement Systems Act, 2007",
            volume: "Pool Balance: ₹450,000 | Expected Solvency: ₹500,000",
            audit_status: "{nodal_status_text} (Variance: -₹50,000)",
            action: "Dual-Core Safety Trigger: Nodal rebalancing hold placed. Direct debit dispatch locked pending human CFO sign-off."
        }},
        treasury: {{
            title: "Marketplace Treasury Pool",
            category: "Platform Commission & Take-Rate Retention",
            regulation: "Platform Seller Contract & Master Service Agreement",
            volume: "10% Standard Rate Retention",
            audit_status: "Variance detected on ORD-001 (Collected 7% vs Contractual 10%)",
            action: "Automated clawback recovery scheduled for next vendor settlement tranche."
        }},
        logistics: {{
            title: "Logistics Clearing Pool",
            category: "3PL Partner Settlement (Delhivery / BlueDart)",
            regulation: "Logistics SLA & Consignment Manifest Verification",
            volume: "Flat ₹100 / Consignment",
            audit_status: "100% Reconciled against tracking POD receipts",
            action: "Cleared for automated daily batch wire."
        }},
        tcs: {{
            title: "Tax Collected at Source (TCS) Escrow",
            category: "Statutory Tax Withholding",
            regulation: "Section 52, Central Goods and Services Tax (CGST) Act, 2017",
            volume: "1.0% on Net E-Commerce Supplies",
            audit_status: "Compliant — BooksAndMore ₹100 timing buffer under 10th-of-month GSTR-8 return rule",
            action: "Preserved in escrow; auto-filed with GSTN portal on monthly cutoff."
        }},
        tds: {{
            title: "Tax Deducted at Source (TDS) Escrow",
            category: "Statutory Direct Tax Withholding",
            regulation: "Section 194-O, Income Tax Act, 1961",
            volume: "0.75% / 1.0% PAN-linked Deduction",
            audit_status: "Reconciled with 100% valid PAN validation checks",
            action: "Deposited into CBDT treasury via Form 26Q."
        }},
        vend1: {{
            title: "VEND-001: TechZone Electronics",
            category: "Planted Edge Case #1: Retroactive Slab Drift",
            regulation: "Seller Addendum v2.4 (Effective Aug 1, 2026)",
            volume: "Order ORD-001 Placed: July 25 (10% slab) | Settled: Aug 2 (7% deducted)",
            audit_status: "Variance: +₹300 Commission Under-Collection",
            action: "Dual-Core Interceptor intercepted action: Contractual rate applied. Leakage arrested."
        }},
        vend2: {{
            title: "VEND-002: FashionHub Apparels",
            category: "Standard Reconciled Beneficiary",
            regulation: "Standard SLA Category A",
            volume: "Order ORD-002 Settled: Net ₹8,900 after 10% fee & taxes",
            audit_status: "Zero Variance — 100% Reconciled",
            action: "Dispatched without friction via Razorpay Route API."
        }},
        vend3: {{
            title: "VEND-003: HomeComforts",
            category: "Planted Edge Case #2: Asymmetric Refund Over-Clawback",
            regulation: "Merchant Protection & Returns Agreement",
            volume: "Order ORD-015: Customer refund ₹1,500 deducted TWICE (Gateway + ERP)",
            audit_status: "CRITICAL BREACH: -₹1,500 Vendor Under-Settlement Discrepancy",
            action: "Payment Blocked: Safety Interceptor raised Human-in-the-Loop exception to refund vendor."
        }},
        vend4: {{
            title: "VEND-004: BooksAndMore",
            category: "Planted Edge Case #3: GSTR-8 Timing Lag",
            regulation: "GST Rules 2017 — Rule 67 Form GSTR-8",
            volume: "Order ORD-028: ₹100 TCS withholding timing difference",
            audit_status: "BENIGN TIMING DRIFT: ₹100 lag within statutory 10-day settlement grace window",
            action: "AI Supervisor marked as Benign Timing Difference — No punitive freeze."
        }},
        vend5: {{
            title: "VEND-005: FitnessFirst Equipment",
            category: "Standard Reconciled Beneficiary",
            regulation: "Standard SLA Category B",
            volume: "Order ORD-042: Settled with zero mathematical discrepancy",
            audit_status: "Zero Variance — Clean Solvency",
            action: "Cleared for automated execution."
        }}
    }};

    // ══════════════════════════════════════════════════════════════════
    // ULTRA-SMOOTH MOMENTUM PAN & CURSOR-ANCHORED ZOOM ENGINE (60/120 FPS)
    // ══════════════════════════════════════════════════════════════════
    let currentScale = 1.0;
    let targetScale = 1.0;
    let currentX = 0;
    let targetX = 0;
    let currentY = 0;
    let targetY = 0;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let animActive = true;
    let renderLoopId = null;

    const viewportGroup = document.getElementById('viewportGroup');
    const canvasWrapper = document.getElementById('canvasWrapper');
    const zoomPill = document.getElementById('zoomPill');

    // High-performance Lerp animation loop
    function updateLoop() {{
        const ease = 0.22; // Silky smooth damping without oscillation
        const scaleDiff = targetScale - currentScale;
        const xDiff = targetX - currentX;
        const yDiff = targetY - currentY;

        currentScale += scaleDiff * ease;
        currentX += xDiff * ease;
        currentY += yDiff * ease;

        viewportGroup.setAttribute(
            'transform',
            `translate(${{currentX.toFixed(2)}}, ${{currentY.toFixed(2)}}) scale(${{currentScale.toFixed(4)}})`
        );

        if (zoomPill) {{
            zoomPill.innerText = Math.round(currentScale * 100) + '%';
        }}

        if (Math.abs(scaleDiff) > 0.0008 || Math.abs(xDiff) > 0.08 || Math.abs(yDiff) > 0.08) {{
            renderLoopId = requestAnimationFrame(updateLoop);
        }} else {{
            currentScale = targetScale;
            currentX = targetX;
            currentY = targetY;
            viewportGroup.setAttribute(
                'transform',
                `translate(${{currentX.toFixed(2)}}, ${{currentY.toFixed(2)}}) scale(${{currentScale.toFixed(4)}})`
            );
            if (zoomPill) {{
                zoomPill.innerText = Math.round(currentScale * 100) + '%';
            }}
            renderLoopId = null;
        }}
    }}

    function requestRender() {{
        if (!renderLoopId) {{
            renderLoopId = requestAnimationFrame(updateLoop);
        }}
    }}

    // Cursor-Anchored Smooth Zoom (Pinned to Mouse Pointer)
    function zoomAtPoint(clientX, clientY, zoomMultiplier) {{
        const rect = canvasWrapper.getBoundingClientRect();
        const mouseX = clientX - rect.left;
        const mouseY = clientY - rect.top;

        const newTargetScale = Math.min(Math.max(targetScale * zoomMultiplier, 0.55), 2.8);

        // Calculate translation so point under cursor stays strictly stationary
        targetX = mouseX - (mouseX - targetX) * (newTargetScale / targetScale);
        targetY = mouseY - (mouseY - targetY) * (newTargetScale / targetScale);
        targetScale = newTargetScale;

        requestRender();
    }}

    function zoomIn() {{
        const rect = canvasWrapper.getBoundingClientRect();
        zoomAtPoint(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.25);
    }}

    function zoomOut() {{
        const rect = canvasWrapper.getBoundingClientRect();
        zoomAtPoint(rect.left + rect.width / 2, rect.top + rect.height / 2, 0.8);
    }}

    function resetZoom() {{
        targetScale = 1.0;
        targetX = 0;
        targetY = 0;
        requestRender();
    }}

    // Double-click on canvas smoothly resets view
    canvasWrapper.addEventListener('dblclick', (e) => {{
        if (e.target.closest('.node-group') || e.target.closest('button')) return;
        resetZoom();
    }});

    // Mouse drag pan with smooth handling
    canvasWrapper.addEventListener('mousedown', (e) => {{
        if (e.target.closest('.node-group') || e.target.closest('button') || e.target.closest('.filter-group')) return;
        isDragging = true;
        canvasWrapper.style.cursor = 'grabbing';
        dragStartX = e.clientX - targetX;
        dragStartY = e.clientY - targetY;
    }});

    window.addEventListener('mousemove', (e) => {{
        if (!isDragging) return;
        targetX = e.clientX - dragStartX;
        targetY = e.clientY - dragStartY;
        requestRender();
    }});

    window.addEventListener('mouseup', () => {{
        if (isDragging) {{
            isDragging = false;
            canvasWrapper.style.cursor = 'grab';
        }}
    }});

    // Silky Smooth Mouse Wheel & Trackpad Pinch Zoom
    canvasWrapper.addEventListener('wheel', (e) => {{
        e.preventDefault();
        // Calculate smooth exponential zoom factor based on wheel delta magnitude
        const delta = -e.deltaY;
        const zoomIntensity = e.ctrlKey ? 0.015 : 0.0018;
        const multiplier = Math.exp(delta * zoomIntensity);

        zoomAtPoint(e.clientX, e.clientY, multiplier);
    }}, {{ passive: false }});

    // Animation toggle
    function toggleAnimation() {{
        animActive = !animActive;
        const particles = document.querySelectorAll('.flow-particle');
        particles.forEach(p => {{
            p.style.display = animActive ? 'block' : 'none';
        }});
        document.getElementById('animBtn').innerText = animActive ? '⚡ Animation: ON' : '⚡ Animation: OFF';
    }}

    // Filter nodes and paths
    function setFilter(category, btn) {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const allNodes = document.querySelectorAll('.node-group');
        const allPaths = document.querySelectorAll('.flow-path, .flow-particle');

        if (category === 'all') {{
            allNodes.forEach(n => n.classList.remove('dimmed'));
            allPaths.forEach(p => p.classList.remove('dimmed'));
            return;
        }}

        allNodes.forEach(n => {{
            if (n.classList.contains('category-' + category) || n.id === 'node-nodal') {{
                n.classList.remove('dimmed');
            }} else {{
                n.classList.add('dimmed');
            }}
        }});

        // Highlight matching paths
        if (category === 'anomalies') {{
            allPaths.forEach(p => {{
                if (p.id.includes('vend1') || p.id.includes('vend3') || p.id.includes('vend4')) {{
                    p.classList.remove('dimmed');
                }} else {{
                    p.classList.add('dimmed');
                }}
            }});
        }} else if (category === 'reconciled') {{
            allPaths.forEach(p => {{
                if (p.id.includes('vend2') || p.id.includes('vend5')) {{
                    p.classList.remove('dimmed');
                }} else {{
                    p.classList.add('dimmed');
                }}
            }});
        }} else if (category === 'statutory') {{
            allPaths.forEach(p => {{
                if (p.id.includes('treasury') || p.id.includes('logistics') || p.id.includes('tcs') || p.id.includes('tds')) {{
                    p.classList.remove('dimmed');
                }} else {{
                    p.classList.add('dimmed');
                }}
            }});
        }}
    }}

    // Interactive Node Click -> Bottom Dossier Inspection
    function inspectNode(nodeKey) {{
        const d = nodeDetails[nodeKey];
        if (!d) return;

        const content = document.getElementById('drawerContent');
        content.innerHTML = `
            <div class="drawer-item" style="min-width:210px;">
                <span class="drawer-label">${{d.category}}</span>
                <span class="drawer-val" style="color:#38bdf8; font-size:13px;">${{d.title}}</span>
            </div>
            <div class="drawer-item" style="min-width:180px;">
                <span class="drawer-label">Regulatory Mandate</span>
                <span class="drawer-val">${{d.regulation}}</span>
            </div>
            <div class="drawer-item" style="min-width:160px;">
                <span class="drawer-label">Flow Volume / Metric</span>
                <span class="drawer-val">${{d.volume}}</span>
            </div>
            <div class="drawer-item" style="min-width:200px;">
                <span class="drawer-label">Audit Engine Verdict</span>
                <span class="drawer-val" style="color:${{d.audit_status.includes('Variance') || d.audit_status.includes('BREACH') || d.audit_status.includes('ALERT') ? '#fb7185' : '#34d399'}};">${{d.audit_status}}</span>
            </div>
            <div class="drawer-item" style="flex:1; min-width:240px;">
                <span class="drawer-label">Safety Action / Interceptor Gate</span>
                <span class="drawer-val" style="color:#e2e8f0; font-size:11px;">${{d.action}}</span>
            </div>
        `;

        document.getElementById('infoDrawer').classList.add('open');
    }}

    function closeDrawer() {{
        document.getElementById('infoDrawer').classList.remove('open');
    }}
</script>

</body>
</html>
"""
    return html_template
