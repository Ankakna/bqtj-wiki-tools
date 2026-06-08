"""
爆枪突击零件（Parts）数据处理器

从 *_XMLOut_partsClass.bin 提取零件数据，按零件名分组输出独立 JSON。
同名的不同等级零件（如 shockParts_1 / shockParts_2）合并为同一个文件。
"""
import os
import re
import ast
import json
import glob as glob_module
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from collections import defaultdict
from core import XmlCleaner, ValueConverter

# --- 配置 ---
XML_DIR = './xml'
OUTPUT_DIR = './data/parts'
REPORT_OUT = './data/parts/处理报告.txt'


def parse_o_attr(value):
    """解析 o 属性中的 Python 字典字面量"""
    if not value or not value.strip():
        return {}
    try:
        return ast.literal_eval(value.strip())
    except (ValueError, SyntaxError):
        return {}


def parse_things_node(things_node):
    """解析单个 <things> 节点"""
    item = {}

    # things 标签自身属性
    for k, v in things_node.attrib.items():
        if k == 'o':
            item['o'] = parse_o_attr(v)
        elif k == 'cnName':
            # 优先级低于子元素 <cnName>，先暂存
            item['_attrCnName'] = v
        else:
            item[k] = ValueConverter.to_smart_value(v, k)

    # 子元素
    for child in things_node:
        tag = child.tag
        text = child.text.strip() if child.text else ''
        if tag == 'name':
            item['name'] = text
        elif tag == 'cnName':
            item['cnName'] = text
        elif tag == 'baseLabel':
            item['baseLabel'] = text
        elif tag == 'description':
            item['description'] = text
        else:
            item[tag] = ValueConverter.to_smart_value(text, tag)

    # 如果没有子元素 cnName，用标签 cnName
    if 'cnName' not in item:
        item['cnName'] = item.pop('_attrCnName', '')
    else:
        item.pop('_attrCnName', None)

    # 默认 itemsLevel = 1
    if 'itemsLevel' not in item:
        item['itemsLevel'] = 1

    return item


def get_group_key(name):
    """从 name 中提取分组键：去掉尾部的 _数字 后缀"""
    return re.sub(r'_\d+$', '', name)


def run_parts_processor():
    """全自动零件处理器：提取 → 按 name 分组 → JSON + Excel"""
    # 按文件名匹配 partsClass，兼容版本号前缀变动
    xml_files = glob_module.glob(os.path.join(XML_DIR, '*partsClass*'))

    XML_FILE = xml_files[0]
    print(f"开始处理零件数据: {XML_FILE}")

    with open(XML_FILE, 'r', encoding='utf-8') as f:
        clean_xml = XmlCleaner.clean(f.read())

    root_el = ET.fromstring(clean_xml)

    # 按 name（去 _N 后缀）分组
    groups = defaultdict(list)

    for father in root_el.findall('.//father'):
        if father.get('name') != 'parts':
            continue
        for things_node in father.findall('things'):
            item = parse_things_node(things_node)
            if not item or 'name' not in item:
                continue
            group_key = get_group_key(item['name'])
            groups[group_key].append(item)

    print(f"[提取] 共提取 {sum(len(v) for v in groups.values())} 个零件条目，{len(groups)} 个 baseLabel 分组")

    # --- 构建分组数据 ---
    parts_pool = {}
    for group_key, items in groups.items():
        first = items[0]
        group_data = {
            "game": "爆枪突击",
            "moduleType": "parts",
            "name": group_key,
            "cnName": first.get('cnName', ''),
            "baseLabel": group_key,
            "objType": first.get('objType', ''),
        }
        # 收集共有属性（取第一个非空值）
        for key in ('maxLevel', 'skillArr', 'iconUrl', 'o', 'description'):
            for item in items:
                if key in item and item[key]:
                    group_data[key] = item[key]
                    break

        # 按 itemsLevel 排序
        items_sorted = sorted(items, key=lambda x: x.get('itemsLevel', 1))
        group_data['items'] = [{k: v for k, v in it.items()
                                if k not in ('baseLabel', '_attrCnName')}
                               for it in items_sorted]

        parts_pool[group_key] = group_data

    # --- 保存独立 JSON ---
    json_dir = os.path.join(OUTPUT_DIR, 'json')
    os.makedirs(json_dir, exist_ok=True)
    for group_key, data in parts_pool.items():
        file_path = os.path.join(json_dir, f"{group_key}.json")
        ordered = {}
        # 置顶键
        for k in ['game', 'moduleType', 'name', 'cnName', 'baseLabel', 'objType', 'maxLevel']:
            if k in data:
                ordered[k] = data[k]
        for k, v in data.items():
            if k not in ordered:
                ordered[k] = v
        with open(file_path, 'w', encoding='utf-8') as j:
            json.dump(ordered, j, ensure_ascii=False, indent=2)
    print(f"独立 JSON: {json_dir}/ ({len(parts_pool)} 个文件)")

    # --- 保存 Excel ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    EXCEL_NAME = f'{OUTPUT_DIR}/零件数据全量更新_{timestamp}.xlsx'

    excel_data = []
    for group_key, data in parts_pool.items():
        excel_data.append({
            "PageName": f"Data:Part/{group_key}.json",
            "Content": json.dumps(data, ensure_ascii=False)
        })

    pd.DataFrame(excel_data).to_excel(EXCEL_NAME, index=False, header=False)
    print(f"Excel: {EXCEL_NAME} ({len(excel_data)} 行)")

    # --- 生成 PartsItemData（精简查询 JSON） ---
    item_data = []
    for group_key, data in parts_pool.items():
        entry = {}
        for k in ('name', 'cnName', 'iconUrl'):
            val = data.get(k)
            if val is not None and val != '':
                entry[k] = val
        item_data.append(entry)

    item_json_path = os.path.join(OUTPUT_DIR, 'PartsItemData.json')
    with open(item_json_path, 'w', encoding='utf-8') as f:
        json.dump(item_data, f, ensure_ascii=False, indent=2)
    print(f"PartsItemData JSON: {item_json_path} ({len(item_data)} 条)")

    # 追加 PartsItemData 到 Excel
    existing_df = pd.read_excel(EXCEL_NAME, header=None)
    new_row = pd.DataFrame([{
        0: "Data:PartsItemData.json",
        1: json.dumps(item_data, ensure_ascii=False)
    }])
    pd.concat([existing_df, new_row], ignore_index=True).to_excel(EXCEL_NAME, index=False, header=False)

    # --- 生成报告 ---
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击零件数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)
    report.append(f"\n[总体概况] 提取零件分组: {len(parts_pool)} 个")
    report.append(f"           零件条目总数: {sum(len(v.get('items', [])) for v in parts_pool.values())} 个")

    obj_stats = defaultdict(int)
    for data in parts_pool.values():
        obj_stats[data.get('objType', 'unknown')] += 1
    report.append("\n[分类统计 (objType)]")
    for t, c in sorted(obj_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {t:12} : {c} 个")

    multi_level = [(n, d) for n, d in parts_pool.items() if len(d.get('items', [])) > 1]
    report.append(f"\n[多等级零件] 共 {len(multi_level)} 组")
    for n, d in multi_level:
        levels = [it.get('itemsLevel', '?') for it in d['items']]
        report.append(f" - {n} ({d.get('cnName','')}) : {len(d['items'])} 级 [{', '.join(str(l) for l in levels)}]")

    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in parts_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" [X] 缺少中文名的零件 ({len(missing_cn)}个): {', '.join(missing_cn)}")
    else:
        report.append(" [OK] 所有零件均包含中文名。")

    missing_icon = [n for n, d in parts_pool.items() if not d.get('iconUrl')]
    if missing_icon:
        report.append(f" [X] 缺少 iconUrl 的零件 ({len(missing_icon)}个): {', '.join(missing_icon)}")
    else:
        report.append(" [OK] 所有零件均包含 iconUrl。")

    final_report = "\n".join(report)
    print(final_report)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告] 统计报告已保存至: {REPORT_OUT}")
    print(f"\n处理完成！提取零件分组: {len(parts_pool)}")


if __name__ == '__main__':
    run_parts_processor()
