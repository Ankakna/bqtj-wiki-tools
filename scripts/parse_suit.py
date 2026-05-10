"""
爆枪突击套装（Suit）数据处理器

从 XML 提取所有套装定义数据，输出 JSON + Excel。
数据结构：gather → father → image（每个 father 包含最多4个部件: head/coat/pants/belt）
"""
from collections import defaultdict
import os
import json
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser, ValueConverter
from config import GATHER_SUIT_MAP, SUIT_NAME_MAP

# --- 配置 ---
XML_DIR = './xml'
JSON_OUT = './data/suit/json'
REPORT_OUT = './data/suit/处理报告.txt'
EXCEL_DIR = './data/suit'


def get_suit_category(gather_cn_name):
    """根据 gather 的 cnName 获取套装分类，返回列表格式（与武器分类一致）"""
    if not gather_cn_name:
        return ["普通套装"]
    return [GATHER_SUIT_MAP.get(gather_cn_name, "普通套装")]


def parse_suit_father(father_node, gather_cn_name, gather_range):
    """解析单个 father 节点，返回套装数据字典"""
    suit_data = {}

    # 处理 father 自身属性
    for k, v in father_node.attrib.items():
        if k == 'name':
            suit_data['name'] = v
            suit_data['father'] = v
        elif k == 'cnName':
            suit_data['fatherCnName'] = v
        else:
            suit_data[k] = ValueConverter.to_smart_value(v, k)

    if 'father' not in suit_data:
        return None

    # 如果 father 没有 cnName，先查映射表，否则用 name
    if 'fatherCnName' not in suit_data:
        suit_data['fatherCnName'] = SUIT_NAME_MAP.get(suit_data['name'], suit_data['name'])

    # 注入 gather 信息
    suit_data['gatherCnName'] = gather_cn_name or ''
    suit_data['gatherRange'] = gather_range or ''

    # 注入分类
    suit_data['category'] = get_suit_category(gather_cn_name)

    # 解析 image 子节点
    images = []
    for image_node in father_node.findall('image'):
        for attr in ['name', 'cnName']:
            if attr in image_node.attrib:
                del image_node.attrib[attr]
        image_data = XmlParser.to_dict(image_node)
        if image_data:
            # 修复 otherObjJson/addObjJson 被 ValueConverter 按逗号误拆的问题
            for key in ('otherObjJson', 'addObjJson'):
                val = image_data.get(key)
                if isinstance(val, list):
                    image_data[key] = ','.join(val)
            images.append(image_data)

    # 非套装 father（如 fashion）：image 没有 type 字段，跳过
    if not images or not any(img.get('type') in ('head', 'coat', 'pants', 'belt') for img in images):
        return None

    suit_data['image'] = images
    return suit_data


def generate_summary(suit_pool):
    """生成数据统计报告"""
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击套装数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)

    total_count = len(suit_pool)
    report.append(f"\n[总体概况] 提取套装总数: {total_count} 个")

    report.append("\n[分类统计]")
    cat_stats = defaultdict(int)
    for data in suit_pool.values():
        for cat in data.get('category', ['未分类']):
            cat_stats[cat] += 1
    for cat, count in sorted(cat_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {cat:12} : {count} 个")

    report.append("\n[部件统计]")
    part_stats = defaultdict(int)
    for data in suit_pool.values():
        part_count = len(data.get('image', []))
        part_stats[part_count] += 1
    for count, suits in sorted(part_stats.items()):
        report.append(f" - {count} 部件 : {suits} 个套装")

    report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
    cn_map = defaultdict(list)
    for name, data in suit_pool.items():
        cn = data.get('fatherCnName') or "[缺失中文名]"
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
        report.append(f"\n 共发现 {dup_count} 组重名套装。")

    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in suit_pool.items() if not d.get('fatherCnName')]
    if missing_cn:
        report.append(f" [X] 缺少中文名 (cnName) 的套装 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" [OK] 所有套装均包含中文名。")

    missing_images = [n for n, d in suit_pool.items() if not d.get('image')]
    if missing_images:
        report.append(f" [X] 缺少部件的套装 ({len(missing_images)}个):")
        report.append(f"    {', '.join(missing_images)}...")
    else:
        report.append(" [OK] 所有套装均包含至少一个部件。")

    final_report = "\n".join(report)
    print(final_report)
    os.makedirs(os.path.dirname(REPORT_OUT), exist_ok=True)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告] 统计报告已保存至: {REPORT_OUT}")


def run_suit_processor():
    """全自动套装处理器：扫描 XML → 提取 gather/father/image → JSON/Excel 输出"""
    print(f"开始全量扫描目录: {XML_DIR}")
    os.makedirs(JSON_OUT, exist_ok=True)

    suit_pool = {}
    skipped_fathers = 0

    for root_dir, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'):
                continue
            try:
                with open(os.path.join(root_dir, file), 'r', encoding='utf-8') as f:
                    clean_xml = XmlCleaner.clean(f.read())
                root_el = ET.fromstring(clean_xml)

                for gather in root_el.findall('.//gather'):
                    gather_cn = gather.get('cnName', '')
                    gather_range = gather.get('range', '')

                    for father in gather.findall('father'):
                        # 跳过没有 image 子节点的 father（如 purgoldEquip 只含 skill）
                        if father.find('image') is None:
                            skipped_fathers += 1
                            continue

                        suit_data = parse_suit_father(father, gather_cn, gather_range)
                        if not suit_data or 'name' not in suit_data:
                            continue

                        suit_data = ValueConverter.prepare_output(suit_data, "爆枪突击", "suit")
                        suit_pool[suit_data['name']] = suit_data

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    print(f"[提取] 共提取 {len(suit_pool)} 个套装（跳过 {skipped_fathers} 个非套装 father）")

    # 生成报告
    generate_summary(suit_pool)

    # --- 保存单个 JSON ---
    print(f"\n正在写入 {len(suit_pool)} 个独立 JSON 文件...")
    for suit_name, data in suit_pool.items():
        file_path = os.path.join(JSON_OUT, f"{suit_name}.json")
        with open(file_path, 'w', encoding='utf-8') as j:
            json.dump(data, j, ensure_ascii=False, indent=2)

    # --- 保存汇总 JSON ---
    os.makedirs(EXCEL_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    SUMMARY_JSON = f'{EXCEL_DIR}/套装数据汇总_{timestamp}.json'
    summary_list = list(suit_pool.values())
    with open(SUMMARY_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary_list, f, ensure_ascii=False, indent=2)
    print(f"汇总 JSON 已生成: {SUMMARY_JSON} ({len(summary_list)} 个套装)")

    # --- 保存 Excel ---
    EXCEL_NAME = f'{EXCEL_DIR}/套装数据全量更新_{timestamp}.xlsx'
    excel_data = []
    for suit_name, data in suit_pool.items():
        excel_data.append({
            "PageName": f"Data:Suit/{suit_name}.json",
            "Content": json.dumps(data, ensure_ascii=False)
        })

    if excel_data:
        pd.DataFrame(excel_data).to_excel(EXCEL_NAME, index=False, header=False)
        print(f"全量 Excel 已生成: {EXCEL_NAME}")

    print(f"\n处理完成！提取套装总数: {len(suit_pool)}")


if __name__ == '__main__':
    run_suit_processor()
