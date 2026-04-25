"""
Things 数据补丁脚本

功能：在 parse_things.py 生成的数据基础上，通过 Arms 数据进行水合补全。
补全范围（按需扩展）：
    - 黑色/暗金/紫金/氩金武器碎片：补全 smeltD、btnList、iconUrl 等
    - 稀有武器碎片：补全描述、smeltD 等

注意：
    - 本脚本作为后处理步骤运行，需要先有 parse_things.py 的输出
    - 只补全到与其他 things 相同完整度，不做完全水合
"""

import os
import json
import glob
import datetime
from typing import Dict, Any, Optional
import pandas as pd
from core import ValueConverter

# --- 配置 ---
THINGS_JSON_DIR = './data/things/json'
ARMS_JSON_DIR = './data/arms/json'
PATCHED_SUFFIX = '_patched'

# 武器颜色等级映射
COLOR_PRIORITY = {
    "rare": 1,      # 红武稀有碎片
    "black": 2,     # 黑武碎片
    "darkgold": 3,  # 暗金碎片
    "purgold": 4,   # 紫金碎片
    "yagold": 5,    # 氩金碎片
}

# Smelt 配置
def get_smelt_config(items_level: int, color: str) -> Dict[str, Any]:
    """
    根据物品等级和颜色返回 smeltD 配置
    """
    config = {
        "type": "armsChip",
        "grade": 1,
        "price": 2,
        "maxNum": None,
        "addType": None
    }

    if items_level < 86:
        config["price"] = 2
        config["grade"] = 1
    elif items_level < 91:
        config["price"] = 10
        config["grade"] = 2
        config["maxNum"] = 1
        config["addType"] = "armsEquip"
    else:
        config["price"] = 1

    # 90级以上或暗金/更高颜色，grade = -1
    if items_level >= 90 or color in ["darkgold", "purgold", "yagold"]:
        config["grade"] = -1

    return config


def load_arms_data() -> Dict[str, Dict[str, Any]]:
    """
    加载武器数据，按名称索引
    返回: {weapon_name: arms_data}
    """
    arms_index = {}

    if not os.path.exists(ARMS_JSON_DIR):
        print(f"[!] 武器数据目录不存在: {ARMS_JSON_DIR}")
        print("    请先运行 parse_arms.py 生成武器数据")
        return arms_index

    for json_file in glob.glob(os.path.join(ARMS_JSON_DIR, '*.json')):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                name = data.get('name')
                if name:
                    arms_index[name] = data
        except Exception as e:
            print(f"[!] 加载武器文件失败 {json_file}: {e}")

    print(f"[OK] 已加载 {len(arms_index)} 个武器定义")
    return arms_index


def load_things_data() -> Dict[str, Dict[str, Any]]:
    """
    加载 things 数据，按名称索引
    """
    things_index = {}

    if not os.path.exists(THINGS_JSON_DIR):
        print(f"[!] Things 数据目录不存在: {THINGS_JSON_DIR}")
        print("    请先运行 parse_things.py 生成基础数据")
        return things_index

    for json_file in glob.glob(os.path.join(THINGS_JSON_DIR, '*.json')):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                name = data.get('name')
                if name:
                    things_index[name] = {
                        'data': data,
                        'file': json_file
                    }
        except Exception as e:
            print(f"[!] 加载 things 文件失败 {json_file}: {e}")

    print(f"[OK] 已加载 {len(things_index)} 个 things 定义")
    return things_index


def is_weapon_chip(thing_data: Dict) -> tuple[bool, Optional[str]]:
    """
    判断是否为武器碎片，并返回对应武器名称

    策略：
    1. 检查 thing 的 name 是否直接匹配武器名（如 rifleHornet）
    2. 检查 cnName 是否以 "碎片" 或 "稀有碎片" 结尾

    返回: (is_chip, weapon_name)
    """
    name = thing_data.get('name', '')
    cn_name = thing_data.get('cnName', '')
    father = thing_data.get('father', '')

    # father 为 blackChip/rareChip 等碎片类型的
    if father not in ['blackChip', 'rareChip']:
        return False, None

    # 稀有碎片的 cnName 以 "稀有碎片" 结尾
    if father == 'rareChip' and cn_name.endswith('稀有碎片'):
        # 提取武器名称：xxx稀有碎片 -> xxx
        weapon_cn = cn_name[:-4]  # 去掉 "稀有碎片"
        return True, name  # 对于稀有碎片，name 就是武器名

    # 黑色碎片的直接对应武器
    if father == 'blackChip':
        # 检查 name 是否就是武器名（没有其他后缀）
        return True, name

    return False, None


def patch_black_weapon_chip(thing_data: Dict, arms_data: Dict) -> bool:
    """
    修补黑色武器碎片数据

    返回: 是否进行了修补
    """
    name = thing_data.get('name')

    # 查找对应武器数据
    if name not in arms_data:
        return False

    arm = arms_data[name]

    # 获取武器属性
    compose_lv = arm.get('composeLv', 0)
    color = arm.get('color', '')

    # 只处理有合成等级的武器
    if compose_lv <= 0:
        return False

    # 补全 secType
    thing_data['secType'] = 'arms'

    # 补全 itemsLevel
    thing_data['itemsLevel'] = compose_lv

    # 补全 iconUrl（如果不存在）
    if not thing_data.get('iconUrl'):
        thing_data['iconUrl'] = f"ThingsIcon/{name}"

    # 补全 smeltD
    smelt_config = get_smelt_config(compose_lv, color)

    # 如果已有 smeltD，合并而不是覆盖
    existing_smelt = thing_data.get('smeltD', {})
    if isinstance(existing_smelt, dict):
        # 保留已有字段，补充缺失字段
        for key, value in smelt_config.items():
            if key not in existing_smelt or existing_smelt[key] is None:
                existing_smelt[key] = value
        thing_data['smeltD'] = existing_smelt
    else:
        thing_data['smeltD'] = smelt_config

    # 补全 btnList
    thing_data['btnList'] = ['compose']

    # 标记为已水合
    thing_data['_patched'] = True
    thing_data['_patchSource'] = 'arms'

    return True


def patch_rare_weapon_chip(thing_data: Dict, arms_data: Dict) -> bool:
    """
    修补稀有武器碎片数据

    返回: 是否进行了修补
    """
    name = thing_data.get('name')
    cn_name = thing_data.get('cnName', '')

    # 确认是稀有碎片
    if not cn_name.endswith('稀有碎片'):
        return False

    # 查找对应武器
    if name not in arms_data:
        return False

    arm = arms_data[name]

    # 检查武器是否有 haveChipB（在 AS 中是方法，这里检查是否有 chipNum > 0）
    chip_num = arm.get('chipNum', 0)
    if chip_num <= 0:
        return False

    weapon_cn_name = arm.get('cnName', '')

    # 补全 secType
    thing_data['secType'] = 'arms'

    # 补全描述（如果不存在）
    if not thing_data.get('description'):
        thing_data['description'] = f"合成{weapon_cn_name}所需物品。"

    # 补全 itemsLevel（使用武器的 rareDropLevel 或默认值）
    if 'itemsLevel' not in thing_data:
        thing_data['itemsLevel'] = arm.get('rareDropLevel', 1)

    # 补全 smeltD（稀有碎片固定配置）
    thing_data['smeltD'] = {
        "type": "armsChip",
        "grade": 1,
        "price": 10
    }

    # 补全 btnList
    thing_data['btnList'] = ['compose']

    # 补全 iconUrl
    if not thing_data.get('iconUrl'):
        thing_data['iconUrl'] = f"ThingsIcon/{name}"

    # 标记为已水合
    thing_data['_patched'] = True
    thing_data['_patchSource'] = 'arms_rare'

    return True


def get_rare_chip_template(things_index: Dict) -> Dict[str, Any]:
    """
    获取 rareChip 模板数据
    用于生成新的稀有武器碎片时作为基础
    """
    if 'rareChip' in things_index:
        return things_index['rareChip']['data'].copy()
    # 如果没有模板，返回基础结构
    return {
        'father': 'rareChip',
        'fatherCnName': '稀有碎片',
        'hideB': True,
        'addDropDefineB': True,
    }


def generate_rare_chips(things_index: Dict, arms_data: Dict) -> int:
    """
    生成缺失的稀有武器碎片

    根据 AS 源码逻辑：
    - 遍历所有武器，找到 chipNum > 0 的武器
    - 从 rareChip 模板复制属性
    - 生成新的稀有碎片

    返回: 生成的碎片数量
    """
    # 获取模板
    template = get_rare_chip_template(things_index)

    generated = 0

    for arm_name, arm_data in arms_data.items():
        # 检查是否有碎片（AS: haveChipB() -> chipNum > 0）
        chip_num = arm_data.get('chipNum', 0)
        if chip_num <= 0:
            continue

        # 检查是否已存在对应的稀有碎片
        if arm_name in things_index:
            continue

        # 获取武器信息
        weapon_cn_name = arm_data.get('cnName', '')
        rare_drop_level = arm_data.get('rareDropLevel', 1)

        # 创建新的稀有碎片
        rare_chip = template.copy()
        rare_chip.update({
            'name': arm_name,
            'cnName': f'{weapon_cn_name}稀有碎片',
            'secType': 'arms',
            'description': f'合成{weapon_cn_name}所需物品。',
            'itemsLevel': rare_drop_level,
            'iconUrl': f'ThingsIcon/{arm_name}',
            'smeltD': {
                'type': 'armsChip',
                'grade': 1,
                'price': 10
            },
            'btnList': ['compose'],
            '_generated': True,
            '_patchSource': 'arms_rare_generated'
        })

        # 添加到索引
        things_index[arm_name] = {
            'data': rare_chip,
            'file': os.path.join(THINGS_JSON_DIR, f'{arm_name}.json')
        }

        generated += 1
        print(f"  [稀有碎片/生成] {arm_name} ({rare_chip['cnName']})")

    return generated


def run_patch():
    """
    主流程：加载数据、匹配、修补、保存
    """
    print("=" * 50)
    print(" Things 数据补丁工具")
    print("=" * 50)

    # 加载武器数据
    print("\n[1/6] 加载武器数据...")
    arms_data = load_arms_data()
    if not arms_data:
        print("[!] 无法加载武器数据，补丁中止")
        return

    # 加载 things 数据
    print("\n[2/6] 加载 Things 数据...")
    things_index = load_things_data()
    if not things_index:
        print("[!] 无法加载 Things 数据，补丁中止")
        return

    # 生成缺失的稀有碎片
    print("\n[3/6] 生成缺失的稀有武器碎片...")
    generated_count = generate_rare_chips(things_index, arms_data)
    print(f"[OK] 生成了 {generated_count} 个稀有碎片")

    # 匹配并修补
    print("\n[4/6] 应用补丁...")

    patch_stats = {
        'black_weapon_chips': 0,
        'rare_weapon_chips': 0,
        'generated': generated_count,
        'skipped': 0,
        'errors': 0
    }

    for thing_name, thing_info in things_index.items():
        thing_data = thing_info['data']
        file_path = thing_info['file']

        try:
            # 检查是否为武器碎片
            is_chip, weapon_name = is_weapon_chip(thing_data)

            if not is_chip:
                continue

            father = thing_data.get('father', '')
            patched = False

            if father == 'blackChip':
                patched = patch_black_weapon_chip(thing_data, arms_data)
                if patched:
                    patch_stats['black_weapon_chips'] += 1
                    print(f"  [黑武碎片] {thing_name} ({thing_data.get('cnName')})")

            elif father == 'rareChip':
                # 跳过多生成的（已经在上一步处理过）
                if thing_data.get('_generated'):
                    patch_stats['rare_weapon_chips'] += 1
                    continue
                patched = patch_rare_weapon_chip(thing_data, arms_data)
                if patched:
                    patch_stats['rare_weapon_chips'] += 1
                    print(f"  [稀有碎片] {thing_name} ({thing_data.get('cnName')})")

            if not patched:
                patch_stats['skipped'] += 1
                print(f"  [跳过物品] {thing_name} ({thing_data.get('cnName')})")

        except Exception as e:
            print(f"  [!] 处理 {thing_name} 时出错: {e}")
            patch_stats['errors'] += 1

    # 保存结果
    print(f"\n[5/5] 保存修补后的数据...")

    total_patched = 0
    for thing_name, thing_info in things_index.items():
        thing_data = thing_info['data']

        # 保存被修补过或新生成的文件
        if thing_data.get('_patched') or thing_data.get('_generated'):
            try:
                file_path = thing_info['file']
                thing_data = ValueConverter.prepare_output(thing_data, "爆枪突击", "things")
                thing_info['data'] = thing_data
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(thing_data, f, ensure_ascii=False, indent=2)
                total_patched += 1
            except Exception as e:
                print(f"  [!] 保存 {thing_name} 失败: {e}")

    # 生成 Excel 批量更新表
    print(f"\n[6/6] 生成 Excel 批量更新表...")
    excel_data = []
    excel_patched_count = 0

    for thing_name, thing_info in things_index.items():
        thing_data = thing_info['data']
        # 只包含被修补过或新生成的数据
        if thing_data.get('_patched') or thing_data.get('_generated'):
            excel_data.append({
                "PageName": f"Data:Things/{thing_data['name']}.json",
                "Content": json.dumps(thing_data, ensure_ascii=False)
            })
            excel_patched_count += 1

    if excel_data:
        EXCEL_OUT_DIR = './data/things'
        os.makedirs(EXCEL_OUT_DIR, exist_ok=True)
        EXCEL_NAME = f'{EXCEL_OUT_DIR}/物品数据更新_补全_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

        df = pd.DataFrame(excel_data)
        df.to_excel(EXCEL_NAME, index=False, header=False)
        print(f"  [OK] Excel 已生成: {EXCEL_NAME}")
        print(f"       包含 {excel_patched_count} 条更新记录")
    else:
        print("  [!] 没有需要更新的数据，跳过 Excel 生成")

    # 统计报告
    print("\n" + "=" * 50)
    print(" 补丁完成报告")
    print("=" * 50)
    print(f" 黑色武器碎片已修补: {patch_stats['black_weapon_chips']}")
    print(f" 稀有武器碎片已生成: {patch_stats['generated']}")
    print(f" 稀有武器碎片已修补: {patch_stats['rare_weapon_chips'] - patch_stats['generated']}")
    print(f" 跳过 (无匹配武器): {patch_stats['skipped']}")
    print(f" 错误: {patch_stats['errors']}")
    print(f" 文件已更新/生成: {total_patched}")
    if excel_data:
        print(f" Excel 更新记录: {excel_patched_count}")
    print("=" * 50)


if __name__ == '__main__':
    run_patch()
