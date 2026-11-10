# 图片压缩工具

在 Windows 本机压缩手机照片、网页素材、毕业长图和证件照等图片。支持单张和批量处理，
内置四档压缩强度，默认保持原格式，也可以统一输出为 JPG、WebP 或 PNG。

所有处理都在本地完成，不上传图片，也不覆盖原图。

## 功能

- 单张、多张图片或整个文件夹批量压缩。
- 四档预设：轻度、标准、强力、极限。
- 默认保持原格式，也可输出 JPG / WebP / PNG。
- 可选“限制长边”，只缩小不放大，保持宽高比。
- 支持 JPG/JPEG、PNG、WebP、BMP、TIFF、HEIC/HEIF 和静态 GIF。
- 输出到指定文件夹，文件名自动加 `_compressed`，重名时追加 `_1`、`_2`。
- 单张失败或跳过不会中断整批处理，完成后给出汇总。
- 图形界面和命令行共用同一套压缩逻辑。

## 环境与安装

- Windows 10/11
- Python 3.8+
- Pillow 10.4+
- pillow-heif 0.18+（HEIC/HEIF 读写）

安装依赖：

```bash
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

如果本机 pip 被代理拦截，可以关闭代理后重试，或者手动下载 `pillow-heif` 的
Windows wheel 后用 `python -m pip install <wheel文件>` 安装。

## 图形界面

双击 `run_gui.bat`，或运行：

```bash
python compress_gui.py
```

使用步骤：

1. 点击“添加图片”或“添加文件夹”；需要递归读取子目录时勾选“包含子文件夹”。
2. 选择压缩档位、输出格式和输出文件夹。
3. 如需缩放，勾选“限制长边”并填写像素值。
4. 点击“开始压缩”，等待进度完成。

界面会在列表中显示每张图的原始大小、压缩后大小和状态。压缩完成后弹窗汇总成功、
跳过和失败数量，以及总体积变化。

## 压缩档位

档位只控制画质或调色板，不自动改变尺寸；尺寸由“限制长边”单独控制。

| 档位 | JPEG 质量 | WebP 质量 | HEIC 质量 | PNG/GIF 颜色数 |
| --- | --- | --- | --- | --- |
| 轻度 | 90 | 85 | 85 | 不量化（PNG 无损优化；GIF 最多 256 色） |
| 标准 | 75 | 75 | 70 | 256 色 |
| 强力 | 55 | 55 | 50 | 128 色 |
| 极限 | 35 | 35 | 30 | 64 色 |

说明：

- JPEG 默认使用 4:2:0 色度采样；轻度档使用 4:4:4，并关闭 `optimize` 以避开
  Pillow 10.4 在部分参数组合下的编码错误。
- WebP 使用 `method=6`，优先压缩率。
- PNG 使用调色板量化时保留透明通道；量化失败会退回无损优化。
- TIFF 使用 deflate 压缩；BMP 本身无压缩。
- 静态 GIF 会减少调色板颜色；多帧动图会跳过。

## 命令行

```bash
# 单张，标准档，保持原格式
python compress.py photo.jpg -o out

# 批量，强力档，输出 WebP，长边限制 1920
python compress.py ./photos -l strong -f webp --max-size 1920 -o out -r

# 指定输出目录并保持原格式
python compress.py a.jpg b.png -o compressed
```

参数：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `inputs` | 图片文件或文件夹，可多个 | 必填 |
| `-l, --level` | `light` / `standard` / `strong` / `extreme` | `standard` |
| `-o, --output` | 输出目录 | 第一张图所在目录的 `compressed/` |
| `-f, --format` | `keep` / `jpg` / `webp` / `png` | `keep` |
| `--max-size` | 限制长边像素，只缩小不放大 | 不限制 |
| `-r, --recursive` | 文件夹输入包含子目录 | 关闭 |

命令行至少成功处理一张时返回 0；全部失败或参数错误时返回 1。

## 说明与限制

- 不覆盖原始文件；输出文件始终使用独立文件名。
- 同格式且未实际缩放时，如果压缩结果反而更大，会保留原图并在状态中说明。
- 明确转换格式或实际缩放时，按用户选择输出；即使文件变大也保留处理结果并提示。
- 动图（多帧 GIF/WebP）暂不处理，会跳过并报告。
- 一寸照片等证件照只做压缩和缩放，不做裁剪、换背景或排版。
- BMP 保持原格式时通常不会变小，建议选择 JPG 或 WebP。
- 压缩时应用 EXIF 方向后移除 EXIF；ICC 色彩配置在支持的目标格式中保留。
- HEIC/HEIF 依赖 `pillow-heif`；缺失时会提示安装命令，其他格式不受影响。
- 不做云端上传、账号、目标文件大小自动搜索或资源管理器拖放。

## 测试

```bash
python -m unittest -v
```

测试覆盖输入发现、四档压缩、格式转换、透明通道、长边缩放、输出命名、原图保留、
BMP/TIFF/GIF、HEIC、批量错误处理和 GUI 冒烟。

## 文件

| 文件 | 作用 |
| --- | --- |
| `compress.py` | 核心压缩逻辑与命令行入口 |
| `compress_gui.py` | Tkinter 图形界面 |
| `test_compress.py` | 核心、批量、CLI、HEIC 测试 |
| `test_gui_smoke.py` | GUI 冒烟测试 |
| `run_gui.bat` | Windows 双击启动图形界面 |
| `requirements.txt` | Pillow、pillow-heif |
| `docs/superpowers/specs/` | 设计文档 |
| `docs/superpowers/plans/` | 实现计划 |
