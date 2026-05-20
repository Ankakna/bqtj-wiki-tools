import re

class XmlCleaner:
    '''
    智能 xml 数据清洗器。
    由于沃龙编写的 xml 中包含大量空格缺失 / 多余问题，
    其中部分会影响 ET 对数据的读取，造成运行报错，
    因此所有 xml 读取前都需要经过清洗，确保数据合规。
    注意，随版本更迭可能产生全新格式的不规范数据，需要注意适配。
    '''
    @staticmethod
    def clean(raw_content: str) -> str:
        '''
        输入源数据，输出清洗后的规范格式 xml。
        逻辑：1. 修复头部缺少空格；2. 修复属性之间缺少空格；3. 清除所有注释和 CDATA
        '''
        if not raw_content: return ""

        # 修复头部
        content = re.sub(r'<\?xmlversion', '<?xml version', raw_content)

        # 修复属性之间的空格丢失 (xxx="xxx"yyy -> xxx="xxx" yyy)
        # 逻辑：
        # ([a-zA-Z0-9_]+\s*=\s*"[^"]*")  -> 匹配一个完整的 key="value" 结构
        # (?=[a-zA-Z])                   -> 使用正向肯定断言，确保后面紧跟的是另一个属性名的开头字母
        #                                   但不对其进行捕获，防止在连续多个粘连时跳过中间的属性
        pattern = r'(\w+\s*=\s*"[^"]*")([a-zA-Z])'
        while re.search(pattern, content):
            content = re.sub(pattern, r'\1 \2', content)

        # 移除注释和 CDATA
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        content = re.sub(r'<!\[CDATA\[.*?\]\]>', '', content, flags=re.DOTALL)
        return content


def clean_game_description(text):
    """
    清理游戏描述文本中的内部标记语法：
    - [n] 替换为真实换行
    - {b}/{/b}、{font...}/{/font} 等格式标记全部删除
    - 逐行去除首尾空白及空行
    """
    if not text:
        return ""
    text = text.replace('[n]', '\n')
    text = text.replace('{b}', '').replace('{/b}', '')
    text = re.sub(r'\{font[^}]*\}', '', text)
    text = text.replace('{/font}', '')
    return "\n".join([line.strip() for line in text.strip().split('\n') if line.strip()])