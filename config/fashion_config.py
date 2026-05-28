"""
时装数据配置

包含 cnName 预处理规则：统一补全"时装"后缀。
"""
import re

# 特殊项：不需要加"时装"后缀的 cnName 集合
FASHION_NO_SUFFIX = {
    "虚化面具",
    "虚化完全体",
    "苍穹钢铁侠",
    "赤焰钢铁侠",
    "小贝头盔",
    "僵尸面具",
    "大圣限时皮肤",
    "雪影限时皮肤",
    "宇航服",
}


# name → 强制 cnName 覆盖表（处理官方数据重名等特殊情况）
FASHION_NAME_MAP = {
    "chinaCaptain": "中国队长时装",
}


def normalize_fashion_cn(cn_name: str) -> str:
    """规范化时装 cnName：若不在白名单中且未以"时装"结尾，则追加"时装"后缀"""
    if not cn_name:
        return cn_name
    if cn_name in FASHION_NO_SUFFIX:
        return cn_name
    if re.search(r'时装$', cn_name):
        return cn_name
    return cn_name + '时装'
