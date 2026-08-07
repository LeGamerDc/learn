"""中文字体 helper。所有模型脚本开头 import 它即可。"""
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

# macOS 上按优先级尝试；Windows/Linux 的候选也一并列出
CANDIDATES = [
    "PingFang SC", "Hiragino Sans GB", "Songti SC", "STHeiti",   # macOS
    "Microsoft YaHei", "SimHei",                                  # Windows
    "Noto Sans CJK SC", "WenQuanYi Zen Hei",                      # Linux
]


def use_cjk_font():
    """把 matplotlib 全局字体设成一个可用的中文字体。返回选中的字体名。"""
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in CANDIDATES:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False  # 负号也会变方框，一起修
            return name
    print("⚠️  没找到中文字体，图里的中文会显示为方框。")
    print("   可用字体前 20 个：", sorted(available)[:20])
    return None


if __name__ == "__main__":
    print("使用字体：", use_cjk_font())
