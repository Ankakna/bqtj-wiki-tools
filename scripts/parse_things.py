from collections import defaultdict
import os
import json
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser, ValueConverter

# --- 配置 ---
XML_DIR = './xml'
JSON_OUT = './data/things/json'
EXCEL_NAME = f'./data/things/物品数据更新_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
REPORT_OUT = './data/things/处理报告.txt'

# Things 特有的 gift 标签字段映射
GIFT_KEYS = ["type", "name", "num", "color", "lv", "childType", "numExtra", "tipB", "dropName"]


def clean_description(text):
    """清理 description 文本，移除多余换行和首尾空格"""
    if not text:
        return ""
    return "".join([line.strip() for line in text.strip().split('\n') if line.strip()])


def parse_gift_element(element):
    """
    解析 gift 标签的内容和属性。
    """
    obj = {}

    if element.attrib:
        for k, v in element.attrib.items():
            obj[k] = ValueConverter.to_smart_value(v, k)

    if element.text and element.text.strip():
        parts = element.text.strip().split(';')
        for i, part in enumerate(parts):
            if i < len(GIFT_KEYS) and part:
                key = GIFT_KEYS[i]
                obj[key] = ValueConverter.to_smart_value(part, key)
    return obj


def process_element(element):
    """
    通用函数，处理 XML 元素（things 的子标签）。
    """
    # 只有属性的标签 -> 对象
    if element.attrib and not element.text and not len(element):
        return {k: ValueConverter.to_smart_value(v, k) for k, v in element.attrib.items()}

    # 同时有属性和文本 -> 对象 + value
    if element.attrib:
        obj = {k: ValueConverter.to_smart_value(v, k) for k, v in element.attrib.items()}
        if element.text and element.text.strip():
            obj['value'] = ValueConverter.to_smart_value(element.text.strip(), element.tag)
        return obj

    # 只有文本的标签 -> 值
    if element.text and element.text.strip():
        text = element.text.strip()
        if element.tag == 'description':
            return clean_description(text)
        return ValueConverter.to_smart_value(text, element.tag)

    return None


def parse_things_node(things_node, father_attrs):
    """
    解析单个 things 节点，返回物品数据字典。
    """
    item_obj = {}

    # 注入父节点属性
    item_obj.update(father_attrs)

    # 处理 things 自身的属性
    if things_node.attrib:
        for k, v in things_node.attrib.items():
            item_obj[k] = ValueConverter.to_smart_value(v, k)

    # 处理子节点
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

    # 将子节点合并到 item_obj
    for tag, values in children_dict.items():
        if len(values) > 1:
            item_obj[tag] = values
        elif len(values) == 1:
            # gift 标签始终作为列表保留
            if tag in ['gift']:
                item_obj[tag] = values
            else:
                item_obj[tag] = values[0]

    return item_obj


def generate_summary(things_pool):
    """生成数据统计报告"""
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击物品数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)

    # 总体统计
    total_count = len(things_pool)
    report.append(f"\n[总体概况] 提取物品总数: {total_count} 个")

    # 按 father 分类统计
    report.append("\n[分类统计 (Father)]")
    father_stats = defaultdict(int)
    for data in things_pool.values():
        f_name = data.get('father', 'unknown')
        father_stats[f_name] += 1

    for f_name, count in sorted(father_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {f_name:20} : {count} 个")

    # 重名检测
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

    # 关键字段缺失检测
    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in things_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" [X] 缺少中文名 (cnName) 的物品 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" [OK] 所有物品均包含中文名。")

    # 输出到终端和文件
    final_report = "\n".join(report)
    print(final_report)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告] 详细统计报告已保存至: {REPORT_OUT}")


def run_things_processor():
    """
    全自动物品处理器。
    逻辑：扫描所有 XML -> 寻找 father/things 结构 -> 提取数据并记录其父节点名称。
    """
    print(f"开始全量扫描目录: {XML_DIR}")
    os.makedirs(JSON_OUT, exist_ok=True)

    # 使用字典存储，name 作为 key，确保同名物品只保留一份（或最后一份）
    things_pool = {}

    for root, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'):
                continue

            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    clean_xml = XmlCleaner.clean(f.read())

                root_el = ET.fromstring(clean_xml)

                # 寻找所有 father 节点
                for father in root_el.findall('.//father'):
                    father_name = father.attrib.get('name')
                    if not father_name or father_name == "parts":
                        continue

                    # 获取父节点属性
                    father_attrs = {}
                    for k, v in father.attrib.items():
                        if k == 'name':
                            father_attrs['father'] = v
                        elif k == 'cnName':
                            father_attrs['fatherCnName'] = v
                        else:
                            father_attrs[k] = ValueConverter.to_smart_value(v, k)

                    # 遍历该 father 下的所有 things
                    for things_node in father.findall('things'):
                        # 解析 things 节点
                        things_data = parse_things_node(things_node, father_attrs)

                        if not things_data or 'name' not in things_data:
                            continue

                        things_data = ValueConverter.prepare_output(things_data, "爆枪突击", "things")

                        # 存入池中，以英文 name 为唯一键
                        things_pool[things_data['name']] = things_data

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    # 生成统计报告
    generate_summary(things_pool)

    # --- 统一保存 ---
    excel_data = []
    print(f"正在写入 {len(things_pool)} 个独立 JSON 文件...")

    for things_name, data in things_pool.items():
        # 保存为单 JSON
        file_path = os.path.join(JSON_OUT, f"{things_name}.json")
        with open(file_path, 'w', encoding='utf-8') as j:
            json.dump(data, j, ensure_ascii=False, indent=2)

        # 准备 Excel 更新表
        excel_data.append({
            "PageName": f"Data:Things/{things_name}.json",
            "Content": json.dumps(data, ensure_ascii=False)
        })

    # 保存 Excel
    if excel_data:
        df = pd.DataFrame(excel_data)
        df.to_excel(EXCEL_NAME, index=False, header=False)
        print(f"处理完成！提取物品总数: {len(things_pool)}")
        print(f"Excel 更新表已生成: {EXCEL_NAME}")


if __name__ == '__main__':
    run_things_processor()
