"""
爆枪突击装备（Equip）数据处理器

从 XML 提取所有装备定义数据，输出 JSON + Excel。
支持三种 equip 形态：武器等级装备（自闭合属性）、护盾装备（自闭合属性）、载具/合体装备（含子元素）。
"""
from collections import defaultdict
import os
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, ValueConverter, OutputWriter, ReportGenerator

# --- 配置 ---
XML_DIR = './xml'
OUTPUT_DIR = './data/equip'


def process_element(element):
    """通用函数，处理 XML 叶子元素"""
    if element.attrib and not element.text and not len(element):
        return {k: ValueConverter.to_smart_value(v, k) for k, v in element.attrib.items()}
    if element.attrib:
        obj = {k: ValueConverter.to_smart_value(v, k) for k, v in element.attrib.items()}
        if element.text and element.text.strip():
            obj['value'] = ValueConverter.to_smart_value(element.text.strip(), element.tag)
        return obj
    if element.text and element.text.strip():
        text = element.text.strip()
        return ValueConverter.to_smart_value(text, element.tag)
    return None


def get_equip_key(equip_data):
    """根据装备数据确定唯一键，返回字符串或 None"""
    name_val = equip_data.get('name')
    if isinstance(name_val, str):
        return name_val
    base = equip_data.get('baseLabel')
    if isinstance(base, str):
        lv = equip_data.get('lv')
        if lv is not None:
            return f"{base}_lv{lv}"
        return base
    return None


def parse_equip_node(equip_node, father_attrs):
    """解析单个 equip 节点，返回装备数据字典"""
    item_obj = {}
    item_obj.update(father_attrs)

    # 处理 equip 标签自身属性
    if equip_node.attrib:
        for k, v in equip_node.attrib.items():
            item_obj[k] = ValueConverter.to_smart_value(v, k)

    # 处理子节点（载具装备含 <main>, <sub>, <addObjJson> 等）
    children_dict = {}
    for child in equip_node:
        tag = child.tag
        if tag not in children_dict:
            children_dict[tag] = []
        processed = process_element(child)
        if processed is not None:
            children_dict[tag].append(processed)

    # 合并子节点到 item_obj
    for tag, values in children_dict.items():
        if len(values) > 1:
            item_obj[tag] = values
        elif len(values) == 1:
            item_obj[tag] = values[0]

    return item_obj


# 等级关联字段：这些字段可能随等级变化，归入 levels 字典
LEVEL_FIELDS = {'hurtMul', 'skillArr', 'iconLabel', 'weaponUrl', 'proAddLv'}
# 元数据字段：不进入 base 也不进入 levels
META_FIELDS = {'game', 'moduleType', 'name', 'cnName', 'baseLabel', 'lv'}


def merge_weapon_levels(equip_pool):
    """将武器等级装备按 baseLabel 合并，产生 levels 结构。返回新的 equip_pool。"""
    weapon_groups = defaultdict(dict)  # baseLabel -> {lv: equip_data}
    standalone = {}

    for key, data in equip_pool.items():
        base = data.get('baseLabel')
        lv = data.get('lv')
        if isinstance(base, str) and lv is not None:
            weapon_groups[base][lv] = data
        else:
            standalone[key] = data

    merged_count = 0
    for base_label, levels_dict in weapon_groups.items():
        if not levels_dict:
            continue

        sorted_levels = sorted(levels_dict.items())
        _first_lv, base_data = sorted_levels[0]

        # 构建 base：从第一级提取固定属性（排除等级关联字段和内部元数据）
        merged = {}
        for k, v in base_data.items():
            if k not in LEVEL_FIELDS and k not in META_FIELDS:
                merged[k] = v

        # 构建 levels
        levels = {}
        for lv, lv_data in sorted_levels:
            level_entry = {}
            for k, v in lv_data.items():
                if k in LEVEL_FIELDS:
                    level_entry[k] = v
            levels[str(lv)] = level_entry

        merged['name'] = base_label
        merged['cnName'] = base_data.get('cnName', '')
        merged['levels'] = levels
        merged = ValueConverter.prepare_output(merged, "爆枪突击", "equip")

        standalone[base_label] = merged
        merged_count += 1

    print(f"[合并] 将 {sum(len(v) for v in weapon_groups.values())} 个武器等级装备合并为 {merged_count} 个")
    return standalone


def generate_summary(equip_pool):
    """生成数据统计报告"""
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击装备数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)

    total_count = len(equip_pool)
    report.append(f"\n[总体概况] 提取装备总数: {total_count} 个")

    report.append("\n[分类统计 (Father)]")
    father_stats = defaultdict(int)
    for data in equip_pool.values():
        f_name = data.get('father', 'unknown')
        father_stats[f_name] += 1
    for f_name, count in sorted(father_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {f_name:20} : {count} 个")

    report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
    cn_map = defaultdict(list)
    for name, data in equip_pool.items():
        cn = data.get('cnName') or "[缺失中文名]"
        cn_map[cn].append(name)
    dup_count = 0
    for cn, names in cn_map.items():
        if len(names) > 1:
            dup_count += 1
            report.append(f" [!]名称: {cn}")
            report.append(f"     关联ID: {', '.join(names)}")
    if dup_count == 0:
        report.append(" [OK]未发现重名冲突。")
    else:
        report.append(f"\n 共发现 {dup_count} 组重名装备。")

    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in equip_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" [X]缺少中文名 (cnName) 的装备 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" [OK]所有装备均包含中文名。")

    final_report = "\n".join(report)
    print(final_report)
    report_path = os.path.join(OUTPUT_DIR, '处理报告.txt')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告]统计报告已保存至: {report_path}")


def run_equip_processor():
    """全自动装备处理器：扫描 XML → 提取 father/equip 结构 → JSON/Excel 输出"""
    print(f"开始全量扫描目录: {XML_DIR}")

    equip_pool = {}

    for root, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'):
                continue
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    clean_xml = XmlCleaner.clean(f.read())
                root_el = ET.fromstring(clean_xml)

                for father in root_el.findall('.//father'):
                    father_name = father.get('name') or father.get('type') or 'unknown'
                    if not father_name:
                        continue

                    father_attrs = {}
                    for k, v in father.attrib.items():
                        if k == 'name':
                            father_attrs['father'] = v
                        elif k == 'cnName':
                            father_attrs['fatherCnName'] = v
                        else:
                            father_attrs[k] = ValueConverter.to_smart_value(v, k)

                    if 'father' not in father_attrs:
                        father_attrs['father'] = father_name

                    for equip_node in father.findall('equip'):
                        equip_data = parse_equip_node(equip_node, father_attrs)
                        equip_key = get_equip_key(equip_data)
                        if not equip_key:
                            continue
                        equip_data = ValueConverter.prepare_output(equip_data, "爆枪突击", "equip")
                        equip_pool[equip_key] = equip_data

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    print(f"\n[提取] 共提取 {len(equip_pool)} 个装备")

    # 合并武器等级装备
    equip_pool = merge_weapon_levels(equip_pool)

    # 生成报告
    generate_summary(equip_pool)

    # --- 保存 JSON + Excel ---
    OutputWriter.write(equip_pool, OUTPUT_DIR, 'Equip', cn_label='装备')
    print(f"\n处理完成！提取装备总数: {len(equip_pool)}")


if __name__ == '__main__':
    run_equip_processor()
