"""
搜狗Scel格式解析以及与ibus词库转换工具
参考: https://www.bilibili.com/read/cv26964625/

最低支持Python版本: 3.7
"""

import glob
import struct
from dataclasses import dataclass
from typing import List, Tuple

PY_OFFSET = 0x1540  # 拼音表偏移
WORDGROUP_OFFSET = 0x2628  # 汉语词组表偏移


class ParseError(Exception):
    """解析错误"""


@dataclass
class WordInfo:
    """
    词组信息
    """

    word: str
    pinyin: str
    count: int

    def __repr__(self) -> str:
        return f"{self.word} {self.pinyin} {self.count}"


@dataclass
class ScelHeader:
    """头部信息"""

    signature: bytes  # 文件标识,12个字节
    name: str  # 词库名
    type: str  # 词库类型
    description: str  # 描述信息
    example: str  # 词库示例


@dataclass
class Pinyin:
    """拼音信息"""

    index: int  # 拼音索引
    length: int  # 拼音字节长度
    pinyin: str  # 拼音字符串


@dataclass
class PinyinTable:
    """拼音表"""

    header: bytes  # 头部，四个字节
    pinyin_list: List[Pinyin]  # 拼音列表


@dataclass
class Word:
    """单词"""

    word_len: int  # 中文词组字节数长度
    word: str  # 中文词组
    ext_len: int  # 扩展信息长度
    ext: bytes  # 扩展信息,前两个字节可能是词频,后八个字节全是0


@dataclass
class WordGroup:
    """词组信息"""

    same: int  # 同音词数量
    py_table_len: int  # 拼音索引表长度
    py_table: List[int]  # 拼音索引表
    words: List[Word]  # 同音词组列表


type WordTable = List[WordGroup]


@dataclass
class Scel:
    """Scel文件"""

    header: ScelHeader  # 文件头部
    pinyin_table: PinyinTable  # 拼音表
    word_table: WordTable  # 汉语词组表

    @classmethod
    def from_binary(cls, data: bytes) -> "Scel":
        """
        从二进制数据中解析Scel文件

        Args:
            data (bytes): 二进制数据

        Returns:
            Scel: Scel文件
        """
        header = parse_header(data)
        py_table = parse_py_table(data[PY_OFFSET:WORDGROUP_OFFSET])
        word_table = parse_word_table(data[WORDGROUP_OFFSET:], py_table)

        return cls(header, py_table, word_table)

    def get_word_info_list(self) -> List[WordInfo]:
        """
        获取词组信息列表

        Args:
            scel (Scel): Scel对象

        Returns:
            List[WordInfo]: 词组信息列表
        """
        word_info_list = []
        for word_group in self.word_table:
            pinyin = get_word_pinyin(
                struct.pack(f"<{len(word_group.py_table)}H", *word_group.py_table),
                self.pinyin_table,
            )
            for word in word_group.words:
                count = struct.unpack("<H", word.ext[:2])[0] if word.ext else 0
                word_info_list.append(WordInfo(word.word, pinyin, count))
        return word_info_list

    def to_ibus(self) -> str:
        """
        转换为ibus词库格式

        Args:
            scel (Scel): Scel对象

        Returns:
            str: ibus词库
        """
        return "\n".join(map(str, self.get_word_info_list())) + "\n"


def parse_header(data: bytes) -> ScelHeader:
    """
    解析头部信息

    Args:
        data (bytes): 头部信息数据

    Returns:
        ScelHeader: 头部信息
    """
    signature = data[:12]
    if signature != b"\x40\x15\x00\x00\x44\x43\x53\x01\x01\x00\x00\x00":
        raise ParseError("解析scel头部失败")
    dict_name = data[0x130:0x338].decode("utf-16le")
    dict_type = data[0x338:0x540].decode("utf-16le")
    description = data[0x540:0xD40].decode("utf-16le")
    example = data[0xD40:0x1540].decode("utf-16le")

    return ScelHeader(signature, dict_name, dict_type, description, example)


def parse_pinyin(data: bytes) -> Tuple[Pinyin, bytes]:
    """
    解析拼音

    Args:
        data (bytes): 拼音数据

    Returns:
        Tuple[Pinyin, bytes]: 拼音信息和剩余数据
    """
    index, length = struct.unpack("<HH", data[:4])
    pinyin: str = data[4 : 4 + length].decode("utf-16le")
    return Pinyin(index, length, pinyin), data[4 + length :]


def parse_py_table(data: bytes) -> PinyinTable:
    """
    解析拼音表

    Args:
        data (bytes): 拼音表数据

    Returns:
        PinyinTable: 拼音表
    """
    if data[:4] != b"\x9d\x01\x00\x00":
        raise ParseError("解析拼音表失败")

    pinyin_table = PinyinTable(data[:4], [])
    data = data[4:]
    while data:
        pinyin, data = parse_pinyin(data)
        pinyin_table.pinyin_list.append(pinyin)

    return pinyin_table


def get_word_pinyin(data: bytes, py_table: PinyinTable) -> str:
    """
    获取词组拼音

    Args:
        data (bytes): 拼音索引数据
        py_table (PinyinTable): 拼音表

    Returns:
        str: 词组拼音
    """
    indices = struct.unpack(f"<{len(data) // 2}H", data)
    return "'".join(py_table.pinyin_list[i].pinyin for i in indices)


def parse_word(data: bytes) -> Tuple[Word, bytes]:
    """
    解析词组

    Args:
        data (bytes): 词组数据

    Returns:
        Tuple[Word, bytes]: 词组信息和剩余数据
    """
    (word_len,) = struct.unpack("<H", data[:2])
    word = data[2 : 2 + word_len].decode("utf-16le")
    (ext_len,) = struct.unpack("<H", data[2 + word_len : 2 + word_len + 2])
    ext = data[2 + word_len + 2 : 2 + word_len + 2 + ext_len]
    return Word(word_len, word, ext_len, ext), data[2 + word_len + 2 + ext_len :]


def parse_word_group(data: bytes, py_table: PinyinTable) -> Tuple[WordGroup, bytes]:
    """
    解析词组信息

    Args:
        data (bytes): 词组信息数据
        py_table (PinyinTable): 拼音表

    Returns:
        Tuple[WordGroup, bytes]: 词组信息和剩余数据
    """
    (same, py_table_len) = struct.unpack("<HH", data[:4])
    py_table_indices = data[4 : 4 + py_table_len]
    py_table_indices = struct.unpack(f"<{py_table_len // 2}H", py_table_indices)
    py_table_indices = [py_table.pinyin_list[i].index for i in py_table_indices]

    words = []
    data = data[4 + py_table_len :]
    for _ in range(same):
        word, data = parse_word(data)
        words.append(word)

    return WordGroup(same, py_table_len, py_table_indices, words), data


def parse_word_table(data: bytes, py_table: PinyinTable) -> WordTable:
    """
    解析词组表

    Args:
        data (bytes): 词组表数据
        py_table (PinyinTable): 拼音表

    Returns:
        WordTable: 词组表
    """
    word_table = []
    while data:
        word_group, data = parse_word_group(data, py_table)
        word_table.append(word_group)

    return word_table


def process_scel_file(file_path: str):
    """
    处理Scel文件

    Args:
        file_path (str): 文件路径
    """
    print(f"正在处理 {file_path}")
    with open(file_path, "rb") as f:
        data = f.read()
    scel = Scel.from_binary(data)
    output_file = file_path.replace(".scel", ".txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(scel.to_ibus())


def main():
    """主函数"""
    scel_files = glob.glob("**/*.scel", recursive=True)

    for scel_file in scel_files:
        process_scel_file(scel_file)


if __name__ == "__main__":
    main()
