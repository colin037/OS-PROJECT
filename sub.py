import sys
import psutil
import csv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from datetime import datetime
from collections import deque

class ProcessFetcher(QThread):
    dataFetched = pyqtSignal(list)

    def run(self):
        while True:
            process_data = [] 
            for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'memory_info']):
                try:
                    pid = proc.info['pid']
                    name = proc.info['name']
                    cpu = proc.info['cpu_percent']
                    memory = proc.info['memory_info'].rss / (1024 * 1024)
                    process_data.append((pid, name, cpu, memory))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            self.dataFetched.emit(process_data)
            self.msleep(3000)

class ProcessMonitor(QMainWindow):
    def __init__(self, is_admin=False):
        super().__init__()
        self.setWindowTitle("Real-Time Process Monitoring")
        self.setGeometry(200, 200, 1000, 500)
        self.is_admin = is_admin
        self.last_alert_pid = None

        self.search_bar = QLineEdit(self)
        self.search_bar.setPlaceholderText("Search by PID or Process Name...")
        self.search_bar.textChanged.connect(self.filter_table)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["PID", "Process Name", "CPU Usage (%)", "Memory Usage (MB)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.setFixedSize(120, 30)
        self.export_button.clicked.connect(self.export_to_csv)

        self.terminate_button = QPushButton("Terminate")
        self.suspend_button = QPushButton("Suspend")
        self.resume_button = QPushButton("Resume")
        
        self.terminate_button.setFixedSize(100, 30)
        self.suspend_button.setFixedSize(100, 30)
        self.resume_button.setFixedSize(100, 30)
        
        self.terminate_button.clicked.connect(self.terminate_process)
        self.suspend_button.clicked.connect(self.suspend_process)
        self.resume_button.clicked.connect(self.resume_process)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.export_button)
        
        if self.is_admin:
            button_layout.addWidget(self.terminate_button)
            button_layout.addWidget(self.suspend_button)
            button_layout.addWidget(self.resume_button)
        
        button_layout.addStretch()

        self.data_window = 20
        self.cpu_usage = deque(maxlen=self.data_window)
        self.memory_usage = deque(maxlen=self.data_window)
        self.timestamps = deque(maxlen=self.data_window)

        self.figure, self.ax = plt.subplots(figsize=(5, 3))
        self.canvas = FigureCanvas(self.figure)

        graph_layout = QVBoxLayout()
        graph_layout.addWidget(self.canvas)
        graph_container = QWidget()
        graph_container.setLayout(graph_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(graph_container)

        layout = QVBoxLayout()
        layout.addWidget(self.search_bar)
        layout.addWidget(splitter)
        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_graph)
        self.timer.start(3000)

        self.worker = ProcessFetcher()
        self.worker.dataFetched.connect(self.update_table)
        self.worker.start()
        self.update_graph()

    @pyqtSlot(list)
    def update_table(self, process_data):
        self.all_processes = process_data
        self.apply_filter()

    def apply_filter(self):
        search_text = self.search_bar.text().lower()
        filtered_data = [p for p in self.all_processes if search_text in str(p[0]).lower() or search_text in p[1].lower()]

        self.table.setSortingEnabled(False)  # ✅ Disable sorting while updating

        self.table.setRowCount(len(filtered_data))
        
        for row, (pid, name, cpu, memory) in enumerate(filtered_data):
            pid_item = QTableWidgetItem(str(pid))
            name_item = QTableWidgetItem(name)
            cpu_item = QTableWidgetItem(f"⚙️ {cpu:.2f}")
            memory_item = QTableWidgetItem(f"🧠 {memory:.2f}")

            # Determine color
            if cpu > 50:
                bg_color = Qt.GlobalColor.red
                fg_color = Qt.GlobalColor.white
            elif cpu > 20:
                bg_color = Qt.GlobalColor.yellow
                fg_color = Qt.GlobalColor.black
            else:
                bg_color = Qt.GlobalColor.white
                fg_color = Qt.GlobalColor.black

            # Apply background color to each item
            for item in [pid_item, name_item, cpu_item, memory_item]:
                item.setBackground(bg_color)
                item.setForeground(fg_color)  # 🆕 this line ensures text is visible

            self.table.setItem(row, 0, pid_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, cpu_item)
            self.table.setItem(row, 3, memory_item)

        self.table.setSortingEnabled(True)  # ✅ Enable sorting after update





    def filter_table(self):
        self.apply_filter()

    def export_to_csv(self):
        with open("process_details.csv", "w", newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["PID", "Process Name", "CPU Usage (%)", "Memory Usage (MB)"])
            for process in self.all_processes:
                writer.writerow(process)
        QMessageBox.information(self, "Success", "Process details exported to CSV successfully.")

    def terminate_process(self):
        selected_row = self.table.currentRow()
        if selected_row != -1:
            pid = int(self.table.item(selected_row, 0).text())
            try:
                psutil.Process(pid).terminate()
                QMessageBox.information(self, "Success", f"Process {pid} terminated successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to terminate process: {e}")

    def suspend_process(self):
        selected_row = self.table.currentRow()
        if selected_row != -1:
            pid = int(self.table.item(selected_row, 0).text())
            try:
                psutil.Process(pid).suspend()
                QMessageBox.information(self, "Success", f"Process {pid} suspended successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to suspend process: {e}")
    
    def resume_process(self):
        selected_row = self.table.currentRow()
        if selected_row != -1:
            pid = int(self.table.item(selected_row, 0).text())
            try:
                psutil.Process(pid).resume()
                QMessageBox.information(self, "Success", f"Process {pid} resumed successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to resume process: {e}")

    def update_graph(self):
        cpu = psutil.cpu_percent()
        memory = psutil.virtual_memory().percent

        self.cpu_usage.append(cpu)
        self.memory_usage.append(memory)
        self.timestamps.append(datetime.now())

        self.ax.clear()
        self.ax.plot(self.timestamps, self.cpu_usage, label="CPU Usage (%)", color='red')
        self.ax.plot(self.timestamps, self.memory_usage, label="Memory Usage (%)", color='blue')

        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Usage (%)")
        self.ax.legend()
        self.ax.grid(True)

        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    is_admin = True  # Change to False for regular users
    window = ProcessMonitor(is_admin=is_admin)
    window.show()
    sys.exit(app.exec())
