import sys
import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit,QSizePolicy, QPushButton, QFileDialog, QMessageBox, QStatusBar, QProgressBar, QComboBox, QSlider
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from pathlib import Path
import re

class VideoFrameExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频关键帧提取工具")
        self.setGeometry(100, 100, 800, 500)
        self.setStyleSheet(""" 
            QMainWindow { background-color: #f0f0f0; }
            QLabel { font-size: 12pt; color: #333; }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                font-size: 12pt;
                margin: 4px 2px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
            QLineEdit {
                padding: 8px;
                font-size: 12pt;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QProgressBar {
                height: 20px;
            }
            QLabel#preview {
                border: 1px solid #ccc;
                padding: 10px;
                min-width: 400px;
                min-height: 300px;
                background-color: #eaeaea;
                text-align: center;
                margin: 10px;
                align-self: center;
            }
        """)
        self.init_ui()
        self.statusBar().showMessage("准备就绪")
        self.cap = None
        self.fps = None
        self.duration = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_preview_frame)
        # 使窗口可以接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # 启用键盘事件
        self.setFocus()  # 确保窗口接收到焦点
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # 文件选择部分
        file_layout = QHBoxLayout()
        self.file_label = QLabel("视频文件:")
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.select_video_file)
        
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)

        # 批量处理
        self.batch_check = QPushButton("批量选择视频文件")
        self.batch_check.clicked.connect(self.select_batch_files)
        layout.addWidget(self.batch_check)

        # 时间输入部分
        time_layout = QHBoxLayout()
        self.time_label = QLabel("时间节点 (秒或以冒号分隔):")
        self.time_input = QLineEdit()
        self.time_input.setPlaceholderText("例如: 5, 10, 1:30, 2:15")
        time_layout.addWidget(self.time_label)
        time_layout.addWidget(self.time_input)
        layout.addLayout(time_layout)

        # 保存路径部分
        save_layout = QHBoxLayout()
        self.save_label = QLabel("保存路径:")
        self.save_path = QLineEdit()
        self.save_path.setPlaceholderText("默认保存到视频所在目录")
        self.save_browse_btn = QPushButton("选择路径...")
        self.save_browse_btn.clicked.connect(self.select_save_path)
        
        save_layout.addWidget(self.save_label)
        save_layout.addWidget(self.save_path)
        save_layout.addWidget(self.save_browse_btn)
        layout.addLayout(save_layout)

        # 图片格式选择
        self.format_label = QLabel("图片格式:")
        self.image_format = QComboBox()
        self.image_format.addItems(["PNG", "JPG", "BMP"])
        layout.addWidget(self.format_label)
        layout.addWidget(self.image_format)

        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # 预览部分
        self.preview_label = QLabel("预览")
        self.preview_label.setObjectName("preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.preview_label.setMaximumSize(800, 450)  # 设置最大尺寸
        layout.addWidget(self.preview_label)

        # 视频时长显示
        self.duration_label = QLabel("视频时长: --")
        layout.addWidget(self.duration_label)

        # 视频进度条
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setMinimum(0)
        self.video_slider.setValue(0)
        self.video_slider.sliderMoved.connect(self.slider_moved)
        self.video_slider.valueChanged.connect(self.slider_moved)
        layout.addWidget(self.video_slider)

        # 操作按钮
        self.extract_btn = QPushButton("开始提取")
        self.extract_btn.setStyleSheet("background-color: #008CBA;")
        self.extract_btn.clicked.connect(self.extract_frames)
        layout.addWidget(self.extract_btn)

        # 状态栏
        self.setStatusBar(QStatusBar())
    
    def keyPressEvent(self, event):
        if self.cap is None:
            return

        key = event.key()

        # 判断按下的键是左键还是右键
        if  key == Qt.Key.Key_Left:  # 左箭头
            current_value = self.video_slider.value()
            new_value = max(current_value - 1, 0)
            self.video_slider.setValue(new_value)

        elif key == Qt.Key.Key_Right:  # 右箭头
            current_value = self.video_slider.value()
            new_value = min(current_value + 1, self.video_slider.maximum())
            self.video_slider.setValue(new_value)

    def select_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "", 
            "视频文件 (*.mp4 *.mov *.avi *.mkv)"
        )
        if file_path:
            self.file_path.setText(file_path)
            self.save_path.clear()
            self.load_video_duration(file_path)

    def select_batch_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择多个视频文件", "", 
            "视频文件 (*.mp4 *.mov *.avi *.mkv)"
        )
        if files:
            self.file_path.setText("\n".join(files))

    def select_save_path(self):
        save_path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if save_path:
            self.save_path.setText(save_path)

    def load_video_duration(self, video_path):
        self.cap = cv2.VideoCapture(video_path)
        if self.cap.isOpened():
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration = total_frames / self.fps
            minutes = int(self.duration // 60)
            seconds = int(self.duration % 60)
            self.duration_label.setText(f"视频时长: {minutes}分 {seconds}秒")
            self.video_slider.setMaximum(total_frames - 1)

    def update_preview_frame(self):
        if self.cap is None:
            return

        current_frame = int(self.video_slider.value())
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = self.cap.read()

        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img).scaled(
                self.preview_label.width(), self.preview_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio
            )
            self.preview_label.setPixmap(pixmap)

    def resizeEvent(self, event):
        """当窗口大小变化时，调整预览图像的大小"""
        super().resizeEvent(event)
        if self.cap:
            self.update_preview_frame()

    def slider_moved(self):
        if self.cap:
            self.update_preview_frame()

    def extract_frames(self):
        video_paths = self.file_path.text().split("\n")
        if not video_paths:
            QMessageBox.warning(self, "警告", "请先选择视频文件")
            return

        # 使用当前视频进度条的位置作为提取的时间
        current_time = self.video_slider.value() / self.fps  # 滑块位置转换为秒
        time_input = f"{current_time:.2f}"  # 格式化为两位小数的秒

        times = [float(time_input)]  # 将当前时间作为提取的时间节点

        # 确定保存路径
        save_path = self.save_path.text() or str(Path(video_paths[0]).parent)
        Path(save_path).mkdir(parents=True, exist_ok=True)

        total_files = len(video_paths)
        self.progress_bar.setMaximum(total_files)

        # 处理每个视频文件
        for video_path in video_paths:
            self.progress_bar.setValue(video_paths.index(video_path) + 1)

            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                QMessageBox.critical(self, "错误", f"无法打开视频文件 {video_path}")
                continue

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps

            success_count = 0
            for t in times:
                if t > duration:
                    QMessageBox.warning(self, "警告", f"时间 {t} 秒超过视频总时长")
                    continue

                # 设置视频位置
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ret, frame = cap.read()

                if ret:
                    filename = f"{Path(video_path).stem}_frame_{t}sec.{self.image_format.currentText().lower()}"
                    save_file = str(Path(save_path) / filename)
                    cv2.imwrite(save_file, frame)
                    success_count += 1

                    # Preview the first frame
                    if success_count == 1:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = frame_rgb.shape
                        bytes_per_line = ch * w
                        q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                        pixmap = QPixmap.fromImage(q_img).scaled(
                            self.preview_label.width(), self.preview_label.height(),
                            Qt.AspectRatioMode.KeepAspectRatio
                        )
                        self.preview_label.setPixmap(pixmap)

                else:
                    QMessageBox.warning(self, "警告", f"无法在 {t} 秒处获取帧")

            cap.release()

            self.statusBar().showMessage(
                f"{video_path}: 成功提取 {success_count}/{len(times)} 帧", 5000
            )

        self.statusBar().showMessage(f"所有文件处理完成", 5000)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoFrameExtractor()
    window.show()
    sys.exit(app.exec())
