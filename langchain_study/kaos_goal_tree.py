import networkx as nx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import sys, os

sys.stdout.reconfigure(encoding='utf-8')

japanese_fonts = [
    'C:/Windows/Fonts/msgothic.ttc',
    'C:/Windows/Fonts/meiryo.ttc',
    'C:/Windows/Fonts/YuGothic.ttc',
    'C:/Windows/Fonts/YuGothM.ttc',
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
    ("ROOT",    "Achieve\nクレソンを手に取った個人客が\n料理法を見つけられる",    "achieve_root"),
    ("TTFB",    "Achieve\nTool Selectorで全質問の75%を\n3秒以内に返す",          "achieve"),
    ("T0",      "Achieve\nTYPE_0: 挨拶・定型応答\n0.5秒以内",                   "achieve"),
    ("T1",      "Achieve\nTYPE_1: 構造化検索\n3秒以内",                          "achieve"),
    ("T2",      "Achieve\nTYPE_2: 意味検索（RAG）\n20秒以内",                    "achieve"),
    ("RT",      "Achieve\nResponseTemplateノード\nNeo4jに格納",                   "achieve_impl"),
    ("SM",      "Achieve\nspaCy Matcher\n地域・季節・用途パターン",               "achieve_impl"),
    ("RAG",     "Achieve\nRAG Hybrid Search\nデフォルト経路維持",                 "achieve_impl"),
    ("AV1",     "Avoid\n全質問にRAGを適用する\n→ 40秒・トークン浪費",             "avoid"),
    ("AV2",     "Avoid\n誤ったツールへの振り分け\n→ 回答品質の低下",              "avoid"),
]

edges = [
    ("ROOT", "TTFB"),
    ("TTFB", "T0"), ("TTFB", "T1"), ("TTFB", "T2"),
    ("T0",   "RT"), ("T1",   "SM"), ("T2",   "RAG"),
    ("TTFB", "AV1"), ("TTFB", "AV2"),
]

for node_id, label, ntype in nodes:
    G.add_node(node_id, label=label, ntype=ntype)

for src, dst in edges:
    G.add_edge(src, dst)

pos = {
    "ROOT": (4, 8),
    "TTFB": (4, 6.5),
    "T0":   (1, 5), "T1": (4, 5), "T2": (7, 5),
    "RT":   (1, 3.5), "SM": (4, 3.5), "RAG": (7, 3.5),
    "AV1":  (1.5, 2), "AV2": (6.5, 2),
}

color_map = {
    "achieve_root": "#534AB7",
    "achieve":      "#0F6E56",
    "achieve_impl": "#0C447C",
    "avoid":        "#A32D2D",
}

fig, ax = plt.subplots(1, 1, figsize=(14, 10))
fig.patch.set_facecolor('#FAFAFA')
ax.set_facecolor('#FAFAFA')

for ntype, color in color_map.items():
    nodelist = [n for n, d in G.nodes(data=True) if d['ntype'] == ntype]
    nx.draw_networkx_nodes(
        G, pos, nodelist=nodelist,
        node_color=color, node_size=3000,
        node_shape='s', ax=ax, alpha=0.85
    )

edge_colors = []
for src, dst in G.edges():
    dst_type = G.nodes[dst]['ntype']
    edge_colors.append('#A32D2D' if dst_type == 'avoid' else '#444441')

nx.draw_networkx_edges(
    G, pos,
    edge_color=edge_colors,
    arrows=True, arrowsize=20,
    width=1.5, ax=ax,
    connectionstyle='arc3,rad=0.05'
)

labels = {n: d['label'] for n, d in G.nodes(data=True)}
nx.draw_networkx_labels(
    G, pos, labels=labels,
    font_size=7, font_color='white',
    font_weight='bold', ax=ax
)

legend_patches = [
    mpatches.Patch(color='#534AB7', label='Achieve（ルート）'),
    mpatches.Patch(color='#0F6E56', label='Achieve（サブゴール）'),
    mpatches.Patch(color='#0C447C', label='Achieve（実装）'),
    mpatches.Patch(color='#A32D2D', label='Avoid'),
]
ax.legend(handles=legend_patches, loc='lower left', fontsize=9)
ax.set_title('Phase 3b Tool Selector — KAOSゴールツリー', fontsize=14, pad=20)
ax.axis('off')

plt.tight_layout()
output_path = 'kaos_goal_tree.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f'保存完了: {output_path}')
