import os
import json
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser
from config import CATEGORY_MAP

# --- 配置 ---
XML_DIR = './xml'
JSON_OUT = './data/arms/json'
EXCEL_NAME = f'./data/arms/武器数据更新_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
SUMMARY_JSON_NAME = f'./data/arms/武器数据汇总_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

def run_arm_processor():
    '''
    武器数据处理主流程。
    扫描 XML -> 清洗数据 -> 提取武器节点 -> 挂载分类 -> 输出成果。
    '''
    print(f"开始处理武器数据...")
    os.makedirs(JSON_OUT, exist_ok=True)

    all_results = []
    summary_data = []  # 用于汇总 JSON

    for root, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'): continue
            
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    # 调用静态工厂清洗 XML
                    clean_xml = XmlCleaner.clean(f.read())
                
                tree = ET.fromstring(clean_xml)
                
                # 遍历所有的 father 标签，因为 armsType 在这里
                # 这个需要手动移到单个武器 json 的属性里
                for father in tree.findall('.//father'):
                    arms_type = father.attrib.get('type', 'unknown')
                    
                    for bullet in father.findall('./bullet'):
                        # 必须拥有 bodyImgRange 标签才是武器，或者 allImgRange
                        # 否则就是子弹定义
                        if bullet.find('bodyImgRange') is None and bullet.find('allImgRange') is None: continue

                        # 移除 bullet 节点自身的 index, name, cnName 属性
                        # 这样就不会与子标签 <name> 等发生冲突或重复
                        for attr in ['index', 'name', 'cnName']:
                            if attr in bullet.attrib: del bullet.attrib[attr]
                        
                        # 调用递归解析器
                        arm_data = XmlParser.to_dict(bullet)
                        if not arm_data or 'name' not in arm_data: continue

                        # 注补充数据
                        arm_data['armsType'] = arms_type
                        arm_data['category'] = CATEGORY_MAP.get(arm_data['name'], ["未分类"])
                        
                        # 导出单个 JSON 文件
                        name = arm_data['name']
                        with open(f"{JSON_OUT}/{name}.json", 'w', encoding='utf-8') as j:
                            json.dump(arm_data, j, ensure_ascii=False, indent=2)

                        # 添加到汇总数据
                        summary_data.append(arm_data)

                        # 准备 Excel 批量更新数据
                        all_results.append({
                            "PageName": f"Data:Arm/{name}.json",
                            "Content": json.dumps(arm_data, ensure_ascii=False)
                        })
                        print(f"  [√] 已处理: {arm_data.get('cnName', name)}")

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")

    # 保存 Excel
    if all_results:
        df = pd.DataFrame(all_results)
        df.to_excel(EXCEL_NAME, index=False, header=False)
        print(f"处理完成！Excel 已生成：{EXCEL_NAME}")

    # 保存汇总 JSON 文件
    if summary_data:
        with open(SUMMARY_JSON_NAME, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        print(f"处理完成！汇总 JSON 已生成：{SUMMARY_JSON_NAME}")
        print(f"       共包含 {len(summary_data)} 个武器定义")

if __name__ == '__main__':
    run_arm_processor()