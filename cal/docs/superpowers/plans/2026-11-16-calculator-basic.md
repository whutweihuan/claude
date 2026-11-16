# 基础计算器 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现支持加减乘除的基本计算器功能，包含主题切换界面

**架构：** 采用模块化设计，分离计算逻辑与UI层，通过事件驱动处理用户输入

**技术栈：** Python 3.10+, Tkinter, pytest

**规格：** docs/superpowers/specs/2026-11-16-calculator-design.md

## 全局约束
- 使用Python 3.10+语法
- 遵循PE8编码规范
- UI使用Tkinter框架
- 测试使用pytest框架

## 审查重点（Review Focus）
- 除以零情况返回错误提示
- 非数字输入时保持界面稳定
- 主题切换时UI元素正确更新
- 连续运算时结果正确累积
- 错误处理时不发生程序崩溃

---

### 任务 1：创建计算核心模块

**文件：**
- 创建：`src/calculator.py`
- 测试：`tests/test_calculator.py`

- [ ] **步骤 1：编写失败的测试**

```python
def test_addition():
    assert add(2, 3) == 5

def test_subtraction():
    assert subtract(5, 3) == 2

def test_multiplication():
    assert multiply(4, 3) == 12

def test_division():
    assert divide(6, 3) == 2
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_calculator.py -v`
预期：FAIL，报错 "name 'add' is not defined"

- [ ] **步骤 3：实现计算函数**

在 `src/calculator.py` 中创建以下函数签名：
```python
def add(a: float, b: float) -> float:
    pass

def subtract(a: float, b: float) -> float:
    pass

def multiply(a: float, b: float) -> float:
    pass

def divide(a: float, b: float) -> float:
    pass
```

- [ ] **步骤 4：实现计算逻辑**

完善函数体为：
```python
def add(a: float, b: float) -> float:
    return a + b

def subtract(a: float, b: float) -> float:
    return a - b

def multiply(a: float, b: float) -> float:
    return a * b

def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
```

- [ ] **步骤 5：运行测试验证通过**

运行：`pytest tests/test_calculator.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add src/calculator.py tests/test_calculator.py
 git commit -m "feat: implement basic calculator operations"
```

---

### 任务 2：创建UI模块

**文件：**
- 创建：`src/ui.py`
- 测试：`tests/test_ui.py`

- [ ] **步骤 1：编写UI测试**

```python
def test_calculator_window():
    app = CalculatorApp()
    assert app.window.winfo_exists() == 1


def test_theme_switch():
    app = CalculatorApp()
    app.toggle_theme()
    assert app.style.theme_use() in ['clam', 'alt']
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_ui.py -v`
预期：FAIL，报错 "name 'CalculatorApp' is not defined"

- [ ] **步骤 3：实现UI类**

在 `src/ui.py` 中创建基础框架：
```python
import tkinter as tk
from tkinter import ttk

class CalculatorApp:
    def __init__(self, root):
        self.root = root
        self.setup_ui()

    def setup_ui(self):
        self.root.title("Basic Calculator")
        self.root.geometry("300x400")
        self.create_widgets()

    def create_widgets(self):
        # UI组件创建逻辑
        pass

    def toggle_theme(self):
        # 主题切换逻辑
        pass
```

- [ ] **步骤 4：实现UI组件**

完善 `create_widgets` 方法：
```python
def create_widgets(self):
    self.style = ttk.Style()
    self.entry = ttk.Entry(self.root, font=('Arial', 20))
    self.entry.pack(pady=10)

    button_frame = ttk.Frame(self.root)
    button_frame.pack()

    # 添加数字按钮和操作符按钮
    # ...（具体按钮布局代码）...
```

- [ ] **步骤 5：实现主题切换功能**

在 `toggle_theme` 方法中添加：
```python
def toggle_theme(self):
    current = self.style.theme_use()
    self.style.theme_use('alt' if current == 'clam' else 'clam')
```

- [ ] **步骤 6：运行测试验证通过**

运行：`pytest tests/test_ui.py -v`
预期：PASS

- [ ] **步骤 7：Commit**

```bash
git add src/ui.py tests/test_ui.py
 git commit -m "feat: implement calculator UI and theme toggle"
```

---

### 任务 3：集成计算逻辑与UI

**文件：**
- 修改：`src/ui.py`
- 测试：`tests/test_integration.py`

- [ ] **步骤 1：编写集成测试**

```python
def test_full_calculation_flow():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '2+3')
    app.calculate()
    assert app.entry.get() == '5'
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_integration.py -v`
预期：FAIL，报错 "name 'calculate' is not defined"

- [ ] **步骤 3：实现计算触发逻辑**

在 `src/ui.py` 中添加：
```python
def calculate(self):
    try:
        result = eval(self.entry.get())
        self.entry.delete(0, tk.END)
        self.entry.insert(0, str(result))
    except Exception as e:
        self.entry.delete(0, tk.END)
        self.entry.insert(0, f"Error: {str(e)}")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_integration.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add src/ui.py tests/test_integration.py
 git commit -m "feat: integrate calculation logic with UI"
```

---

### 任务 4：添加错误处理机制

**文件：**
- 修改：`src/ui.py`
- 测试：`tests/test_error_handling.py`

- [ ] **步骤 1：编写错误处理测试**

```python
def test_divide_by_zero():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '5/0')
    app.calculate()
    assert app.entry.get() == "Error: Cannot divide by zero"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_error_handling.py -v`
预期：FAIL，报错 "name 'calculate' is not defined"

- [ ] **步骤 3：实现错误处理**

在 `src/ui.py` 的 `calculate` 方法中添加：
```python
except ValueError as e:
    self.entry.delete(0, tk.END)
    self.entry.insert(0, f"Error: {str(e)}")
```

- [ ] **步骤 4：运行测试验证通过**

运行：`pytest tests/test_error_handling.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add src/ui.py tests/test_error_handling.py
 git commit -m "fix: add error handling for division by zero"
```

---

### 任务 5：添加历史记录功能（可选）

**文件：**
- 修改：`src/ui.py`
- 测试：`tests/test_history.py`

- [ ] **步骤 1：编写历史记录测试**

```python
def test_history_display():
    root = tk.Tk()
    app = CalculatorApp(root)
    app.entry.insert(0, '2+2')
    app.calculate()
    assert app.history.get() == "2+2=4"
```

- [ ] **步骤 2：运行测试验证失败**

运行：`pytest tests/test_history.py -v`
预期：FAIL，报错 "name 'history' is not defined"

- [ ] **步骤 3：实现历史记录**

在 `src/ui.py` 中添加：
```python
self.history = ttk.Entry(self.root, font=('Arial', 12))
self.history.pack(pady=5)

def update_history(self, expression, result):
    self.history.delete(0, tk.END)
    self.history.insert(0, f"{expression}={result}")
```

- [ ] **步骤 4：更新 calculate 方法**

在计算成功后调用：
```python
self.update_history(self.entry.get(), str(result))
```

- [ ] **步骤 5：运行测试验证通过**

运行：`pytest tests/test_history.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add src/ui.py tests/test_history.py
 git commit -m "feat: add calculation history display"
```
