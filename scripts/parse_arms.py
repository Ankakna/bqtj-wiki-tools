import os
import json
import pandas as pd
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser, ValueConverter, OutputWriter, ReportGenerator
from config import CATEGORY_MAP, ARM_NAME_MAP

# --- 配置 ---
XML_DIR = './xml'
OUTPUT_DIR = './data/arms'

def run_arm_processor():
    '''
    武器数据处理主流程。
    扫描 XML -> 清洗数据 -> 提取武器节点 -> 挂载分类 -> 输出成果。
    '''
    print(f"开始处理武器数据...")

    arm_pool = {}

    for root, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'): continue

            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    clean_xml = XmlCleaner.clean(f.read())

                tree = ET.fromstring(clean_xml)

                for father in tree.findall('.//father'):
                    arms_type = father.attrib.get('type', 'unknown')

                    for bullet in father.findall('./bullet'):
                        if bullet.find('bodyImgRange') is None and bullet.find('allImgRange') is None: continue

                        for attr in ['index', 'name', 'cnName']:
                            if attr in bullet.attrib: del bullet.attrib[attr]

                        arm_data = XmlParser.to_dict(bullet)
                        if not arm_data or 'name' not in arm_data: continue

                        arm_data['armsType'] = arms_type
                        arm_data['category'] = CATEGORY_MAP.get(arm_data['name'], ["未分类"])

                        # 处理重名：肉鸽武器加"-肉鸽"后缀
                        cn = arm_data.get('cnName', '')
                        if 'death' in arm_data['category']:
                            arm_data['cnName'] = cn + '-肉鸽'
                        # 随机属性武器加"-随机属性武器"后缀
                        elif arm_data.get('randomPro', 0) > 0:
                            arm_data['cnName'] = cn + '-随机属性武器'

                        # 特例覆盖：强制 cnName 映射
                        if arm_data.get('name') in ARM_NAME_MAP:
                            arm_data['cnName'] = ARM_NAME_MAP[arm_data['name']]

                        arm_data = ValueConverter.prepare_output(arm_data, "爆枪突击", "arms")

                        arm_pool[arm_data['name']] = arm_data
                        print(f"  [√] 已处理: {arm_data.get('cnName', arm_data['name'])}")

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    # --- 生成报告 ---
    ReportGenerator.generate(arm_pool, OUTPUT_DIR, report_prefix='武器', group_field='armsType')

    # --- 保存输出 ---
    timestamp = OutputWriter.write(arm_pool, OUTPUT_DIR, 'Arm', cn_label='武器')

    # --- 生成 ArmsItemData（Item 模块所需的精简整合 JSON） ---
    item_fields = ['name', 'cnName', 'bodyImgRange', 'color']
    item_data = []
    for arm in arm_pool.values():
        entry = {}
        for k in item_fields:
           val = arm.get(k)
           if val is not None and val != "":
                entry[k] = val
        item_data.append(entry)

    arms_item_json = {
        "data": {
            "father": {
                "@name": "ArmsItem",
                "@cnName": "武器标签",
                "item": item_data
            }
        }
    }

    item_json_path = os.path.join(OUTPUT_DIR, 'ArmsItemData.json')
    with open(item_json_path, 'w', encoding='utf-8') as f:
        json.dump(arms_item_json, f, ensure_ascii=False, indent=2)
    print(f"ArmsItemData JSON: {item_json_path} ({len(item_data)} 条)")

    # 追加到 Excel
    excel_path = os.path.join(OUTPUT_DIR, f'武器数据更新_{timestamp}.xlsx')
    existing_df = pd.read_excel(excel_path, header=None)
    new_row = pd.DataFrame([{
        0: "Data:ArmsItemData.json",
        1: json.dumps(arms_item_json, ensure_ascii=False)
    }])
    combined_df = pd.concat([existing_df, new_row], ignore_index=True)
    combined_df.to_excel(excel_path, index=False, header=False)

    print(f"处理完成！共包含 {len(arm_pool)} 个武器定义")

if __name__ == '__main__':
    run_arm_processor()
