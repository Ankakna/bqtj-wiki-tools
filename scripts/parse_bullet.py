"""
爆枪突击子弹（Bullet）数据处理器

从 XML 提取非武器子弹定义数据，输出 JSON + Excel。
通过检测 bodyImgRange / allImgRange 排除武器子弹，仅保留英雄技能弹、载具弹、敌弹等。
"""
from collections import defaultdict
import os
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser, ValueConverter, OutputWriter, ReportGenerator

# --- 配置 ---
XML_DIR = './xml'
OUTPUT_DIR = './data/bullet'


def is_weapon_bullet(bullet_node):
    """武器子弹以 bodyImgRange 或 allImgRange 为特征，需排除"""
    return bullet_node.find('bodyImgRange') is not None or bullet_node.find('allImgRange') is not None


def generate_summary(bullet_pool):
    """生成数据统计报告"""
    report = []
    report.append("=" * 50)
    report.append(f" 爆枪突击子弹数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 50)

    total_count = len(bullet_pool)
    report.append(f"\n[总体概况] 提取非武器子弹总数: {total_count} 个")

    report.append("\n[分类统计 (Father)]")
    father_stats = defaultdict(int)
    for data in bullet_pool.values():
        f_name = data.get('father', 'unknown')
        father_stats[f_name] += 1
    for f_name, count in sorted(father_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {f_name:20} : {count} 个")

    report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
    cn_map = defaultdict(list)
    for name, data in bullet_pool.items():
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
        report.append(f"\n 共发现 {dup_count} 组重名子弹。")

    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in bullet_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" [X]缺少中文名 (cnName) 的子弹 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" [OK]所有子弹均包含中文名。")

    final_report = "\n".join(report)
    print(final_report)
    report_path = os.path.join(OUTPUT_DIR, '处理报告.txt')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n[报告]统计报告已保存至: {report_path}")


def run_bullet_processor():
    """全自动子弹处理器：扫描 XML → 提取 father/bullet 结构（排除武器）→ JSON/Excel 输出"""
    print(f"开始全量扫描目录: {XML_DIR}")

    bullet_pool = {}
    skipped_weapons = 0

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

                    for bullet_node in father.findall('bullet'):
                        # 排除武器子弹
                        if is_weapon_bullet(bullet_node):
                            skipped_weapons += 1
                            continue

                        # 移除标签上可能与子元素冲突的属性
                        for attr in ['name', 'cnName']:
                            if attr in bullet_node.attrib:
                                del bullet_node.attrib[attr]

                        bullet_data = XmlParser.to_dict(bullet_node)
                        if not bullet_data or 'name' not in bullet_data:
                            continue

                        bullet_data.update(father_attrs)
                        bullet_data = ValueConverter.prepare_output(bullet_data, "爆枪突击", "bullet")
                        bullet_pool[bullet_data['name']] = bullet_data

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    print(f"\n[提取] 共提取 {len(bullet_pool)} 个非武器子弹（跳过 {skipped_weapons} 个武器子弹）")

    # 生成报告
    generate_summary(bullet_pool)

    # --- 保存 JSON + Excel ---
    OutputWriter.write(bullet_pool, OUTPUT_DIR, 'Bullet', cn_label='子弹')
    print(f"\n处理完成！提取非武器子弹总数: {len(bullet_pool)}")


if __name__ == '__main__':
    run_bullet_processor()
