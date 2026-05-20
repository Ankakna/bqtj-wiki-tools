# CLAUDE.md

本文档为 Claude Code (claude.ai/code) 提供在本仓库中工作时的指导。

## 重要限制

**所有输出必须使用中文。**

## 项目概述

爆枪突击 Wiki 数据处理工具库 - 用于处理游戏 XML 数据并转换为 灰机 Wiki (Huiji Wiki) 所需的 JSON 格式的 Python 工具。

## 架构设计

本项目采用三层架构：

```
core/        - XML 解析与转换工具类
config/      - 映射配置（如武器类别映射）
scripts/     - 数据处理器入口
xml/         - 源 XML 游戏数据文件（纳入 git 管理）
data/        - 生成的输出文件（JSON + Excel，已加入 gitignore）
```

### 核心模块 (`core/`)

- `XmlCleaner` ([cleaner.py](core/cleaner.py)) - 预处理原始 XML，修复格式问题（属性间缺少空格、头部格式错误）后再进行解析
- `XmlParser` ([parser.py](core/parser.py)) - 递归将 XML 转换为 Python 字典；处理包含嵌入式 JSON 的特殊 `<obj>` 标签
- `ValueConverter` ([converter.py](core/converter.py)) - 基于字段命名约定的智能类型转换：
  - 以 `B` 结尾的字段 → 布尔值
  - 以 `Arr` 结尾的字段 → 列表
  - 以 `0x` 开头的值 → 保留为十六进制字符串（颜色值）
  - Python 字典字面量（`{'key': value}`）→ dict 对象
  - 数字字符串 → 整数/浮点数

### 脚本 (`scripts/`)

每个脚本都是针对特定数据类型的独立处理器：

- `parse_arms.py` - 从 XML 处理武器数据，输出：
  - 独立 JSON 文件（`data/arms/json/*.json`）
  - 汇总 JSON 文件（`data/arms/武器数据汇总_*.json`）
  - Excel 更新表（`data/arms/武器数据更新_*.xlsx`）
- `parse_skills.py` - 处理具有 father/skill 层级结构的技能数据，包含重名检测和报告功能
- `parse_things.py` - 处理物品数据（碎片、材料等），支持 gift 等特殊子标签解析，包含重名检测、报告功能和武器碎片自动补丁
- `patch_things.py` - 兼容入口，直接调用 parse_things.py 的完整流程
- `parse_body.py` - 处理角色数据，支持嵌套的 hurtArr 攻击数据解析，包含重名检测和报告功能
- `parse_equip.py` - 处理装备数据（饰品、护盾、载具、副手），支持自闭合属性型和含子元素型，包含重名检测和报告功能
- `parse_bullet.py` - 处理非武器子弹数据（英雄技能子弹、载具子弹、敌方子弹等），通过 bodyImgRange/allImgRange 排除武器子弹，包含重名检测和报告功能
- `parse_suit.py` - 处理套装数据，从 gather → father → image 层级提取套装定义，基于 gather 的 cnName 挂载分类，包含重名检测和报告功能
- `parse_fashion.py` - 处理时装数据，从 16_XMLOut_fashionClass.bin 提取所有时装条目，独立输出 JSON + Excel文件。

## 常用命令

### 运行处理器

```bash
# 处理武器数据（输出至 data/arms/）
python scripts/parse_arms.py

# 处理技能数据（输出至 data/skills/）
python scripts/parse_skills.py

# 处理物品数据（含武器碎片自动补丁，输出至 data/things/）
# 如需完整补丁效果，请先运行 parse_arms.py 生成武器数据
python scripts/parse_things.py

# 处理角色数据（输出至 data/body/）
python scripts/parse_body.py

# 处理套装数据（输出至 data/suit/）
python scripts/parse_suit.py

# 处理装备数据（输出至 data/equip/）
python scripts/parse_equip.py

# 处理时装数据（输出至 data/fashion/）
python scripts/parse_fashion.py

# 处理非武器子弹数据（输出至 data/bullet/）
python scripts/parse_bullet.py
```

### 环境配置

```bash
# 创建虚拟环境（.venv/ 已存在）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 以可编辑模式安装
pip install -e .
```

## 关键约定

### XML 文件格式

源文件使用 `.bin` 扩展名（而非 `.xml`），但内容实际为 XML 格式。它们存放在 `xml/` 目录中并纳入 git 管理。

### 数据结构模式

- **武器**：存储在 `<father type="...">` → `<bullet>` 节点下；通过存在 `bodyImgRange` 或 `allImgRange` 子元素来识别武器
- **技能**：存储在 `<father name="...">` → `<skill>` 节点下
- **物品**：存储在 `<father>` → `<things>` 节点下
- **角色**：存储在 `<father name="..." cnName="...">` → `<body>` 节点下，含嵌套的 `<hurtArr>` 攻击数据
- **套装**：存储在 `<gather cnName="...">` → `<father name="...">` → `<image>` 节点下（最多4个部件: head/coat/pants/belt）
- **装备**：存储在 `<father>` → `<equip>` 节点下。三种形态：副手（自闭合，属性含 baseLabel/lv）、护盾饰品（自闭合，属性含 baseLabel/maxLv）、载具（含子元素如 main/sub/addObjJson）
- **子弹（非武器）**：存储在 `<father>` → `<bullet>` 节点下。通过检测 bodyImgRange/allImgRange 来排除武器子弹
- **时装**：存储在 `16_XMLOut_fashionClass.bin` 的 `<father name="fashion">` → `<image>` 节点下，每个 image 是独立的时装条目

### 输出格式

- **独立 JSON 文件**：以实体的 `name` 字段命名，存放在 `data/<type>/json/`
- **汇总 JSON 文件**（武器数据）：所有武器合并为一个数组，`data/arms/武器数据汇总_*.json`
- **Excel 批量文件**：生成时附带时间戳，用于 HuijiBot 批量上传，存放在 `data/<type>/`

### 类别映射

武器类别在 [config/arm_map.py](config/arm_map.py) 中通过 `CATEGORY_MAP` 字典手动映射，因为游戏数据缺乏可靠的类别元数据。

套装类别在 [config/suit_map.py](config/suit_map.py) 中通过 `GATHER_SUIT_MAP` 字典映射，基于 gather 标签的 cnName 属性判定分类。无 cnName 的 gather 默认为"普通套装"。

## 数据水合说明

部分 things 数据（如武器碎片）在 XML 中只有基础定义，游戏运行时通过 AS3 代码水合生成完整数据。Wiki 无法运行时水合，因此 `parse_things.py` 在提取完成后会自动进行静态补丁：

**补丁逻辑**：
- 黑色武器碎片（blackChip）：匹配 arms 数据，补全 `itemsLevel`、`smeltD`、`btnList`、`iconUrl`
- 稀有武器碎片（rareChip）：补全描述、`smeltD`、`btnList`
- 自动生成武器缺少的稀有碎片条目

**注意**：如需完整补丁效果，请先运行 `parse_arms.py` 生成武器数据。

## 注意事项

- `data/` 目录已加入 gitignore - 生成的文件不应提交
- XML 文件常存在格式问题（属性间缺少空格），由 `XmlCleaner` 处理
- 本项目使用 `pandas` 生成 Excel，使用 `xml.etree.ElementTree` 解析 XML
