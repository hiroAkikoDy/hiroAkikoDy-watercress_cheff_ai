import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

japanese_fonts = [
    'C:/Windows/Fonts/YuGothic.ttc',
    'C:/Windows/Fonts/YuGothM.ttc',
    'C:/Windows/Fonts/meiryo.ttc',
    'C:/Windows/Fonts/msgothic.ttc',
]
jp_font_path = None
for fp in japanese_fonts:
    if os.path.exists(fp):
        jp_font_path = fp
        break

if jp_font_path:
    fm.fontManager.addfont(jp_font_path)
    prop = fm.FontProperties(fname=jp_font_path)
    jp_font_name = prop.get_name()
    plt.rcParams['font.family'] = jp_font_name
    plt.rcParams['font.sans-serif'] = [jp_font_name, 'DejaVu Sans']
    print(f"フォント: {jp_font_name}", flush=True)
else:
    print("警告: 日本語フォントが見つかりません", flush=True)

G = nx.DiGraph()

nodes = [
    ("ROOT",   "Achieve\nクレソンを手に取った個人客が\n料理法を見つけられる", "achieve_root"),
    ("FAST",   "Achieve\nTYPE_0・TYPE_1で\n65%の質問を即時返答", "achieve_p3b"),
    ("T0",     "Achieve\nTYPE_0: 挨拶・定型\n0.5秒以内", "achieve_p3b_impl"),
    ("T1",     "Achieve\nTYPE_1: キーワード検索\n3秒以内", "achieve_p3b_impl"),
    ("T3",     "Achieve\nTYPE_3: 対話型絞り込み\n基本2往復・最大3往復", "achieve_p4"),
    ("DIAL",   "Achieve\n条件収集\n人数・ジャンル・用途", "achieve_p4_impl"),
    ("RAG3",   "Achieve\n条件付きRAG検索", "achieve_p4_impl"),
    ("MULTI",  "Achieve\nマルチペルソナ\nChef→Nutritionist", "achieve_p4_impl"),
    ("ASYNC",  "Achieve\n非同期レポート生成\nブロッキング解消", "achieve_p4b"),
    ("INTV",   "Achieve\nインタビュアーAI\nレポート生成中に会話継続", "achieve_p4b"),
    ("POLL",   "Achieve\nポーリング\n5秒ごとに完了確認", "achieve_p4b_impl"),
    ("CACHE",  "Achieve\nreport_cache\nsession_idで管理", "achieve_p4b_impl"),
    ("IQ1",    "Achieve\nQ1: アレルギー・苦手食材\n安全性を最優先で確認", "achieve_p4b_impl"),
    ("IQ2",    "Achieve\nQ2: 調理時間 or 冷蔵庫食材\n実用性を確認", "achieve_p4b_impl"),
    ("AV1",    "Avoid\nエキスパートシステム化\n→ルール爆発", "avoid"),
    ("AV2",    "Avoid\n対話が3往復を超える\n→ユーザー離脱", "avoid"),
    ("AV3",    "Avoid\nレポート生成中の\nユーザー待機体験", "avoid"),
    ("AV4",    "Avoid\nインタビューが\n2問を超える\n→煩わしさ", "avoid"),
]

edges = [
    ("ROOT",  "FAST"),
    ("ROOT",  "T3"),
    ("ROOT",  "ASYNC"),
    ("FAST",  "T0"),
    ("FAST",  "T1"),
    ("T3",    "DIAL"),
    ("T3",    "RAG3"),
    ("T3",    "MULTI"),
    ("ASYNC", "POLL"),
    ("ASYNC", "CACHE"),
    ("INTV",  "IQ1"),
    ("INTV",  "IQ2"),
    ("ASYNC", "INTV"),
    ("ROOT",  "AV1"),
    ("DIAL",  "AV2"),
    ("ASYNC", "AV3"),
    ("INTV",  "AV4"),
]

for node_id, label, ntype in nodes:
    G.add_node(node_id, label=label, ntype=ntype)
for src, dst in edges:
    G.add_edge(src, dst)

pos = {
    "ROOT":  (5.5, 10),
    "FAST":  (1.5, 8.5),
    "T3":    (5.5, 8.5),
    "ASYNC": (9.5, 8.5),
    "T0":    (0.5, 7),
    "T1":    (2.5, 7),
    "DIAL":  (4, 7),
    "RAG3":  (5.5, 7),
    "MULTI": (7, 7),
    "POLL":  (8.5, 7),
    "CACHE": (10.5, 7),
    "INTV":  (9.5, 5.5),
    "IQ1":   (8.5, 4),
    "IQ2":   (10.5, 4),
    "AV1":   (1.5, 5.5),
    "AV2":   (4, 5.5),
    "AV3":   (7, 5.5),
    "AV4":   (11.5, 2.5),
}

color_map = {
    "achieve_root":     "#534AB7",
    "achieve_p3b":      "#0F6E56",
    "achieve_p3b_impl": "#0C447C",
    "achieve_p4":       "#1A7A4A",
    "achieve_p4_impl":  "#155A8A",
    "achieve_p4b":      "#B05A00",
    "achieve_p4b_impl": "#7A3F00",
    "avoid":            "#A32D2D",
}

fig, ax = plt.subplots(figsize=(20, 12))
fig.patch.set_facecolor('#FAFAFA')
ax.set_facecolor('#FAFAFA')

for ntype, color in color_map.items():
    nodelist = [n for n, d in G.nodes(data=True) if d['ntype'] == ntype]
    if nodelist:
        nx.draw_networkx_nodes(
            G, pos, nodelist=nodelist,
            node_color=color, node_size=2200,
            node_shape='s', ax=ax, alpha=0.85
        )

edge_colors = []
for src, dst in G.edges():
    dst_type = G.nodes[dst]['ntype']
    if dst_type == 'avoid':
        edge_colors.append('#A32D2D')
    else:
        edge_colors.append('#444441')

nx.draw_networkx_edges(
    G, pos, edge_color=edge_colors,
    arrows=True, arrowsize=15, width=1.5, ax=ax,
    connectionstyle='arc3,rad=0.05'
)

labels = {n: d['label'] for n, d in G.nodes(data=True)}
nx.draw_networkx_labels(
    G, pos, labels=labels,
    font_size=6, font_color='white',
    font_weight='bold', ax=ax
)

legend_patches = [
    mpatches.Patch(color='#534AB7', label='Achieve（ルート）'),
    mpatches.Patch(color='#0F6E56', label='Achieve（Phase 3b）'),
    mpatches.Patch(color='#0C447C', label='Achieve（Phase 3b実装）'),
    mpatches.Patch(color='#1A7A4A', label='Achieve（Phase 4）'),
    mpatches.Patch(color='#155A8A', label='Achieve（Phase 4実装）'),
    mpatches.Patch(color='#B05A00', label='Achieve（Phase 4b NEW）'),
    mpatches.Patch(color='#7A3F00', label='Achieve（Phase 4b実装）'),
    mpatches.Patch(color='#A32D2D', label='Avoid'),
]
ax.legend(handles=legend_patches, loc='lower left', fontsize=8)
ax.set_title(
    'Phase 4b 非同期レポート + インタビュアーAI — KAOSゴールツリー',
    fontsize=14, pad=20
)
ax.axis('off')
plt.tight_layout()

output_path = os.path.join(os.path.dirname(__file__), 'kaos_goal_tree_phase4b.png')
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f'保存完了: {output_path}')
