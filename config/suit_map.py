# 套装 gather cnName → Wiki 分类 映射表
# 映射依据：gather 标签的 cnName 属性判定套装分类
# 当 gather 没有 cnName 时，默认分类为"普通套装"

GATHER_SUIT_MAP = {
    "稀有套装": "稀有套装",
    "竞技场套装": "竞技场套装",
    "特殊": "竞技场套装",
    "黑色": "黑色套装",
    "暗金": "暗金套装",
    "紫金": "暗金套装",
    "氩星": "暗金套装",
}

# father name → 补全 cnName 映射表
# 部分套装 father 标签在 XML 中缺少 cnName，在此手动补全
SUIT_NAME_MAP = {
    "normalEquip": "白色超人",
    "superMan": "蓝色超人",
    "footballPlayer": "勇气橄榄",
    "greenFootballPlayer": "幻想橄榄",
    "cityBoy": "红刘海",
    "blueWaist": "白刘海",
}
