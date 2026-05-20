"""
爆枪突击角色（Body）数据处理器

从 XML 提取所有角色定义数据，输出 JSON + Excel。
支持嵌套的 <hurtArr> 攻击数据解析。
"""
from collections import defaultdict
import os
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser, ValueConverter, OutputWriter
from config import BODY_RENAME_MAP
# --- 配置 ---
XML_DIR = './xml'
OUTPUT_DIR = './data/body'


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


def parse_body_node(body_node, father_attrs):
    """解析单个 <body> 节点，返回角色数据字典"""
    item_obj = {}
    item_obj.update(father_attrs)

    # 处理 body 标签自身属性（保留 shell 等，跳过 index 属性）
    if body_node.attrib:
        for k, v in body_node.attrib.items():
            if k == 'index':
                continue
            if k == 'name':
                # body 标签的 name 属性与 cnName 子标签内容可能不一致，以 name 为准
                item_obj['cnName'] = ValueConverter.to_smart_value(v, k)
                continue
            item_obj[k] = ValueConverter.to_smart_value(v, k)

    # 处理子节点
    children_dict = {}
    for child in body_node:
        tag = child.tag
        if tag == 'cnName' and item_obj.get('cnName'):
            continue
        if tag not in children_dict:
            children_dict[tag] = []

        if tag == 'hurtArr':
            # 攻击数据容器：遍历内部 <hurt> 子元素
            for hurt_node in child.findall('hurt'):
                hurt_obj = {}
                for hurt_child in hurt_node:
                    processed = process_element(hurt_child)
                    if processed is not None:
                        if isinstance(processed, dict) and hurt_child.tag not in hurt_obj:
                            hurt_obj[hurt_child.tag] = processed
                        elif hurt_child.tag in hurt_obj:
                            existing = hurt_obj[hurt_child.tag]
                            if isinstance(existing, list):
                                existing.append(processed)
                            else:
                                hurt_obj[hurt_child.tag] = [existing, processed]
                        else:
                            hurt_obj[hurt_child.tag] = processed
                if hurt_node.attrib:
                    for k, v in hurt_node.attrib.items():
                        hurt_obj[k] = ValueConverter.to_smart_value(v, k)
                children_dict[tag].append(hurt_obj)
        else:
            processed = process_element(child)
            if processed is not None:
                children_dict[tag].append(processed)

    # 合并子节点到 item_obj
    for tag, values in children_dict.items():
        if len(values) > 1:
            item_obj[tag] = values
        elif len(values) == 1:
            if tag in ('hurtArr',):
                item_obj[tag] = values
            else:
                item_obj[tag] = values[0]

    return item_obj


def generate_summary(body_pool):
    """生成数据统计报告"""
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击角色数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)

    total_count = len(body_pool)
    report.append(f"\n[总体概况] 提取角色总数: {total_count} 个")

    report.append("\n[分类统计 (Father)]")
    father_stats = defaultdict(int)
    for data in body_pool.values():
        f_name = data.get('father', 'unknown')
        father_stats[f_name] += 1
    for f_name, count in sorted(father_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {f_name:20} : {count} 个")

    report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
    cn_map = defaultdict(list)
    for name, data in body_pool.items():
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
        report.append(f"\n 共发现 {dup_count} 组重名角色。")

    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in body_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" [X]缺少中文名 (cnName) 的角色 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" [OK]所有角色均包含中文名。")

    final_report = "\n".join(report)
    print(final_report)
    report_path = os.path.join(OUTPUT_DIR, '处理报告.txt')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告]统计报告已保存至: {report_path}")


def run_body_processor():
    """全自动角色处理器：扫描 XML → 提取 father/body 结构 → JSON/Excel 输出"""
    print(f"开始全量扫描目录: {XML_DIR}")

    body_pool = {}

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

                    # 必须有 father 字段
                    if 'father' not in father_attrs:
                        father_attrs['father'] = father_name

                    for body_node in father.findall('body'):
                        body_data = parse_body_node(body_node, father_attrs)
                        if not body_data or 'name' not in body_data:
                            continue
                        body_data = ValueConverter.prepare_output(body_data, "爆枪突击", "body")
                        body_pool[body_data['name']] = body_data

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    print(f"\n[提取] 共提取 {len(body_pool)} 个角色")

    # 尸宠单位自动添加"尸宠"前缀（father 为 pet 的单位）
    pet_prefixed = 0
    for name, data in body_pool.items():
        if data.get('father') == 'pet' and not data.get('cnName', '').startswith('尸宠'):
            data['cnName'] = '尸宠' + data['cnName']
            pet_prefixed += 1
    if pet_prefixed:
        print(f"已为 {pet_prefixed} 个尸宠单位添加\"尸宠\"前缀")

    # 应用角色重命名表
    renamed_count = 0
    for name, data in body_pool.items():
        if name in BODY_RENAME_MAP:
            data['cnName'] = BODY_RENAME_MAP[name]
            renamed_count += 1
    if renamed_count:
        print(f"已根据重命名表更新 {renamed_count} 个角色的 cnName")

    # 生成报告
    generate_summary(body_pool)

    # --- 保存 JSON + Excel ---
    OutputWriter.write(body_pool, OUTPUT_DIR, 'Body', cn_label='角色')
    print(f"\n处理完成！提取角色总数: {len(body_pool)}")



if __name__ == '__main__':
    run_body_processor()
