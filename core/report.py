"""
通用统计报告生成器。

各处理器调用 ReportGenerator.generate(pool, output_dir, **config) 即可。
"""
from collections import defaultdict
import os
import datetime


class ReportGenerator:
    """
    通用统计报告生成器。

    接受以 name 为键的数据池，输出标准统计报告（终端 + 文件）。
    通过 config 覆盖字段名与报告前缀，适配不同数据类型。
    """

    @staticmethod
    def generate(pool, output_dir, **config):
        """
        参数:
            pool: dict[str, dict] — 以 name 为键的数据池
            output_dir: str — 报告输出目录
            **config:
                report_prefix: str = '数据'        — 报告标题前缀（如 '技能'、'角色'）
                cn_field: str = 'cnName'           — 中文名字段名
                group_field: str = 'father'        — 分类统计的分组字段
                extra_checks: dict = None           — 额外检测项 {label: field_name}
                report_filename: str = '处理报告.txt' — 报告文件名
        """
        prefix = config.get('report_prefix', '数据')
        cn_field = config.get('cn_field', 'cnName')
        group_field = config.get('group_field', 'father')
        extra_checks = config.get('extra_checks', {})
        filename = config.get('report_filename', '处理报告.txt')

        report = []
        report.append("=" * 50)
        report.append(f" 爆枪突击{prefix}处理报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 50)

        # 总体统计
        total = len(pool)
        report.append(f"\n[总体概况] 提取{prefix}总数: {total} 个")

        # 分类统计
        report.append(f"\n[分类统计]")
        group_stats = defaultdict(int)
        for data in pool.values():
            val = data.get(group_field)
            if isinstance(val, list):
                for v in val:
                    group_stats[str(v)] += 1
            else:
                group_stats[str(val) if val else 'unknown'] += 1
        for g, count in sorted(group_stats.items(), key=lambda x: x[1], reverse=True):
            report.append(f" - {g:20} : {count} 个")

        # 重名检测
        report.append("\n[重名异常检测 (同一中文名对应多个英文 ID)]")
        cn_map = defaultdict(list)
        for name, data in pool.items():
            cn = data.get(cn_field) or "[缺失中文名]"
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
            report.append(f"\n 共发现 {dup_count} 组重名{prefix}。")

        # 关键字段缺失检测
        report.append("\n[异常数据检测]")
        missing_cn = [n for n, d in pool.items() if not d.get(cn_field)]
        if missing_cn:
            report.append(f" [X]缺少中文名的{prefix} ({len(missing_cn)}个):")
            report.append(f"    {', '.join(missing_cn[:20])}...")
        else:
            report.append(f" [OK]所有{prefix}均包含中文名。")

        # 额外检测
        if extra_checks:
            for label, field in extra_checks.items():
                missing = [n for n, d in pool.items() if not d.get(field)]
                if missing:
                    report.append(f" [X]{label} ({len(missing)}个):")
                    report.append(f"    {', '.join(missing)}...")
                else:
                    report.append(f" [OK]所有{prefix}均包含{label}。")

        # 输出
        final_report = "\n".join(report)
        print(final_report)

        file_path = os.path.join(output_dir, filename)
        os.makedirs(output_dir, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_report)
        print(f"\n[报告]统计报告已保存至: {file_path}")
