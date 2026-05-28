import os
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
    OutputWriter.write(arm_pool, OUTPUT_DIR, 'Arm', cn_label='武器')
    print(f"处理完成！共包含 {len(arm_pool)} 个武器定义")

if __name__ == '__main__':
    run_arm_processor()
