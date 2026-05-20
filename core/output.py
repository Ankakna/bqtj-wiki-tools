"""
通用数据输出器。

各处理器调用 OutputWriter.write(pool, ...) 即可完成全部输出：
  - 独立 JSON（wiki Data: 页面引用）
  - 聚合 JSON（手动上传 / 备份）
  - Excel 批量更新表（Bot 上传）
"""
import os
import json
import datetime
import pandas as pd


class OutputWriter:
    """
    通用数据输出器。

    每次调用同时产出三样：
      1. 独立 JSON  — output_dir/json/{name}.json（每个实体一个）
      2. 聚合 JSON  — output_dir/{label}数据汇总_{ts}.json
      3. Excel 表   — output_dir/{label}数据更新_{ts}.xlsx
    """

    @staticmethod
    def write(pool, output_dir, wiki_prefix, cn_label='', clean_keys=None, skip_excel=False):
        """
        参数:
            pool: dict[str, dict] — 以 name 为键的数据池
            output_dir: str — 输出根目录（如 './data/skills'）
            wiki_prefix: str — Wiki Data: 命名空间（如 'Skill'、'Arm'）
            cn_label: str — 中文标签（如 '技能'、'武器'），用于文件名
            clean_keys: list — 写入前移除的字段（如 ['_patched']）
            skip_excel: bool — 跳过 Excel 生成
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(output_dir, exist_ok=True)

        if clean_keys:
            OutputWriter._clean(pool, clean_keys)

        # 1. 独立 JSON
        OutputWriter._write_individual_json(pool, output_dir)

        # 2. 聚合 JSON
        OutputWriter._write_aggregated_json(pool, output_dir, cn_label, timestamp)

        # 3. Excel
        if not skip_excel:
            OutputWriter._write_excel(pool, output_dir, wiki_prefix, cn_label, timestamp)

        return timestamp

    @staticmethod
    def _clean(pool, keys):
        for data in pool.values():
            for k in keys:
                data.pop(k, None)

    @staticmethod
    def _write_individual_json(pool, output_dir):
        json_dir = os.path.join(output_dir, 'json')
        os.makedirs(json_dir, exist_ok=True)

        print(f"正在写入 {len(pool)} 个独立 JSON...")
        for name, data in pool.items():
            file_path = os.path.join(json_dir, f"{name}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"独立 JSON: {json_dir}/ ({len(pool)} 个文件)")

    @staticmethod
    def _write_aggregated_json(pool, output_dir, cn_label, timestamp):
        label = cn_label or '数据'
        path = os.path.join(output_dir, f"{label}数据汇总_{timestamp}.json")
        data_list = list(pool.values())
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        print(f"聚合 JSON: {path} ({len(data_list)} 条)")

    @staticmethod
    def _write_excel(pool, output_dir, wiki_prefix, cn_label, timestamp):
        label = cn_label or '数据'
        path = os.path.join(output_dir, f"{label}数据更新_{timestamp}.xlsx")

        excel_data = []
        for name, data in pool.items():
            excel_data.append({
                "PageName": f"Data:{wiki_prefix}/{name}.json",
                "Content": json.dumps(data, ensure_ascii=False)
            })

        if excel_data:
            pd.DataFrame(excel_data).to_excel(path, index=False, header=False)
            print(f"Excel: {path} ({len(excel_data)} 行)")

    @staticmethod
    def write_excel(pool, output_dir, wiki_prefix, excel_label):
        """单独生成 Excel（用于补丁增量等特殊场景）"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        label = excel_label or '数据'
        OutputWriter._write_excel(pool, output_dir, wiki_prefix, label, timestamp)
        return timestamp
