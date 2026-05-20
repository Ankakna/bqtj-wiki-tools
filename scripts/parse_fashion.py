"""
爆枪突击时装（Fashion）数据处理器

从 16_XMLOut_fashionClass.bin 提取所有时装定义，输出独立 JSON + Excel。
每个 <image> 是一个完整的时装条目，以 name 为唯一标识。
"""
import os
import json
import ast
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, ValueConverter
from config import normalize_fashion_cn

# --- 配置 ---
XML_FILE = './xml/16_XMLOut_fashionClass.bin'
JSON_OUT = './data/fashion/json'
EXCEL_DIR = './data/fashion'


def parse_add_obj_json(text):
    """将 Python 字典字面量（单引号）解析为真正的 dict"""
    if not text or not text.strip():
        return {}
    try:
        return ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        return text.strip()


def parse_image_node(image_node):
    """解析单个 <image> 节点，返回时装数据字典"""
    item = {}

    # 处理 image 标签自身属性
    for k, v in image_node.attrib.items():
        if k == 'name':
            item['name'] = v
        elif k == 'cnName':
            item['cnName'] = normalize_fashion_cn(v)
        else:
            item[k] = ValueConverter.to_smart_value(v, k)

    # 处理子元素
    for child in image_node:
        tag = child.tag
        text = child.text.strip() if child.text else ''
        if tag == 'addObjJson':
            parsed = ValueConverter.to_smart_value(text, tag)
            if isinstance(parsed, list):
                text = ','.join(parsed)
            elif parsed:
                text = str(parsed)
            item['addObjJson'] = parse_add_obj_json(text)
        elif tag == 'description':
            item['description'] = text
        else:
            item[tag] = ValueConverter.to_smart_value(text, tag)

    return item


def run_fashion_processor():
    """全自动时装处理器：提取 XML → 独立 JSON + Excel"""
    print(f"开始处理时装数据: {XML_FILE}")

    if not os.path.exists(XML_FILE):
        print(f"  [!] 文件不存在: {XML_FILE}")
        return

    with open(XML_FILE, 'r', encoding='utf-8') as f:
        clean_xml = XmlCleaner.clean(f.read())

    root_el = ET.fromstring(clean_xml)

    fashion_items = []
    for gather in root_el.findall('.//gather'):
        for father in gather.findall('father'):
            if father.get('name') != 'fashion':
                continue
            for image_node in father.findall('image'):
                item = parse_image_node(image_node)
                if item and 'name' in item:
                    item = ValueConverter.prepare_output(item, "爆枪突击", "fashion")
                    fashion_items.append(item)

    print(f"[提取] 共提取 {len(fashion_items)} 个时装")

    # --- 保存独立 JSON ---
    os.makedirs(JSON_OUT, exist_ok=True)
    for item in fashion_items:
        name = item['name']
        file_path = os.path.join(JSON_OUT, f"{name}.json")
        with open(file_path, 'w', encoding='utf-8') as j:
            json.dump(item, j, ensure_ascii=False, indent=2)
    print(f"独立 JSON 已生成: {JSON_OUT}/ ({len(fashion_items)} 个文件)")

    # --- 保存 Excel ---
    os.makedirs(EXCEL_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    EXCEL_NAME = f'{EXCEL_DIR}/时装数据全量更新_{timestamp}.xlsx'

    excel_data = []
    for item in fashion_items:
        excel_data.append({
            "PageName": f"Data:Fashion/{item['name']}.json",
            "Content": json.dumps(item, ensure_ascii=False)
        })

    pd.DataFrame(excel_data).to_excel(EXCEL_NAME, index=False, header=False)
    print(f"Excel 已生成: {EXCEL_NAME} ({len(excel_data)} 行)")
    print(f"\n处理完成！提取时装总数: {len(fashion_items)}")


if __name__ == '__main__':
    run_fashion_processor()
