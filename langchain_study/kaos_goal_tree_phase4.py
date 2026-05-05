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
    ("ROOT", "Achieve\nクレソンを手に取った個人客が\n料理法を見つけられる", "achieve_root"),
    ("FAST",  "Achieve\nTYPE_0・TYPE_1で\n65%の質問を即時返答", "achieve"),
    ("T0",    "Achieve\nTYPE_0: 挨拶・定型\n0.5秒以内", "achieve_impl"),
    ("T1",    "Achieve\nTYPE_1: キーワード検索\n3秒以内", "achieve_impl"),
    ("T3",    "Achieve\nTYPE_3: 対話型絞り込み\n残り全ての質問", "achieve_new"),
    ("DIAL",  "Achieve\n対話エンジン\n基本2往復・最大3往復", "achieve_new"),
    ("RAG3",  "Achieve\n条件付きRAG検索\n収集条件をCypherフィルターに", "achieve_new"),
    ("MULTI", "Achieve\nマルチペルソナレポート\n司会→シェフ→栄養士→司会", "achieve_new"),
    ("MC",    "Achieve\n司会ペルソナ\n導入とまとめ", "achieve_impl_new"),
    ("CHEF",  "Achieve\nシェフペルソナ\n調理技術・レシピ", "achieve_impl_new"),
    ("NUTR",  "Achieve\n栄養士ペルソナ\n栄養価・健康メリット", "achieve_impl_new"),
    ("T2DEP", "Achieve\nTYPE_2廃止\nTYPE_3に統合", "deprecated"),
    ("AV1",   "Avoid\nエキスパートシステム化\n→ルール爆発・例外対応不能", "avoid"),
    ("AV2",   "Avoid\n対話が3往復を超える\n→ユーザー離脱リスク", "avoid"),
    ("AV3",   "Avoid\nペルソナ発言が長すぎる\n→300字超・読まれない", "avoid"),
]

edges = [
    ("ROOT", "FAST"),
    ("ROOT", "T3"),
    ("FAST", "T0"),
    ("FAST", "T1"),
    ("T3",   "DIAL"),
    ("T3",   "RAG3"),
    ("T3",   "MULTI"),
    ("MULTI","MC"),
    ("MULTI","CHEF"),
    ("MULTI","NUTR"),
    ("T3",   "T2DEP"),
    ("ROOT", "AV1"),
    ("DIAL", "AV2"),
    ("MULTI","AV3"),
]

for node_id, label, ntype in nodes:
    G.add_node(node_id, label=label, ntype=ntype)
for src, dst in edges:
    G.add_edge(src, dst)

pos = {
    "ROOT":  (5, 10),
    "FAST":  (2, 8.5),
    "T3":    (7.5, 8.5),
    "T0":    (1, 7),
    "T1":    (3, 7),
    "DIAL":  (5.5, 7),
    "RAG3":  (7.5, 7),
    "MULTI": (9.5, 7),
    "MC":    (8.5, 5.5),
    "CHEF":  (9.5, 5.5),
    "NUTR":  (10.5, 5.5),
    "T2DEP": (6.5, 5.5),
    "AV1":   (2, 5.5),
    "AV2":   (5, 5.5),
    "AV3":   (9, 4),
}

color_map = {
    "achieve_root":    "#534AB7",
    "achieve":         "#0F6E56",
    "achieve_impl":    "#0C447C",
    "achieve_new":     "#1A7A4A",
    "achieve_impl_new":"#155A8A",
    "deprecated":      "#888888",
    "avoid":           "#A32D2D",
}

fig, ax = plt.subplots(figsize=(18, 12))
fig.patch.set_facecolor('#FAFAFA')
ax.set_facecolor('#FAFAFA')

for ntype, color in color_map.items():
    nodelist = [n for n, d in G.nodes(data=True) if d['ntype'] == ntype]
    if nodelist:
        nx.draw_networkx_nodes(
            G, pos, nodelist=nodelist,
            node_color=color, node_size=2500,
            node_shape='s', ax=ax, alpha=0.85
        )

edge_colors = []
for src, dst in G.edges():
    dst_type = G.nodes[dst]['ntype']
    if dst_type == 'avoid':
        edge_colors.append('#A32D2D')
    elif dst_type == 'deprecated':
        edge_colors.append('#888888')
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
    font_size=6.5, font_color='white',
    font_weight='bold', ax=ax
)

legend_patches = [
    mpatches.Patch(color='#534AB7', label='Achieve（ルート）'),
    mpatches.Patch(color='#0F6E56', label='Achieve（Phase 3b）'),
    mpatches.Patch(color='#0C447C', label='Achieve（Phase 3b実装）'),
    mpatches.Patch(color='#1A7A4A', label='Achieve（Phase 4 NEW）'),
    mpatches.Patch(color='#155A8A', label='Achieve（Phase 4実装）'),
    mpatches.Patch(color='#888888', label='廃止（TYPE_2）'),
    mpatches.Patch(color='#A32D2D', label='Avoid'),
]
ax.legend(handles=legend_patches, loc='lower left', fontsize=8)
ax.set_title(
    'Phase 4 マルチペルソナ × 対話型絞り込み — KAOSゴールツリー',
    fontsize=14, pad=20
)
ax.axis('off')
plt.tight_layout()

output_path = os.path.join(os.path.dirname(__file__), 'kaos_goal_tree_phase4.png')
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f'保存完了: {output_path}')
