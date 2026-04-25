from collections import defaultdict
import os
import json
import pandas as pd
import datetime
import xml.etree.ElementTree as ET
from core import XmlCleaner, XmlParser, ValueConverter

# --- 配置 ---
XML_DIR = './xml'
JSON_OUT = './data/skills/json'
EXCEL_NAME = f'./data/skills/技能数据全量更新_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
# 报告输出路径
REPORT_OUT = './data/skills/处理报告.txt'

def generate_summary(skill_pool):
    '''生成数据统计报告'''
    report = []
    report.append("="*50)
    report.append(f" 爆枪突击技能数据处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("="*50)

    # 总体统计
    total_count = len(skill_pool)
    report.append(f"\n[总体概况] 提取技能总数: {total_count} 个")

    # 分类统计
    report.append("\n[分类统计 (Father)]")
    father_stats = defaultdict(int)
    for data in skill_pool.values():
        f_name = data.get('father', 'unknown')
        father_stats[f_name] += 1
    
    # 按数量降序排序
    for f_name, count in sorted(father_stats.items(), key=lambda x: x[1], reverse=True):
        report.append(f" - {f_name:20} : {count} 个")

    # 重名检测
    report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
    cn_map = defaultdict(list)
    for name, data in skill_pool.items():
        cn = data.get('cnName') or "[缺失中文名]"
        cn_map[cn].append(name)
    
    dup_count = 0
    for cn, names in cn_map.items():
        if len(names) > 1:
            dup_count += 1
            report.append(f" ⚠️  名称: {cn}")
            report.append(f"     关联ID: {', '.join(names)}")
    
    if dup_count == 0:
        report.append(" ✅ 未发现重名冲突。")
    else:
        report.append(f"\n 共发现 {dup_count} 组重名技能。")

    # 关键字段缺失检测
    report.append("\n[异常数据检测]")
    missing_cn = [n for n, d in skill_pool.items() if not d.get('cnName')]
    if missing_cn:
        report.append(f" ❌ 缺少中文名 (cnName) 的技能 ({len(missing_cn)}个):")
        report.append(f"    {', '.join(missing_cn[:20])}...")
    else:
        report.append(" ✅ 所有技能均包含中文名。")

    # 输出到终端和文件
    final_report = "\n".join(report)
    print(final_report)
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"\n📄 详细统计报告已保存至: {REPORT_OUT}")

def run_skill_processor():
    '''
    全自动技能处理器。
    逻辑：扫描所有 XML -> 寻找 father/skill 结构 -> 提取数据并记录其父节点名称。
    '''
    print(f"开始全量扫描目录: {XML_DIR}")
    os.makedirs(JSON_OUT, exist_ok=True)
    
    # 使用字典存储，name 作为 key，确保同一个技能名只保留一份（或最后一份）
    skill_pool = {}

    for root, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith('.bin'): continue
            
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    clean_xml = XmlCleaner.clean(f.read())
                
                root_el = ET.fromstring(clean_xml)
                
                # 寻找所有 father 节点
                for father in root_el.findall('.//father'):
                    # 获取父节点标识，优先取 name，没有则取 type
                    # 正常来说应该所有都是 name
                    father_name = father.get('name') or father.get('type') or "unknown"
                    
                    # 遍历该 father 下的所有 skill
                    for skill_node in father.findall('skill'):
                        # 防止属性与子标签冲突
                        # 移除标签自带的冗余属性，确保解析器只从子标签获取 name
                        for attr in ['name', 'cnName']:
                            if attr in skill_node.attrib:
                                del skill_node.attrib[attr]

                        # 使用 XmlParser 递归解析
                        skill_data = XmlParser.to_dict(skill_node)
                        
                        if not skill_data or 'name' not in skill_data:
                            continue
                        
                        # 注入 father 属性
                        skill_data['father'] = father_name
                        skill_data = ValueConverter.prepare_output(skill_data, "爆枪突击", "skills")

                        # 存入池中，以英文 name 为唯一键
                        skill_pool[skill_data['name']] = skill_data

            except Exception as e:
                print(f"  [!] 错误文件 {file}: {e}")
    
    # 生成统计报告
    generate_summary(skill_pool)

    # --- 统一保存 ---
    excel_data = []
    print(f"正在写入 {len(skill_pool)} 个独立 JSON 文件...")
    
    for skill_name, data in skill_pool.items():
        # 保存为单 JSON
        file_path = os.path.join(JSON_OUT, f"{skill_name}.json")
        with open(file_path, 'w', encoding='utf-8') as j:
            json.dump(data, j, ensure_ascii=False, indent=2)
        
        # 准备 Excel 更新表
        excel_data.append({
            "PageName": f"Data:Skill/{skill_name}.json",
            "Content": json.dumps(data, ensure_ascii=False)
        })

    # 保存 Excel
    if excel_data:
        df = pd.DataFrame(excel_data)
        df.to_excel(EXCEL_NAME, index=False, header=False)
        print(f"处理完成！提取技能总数: {len(skill_pool)}")
        print(f"Excel 更新表已生成: {EXCEL_NAME}")

if __name__ == '__main__':
    run_skill_processor()