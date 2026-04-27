# 技能 father → Wiki 显示分类 映射表
# 与 Wiki 端 Module:SkillQuery 中的 skillTypeMap 保持一致
# 用途：重名检测时，只有同一显示分类下出现重名才算真正冲突
#       （跨分类的同名技能在 Wiki 上通过分类后缀自然区分）

SKILL_CATEGORY_MAP = {
    "enemy": "敌方技能",
    "enemySuper": "敌方技能",
    "enemySkill": "敌方技能",
    "enemySkillLink": "敌方技能",
    "noEnemySuper": "敌方技能",
    "otherEnemy": "敌方技能",
    "snake": "敌方技能",
    "xiaoMei": "敌方技能",

    "godArmsSkill": "武器技能",
    "godArmsSkill_link": "武器技能",
    "armsSkill": "武器技能",

    "demonSkill": "修罗技能",

    "heroSkill": "英雄技能",
    "heroSkillLink": "英雄技能",

    "task": "任务技能",

    "space": "太空技能",
    "ore": "太空技能",
    "craft": "太空技能",
    "friable": "太空技能",

    "loveSkill": "好感技能",

    "deviceSkill": "装置技能",
    "deviceSkill_link": "装置技能",

    "petBodySkill": "尸宠技能",
    "petSkill": "尸宠技能",

    "vehicleSkill": "载具技能",
    "vehicle": "载具技能",
    "vehicleNormal": "载具技能",
    "vehicleSkillLink": "载具技能",

    "fashion": "时装技能",
    "fashionSkill": "时装技能",

    "deathArms": "肉鸽技能",
    "deathRole": "肉鸽技能",
    "death": "肉鸽技能",
    "deathRoleOther": "肉鸽技能",

    "unionSkill": "军队技能",

    "outfitSkill": "套件技能",

    "purgoldEquip": "装备技能",
    "headSkill": "装备技能",
    "coatSkill": "装备技能",
    "jewelry": "饰品技能",
    "equipSkill_link": "装备技能",

    "weaponSkill": "副手技能",

    "thingsEffect": "其他效果",
    "dropEffect": "其他效果",
    "drop": "其他效果",

    "partsSkill": "零件技能",

    "nightmare": "敏感技能",

    "peakSkill": "巅峰技能",

    "shield": "护盾技能",

    "forest": "其他技能",
    "unknown": "其他技能",
    "other": "其他技能",
    "food": "其他技能",
    "we": "其他技能",
    "normal": "测试技能",
    "sceneSkill": "其他技能",
}
