# 项目经验

本文件记录在本仓库中踩过的坑和验证过的做法，供后续会话参考。新经验追加到对应章节。

## Tkinter / Windows DPI 布局

**症状**：自动化 GUI 测试全绿，但实际双击启动后中文文字被裁切；仓库行文字只剩一条、菜地作物名顶部缺一截。

**根因**：

- `main()` 里调用了 `SetProcessDpiAwareness(1)`。实际运行时 Tk scaling 会从测试环境的约 1.33 变成 2.33，字体按比例变大。
- 布局测试直接在测试进程里 `FarmApp(...)`，没有走 `main()` 的 DPI 设置，测到的是缩小后的布局。
- 仓库行用固定 `width=4/6/7` 的字符宽度。字体变大后一行需要 401px，面板只有 296px，名称标签被挤成 1px。
- Canvas 文字用居中锚点画在 y=12，字体变高后 bbox 顶部到 -5，被画布上边缘裁掉。

**做法**：

1. 只要应用会开启 DPI 感知，布局测试就必须在**子进程**里先调用同一个 DPI 设置，再创建 Tk；不要在同一测试进程里直接实例化。
2. 中文标签不要用固定字符宽度硬挤。优先用自然宽度 + `pack`/`grid` 的权重；需要对齐时再按实际字体 `measure()` 计算。
3. 面板设置 `pack_propagate(False)` 时，子控件溢出**不会**反映到窗口的 `winfo_reqwidth()`；必须逐个检查子控件的 `winfo_reqwidth() <= winfo_width()`。
4. Canvas 里靠近上边缘的文字用 `anchor="n"` 并留正的上边距；不要用居中锚点放在很小的 y 上。
5. 回归断言：文字 `font.measure(text) <= widget.winfo_width()`；Canvas 文字 `bbox` 不越出画布；`minsize` 不小于布局需要的宽度。

**本项目的落地值**：

- 窗口 `1280×680`，最小 `1260×640`。
- 仓库面板宽 `340`，每行用自然宽度排列。
- 菜地画布 `200×160`，作物名 `anchor="n"`、`y=2`。
- 回归测试：`farmer/test_gui_smoke.py::GuiLayoutTests::test_layout_fits_with_real_dpi_awareness`。

## 存档安全

- 读存档时把“文件不存在 / JSON 损坏 / 暂时读不到”分开处理。`PermissionError`、文件被占用等 I/O 错误不能当成损坏，更不能开新局后自动保存覆盖原档。
- 存档写入用临时文件 + `os.replace` 原子替换；只有解析或校验失败才把原文件重命名为 `*.corrupt-<时间戳>.json`。
- 读档失败时进入本次不写盘模式，界面提示原因，关闭程序也不能覆盖原文件。

## Git 卫生

- `.gitignore` 只对未跟踪文件生效。已经被跟踪的 `__pycache__`、`save.json` 等要用 `git rm --cached` 移出索引，磁盘文件保留。
- 通用忽略规则放根目录 `.gitignore`，项目特有的放子目录（例如 `farmer/.gitignore`）。
- 提交前确认只暂存目标文件；工作区里其他项目的未提交改动不要顺手带进去。

## 技能与验证

- 修 UI/交互 bug 也走 systematic-debugging：先量实际控件尺寸和文字 bbox，再改布局；不要凭“看起来差不多”直接调参数。
- 声称修好之前必须跑完整测试套件，并尽量模拟真实启动路径（包括 DPI、真实 save 路径、主窗口 mainloop）。
