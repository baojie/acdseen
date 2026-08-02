# ACDSeeN

1996 年 ACDSee 1.2x 的复刻 —— 一个浏览器 + 一个看图器。

没有数据库，没有编辑器，没有云。只求打开得快、翻页不卡、手不离键盘。

## 关于「DOS 版 ACDSee」

ACDSee 从来不是 DOS 软件 —— 它 1994 年 11 月首发，是 Windows 3.1 的 16 位程序，
1997 年才有 32 位的 "ACDSee 95"，3.0 要到 1999 年。DOS 下同气质的看图软件是
CompuShow (CSHOW)、VPIC、SEA、Graphic Workshop 那一批。

本项目复刻的是 **ACDSee 1.2x（1996）**。那个版本的定位非常清楚：
**它不是图片管理器，也没有任何编辑功能**，只有一个 Browser 和一个 Viewer。

| 原版 1.2x 有 | 本项目 |
|---|---|
| Image Browser：目录树 + 彩色缩略图 | ✅ |
| 内建删除 / 重命名 / 复制 / 移动 | ✅ |
| Image Viewer：全屏、缩放、快速滚动 | ✅ |
| 解码过程中即可滚动缩放 | ✅ 两段式解码 |
| 幻灯片，自动 / 手动，预读下一张 | ✅ |
| BMP GIF JPG PNG PCX TGA TIFF Photo-CD | ✅ 另加 WebP / PSD / AVIF |

原版**没有**的一律不做：无标签分类、无 EXIF 面板、无编辑、无批处理、无插件。
这些是 3.0 之后堆上去的东西，也正是今天难找到「简单看图软件」的原因。

## 特性

- **浏览器**：左边目录树，右边缩略图，只看一个目录，不递归、不建库、不扫全盘
- **看图器**：全屏看图，屏幕上除了图什么都没有，信息走可开关的 OSD 叠层
- **永不"加载中"**：两段式解码 + 预读，翻页零延迟（详见下文「技术实现」）
- **全键盘可达**：文件操作（重命名 / 删除 / 复制 / 移动）内建，不用切回文件管理器
- **幻灯片**：可调间隔，支持方向键、缩放、单击翻页等完整快捷键

## 安装

依赖：

- Python 3.10+
- [PySide6](https://pypi.org/project/PySide6/)（必需）
- [Pillow](https://pypi.org/project/Pillow/)（可选，仅用于 PCX/PCD/PSD 等 Qt 不认的老格式兜底）

```bash
./setup.sh        # 一键创建虚拟环境并安装依赖
```

或手动：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 使用

```bash
./run.sh                       # 打开上次的目录（没有就是当前目录）
./run.sh ~/Pictures            # 打开指定目录的浏览器
./run.sh photo.jpg             # 直接全屏看这张图，并把同目录其他图排进列表
```

等价于 `python -m acdseen [参数]`。

## 支持的格式

| 来源 | 格式 |
|------|------|
| Qt 内置 | BMP、GIF、JPEG/JPG、PNG、TGA、TIFF、WebP、PBM/PGM/PPM、XBM、XPM、ICO、SVG |
| Pillow 兜底 | PCX、Photo-CD(PCD)、PSD、JP2、AVIF、HEIC |

缩略图磁盘缓存放 `~/.cache/acdseen/thumbs`（遵循 XDG），菜单「查看 → 清空缩略图缓存」可随时清掉。

## 快捷键

### 浏览器

| 按键 | 功能 |
|------|------|
| `Enter` / 双击 | 查看图片 |
| `Backspace` | 回到上级目录 |
| `F2` | 重命名 |
| `Del` | 删除 |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | 复制 / 剪切 / 粘贴到当前目录 |
| `Ctrl+Shift+C` / `Ctrl+Shift+M` | 复制到… / 移动到… |
| `Ctrl++` / `Ctrl+-` | 缩略图放大 / 缩小 |
| `F5` | 刷新 |
| `F9` | 显示 / 隐藏目录树 |
| `Ctrl+S` | 从第一张开始全屏幻灯片 |

### 看图器

| 按键 | 功能 |
|------|------|
| `空格` / `PgDn` / `→` | 下一张 |
| `退格` / `PgUp` / `←` | 上一张 |
| `Home` / `End` | 第一张 / 最后一张 |
| `+` / `-` | 放大 / 缩小 |
| `*` | 适应窗口 |
| `/` | 实际大小 1:1 |
| `W` | 适应宽度 |
| `F` / `Enter` / `F11` | 全屏切换 |
| `S` | 幻灯片开关 |
| `[` / `]` | 幻灯片间隔 减 / 加 |
| `I` | 显示 / 隐藏信息条 |
| `Del` | 删除当前图片 |
| `Esc` | 退出全屏 / 关闭 |

**鼠标**：单击翻页，拖拽平移，滚轮翻页，`Ctrl+滚轮` 缩放，中键切换 适应/1:1，双击全屏。

## 技术实现

实测（4000×3000 JPEG，冷缓存，Python 3.14 + PySide6）：

```
Python 导入 + QApplication : 199 ms
到首帧上屏                 : 255 ms      ← 用户感知到的「打开」时间
到全尺寸就绪               : 331 ms
```

「永远不出现加载中」的手感，来自三条并行通道：

1. **两段式解码**。先用 `QImageReader.setScaledSize()` 拿一张 1024px 边长的预览 —— JPEG 走 DCT 缩放，比全解码快 4-8 倍 —— 立刻上屏；同一张图的全尺寸在后台线程继续解，解完无缝替换，缩放/平移参数保持不变。
2. **预读**。停在第 *i* 张时，后台把 `i±2` 的全部解好塞进 LRU 缓存，翻页时直接命中，这一帧就是全尺寸。
3. **独立缩略图通道**。缩略图走自己的线程池 + 磁盘缓存（key 含路径 + mtime + 尺寸，文件变了自动失效），和看图器的解码线程互不抢占；切目录时用 generation 计数器作废所有在飞任务。

## 项目结构

```
acdseen/
├── __main__.py    入口
├── main.py        启动逻辑（目录 / 单张图 / 记住上次目录）
├── browser.py     浏览器：目录树 + 缩略图 + 文件操作
├── viewer.py      全屏看图器：导航、缩放、幻灯片、OSD
├── loader.py      解码层：缩略图线程池、两段式加载、预读、LRU
├── config.py      集中放的"手感"参数（缩放步进、缓存大小、预读张数…）
└── util.py        格式化、自然排序等小工具
```

## 开发

```bash
./setup.sh && ./run.sh        # 搭建环境并运行
```

设计取舍都写在各模块的 docstring 里，改"手感"参数去 `config.py`。

### 测试

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

全部跑在 `QT_QPA_PLATFORM=offscreen` 下，无需真实显示环境；缩略图缓存和
QSettings 都被重定向到临时目录，不会碰你的 `~/.cache` 和真实配置。

夹具会按环境能力生成测试图：GIF 无论如何 Qt 都写不出，TIFF 取决于有没有
`qtimageformats` 插件，PCX 只有 Pillow 认——写不出的格式就不生成，对应
测试自动跳过。

`tests/test_loader.py` 里有三条测试直接对应开发期修过的真实 bug，
删掉它们等于把坑重新挖开：

| 测试 | 挡住的坑 |
|---|---|
| `test_多线程并发解码pcx不崩溃` | Pillow 插件 lazy-import 在多工作线程下撞崩 shiboken（进程级 fatal error） |
| `test_缩略图确实生成且尺寸正确` | `QImage.scaled()` 传 int 而非 Qt 枚举，任务静默抛异常，缩略图全空 |
| `test_pil兜底不经过ImageQt` | `PIL.ImageQt` 在工作线程碰 Qt binding 会炸，必须自己从原始字节构造 `QImage` |
