# 屏幕自动化 Demo（截图识别 + 录制/回放 + GUI）

一个用于验证可行性的最小化项目：基于截图识别（OpenCV 模板匹配）+ 模拟人手操作（PyAutoGUI），支持录制/回放、顺序模式（含引导式录制）、判断模式、导入导出，并提供 PyQt5 GUI 编辑器与内置控制台。已扩展动作包括：拖拽、长按、按时长移动。模板匹配支持多尺度与预处理（边缘/阈值），截图后端采用 mss，避免 pyscreeze/Pillow 兼容性问题。

## 功能概览
- 录制/回放：捕获鼠标（移动/点击/滚轮）与键盘（按下/释放），按时间戳回放。
- 顺序模式：按添加顺序逐步识图并执行操作。
- 判断模式：同屏多目标时按优先级执行最高者。
- GUI 编辑器（PyQt5）：选择模板（ROI 框选）、添加顺序/判断项、运行测试，带内置控制台。
- 导入/导出：将操作配置与资源目录打包为 zip，或从 zip 恢复。
- 动作扩展：click、double、right_click、move_duration、long_press、drag。
- 模板匹配增强：多尺度匹配、预处理（none/canny/threshold）。
- 全局热键：Alt+1 开始录制、Alt+2 停止录制、Alt+3 开始回放（不会被录入到操作中）。
- 引导式顺序录制：每步先配置动作与参数，然后框选 ROI，点击“下一步”，最后“录制结束并保存”。

## 目录结构
- requirements.txt
- main.py（直接启动 GUI）
- app/
  - vision.py（截图、ROI 框选、模板匹配：多尺度+预处理）
  - recorder.py（事件录制）
  - player.py（动作回放与扩展动作）
  - sequence_modes.py（顺序/判断模式，动作参数与视觉选项）
  - io_utils.py（导入导出）
  - gui.py（PyQt5 界面）
- resources/（模板图保存目录，运行时会创建）
- operations.json / sequences.json / conditionals.json（默认输出/配置文件名）

## 安装
建议使用虚拟环境，Windows PowerShell 示例：
```powershell
pip install -r "c:\Users\chinese\PycharmProjects\Operate this piece\requirements.txt"
```
注意：
- 若使用 GUI，需要具备图形界面环境。
- Windows 显示缩放建议 100%，以避免坐标与匹配偏差。
- 如遇权限问题，请以管理员权限运行终端/IDE。

## 快速使用（GUI）
- 启动 GUI：
```powershell
python "c:\Users\chinese\PycharmProjects\Operate this piece\main.py"
```

- 录制/回放 标签
  - 设置“录制输出文件”，点击“开始录制”，完成后点“停止录制”。
  - 选择“回放输入文件”，设置“循环次数/间隔”，点“开始回放”。
  - 全局热键：Alt+1 开始录制，Alt+2 停止录制，Alt+3 开始回放。

- 顺序模式 标签（两种方式）
  - 普通添加：选择模板、动作与参数，点击“添加到顺序”，再“执行顺序匹配”。
  - 引导式录制：点击“开始引导式录制”，每次“下一步（选择动作并框选）”后自动保存模板图至 resources/seq_step_N.png，最后“录制结束并保存”（写入 sequences.json）。

- 判断模式 标签
  - 添加判断项（包含优先级、动作与参数、视觉选项），点击“执行一次判断”运行一次优先级决策。

- 模板 标签
  - 选择保存路径，点击“屏幕框选 ROI 并保存”，回车确认后保存模板图。

- 导入导出 标签
  - 导出：打包 operations/sequences/conditionals/resources 到 zip。
  - 导入：从 zip 解压到指定目录。

### 顺序模式（Sequence）
动作可选：
- click（支持 params: button/left|right|middle, clicks, interval）
- double
- right_click
- move_duration（params: duration）
- long_press（params: button, duration）
- drag（params: to_x, to_y, duration, button）

视觉选项：
- `preprocess`: none/canny/threshold
- `multi_scale`: 开启多尺度匹配

运行：在 GUI 的“顺序模式”页点击“执行顺序匹配”（阈值默认 0.85，可调整）。

### 判断模式（Conditionals）
添加判断项（priority 越大优先级越高），在 GUI 的“判断模式”页点击“执行一次判断”。

### GUI 编辑器
- 选择模板（可浏览或 ROI 框选并保存到 resources/）。
- 选择动作与参数（JSON 形式）。
- 选择视觉选项（预处理、多尺度）与匹配阈值。
- 将条目写入 sequences.json 或 conditionals.json，并可直接执行 seq/cond 运行进行验证。

## 实现说明（简要）
- 图像匹配：`vision.locate_template_on_screen` 支持
  - 预处理：none/canny/threshold（Otsu）
  - 多尺度：在 0.6-1.4 比例区间重采样模板进行匹配，取最高分
  - 匹配方法：`cv2.TM_CCOEFF_NORMED`
- 动作回放：`player.simple_action`
  - click/double/right_click/move_duration/long_press/drag
  - 通过 `params` 字典传入参数
- 顺序/判断模式：`sequence_modes.py`
  - JSON 结构中支持 `params`、`preprocess`、`multi_scale` 字段
  - 判断模式根据 `priority` 选最高优先级匹配项
- GUI：`app/gui.py` 使用 PyQt5 快速构建，调用上述 API。
- 截图：`vision.take_screenshot_cv` 使用 mss 采集整屏，ROI 选择用 OpenCV 窗口。
- 回放速度：移除了 PyAutoGUI 的隐式延时（PAUSE/MINIMUM_* 为 0），按录制时间戳还原节奏。

## 可选增强（后续）
- OCR（pytesseract）文字识别匹配（需安装 Tesseract OCR 并配置 PATH）。
- 多目标/重复匹配、区域限定搜索、颜色空间增强、稳健特征（ORB/SIFT）。
- 高级编辑器（轨迹可视化、时间轴编辑、条件分支流程）。

## 未来可更新内容（Roadmap）
- 引导式顺序录制的“测试本步定位/执行”按钮，便于即点即测。
- 引导式顺序录制支持全局热键（如 Alt+4 下一步、Alt+5 完成保存）。
- OCR 条件匹配：在判断模式中增加文字识别筛选，支持语言包选择与区域限制。
- 多尺度自适应与金字塔匹配，动态阈值建议与匹配置信度可视化。
- 回放轨迹可视化叠加层（半透明），便于调试点击点与拖拽路径。
- 工作区导出格式版本化与兼容检查，防止资源错配。
- 跨分辨率/缩放的模板归一化与定位偏移校正。

## 常见问题
- 鼠标移动到左上角会触发 PyAutoGUI 的 FAILSAFE 保护并中断。
- 多显示器/缩放会导致坐标偏差，尽量统一为 100% 缩放进行测试。
- ROI 选择基于 OpenCV 弹窗，请在有图形界面的环境使用；截图采用 mss，通常无需额外配置。

## 许可
仅用于演示与验证用途。
