# 图片拼接工具

把多张图片按**横排**或**竖排**拼成一张长图，支持间距、背景色、透明背景、
交叉方向对齐、统一尺寸和输出格式转换。

## 环境

- Python 3.8+
- Pillow（已安装：`python -m pip install Pillow`）

## 图形界面（推荐日常使用）

```bash
python stitch_gui.py
```

Windows 下也可以双击 `run_gui.bat` 启动（不显示黑色控制台窗口）。

界面功能：

1. 「添加图片」或「添加文件夹」，用「上移 / 下移」调整拼接顺序；
2. 选择横排 / 竖排，设置间距、背景色（可勾选透明背景）；
3. 选择缩放方式（保持原尺寸 / 统一到最大 / 统一到第一张）和对齐方式；
4. 选择输出文件，点击「开始拼接」。

## 命令行

```bash
# 横排：三张图从左到右，间隔 10 像素
python stitch.py a.jpg b.jpg c.jpg -d horizontal --gap 10 -o 横排.png

# 竖排：拼接整个文件夹（按文件名自然排序：1, 2, 10, ...）
python stitch.py ./photos -d vertical --gap 20 --bg white -o 竖排.jpg

# 横排并把高度统一到最大那张，输出长边不超过 4000 像素的 JPEG
python stitch.py "D:/照片/*.jpg" -d h --fit max --max-size 4000 -o out.jpg

# 透明背景（仅 PNG / WebP / TIFF 等支持透明度的格式）
python stitch.py a.png b.png -d h --bg transparent -o out.png
```

### 参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `inputs` | 图片文件、文件夹或带引号的通配符，可多个 | 必填 |
| `-d, --direction` | `horizontal` / `h` / `row` 横排，`vertical` / `v` / `column` 竖排 | `horizontal` |
| `-o, --output` | 输出文件路径，格式由扩展名决定 | `stitched.png` |
| `--gap` | 图片间距（像素） | `0` |
| `--bg` | 背景色：颜色名、`#rrggbb`、`rgb(...)` 或 `transparent` | `white` |
| `--align` | 交叉方向对齐：`start` / `center` / `end` | `center` |
| `--fit` | 尺寸不一时：`none` 保持原样、`max` 统一到最大、`first` 统一到第一张 | `none` |
| `--sort` | `auto` 保持输入顺序（目录/通配符内部自然排序）、`name`、`mtime` | `auto` |
| `--reverse` | 反转图片顺序 | 关闭 |
| `-r, --recursive` | 递归读取子目录 | 关闭 |
| `--max-size` | 限制输出长边像素数，超出则等比缩小 | 不限制 |
| `--quality` | JPEG / WebP 质量（1-100） | `95` |

支持输入：jpg / jpeg / png / bmp / gif / webp / tif / tiff。  
支持输出：jpg / jpeg / png / bmp / webp / tif / tiff。

### 说明

- 图片按自然顺序排列，例如 `1.png < 2.png < 10.png`；
- 自动处理手机照片的 EXIF 旋转；
- 对同一目录重复执行时，会自动排除上次生成的输出文件；
- JPEG / BMP 不支持透明，透明背景会自动用白色铺底并给出提示；
- 无法读取的图片会给出警告并跳过，不影响其余图片。

## 测试

```bash
python test_stitch.py -v
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `stitch.py` | 命令行工具 + 拼接核心逻辑 |
| `stitch_gui.py` | 图形界面 |
| `run_gui.bat` | Windows 双击启动图形界面 |
| `test_stitch.py` | 自动化测试 |
