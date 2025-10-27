import sys
import json
import traceback
import threading
import os
from PyQt5 import QtWidgets, QtCore, QtGui
from .vision import select_roi_and_save
from .sequence_modes import add_sequence_step, run_sequence, add_conditional_item, run_conditionals, save_sequence
from .player import play_recording
from .recorder import Recorder
from .io_utils import export_project, import_project
from pynput import keyboard

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES_DIR = os.path.join(BASE_DIR, 'resources')
DEFAULT_SEQ = os.path.join(BASE_DIR, 'sequences.json')
DEFAULT_COND = os.path.join(BASE_DIR, 'conditionals.json')
DEFAULT_REC = os.path.join(BASE_DIR, 'operations.json')


class ConsoleEmitter(QtCore.QObject):
    text = QtCore.pyqtSignal(str)


class ConsoleRedirector:
    def __init__(self, emitter: ConsoleEmitter, prefix: str = ""):
        self.emitter = emitter
        self.prefix = prefix
        self._lock = threading.Lock()

    def write(self, s):
        if not s:
            return
        with self._lock:
            self.emitter.text.emit((self.prefix + s).rstrip("\n") + "\n")

    def flush(self):
        pass


class Worker(QtCore.QThread):
    finished_ok = QtCore.pyqtSignal()
    finished_err = QtCore.pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.fn(*self.args, **self.kwargs)
            self.finished_ok.emit()
        except Exception:
            self.finished_err.emit(traceback.format_exc())


class MainWindow(QtWidgets.QMainWindow):
    # Define signals at class level (required by PyQt)
    sig_start_record = QtCore.pyqtSignal()
    sig_stop_record = QtCore.pyqtSignal()
    sig_start_play = QtCore.pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setWindowTitle('屏幕自动化工具 - Demo')
        self.resize(900, 650)
        self.console_emitter = ConsoleEmitter()
        self.console_emitter.text.connect(self._append_console)
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = ConsoleRedirector(self.console_emitter, "")
        sys.stderr = ConsoleRedirector(self.console_emitter, "[ERR] ")

        self.recorder = None  # type: Recorder
        self._hk_listener = None  # Global hotkeys listener

        # Connect signals defined at class level
        self.sig_start_record.connect(self._rec_start)
        self.sig_stop_record.connect(self._rec_stop)
        self.sig_start_play.connect(self._play_start)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        self.tabs = QtWidgets.QTabWidget()
        vbox.addWidget(self.tabs)
        self.console = QtWidgets.QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("font-family: Consolas, Monaco, monospace; font-size: 12px;")
        vbox.addWidget(self.console, 1)

        self._build_record_play_tab()
        self._build_sequence_tab()
        self._build_conditionals_tab()
        self._build_template_tab()
        self._build_io_tab()
        self._start_hotkeys()

    def closeEvent(self, e):
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        try:
            if self._hk_listener:
                self._hk_listener.stop()
        except Exception:
            pass
        super().closeEvent(e)

    def _append_console(self, s: str):
        self.console.moveCursor(QtGui.QTextCursor.End)
        self.console.insertPlainText(s)
        self.console.moveCursor(QtGui.QTextCursor.End)

    # Tabs
    def _build_record_play_tab(self):
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)

        # Recording
        grid.addWidget(QtWidgets.QLabel('录制输出文件:'), 0, 0)
        self.rec_out = QtWidgets.QLineEdit(DEFAULT_REC)
        btn_rec_browse = QtWidgets.QPushButton('浏览')
        btn_rec_start = QtWidgets.QPushButton('开始录制')
        btn_rec_stop = QtWidgets.QPushButton('停止录制')
        grid.addWidget(self.rec_out, 0, 1)
        grid.addWidget(btn_rec_browse, 0, 2)
        grid.addWidget(btn_rec_start, 1, 1)
        grid.addWidget(btn_rec_stop, 1, 2)

        # Playback
        grid.addWidget(QtWidgets.QLabel('回放输入文件:'), 2, 0)
        self.play_in = QtWidgets.QLineEdit(DEFAULT_REC)
        btn_play_browse = QtWidgets.QPushButton('浏览')
        grid.addWidget(self.play_in, 2, 1)
        grid.addWidget(btn_play_browse, 2, 2)

        grid.addWidget(QtWidgets.QLabel('循环次数:'), 3, 0)
        self.play_loop = QtWidgets.QSpinBox()
        self.play_loop.setRange(1, 999)
        self.play_loop.setValue(1)
        grid.addWidget(self.play_loop, 3, 1)

        grid.addWidget(QtWidgets.QLabel('循环间隔(s):'), 4, 0)
        self.play_interval = QtWidgets.QDoubleSpinBox()
        self.play_interval.setRange(0.0, 10.0)
        self.play_interval.setSingleStep(0.1)
        self.play_interval.setValue(1.0)
        grid.addWidget(self.play_interval, 4, 1)

        btn_play = QtWidgets.QPushButton('开始回放')
        grid.addWidget(btn_play, 5, 1)

        self.tabs.addTab(w, '录制 / 回放')

        # Connections
        btn_rec_browse.clicked.connect(self._rec_browse)
        btn_rec_start.clicked.connect(self._rec_start)
        btn_rec_stop.clicked.connect(self._rec_stop)
        btn_play_browse.clicked.connect(self._play_browse)
        btn_play.clicked.connect(self._play_start)

    def _build_sequence_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        self.seq_template = QtWidgets.QLineEdit()
        btn_tpl_browse = QtWidgets.QPushButton('浏览模板')
        hb_tpl = QtWidgets.QHBoxLayout()
        hb_tpl.addWidget(self.seq_template)
        hb_tpl.addWidget(btn_tpl_browse)

        self.seq_action = QtWidgets.QComboBox()
        self.seq_action.addItems(['click', 'double', 'right_click', 'move_duration', 'long_press', 'drag'])
        self.seq_params = QtWidgets.QLineEdit()
        self.seq_params.setPlaceholderText('{"duration":0.3, "to_x":900, "to_y":600}')
        self.seq_preprocess = QtWidgets.QComboBox()
        self.seq_preprocess.addItems(['none', 'canny', 'threshold'])
        self.seq_multi = QtWidgets.QCheckBox('多尺度匹配')
        self.seq_threshold = QtWidgets.QDoubleSpinBox()
        self.seq_threshold.setRange(0.0, 1.0)
        self.seq_threshold.setSingleStep(0.01)
        self.seq_threshold.setValue(0.85)

        btn_add = QtWidgets.QPushButton('添加到顺序')
        btn_run = QtWidgets.QPushButton('执行顺序匹配')

        # Guided recording controls
        guide_hb = QtWidgets.QHBoxLayout()
        self.btn_seq_guide_start = QtWidgets.QPushButton('开始引导式录制')
        self.btn_seq_guide_next = QtWidgets.QPushButton('下一步（选择动作并框选）')
        self.btn_seq_guide_finish = QtWidgets.QPushButton('录制结束并保存')
        self.btn_seq_guide_next.setEnabled(False)
        self.btn_seq_guide_finish.setEnabled(False)
        guide_hb.addWidget(self.btn_seq_guide_start)
        guide_hb.addWidget(self.btn_seq_guide_next)
        guide_hb.addWidget(self.btn_seq_guide_finish)

        form.addRow('模板:', hb_tpl)
        form.addRow('动作:', self.seq_action)
        form.addRow('参数(JSON):', self.seq_params)
        form.addRow('预处理:', self.seq_preprocess)
        form.addRow('', self.seq_multi)
        form.addRow('阈值:', self.seq_threshold)
        form.addRow('', btn_add)
        form.addRow('', btn_run)
        form.addRow('引导式录制:', guide_hb)

        self.tabs.addTab(w, '顺序模式')

        btn_tpl_browse.clicked.connect(lambda: self._browse_into(self.seq_template))
        btn_add.clicked.connect(self._seq_add)
        btn_run.clicked.connect(self._seq_run)
        self.btn_seq_guide_start.clicked.connect(self._guide_seq_start)
        self.btn_seq_guide_next.clicked.connect(self._guide_seq_next)
        self.btn_seq_guide_finish.clicked.connect(self._guide_seq_finish)

        # Internal state for guided recording
        self._guide_seq_active = False
        self._guide_seq_steps = []
        self._guide_seq_counter = 0

    def _build_conditionals_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        self.cond_template = QtWidgets.QLineEdit()
        btn_tpl_browse = QtWidgets.QPushButton('浏览模板')
        hb_tpl = QtWidgets.QHBoxLayout()
        hb_tpl.addWidget(self.cond_template)
        hb_tpl.addWidget(btn_tpl_browse)

        self.cond_action = QtWidgets.QComboBox()
        self.cond_action.addItems(['click', 'double', 'right_click', 'move_duration', 'long_press', 'drag'])
        self.cond_params = QtWidgets.QLineEdit()
        self.cond_priority = QtWidgets.QSpinBox()
        self.cond_priority.setRange(0, 999)
        self.cond_priority.setValue(1)
        self.cond_preprocess = QtWidgets.QComboBox()
        self.cond_preprocess.addItems(['none', 'canny', 'threshold'])
        self.cond_multi = QtWidgets.QCheckBox('多尺度匹配')
        self.cond_threshold = QtWidgets.QDoubleSpinBox()
        self.cond_threshold.setRange(0.0, 1.0)
        self.cond_threshold.setSingleStep(0.01)
        self.cond_threshold.setValue(0.85)

        btn_add = QtWidgets.QPushButton('添加判断项')
        btn_run = QtWidgets.QPushButton('执行一次判断')

        form.addRow('模板:', hb_tpl)
        form.addRow('动作:', self.cond_action)
        form.addRow('参数(JSON):', self.cond_params)
        form.addRow('优先级:', self.cond_priority)
        form.addRow('预处理:', self.cond_preprocess)
        form.addRow('', self.cond_multi)
        form.addRow('阈值:', self.cond_threshold)
        form.addRow('', btn_add)
        form.addRow('', btn_run)

        self.tabs.addTab(w, '判断模式')

        btn_tpl_browse.clicked.connect(lambda: self._browse_into(self.cond_template))
        btn_add.clicked.connect(self._cond_add)
        btn_run.clicked.connect(self._cond_run)

    def _build_template_tab(self):
        w = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(w)
        grid.addWidget(QtWidgets.QLabel('保存模板到:'), 0, 0)
        self.tpl_out = QtWidgets.QLineEdit(os.path.join(RES_DIR, 'template.png'))
        btn_browse = QtWidgets.QPushButton('浏览')
        btn_roi = QtWidgets.QPushButton('屏幕框选 ROI 并保存')
        grid.addWidget(self.tpl_out, 0, 1)
        grid.addWidget(btn_browse, 0, 2)
        grid.addWidget(btn_roi, 1, 1)
        self.tabs.addTab(w, '模板')

        btn_browse.clicked.connect(lambda: self._save_to(self.tpl_out))
        btn_roi.clicked.connect(self._tpl_select_roi)

    def _build_io_tab(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)

        # Export
        self.export_out = QtWidgets.QLineEdit(os.path.join(BASE_DIR, 'export.zip'))
        btn_export = QtWidgets.QPushButton('导出 (ops/seq/cond/resources)')
        # Import
        self.import_zip = QtWidgets.QLineEdit(os.path.join(BASE_DIR, 'export.zip'))
        self.import_to = QtWidgets.QLineEdit(os.path.join(BASE_DIR, 'imported'))
        btn_import = QtWidgets.QPushButton('导入 ZIP')

        form.addRow('导出 ZIP:', self.export_out)
        form.addRow('', btn_export)
        form.addRow('导入 ZIP:', self.import_zip)
        form.addRow('解压到:', self.import_to)
        form.addRow('', btn_import)

        self.tabs.addTab(w, '导入导出')

        btn_export.clicked.connect(self._export_zip)
        btn_import.clicked.connect(self._import_zip)

    # Handlers
    def _rec_browse(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, '保存录制到', DEFAULT_REC, 'JSON (*.json)')
        if path:
            self.rec_out.setText(path)

    def _rec_start(self):
        if self.recorder is not None:
            print('录制已在进行中')
            return
        self.recorder = Recorder()
        self.recorder.start()
        print('开始录制（在终端无法停止，使用本窗口“停止录制”按钮）')

    def _rec_stop(self):
        if not self.recorder:
            print('尚未开始录制')
            return
        try:
            self.recorder.stop()
            out = self.rec_out.text().strip() or DEFAULT_REC
            self.recorder.save(out)
            print(f'录制已保存: {out}')
        finally:
            self.recorder = None

    def _play_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, '选择回放文件', DEFAULT_REC, 'JSON (*.json)')
        if path:
            self.play_in.setText(path)

    def _play_start(self):
        path = self.play_in.text().strip() or DEFAULT_REC
        loop = int(self.play_loop.value())
        interval = float(self.play_interval.value())
        print(f'开始回放: {path}, loop={loop}, interval={interval}')
        self._run_in_worker(play_recording, path, loop, interval)

    def _start_hotkeys(self):
        # Alt+1 start record, Alt+2 stop record, Alt+3 start playback
        def hk_start_record():
            print('[HK] Alt+1 -> 开始录制')
            self.sig_start_record.emit()

        def hk_stop_record():
            print('[HK] Alt+2 -> 停止录制')
            self.sig_stop_record.emit()

        def hk_start_play():
            print('[HK] Alt+3 -> 开始回放')
            self.sig_start_play.emit()

        try:
            self._hk_listener = keyboard.GlobalHotKeys({
                '<alt>+1': hk_start_record,
                '<alt>+2': hk_stop_record,
                '<alt>+3': hk_start_play,
            })
            self._hk_listener.start()
            print('全局热键已注册：Alt+1 开始录制，Alt+2 停止录制，Alt+3 开始回放')
        except Exception as e:
            print('[ERR] 注册全局热键失败:\n' + str(e))

    def _browse_into(self, line_edit: QtWidgets.QLineEdit):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, '选择模板', RES_DIR, 'Images (*.png *.jpg *.jpeg)')
        if path:
            line_edit.setText(path)

    def _seq_add(self):
        tpl = self.seq_template.text().strip()
        if not tpl:
            QtWidgets.QMessageBox.warning(self, '错误', '请选择模板')
            return
        params = self._read_json(self.seq_params.text())
        add_sequence_step(DEFAULT_SEQ, tpl, self.seq_action.currentText(), params=params, preprocess=self.seq_preprocess.currentText(), multi_scale=self.seq_multi.isChecked())
        print('已添加到 sequences.json')

    def _seq_run(self):
        thr = float(self.seq_threshold.value())
        print(f'执行顺序匹配，threshold={thr}')
        self._run_in_worker(run_sequence, DEFAULT_SEQ, thr)

    # Guided sequence workflow
    def _guide_seq_start(self):
        self._guide_seq_active = True
        self._guide_seq_steps = []
        self._guide_seq_counter = 0
        self.btn_seq_guide_start.setEnabled(False)
        self.btn_seq_guide_next.setEnabled(True)
        self.btn_seq_guide_finish.setEnabled(True)
        print('引导式顺序录制开始：每次点击“下一步”，先设定动作与参数，再弹出 ROI 窗口进行框选。')

    def _guide_seq_next(self):
        if not self._guide_seq_active:
            return
        # choose action/params/preprocess/multi first, then ROI
        action = self.seq_action.currentText()
        params = self._read_json(self.seq_params.text())
        preprocess = self.seq_preprocess.currentText()
        multi = self.seq_multi.isChecked()

        # ROI select and auto-save template
        os.makedirs(RES_DIR, exist_ok=True)
        self._guide_seq_counter += 1
        out_path = os.path.join(RES_DIR, f'seq_step_{self._guide_seq_counter}.png')
        print(f'第 {self._guide_seq_counter} 步：准备框选 ROI，保存为 {out_path}')
        try:
            select_roi_and_save(out_path)
            step = {"template": out_path, "action": action}
            if params:
                step["params"] = params
            if preprocess and preprocess != 'none':
                step["preprocess"] = preprocess
            if multi:
                step["multi_scale"] = True
            self._guide_seq_steps.append(step)
            print(f'已添加步骤 #{self._guide_seq_counter}')
        except Exception as e:
            print('[ERR] 引导式步骤失败:\n' + str(e))

    def _guide_seq_finish(self):
        if not self._guide_seq_active:
            return
        try:
            save_sequence(DEFAULT_SEQ, self._guide_seq_steps)
            print(f'引导式录制结束，已保存 {len(self._guide_seq_steps)} 步到 {DEFAULT_SEQ}')
        finally:
            self._guide_seq_active = False
            self.btn_seq_guide_start.setEnabled(True)
            self.btn_seq_guide_next.setEnabled(False)
            self.btn_seq_guide_finish.setEnabled(False)

    def _cond_add(self):
        tpl = self.cond_template.text().strip()
        if not tpl:
            QtWidgets.QMessageBox.warning(self, '错误', '请选择模板')
            return
        params = self._read_json(self.cond_params.text())
        add_conditional_item(DEFAULT_COND, tpl, self.cond_action.currentText(), priority=int(self.cond_priority.value()), params=params, preprocess=self.cond_preprocess.currentText(), multi_scale=self.cond_multi.isChecked())
        print('已添加到 conditionals.json')

    def _cond_run(self):
        thr = float(self.cond_threshold.value())
        print(f'执行一次判断，threshold={thr}')
        self._run_in_worker(run_conditionals, DEFAULT_COND, thr)

    def _save_to(self, line_edit: QtWidgets.QLineEdit):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, '保存模板到', line_edit.text() or os.path.join(RES_DIR, 'template.png'), 'PNG (*.png)')
        if path:
            line_edit.setText(path)

    def _tpl_select_roi(self):
        # ROI 框选使用 OpenCV GUI，需在主线程执行，避免崩溃
        os.makedirs(RES_DIR, exist_ok=True)
        out = self.tpl_out.text().strip() or os.path.join(RES_DIR, 'template.png')
        print('打开 ROI 选择窗口...')
        try:
            select_roi_and_save(out)
            print(f'模板已保存: {out}')
        except Exception as e:
            print('[ERR] ROI 选择失败:\n' + str(e))

    def _export_zip(self):
        out = self.export_out.text().strip() or os.path.join(BASE_DIR, 'export.zip')
        print(f'导出到: {out}')
        export_project(out, files=[DEFAULT_REC, DEFAULT_SEQ, DEFAULT_COND], resource_dirs=[RES_DIR])
        print('导出完成')

    def _import_zip(self):
        zip_path = self.import_zip.text().strip()
        to_dir = self.import_to.text().strip() or os.path.join(BASE_DIR, 'imported')
        print(f'从 {zip_path} 导入到 {to_dir}')
        import_project(zip_path, to_dir)
        print('导入完成')

    def _read_json(self, text: str):
        text = (text or '').strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, '错误', f'Params 不是合法 JSON\n{e}')
            return None

    def _run_in_worker(self, fn, *args, **kwargs):
        worker = Worker(fn, *args, **kwargs)
        worker.finished_ok.connect(lambda: print('任务完成'))
        worker.finished_err.connect(lambda err: print('[ERR] 任务失败\n' + err))
        worker.start()
        # Keep reference to avoid GC
        if not hasattr(self, '_workers'):
            self._workers = []
        self._workers.append(worker)


def run_gui():
    # High DPI support and cleaner scaling on Windows
    try:
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
    except Exception:
        pass

    app = QtWidgets.QApplication(sys.argv)

    def _global_excepthook(tp, val, tb):
        msg = ''.join(traceback.format_exception(tp, val, tb))
        try:
            QtWidgets.QMessageBox.critical(None, '未捕获异常', msg)
        except Exception:
            pass
        print('[ERR] 未捕获异常\n' + msg)

    sys.excepthook = _global_excepthook

    w = MainWindow()
    w.show()
    app.exec_()
