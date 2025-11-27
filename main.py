# main.py
from core.graph_builder import build_graph

if __name__ == "__main__":
    app = build_graph()
    final = app.invoke({})
    print("\n=== FINAL ANALYSIS ===")
    print(final["analysis"])