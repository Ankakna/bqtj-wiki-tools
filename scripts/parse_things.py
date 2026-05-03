"""
爆枪突击物品数据处理器（含补丁水合）

一步完成：XML 提取 → 武器碎片数据补全 → JSON/Excel 输出
"""
from collections import defaultdict
import os
import json
import glob
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from typing import Dict, Any
from core import XmlCleaner, XmlParser, ValueConverter

# --- 配置 ---
XML_DIR = './xml'
JSON_OUT = './data/things/json'
ARMS_JSON_DIR = './data/arms/json'
REPORT_OUT = './data/things/处理报告.txt'
EXCEL_DIR = './data/things'

# Things 特有的 gift 标签字段映射
GIFT_KEYS = ["type", "name", "num", "color", "lv", "childType", "numExtra", "tipB", "dropName"]

# Smelt 配置
def _get_smelt_config(items_level: int, color: str) -> Dict[str, Any]:
    config = {"type": "armsChip", "grade": 1, "price": 2, "maxNum": None, "addType": None}
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
    if items_level >= 90 or color in ["darkgold", "purgold", "yagold"]:
        config["grade"] = -1
    return config


def clean_description(text):
    """清理 description 文本"""
    if not text:
        return ""
    return "".join([line.strip() for line in text.strip().split('\n') if line.strip()])


def parse_gift_element(element):
    """解析 gift 标签的内容和属性"""
    obj = {}
    if element.attrib:
        for k, v in element.attrib.items():
            obj[k] = ValueConverter.to_smart_value(v, k)
    if element.text and element.text.strip():
        parts = element.text.strip().split(';')
        for i, part in enumerate(parts):
            if i < len(GIFT_KEYS) and part:
                obj[GIFT_KEYS[i]] = ValueConverter.to_smart_value(part, GIFT_KEYS[i])
    return obj


def process_element(element):
    """通用函数，处理 XML 元素"""
    if element.attrib and not element.text and not len(element):
        return {k: ValueConverter.to_smart_value(v, k) for k, v in element.attrib.items()}
    if element.attrib:
        obj = {k: ValueConverter.to_smart_value(v, k) for k, v in element.attrib.items()}
        if element.text and element.text.strip():
            obj['value'] = ValueConverter.to_smart_value(element.text.strip(), element.tag)
        return obj
    if element.text and element.text.strip():
        text = element.text.strip()
        if element.tag == 'description':
            return clean_description(text)
        return ValueConverter.to_smart_value(text, element.tag)
    return None


def parse_things_node(things_node, father_attrs):
    """解析单个 things 节点"""
    item_obj = {}
    item_obj.update(father_attrs)
    if things_node.attrib:
        for k, v in things_node.attrib.items():
            item_obj[k] = ValueConverter.to_smart_value(v, k)
    children_dict = {}
    for child in things_node:
        tag = child.tag
        if tag not in children_dict:
            children_dict[tag] = []
        if tag == 'gift':
            children_dict[tag].append(parse_gift_element(child))
        else:
            processed_value = process_element(child)
            if processed_value is not None:
                children_dict[tag].append(processed_value)
    for tag, values in children_dict.items():
        if len(values) > 1:
            item_obj[tag] = values
        elif len(values) == 1:
            if tag in ['gift']:
                item_obj[tag] = values
            else:
                item_obj[tag] = values[0]
    return item_obj


# ============================================================
#  补丁阶段：武器碎片数据水合
# ============================================================

def _load_arms_data() -> Dict[str, Dict[str, Any]]:
    """加载武器数据，按名称索引"""
    arms_index = {}
    if not os.path.exists(ARMS_JSON_DIR):
        print(f"\n[补丁] 武器数据目录不存在: {ARMS_JSON_DIR}，跳过补丁阶段")
        print("       请先运行 parse_arms.py 生成武器数据")
        return arms_index
    for json_file in glob.glob(os.path.join(ARMS_JSON_DIR, '*.json')):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                name = data.get('name')
                if name:
                    arms_index[name] = data
        except Exception as e:
            print(f"[补丁] 加载武器文件失败 {json_file}: {e}")
    print(f"[补丁] 已加载 {len(arms_index)} 个武器定义")
    return arms_index


def _patch_black_chip(thing_data: dict, arms_data: dict) -> bool:
    """修补黑色武器碎片数据"""
    name = thing_data.get('name')
    if name not in arms_data:
        return False
    arm = arms_data[name]
    compose_lv = arm.get('composeLv', 0)
    if compose_lv <= 0:
        return False

    thing_data['secType'] = 'arms'
    thing_data['itemsLevel'] = compose_lv
    if not thing_data.get('iconUrl'):
        thing_data['iconUrl'] = f"ThingsIcon/{name}"

    smelt_config = _get_smelt_config(compose_lv, arm.get('color', ''))
    existing_smelt = thing_data.get('smeltD', {})
    if isinstance(existing_smelt, dict):
        for key, value in smelt_config.items():
            if key not in existing_smelt or existing_smelt[key] is None:
                existing_smelt[key] = value
        thing_data['smeltD'] = existing_smelt
    else:
        thing_data['smeltD'] = smelt_config

    thing_data['btnList'] = ['compose']
    thing_data['_patched'] = True
    return True


def _patch_rare_chip(thing_data: dict, arms_data: dict) -> bool:
    """修补稀有武器碎片数据"""
    name = thing_data.get('name')
    cn_name = thing_data.get('cnName', '')
    if not cn_name.endswith('稀有碎片'):
        return False
    if name not in arms_data:
        return False
    arm = arms_data[name]
    if arm.get('chipNum', 0) <= 0:
        return False

    thing_data['secType'] = 'arms'
    if not thing_data.get('description'):
        thing_data['description'] = f"合成{arm.get('cnName', '')}所需物品。"
    if 'itemsLevel' not in thing_data:
        thing_data['itemsLevel'] = arm.get('rareDropLevel', 1)
    thing_data['smeltD'] = {"type": "armsChip", "grade": 1, "price": 10}
    thing_data['btnList'] = ['compose']
    if not thing_data.get('iconUrl'):
        thing_data['iconUrl'] = f"ThingsIcon/{name}"
    thing_data['_patched'] = True
    return True


def _generate_missing_rare_chips(things_pool: dict, arms_data: dict) -> int:
    """为 chipNum > 0 但尚无 things 条目的武器生成稀有碎片"""
    # 获取 rareChip 模板
    template = things_pool.get('rareChip', {}).copy() if 'rareChip' in things_pool else {
        'father': 'rareChip', 'fatherCnName': '稀有碎片', 'hideB': True, 'addDropDefineB': True,
    }

    generated = 0
    for arm_name, arm_data in arms_data.items():
        if arm_data.get('chipNum', 0) <= 0:
            continue
        if arm_name in things_pool:
            continue

        rare_chip = template.copy()
        weapon_cn = arm_data.get('cnName', '')
        rare_chip.update({
            'name': arm_name,
            'cnName': f'{weapon_cn}稀有碎片',
            'secType': 'arms',
            'description': f'合成{weapon_cn}所需物品。',
            'itemsLevel': arm_data.get('rareDropLevel', 1),
            'iconUrl': f'ThingsIcon/{arm_name}',
            'smeltD': {'type': 'armsChip', 'grade': 1, 'price': 10},
            'btnList': ['compose'],
            '_generated': True,
        })
        things_pool[arm_name] = rare_chip
        generated += 1
        print(f"  [补丁/生成] 稀有碎片: {arm_name} ({rare_chip['cnName']})")

    return generated


def _apply_patches(things_pool: dict) -> dict:
    """对 things_pool 执行武器碎片补丁，返回统计信息"""
    arms_data = _load_arms_data()
    if not arms_data:
        return {}

    # 生成缺失的稀有碎片
    generated = _generate_missing_rare_chips(things_pool, arms_data)

    stats = {'black_chips': 0, 'rare_chips': 0, 'generated': generated, 'skipped': 0, 'errors': 0}
    for thing_name, thing_data in things_pool.items():
        try:
            father = thing_data.get('father', '')
            if father not in ['blackChip', 'rareChip']:
                continue

            if father == 'blackChip':
                if _patch_black_chip(thing_data, arms_data):
                    stats['black_chips'] += 1
                    print(f"  [补丁/黑武碎片] {thing_name} ({thing_data.get('cnName')})")
                else:
                    stats['skipped'] += 1
            elif father == 'rareChip':
                if thing_data.get('_generated'):
                    stats['rare_chips'] += 1
                    continue
                if _patch_rare_chip(thing_data, arms_data):
                    stats['rare_chips'] += 1
                    print(f"  [补丁/稀有碎片] {thing_name} ({thing_data.get('cnName')})")
                else:
                    stats['skipped'] += 1
        except Exception as e:
            print(f"  [!] 处理 {thing_name} 时出错: {e}")
            stats['errors'] += 1

    return stats


# ============================================================
#  报告与输出
# ============================================================

def generate_summary(things_pool, patch_stats=None):
    """生成数据统计报告"""
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击物品数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)

    total_count = len(things_pool)
    report.append(f"\n[总体概况] 提取物品总数: {total_count} 个")

    report.append("\n[分类统计 (Father)]")
    father_stats = defaultdict(int)
    for data in things_pool.values():
        f_name = data.get('father', 'unknown')
        father_stats[f_name] += 1
    for f_name, count in sorted(father_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {f_name:20} : {count} 个")

    report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
    cn_map = defaultdict(list)
    for name, data in things_pool.items():
        cn = data.get('cnName') or "[缺失中文名]"
        cn_map[cn].append(name)
    dup_count = 0
    for cn, names in cn_map.items():
        if len(names) > 1:
            dup_count += 1
            report.append(f" [!] 名称: {cn}")
            report.append(f"     关联ID: {', '.join(names)}")
    if dup_count == 0:
        report.append(" [OK] 未发现重名冲突。")
    else:
        report.append(f"\n 共发现 {dup_count} 组重名物品。")

    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in things_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" [X] 缺少中文名 (cnName) 的物品 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" [OK] 所有物品均包含中文名。")

    # 补丁统计
    if patch_stats:
        total_patched = patch_stats['black_chips'] + patch_stats['rare_chips'] + patch_stats['generated']
        report.append(f"\n[补丁水合]")
        report.append(f" 黑色武器碎片已修补: {patch_stats['black_chips']}")
        report.append(f" 稀有武器碎片已修补: {patch_stats['rare_chips'] - patch_stats['generated']}")
        report.append(f" 稀有武器碎片已生成: {patch_stats['generated']}")
        report.append(f" 跳过: {patch_stats['skipped']}")
        if patch_stats['errors']:
            report.append(f" 错误: {patch_stats['errors']}")
        report.append(f" 合计修补/生成: {total_patched}")

    final_report = "\n".join(report)
    print(final_report)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告] 统计报告已保存至: {REPORT_OUT}")


def run_things_processor():
    """全自动物品处理器：XML 提取 + 武器碎片补丁 → JSON/Excel"""

    print(f"开始全量扫描目录: {XML_DIR}")
    os.makedirs(JSON_OUT, exist_ok=True)

    # ======== Phase 1: XML 提取 ========
    print("\n--- Phase 1: XML 提取 ---")
    things_pool = {}

    for root, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'):
                continue
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    clean_xml = XmlCleaner.clean(f.read())
                root_el = ET.fromstring(clean_xml)
                for father in root_el.findall('.//father'):
                    father_name = father.attrib.get('name')
                    if not father_name or father_name == "parts":
                        continue
                    father_attrs = {}
                    for k, v in father.attrib.items():
                        if k == 'name':
                            father_attrs['father'] = v
                        elif k == 'cnName':
                            father_attrs['fatherCnName'] = v
                        else:
                            father_attrs[k] = ValueConverter.to_smart_value(v, k)
                    for things_node in father.findall('things'):
                        things_data = parse_things_node(things_node, father_attrs)
                        if not things_data or 'name' not in things_data:
                            continue
                        things_data = ValueConverter.prepare_output(things_data, "爆枪突击", "things")
                        things_pool[things_data['name']] = things_data
            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    print(f"[提取] 共提取 {len(things_pool)} 个物品")

    # ======== Phase 2: 武器碎片补丁 ========
    print("\n--- Phase 2: 武器碎片数据补丁 ---")
    patch_stats = _apply_patches(things_pool)

    # ======== Phase 3: 报告与输出 ========
    print(f"\n--- Phase 3: 保存输出 ---")
    generate_summary(things_pool, patch_stats)

    # 保存 JSON
    print(f"\n正在写入 {len(things_pool)} 个独立 JSON 文件...")
    for things_name, data in things_pool.items():
        file_path = os.path.join(JSON_OUT, f"{things_name}.json")
        # 输出前清理内部标记
        output_data = data.copy()
        output_data.pop('_generated', None)
        with open(file_path, 'w', encoding='utf-8') as j:
            json.dump(output_data, j, ensure_ascii=False, indent=2)

    # 生成 Excel（全量 + 补丁标记）
    os.makedirs(EXCEL_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    all_excel = []
    patch_excel = []

    for things_name, data in things_pool.items():
        output_data = data.copy()
        is_patched = output_data.pop('_generated', None) or output_data.pop('_patched', None)
        entry = {
            "PageName": f"Data:Things/{things_name}.json",
            "Content": json.dumps(output_data, ensure_ascii=False)
        }
        all_excel.append(entry)
        if is_patched:
            patch_excel.append(entry)

    # 全量 Excel
    if all_excel:
        EXCEL_FULL = f'{EXCEL_DIR}/物品数据全量更新_{timestamp}.xlsx'
        pd.DataFrame(all_excel).to_excel(EXCEL_FULL, index=False, header=False)
        print(f"全量 Excel 已生成: {EXCEL_FULL}")

    # 增量 Excel（仅补丁项）
    if patch_excel:
        EXCEL_PATCH = f'{EXCEL_DIR}/物品数据更新_补全_{timestamp}.xlsx'
        pd.DataFrame(patch_excel).to_excel(EXCEL_PATCH, index=False, header=False)
        print(f"补丁增量 Excel 已生成: {EXCEL_PATCH} ({len(patch_excel)} 条)")

    # 最终统计
    total_patched = patch_stats.get('black_chips', 0) + patch_stats.get('rare_chips', 0) + patch_stats.get('generated', 0)
    print(f"\n处理完成！物品总数: {len(things_pool)}，本次修补/生成: {total_patched}")


if __name__ == '__main__':
    run_things_processor()
