# SCEL2IBUS: 搜狗词库转换为 ibus 词库

原代码来自 BiliBili 专栏 [Ubuntu 中 ibus 输入法导入搜狗词库 ](https://www.bilibili.com/read/cv26964625/)

## 使用方法

确保你已经正确安装了 ibus-libpinyin 输入法

确保 Python 版本为 3.7 或以上。运行`python --version`查看版本

使用 git 克隆本项目到本地

```bash
git clone https://github.com/Microwave-WYB/scel2ibus.git
cd scel2ibus
```

> 如果无法克隆 GitHub，可以直接复制[scel2ibus.py](scel2ibus.py)到本地。

将搜狗词库文件（.scel）和[scel2ibus.py](scel2ibus.py)放在同一目录下，然后运行

```bash
python scel2ibus.py
```

脚本会自动将词库转换为 ibus 词库，并保存在同一目录下。
