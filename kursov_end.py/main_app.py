import customtkinter as ctk
import tkinter as tk
import threading
import time
import socket
import platform
import json
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Dict, List

from database import Database
from hardware import HardwareCollector, LIBRE_AVAILABLE, SCREENINFO_AVAILABLE, TRAY_AVAILABLE
from tray_icon import TrayIconSingle
from utils import set_window_icon, force_exit

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MainApp(ctk.CTkToplevel):
    def __init__(self, parent, username: str):
        super().__init__(parent)
        self.title(f"System Monitor - {username}")
        self.geometry("1400x850")
        self.minsize(1100, 700)
        set_window_icon(self)

        self.username = username
        self.db = Database()
        self.collector = HardwareCollector()
        self.running = True
        self.update_count = 0
        self.start_time = time.time()
        self.current_data = {}

        self.current_values = {'CPU': 0, 'RAM': 0, 'GPU': 0}
        self.target_values = {'CPU': 0, 'RAM': 0, 'GPU': 0}

        self.temp_widgets = {}
        self.scroll_position = 0.0
        self.info_scroll_pos = 0.0

        self._closing = False
        self._after_ids = []

        self.tray_icons = []
        self.tray_update_interval = 2
        self.tray_enabled_var = tk.BooleanVar(value=False)

        self.selected_temp_category = tk.StringVar(value="All")
        self._temp_widgets_cache = {}
        self._temp_display_initialized = False
        self._temp_category = "All"
        self._last_temperatures = {}

        self.center_window()
        self.create_ui()
        self.start_monitoring()
        after_id = self.after(100, self.load_initial_data)
        self._after_ids.append(after_id)
        self.bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    def center_window(self):
        self.update_idletasks()
        width, height = 1400, 850
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_ui(self):
        self.main_container = ctk.CTkFrame(self)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)

        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.pack(fill="both", expand=True)

        self.info_tab = self.tabview.add("System Info")
        self.monitor_tab = self.tabview.add("Monitoring")
        self.database_tab = self.tabview.add("Database")
        self.settings_tab = self.tabview.add("Settings")
        self.all_data_tab = self.tabview.add("All Data")
        self.help_tab = self.tabview.add("Help")

        self.create_system_info_tab()
        self.create_monitor_tab()
        self.create_database_tab()
        self.create_settings_tab()
        self.create_all_data_tab()
        self.create_help_tab()

        self.status_frame = ctk.CTkFrame(self, height=35, fg_color="#2B2B2B")
        self.status_frame.pack(side="bottom", fill="x")

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="System ready",
            font=ctk.CTkFont(size=12),
            text_color="#90EE90"
        )
        self.status_label.pack(side="left", padx=15, pady=8)

        self.time_label = ctk.CTkLabel(
            self.status_frame,
            text=datetime.now().strftime("%H:%M:%S"),
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.time_label.pack(side="right", padx=15, pady=8)

        self.update_time()

    def update_time(self):
        if self._closing:
            return
        self.time_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        after_id = self.after(1000, self.update_time)
        self._after_ids.append(after_id)

    # -------------------- SYSTEM INFO TAB --------------------
    def create_system_info_tab(self):
        selector_frame = ctk.CTkFrame(self.info_tab, fg_color="#2B2B2B")
        selector_frame.pack(fill="x", padx=10, pady=10)

        label = ctk.CTkLabel(selector_frame, text="Select category:", font=ctk.CTkFont(size=14))
        label.pack(side="left", padx=10, pady=5)

        self.category_var = tk.StringVar(value="OS & Platform")
        categories = [
            "OS & Platform",
            "Motherboard",
            "Processor (CPU)",
            "Memory (RAM)",
            "Graphics (GPU)",
            "Storage",
            "Network Adapters",
            "Monitors",
            "Temperatures"
        ]

        self.category_menu = ctk.CTkOptionMenu(
            selector_frame,
            values=categories,
            variable=self.category_var,
            command=self.on_category_change,
            width=250, height=35,
            font=ctk.CTkFont(size=13)
        )
        self.category_menu.pack(side="left", padx=10, pady=5)

        self.info_textbox = ctk.CTkTextbox(
            self.info_tab,
            font=ctk.CTkFont(family="Consolas", size=14),
            wrap="word"
        )
        self.info_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def on_category_change(self, choice):
        if hasattr(self, 'current_data') and self.current_data:
            self.display_category_info(choice, self.current_data)

    def display_category_info(self, category: str, data: Dict):
        if self._closing:
            return
        try:
            self.info_scroll_pos = self.info_textbox.yview()[0]
        except:
            pass
        info = self._build_category_info(category, data)
        self.info_textbox.delete("1.0", "end")
        self.info_textbox.insert("1.0", info)
        try:
            self.info_textbox.yview_moveto(self.info_scroll_pos)
        except:
            pass

    def _format_dict(self, data: Dict, title: str = "") -> str:
        lines = []
        if title:
            lines.append(f"\n{title}:")
        for key, value in data.items():
            if value is None or value == 'N/A' or value == '' or value == 0:
                continue
            if isinstance(value, bool):
                value = 'Yes' if value else 'No'
            lines.append(f"  {key:<20} : {value}")
        return '\n'.join(lines)

    def _build_category_info(self, category, data):
        sys_info = data.get('system_info', {})
        cpu = data.get('cpu', {})
        ram = data.get('ram', {})
        gpu_list = data.get('gpu', [])
        disks = data.get('disks', [])
        network = data.get('network', [])
        monitors = data.get('monitors', [])
        temps = data.get('temperatures', {})

        if category == "OS & Platform":
            info = f"""
============================================================
                    OS & PLATFORM
============================================================
"""
            os_data = {
                'Operating System': f"{platform.system()} {platform.release()}",
                'OS Version': platform.version(),
                'Architecture': platform.machine(),
                'Computer Name': socket.gethostname(),
                'User': self.username,
                'Program Uptime': f"{int((time.time() - self.start_time) // 60)} min",
                'Date & Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Processor': platform.processor(),
                'Total Physical Memory': f"{sys_info.get('total_physical_memory', 0):.2f} GB" if sys_info.get('total_physical_memory', 0) > 0 else None,
                'Domain': sys_info.get('domain'),
                'Workgroup': sys_info.get('workgroup'),
                'System Type': sys_info.get('system_type'),
                'Hypervisor Present': sys_info.get('hypervisor_present')
            }
            info += self._format_dict(os_data)
            return info

        elif category == "Motherboard":
            info = f"""
============================================================
              MOTHERBOARD & BIOS
============================================================
"""
            mb_data = {
                'Manufacturer': sys_info.get('motherboard_manufacturer'),
                'Model': sys_info.get('motherboard_model'),
                'Version': sys_info.get('motherboard_version'),
                'Serial Number': sys_info.get('motherboard_serial'),
                'Name': sys_info.get('motherboard_name'),
                'Description': sys_info.get('motherboard_description'),
                'Status': sys_info.get('motherboard_status')
            }
            info += self._format_dict(mb_data, "MOTHERBOARD")
            bios_data = {
                'Manufacturer': sys_info.get('bios_manufacturer'),
                'Version': sys_info.get('bios_version'),
                'Date': sys_info.get('bios_date'),
                'Serial': sys_info.get('bios_serial'),
                'Name': sys_info.get('bios_name'),
                'Description': sys_info.get('bios_description')
            }
            info += self._format_dict(bios_data, "\nBIOS")
            return info

        elif category == "Processor (CPU)":
            info = f"""
============================================================
                    PROCESSOR (CPU)
============================================================
"""
            cpu_data = {
                'Manufacturer': cpu.get('manufacturer'),
                'Model': cpu.get('name'),
                'Architecture': cpu.get('architecture'),
                'Socket': cpu.get('socket'),
                'Physical Cores': cpu.get('physical_cores'),
                'Logical Cores': cpu.get('logical_cores'),
                'Current Frequency': f"{cpu.get('current_frequency', 0):.0f} MHz" if cpu.get('current_frequency', 0) > 0 else None,
                'Max Frequency': f"{cpu.get('max_frequency', 0):.0f} MHz" if cpu.get('max_frequency', 0) > 0 else None,
                'Min Frequency': f"{cpu.get('min_frequency', 0):.0f} MHz" if cpu.get('min_frequency', 0) > 0 else None,
                'L2 Cache': cpu.get('l2_cache'),
                'L3 Cache': cpu.get('l3_cache'),
                'Family': cpu.get('family'),
                'Model': cpu.get('model'),
                'Stepping': cpu.get('stepping'),
                'Processor ID': cpu.get('processor_id'),
                'Version': cpu.get('version'),
                'Data Width': cpu.get('data_width'),
                'Address Width': cpu.get('address_width'),
                'Status': cpu.get('status'),
                'Current Load': f"{cpu.get('load', 0):.1f}%",
                'Temperature': f"{cpu.get('temperature', 0):.1f} C" if cpu.get('temperature', 0) > 0 else None
            }
            info += self._format_dict(cpu_data)
            return info

        elif category == "Memory (RAM)":
            info = f"""
============================================================
                    MEMORY (RAM)
============================================================
"""
            ram_data = {
                'Total Memory': f"{ram.get('total', 0):.2f} GB",
                'Used Memory': f"{ram.get('used', 0):.2f} GB",
                'Available Memory': f"{ram.get('available', 0):.2f} GB",
                'Memory Usage': f"{ram.get('percent', 0):.1f}%",
                'Total Slots': ram.get('total_slots'),
                'Used Slots': ram.get('used_slots')
            }
            info += self._format_dict(ram_data)
            modules = ram.get('modules', [])
            if modules:
                info += "\n  Memory Modules:"
                for i, mod in enumerate(modules, 1):
                    mod_data = {
                        f'Slot {i}': '',
                        '  Bank': mod.get('bank'),
                        '  Size': f"{mod.get('size', 0):.2f} GB" if mod.get('size', 0) > 0 else None,
                        '  Speed': f"{mod.get('speed')} MHz" if mod.get('speed') and mod.get('speed') != 'N/A' else None,
                        '  Manufacturer': mod.get('manufacturer'),
                        '  Model': mod.get('model'),
                        '  Serial': mod.get('serial'),
                        '  Device Locator': mod.get('device_locator')
                    }
                    info += '\n' + self._format_dict(mod_data)
            else:
                info += "\n  No memory modules detected"
            return info

        elif category == "Graphics (GPU)":
            info = f"""
============================================================
                    GRAPHICS (GPU)
============================================================
"""
            if gpu_list:
                for i, gpu in enumerate(gpu_list, 1):
                    gpu_data = {
                        f'GPU #{i}': gpu.get('name'),
                        'Memory Total': f"{gpu.get('memory_total', 0):.1f} GB" if gpu.get('memory_total', 0) > 0 else None,
                        'Memory Used': f"{gpu.get('memory_used', 0):.1f} GB" if gpu.get('memory_used', 0) > 0 else None,
                        'Memory Free': f"{gpu.get('memory_free', 0):.1f} GB" if gpu.get('memory_free', 0) > 0 else None,
                        'Load': f"{gpu.get('load', 0):.1f}%",
                        'Temperature': f"{gpu.get('temperature', 0):.1f} C" if gpu.get('temperature', 0) > 0 else None,
                        'Driver Version': gpu.get('driver'),
                        'Video Processor': gpu.get('video_processor'),
                        'Video Memory Type': gpu.get('video_memory_type'),
                        'Current Resolution': gpu.get('current_horizontal_res') if gpu.get('current_horizontal_res') and gpu.get('current_horizontal_res') != 'N/A' else None,
                        'Refresh Rate': gpu.get('current_refresh_rate') if gpu.get('current_refresh_rate') and gpu.get('current_refresh_rate') != 'N/A' else None,
                        'Max Refresh Rate': gpu.get('max_refresh_rate') if gpu.get('max_refresh_rate') and gpu.get('max_refresh_rate') != 'N/A' else None,
                        'Min Refresh Rate': gpu.get('min_refresh_rate') if gpu.get('min_refresh_rate') and gpu.get('min_refresh_rate') != 'N/A' else None,
                        'Video Mode': gpu.get('video_mode_description'),
                        'Device ID': gpu.get('device_id'),
                        'PNP Device ID': gpu.get('pnp_device_id'),
                        'Status': gpu.get('status'),
                        'Manufacturer': gpu.get('manufacturer'),
                        'Description': gpu.get('description')
                    }
                    info += self._format_dict(gpu_data)
            else:
                info += "\n  No GPU detected"
            return info

        elif category == "Storage":
            info = f"""
============================================================
                    STORAGE
============================================================
"""
            if disks:
                for disk in disks:
                    disk_data = {
                        'Device': disk.get('device'),
                        'Model': disk.get('model'),
                        'Serial Number': disk.get('serial'),
                        'Type': disk.get('type'),
                        'Interface': disk.get('interface'),
                        'Filesystem': disk.get('filesystem'),
                        'Mount Point': disk.get('mount'),
                        'Status': disk.get('status'),
                        'Total': f"{disk.get('total', 0):.1f} GB",
                        'Used': f"{disk.get('used', 0):.1f} GB ({disk.get('percent', 0):.1f}%)",
                        'Free': f"{disk.get('free', 0):.1f} GB",
                        'Temperature': f"{disk.get('temperature', 0):.1f} C" if disk.get('temperature', 0) > 0 else None
                    }
                    info += self._format_dict(disk_data)
                    info += "\n"
            else:
                info += "\n  No storage devices detected"
            return info

        elif category == "Network Adapters":
            info = f"""
============================================================
              NETWORK ADAPTERS
============================================================
"""
            if network:
                for adapter in network:
                    net_data = {
                        'Adapter': adapter.get('name'),
                        'Status': adapter.get('status'),
                        'Speed': adapter.get('speed'),
                        'MAC Address': adapter.get('mac'),
                        'IPv4 Address': adapter.get('ipv4'),
                        'IPv6 Address': adapter.get('ipv6'),
                        'Manufacturer': adapter.get('manufacturer'),
                        'Product Name': adapter.get('product_name'),
                        'Adapter Type': adapter.get('adapter_type'),
                        'Physical Adapter': adapter.get('physical_adapter'),
                        'Net Enabled': adapter.get('net_enabled'),
                        'Device ID': adapter.get('device_id'),
                        'PNP Device ID': adapter.get('pnp_device_id'),
                        'Sent (MB)': f"{adapter.get('bytes_sent', 0):.2f}" if adapter.get('bytes_sent', 0) > 0 else None,
                        'Received (MB)': f"{adapter.get('bytes_recv', 0):.2f}" if adapter.get('bytes_recv', 0) > 0 else None
                    }
                    info += self._format_dict(net_data)
                    info += "\n"
            else:
                info += "\n  No network adapters detected"
            return info

        elif category == "Monitors":
            info = f"""
============================================================
                    MONITORS
============================================================
"""
            if monitors:
                for monitor in monitors:
                    mon_data = {
                        'Name': monitor.get('name'),
                        'Primary': monitor.get('is_primary'),
                        'Resolution': f"{monitor.get('width', 0)} x {monitor.get('height', 0)}" if monitor.get('width', 0) > 0 else None,
                        'Aspect Ratio': monitor.get('aspect_ratio'),
                        'Physical Size (mm)': f"{monitor.get('width_mm', 0)} x {monitor.get('height_mm', 0)}" if monitor.get('width_mm', 0) and monitor.get('height_mm', 0) else None,
                        'Diagonal (inches)': monitor.get('diagonal_inches'),
                        'Pixel Density (PPI)': monitor.get('ppi'),
                        'Manufacturer': monitor.get('manufacturer'),
                        'Product Name': monitor.get('product_name'),
                        'Serial Number': monitor.get('serial')
                    }
                    info += self._format_dict(mon_data)
                    info += "\n"
            else:
                info += "\n  No monitors detected"
            return info

        elif category == "Temperatures":
            info = f"""
============================================================
                    TEMPERATURES
============================================================
"""
            if temps:
                for name, temp in temps.items():
                    color = "G" if temp < 50 else "Y" if temp < 70 else "R"
                    info += f"  [{color}] {name:<25} : {temp:.1f} C\n"
            else:
                info += "\n  No temperature data available"
            return info

        return ""

    # -------------------- MONITORING TAB --------------------
    def create_monitor_tab(self):
        monitor_frame = ctk.CTkFrame(self.monitor_tab)
        monitor_frame.pack(fill="both", expand=True, padx=15, pady=15)

        title = ctk.CTkLabel(
            monitor_frame,
            text="Real-Time Resource Monitoring",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=(10, 20))

        # Прогресс-бары
        metrics_frame = ctk.CTkFrame(monitor_frame)
        metrics_frame.pack(fill="x", padx=20, pady=10)

        self.progress_bars = {}
        self.progress_labels = {}
        metrics = [("CPU", "#4CAF50", "Processor"), ("RAM", "#2196F3", "Memory"), ("GPU", "#FF9800", "Graphics")]

        for key, color, name in metrics:
            frame = ctk.CTkFrame(metrics_frame)
            frame.pack(side="left", expand=True, fill="both", padx=10, pady=10)

            label = ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(size=14, weight="bold"))
            label.pack(pady=(10, 5))

            progress = ctk.CTkProgressBar(frame, width=250, height=35, progress_color=color)
            progress.pack(pady=10)
            progress.set(0)

            value_label = ctk.CTkLabel(frame, text="0%", font=ctk.CTkFont(size=24, weight="bold"))
            value_label.pack(pady=5)

            self.progress_bars[key] = progress
            self.progress_labels[key] = value_label

        # Температуры
        temp_frame = ctk.CTkFrame(monitor_frame)
        temp_frame.pack(fill="both", expand=True, padx=20, pady=20)

        temp_title_frame = ctk.CTkFrame(temp_frame, fg_color="transparent")
        temp_title_frame.pack(fill="x", pady=(10, 5))

        temp_title = ctk.CTkLabel(
            temp_title_frame,
            text="Component Temperatures",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        temp_title.pack(side="left", padx=5)

        categories = ["All", "CPU", "CPU Cores", "GPU", "Motherboard", "Disks", "Other"]
        self.temp_category_menu = ctk.CTkOptionMenu(
            temp_title_frame,
            values=categories,
            variable=self.selected_temp_category,
            command=self._on_temp_category_changed,
            width=150, height=30,
            font=ctk.CTkFont(size=13)
        )
        self.temp_category_menu.pack(side="right", padx=5)

        self.temp_scroll_frame = ctk.CTkScrollableFrame(temp_frame, height=300)
        self.temp_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Дополнительные сенсоры
        extra_frame = ctk.CTkFrame(monitor_frame)
        extra_frame.pack(fill="x", padx=20, pady=10)

        extra_title = ctk.CTkLabel(
            extra_frame,
            text="Additional Sensors",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        extra_title.pack(pady=(10, 5))

        self.extra_container = ctk.CTkFrame(extra_frame, fg_color="transparent")
        self.extra_container.pack(fill="x", padx=20, pady=10)

        self._temp_widgets_cache = {}
        self._temp_display_initialized = False
        self._temp_category = "All"
        self._last_temperatures = {}

    # ---------- Методы для температур (фильтрация, группировка, обновление) ----------
    def _on_temp_category_changed(self, choice):
        self._temp_display_initialized = False
        self._temp_category = choice
        self.update_temperatures_display(self._last_temperatures)

    def _filter_temperatures_by_category(self, temps: Dict, category: str) -> Dict:
        if category == "All":
            return temps
        filtered = {}
        for name, temp in temps.items():
            name_lower = name.lower()
            if category == "CPU":
                if 'cpu' in name_lower and 'core' not in name_lower and 'package' not in name_lower:
                    filtered[name] = temp
            elif category == "CPU Cores":
                if 'core' in name_lower or 'core' in name:
                    filtered[name] = temp
            elif category == "GPU":
                if 'gpu' in name_lower:
                    filtered[name] = temp
            elif category == "Motherboard":
                if 'mb:' in name_lower or 'motherboard' in name_lower or 'chipset' in name_lower or 'thermal' in name_lower:
                    filtered[name] = temp
            elif category == "Disks":
                if 'disk' in name_lower or 'ssd' in name_lower or 'hdd' in name_lower or 'nvme' in name_lower:
                    filtered[name] = temp
            elif category == "Other":
                if not any(kw in name_lower for kw in ['cpu', 'core', 'gpu', 'mb:', 'motherboard', 'chipset', 'thermal', 'disk', 'ssd', 'hdd', 'nvme']):
                    filtered[name] = temp
        return filtered

    def _group_temperatures(self, temps: Dict) -> Dict:
        grouped = {
            "CPU": {}, "CPU Cores": {}, "GPU": {},
            "Motherboard": {}, "Disks": {}, "Other": {}
        }
        for name, temp in temps.items():
            name_lower = name.lower()
            if 'cpu' in name_lower and 'core' not in name_lower and 'package' not in name_lower:
                grouped["CPU"][name] = temp
            elif 'core' in name_lower or 'core' in name:
                grouped["CPU Cores"][name] = temp
            elif 'gpu' in name_lower:
                grouped["GPU"][name] = temp
            elif 'mb:' in name_lower or 'motherboard' in name_lower or 'chipset' in name_lower or 'thermal' in name_lower:
                grouped["Motherboard"][name] = temp
            elif 'disk' in name_lower or 'ssd' in name_lower or 'hdd' in name_lower or 'nvme' in name_lower:
                grouped["Disks"][name] = temp
            else:
                grouped["Other"][name] = temp
        return {k: v for k, v in grouped.items() if v}

    def _get_color(self, temp):
        if temp < 40:
            return "#4CAF50"
        elif temp < 60:
            return "#FFC107"
        elif temp < 75:
            return "#FF9800"
        else:
            return "#F44336"

    def _clear_temp_display(self, message: str):
        for widget in self.temp_scroll_frame.winfo_children():
            widget.destroy()
        self._temp_widgets_cache = {}
        label = ctk.CTkLabel(
            self.temp_scroll_frame,
            text=message,
            font=ctk.CTkFont(size=14),
            text_color="orange"
        )
        label.pack(pady=30)

    def _build_temp_widgets(self, temps: Dict, category: str):
        for widget in self.temp_scroll_frame.winfo_children():
            widget.destroy()
        self._temp_widgets_cache = {}

        if category == "All":
            grouped = self._group_temperatures(temps)
            for cat_name, items in grouped.items():
                cat_frame = ctk.CTkFrame(self.temp_scroll_frame, fg_color="#2B2B2B", corner_radius=8)
                cat_frame.pack(fill="x", padx=5, pady=5)

                cat_label = ctk.CTkLabel(
                    cat_frame,
                    text=f"┌── {cat_name} ──",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color="#FFD700"
                )
                cat_label.pack(anchor="w", padx=10, pady=(5, 0))

                for name, temp in items.items():
                    item_frame = ctk.CTkFrame(cat_frame, fg_color="transparent")
                    item_frame.pack(fill="x", padx=15, pady=2)

                    display_name = name.replace('MB:', '').replace('Disk:', '').replace('Thermal:', '').strip()
                    if len(display_name) > 30:
                        display_name = display_name[:27] + "..."

                    name_label = ctk.CTkLabel(
                        item_frame,
                        text=display_name,
                        font=ctk.CTkFont(size=12),
                        text_color="gray",
                        anchor="w"
                    )
                    name_label.pack(side="left", padx=5)

                    temp_label = ctk.CTkLabel(
                        item_frame,
                        text=f"{temp:.1f} °C",
                        font=ctk.CTkFont(size=14, weight="bold"),
                        text_color=self._get_color(temp)
                    )
                    temp_label.pack(side="right", padx=5)

                    self._temp_widgets_cache[(cat_name, name)] = temp_label

                sep = ctk.CTkFrame(cat_frame, height=1, fg_color="#3B3B3B")
                sep.pack(fill="x", padx=10, pady=(5, 0))
        else:
            for name, temp in temps.items():
                item_frame = ctk.CTkFrame(self.temp_scroll_frame, fg_color="#2B2B2B", corner_radius=6)
                item_frame.pack(fill="x", padx=5, pady=2)

                display_name = name.replace('MB:', '').replace('Disk:', '').replace('Thermal:', '').strip()
                if len(display_name) > 30:
                    display_name = display_name[:27] + "..."

                name_label = ctk.CTkLabel(
                    item_frame,
                    text=display_name,
                    font=ctk.CTkFont(size=12),
                    text_color="gray",
                    anchor="w"
                )
                name_label.pack(side="left", padx=10, pady=3)

                temp_label = ctk.CTkLabel(
                    item_frame,
                    text=f"{temp:.1f} °C",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=self._get_color(temp)
                )
                temp_label.pack(side="right", padx=10, pady=3)

                self._temp_widgets_cache[("flat", name)] = temp_label

    def update_temperatures_display(self, temperatures: Dict):
        if self._closing:
            return

        self._last_temperatures = temperatures
        category = self.selected_temp_category.get()

        if not temperatures:
            self._clear_temp_display("No temperature data available")
            return

        filtered = self._filter_temperatures_by_category(temperatures, category)
        if not filtered:
            self._clear_temp_display(f"No temperatures found for category: {category}")
            return

        if category != self._temp_category or not self._temp_display_initialized:
            self._temp_category = category
            self._build_temp_widgets(filtered, category)
            self._temp_display_initialized = True
            return

        for key, label in self._temp_widgets_cache.items():
            if isinstance(key, tuple):
                name = key[1]
            else:
                name = key
            if name in filtered:
                temp = filtered[name]
                label.configure(text=f"{temp:.1f} °C", text_color=self._get_color(temp))
            else:
                label.master.pack_forget()

    def update_extra_sensors_display(self, sensors: List):
        if self._closing:
            return
        for widget in self.extra_container.winfo_children():
            widget.destroy()
        if not sensors:
            no_data_label = ctk.CTkLabel(
                self.extra_container,
                text="No additional sensors found",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            no_data_label.pack(pady=30)
            return
        for sensor in sensors:
            frame = ctk.CTkFrame(self.extra_container, fg_color="#2B2B2B", corner_radius=6)
            frame.pack(fill="x", padx=5, pady=2)
            name_label = ctk.CTkLabel(frame, text=sensor.get('name', 'Unknown')[:30], font=ctk.CTkFont(size=11), text_color="gray")
            name_label.pack(side="left", padx=10, pady=3)
            value_label = ctk.CTkLabel(frame, text=f"{sensor.get('value', 0):.1f} {sensor.get('unit', '')}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#87CEEB")
            value_label.pack(side="right", padx=10, pady=3)

    # ---------- Database Tab ----------
    def create_database_tab(self):
        db_frame = ctk.CTkFrame(self.database_tab)
        db_frame.pack(fill="both", expand=True, padx=15, pady=15)

        title = ctk.CTkLabel(
            db_frame,
            text="Database Management",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=(10, 15))

        btn_frame = ctk.CTkFrame(db_frame)
        btn_frame.pack(fill="x", padx=10, pady=10)

        export_btn = ctk.CTkButton(
            btn_frame,
            text="Export to JSON",
            command=self.export_data,
            fg_color="#2E8B57", width=150
        )
        export_btn.pack(side="left", padx=5)

        refresh_btn = ctk.CTkButton(
            btn_frame,
            text="Refresh",
            command=self.refresh_db_data,
            fg_color="#4169E1", width=150
        )
        refresh_btn.pack(side="left", padx=5)

        clear_btn = ctk.CTkButton(
            btn_frame,
            text="Clear Display",
            command=self.clear_db_display,
            fg_color="#DC143C", width=150
        )
        clear_btn.pack(side="left", padx=5)

        self.db_text = ctk.CTkTextbox(
            db_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            wrap="word"
        )
        self.db_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh_db_data(self):
        sessions = self.db.get_all_sessions(10)
        if sessions:
            db_text = "============================================================\n"
            db_text += "                 SESSION HISTORY\n"
            db_text += "============================================================\n\n"
            for session in sessions:
                db_text += f"""
SESSION #{session.get('id', 'N/A')}
  User             : {session.get('username', 'N/A')}
  Start Time       : {session.get('start_time', 'N/A')[:19] if session.get('start_time') else 'N/A'}
  End Time         : {session.get('end_time', 'Active')[:19] if session.get('end_time') else 'Active'}
  CPU Load         : {session.get('cpu_load', 0):.1f}%
  RAM Usage        : {session.get('ram_percent', 0):.1f}%
"""
            self.db_text.delete("1.0", "end")
            self.db_text.insert("1.0", db_text)
        else:
            self.db_text.delete("1.0", "end")
            self.db_text.insert("1.0", "No data in database")

    def clear_db_display(self):
        self.db_text.delete("1.0", "end")
        self.db_text.insert("1.0", "Display cleared")
        self.update_status("Display cleared", "orange")

    def export_data(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Data"
        )
        if file_path:
            if self.db.export_to_json(file_path):
                messagebox.showinfo("Success", f"Data exported to:\n{file_path}")
                self.update_status("Data exported", "green")
            else:
                messagebox.showerror("Error", "Failed to export data")

    # ---------- Settings Tab ----------
    def create_settings_tab(self):
        settings_frame = ctk.CTkScrollableFrame(self.settings_tab)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Appearance
        appearance_frame = ctk.CTkFrame(settings_frame)
        appearance_frame.pack(fill="x", pady=10)
        appearance_title = ctk.CTkLabel(
            appearance_frame,
            text="Appearance",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        appearance_title.pack(pady=(10, 15))
        theme_frame = ctk.CTkFrame(appearance_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=5)
        theme_label = ctk.CTkLabel(theme_frame, text="Theme:", width=150)
        theme_label.pack(side="left")
        self.theme_var = tk.StringVar(value="dark")
        theme_menu = ctk.CTkOptionMenu(
            theme_frame,
            values=["dark", "light"],
            variable=self.theme_var,
            command=self.change_theme,
            width=150
        )
        theme_menu.pack(side="left", padx=10)

        # Update interval
        update_frame = ctk.CTkFrame(settings_frame)
        update_frame.pack(fill="x", pady=10)
        update_title = ctk.CTkLabel(
            update_frame,
            text="Data Update",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        update_title.pack(pady=(10, 15))
        interval_frame = ctk.CTkFrame(update_frame, fg_color="transparent")
        interval_frame.pack(fill="x", padx=20, pady=5)
        interval_label = ctk.CTkLabel(interval_frame, text="Update Interval (sec):", width=150)
        interval_label.pack(side="left")
        self.interval_var = tk.StringVar(value="0.5")
        interval_menu = ctk.CTkOptionMenu(
            interval_frame,
            values=["0.5", "1", "2", "3", "5"],
            variable=self.interval_var,
            command=self.change_interval,
            width=150
        )
        interval_menu.pack(side="left", padx=10)

        # System Tray
        tray_frame = ctk.CTkFrame(settings_frame)
        tray_frame.pack(fill="x", pady=10)
        tray_title = ctk.CTkLabel(
            tray_frame,
            text="System Tray",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        tray_title.pack(pady=(10, 15))

        if TRAY_AVAILABLE:
            self.tray_enabled_var = tk.BooleanVar(value=False)
            tray_check = ctk.CTkCheckBox(
                tray_frame,
                text="Enable system tray",
                variable=self.tray_enabled_var,
                command=self.on_tray_toggle
            )
            tray_check.pack(anchor="w", padx=20, pady=5)

            metrics_frame = ctk.CTkFrame(tray_frame, fg_color="transparent")
            metrics_frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(metrics_frame, text="Display metrics:").pack(anchor="w")

            self.tray_metrics_vars = {}
            for metric in ['CPU', 'RAM', 'GPU']:
                var = tk.BooleanVar(value=True)
                self.tray_metrics_vars[metric.lower()] = var
                cb = ctk.CTkCheckBox(
                    metrics_frame,
                    text=metric,
                    variable=var,
                    command=self.on_tray_metrics_change
                )
                cb.pack(anchor="w", padx=20)

            interval_tray_frame = ctk.CTkFrame(tray_frame, fg_color="transparent")
            interval_tray_frame.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(interval_tray_frame, text="Tray update interval (sec):").pack(side="left")
            self.tray_interval_var = tk.StringVar(value="2")
            tray_interval_menu = ctk.CTkOptionMenu(
                interval_tray_frame,
                values=["1", "2", "3", "5", "10"],
                variable=self.tray_interval_var,
                command=self.on_tray_interval_change,
                width=100
            )
            tray_interval_menu.pack(side="left", padx=10)

            minimize_btn = ctk.CTkButton(
                tray_frame,
                text="Minimize to Tray",
                command=self.minimize_to_tray
            )
            minimize_btn.pack(pady=10)
        else:
            warn_label = ctk.CTkLabel(
                tray_frame,
                text="pystray (PIL) is not installed. Tray functionality disabled.",
                text_color="orange",
                font=ctk.CTkFont(size=12)
            )
            warn_label.pack(pady=10)

        about_btn = ctk.CTkButton(
            settings_frame,
            text="About",
            command=self.show_about,
            width=200, height=35
        )
        about_btn.pack(pady=15)

    # ---------- Tray methods ----------
    def recreate_tray_icons(self):
        for icon in self.tray_icons:
            try:
                icon.stop()
            except:
                pass
        self.tray_icons.clear()
        if not self.tray_enabled_var.get():
            return
        active_metrics = [k for k, v in self.tray_metrics_vars.items() if v.get()]
        for metric in active_metrics:
            icon = TrayIconSingle(self, metric, self.tray_update_interval)
            threading.Thread(target=icon.run, daemon=True).start()
            self.tray_icons.append(icon)

    def on_tray_toggle(self):
        self.recreate_tray_icons()
        self.update_status("Tray enabled" if self.tray_enabled_var.get() else "Tray disabled", "blue")

    def on_tray_metrics_change(self):
        if self.tray_enabled_var.get():
            self.recreate_tray_icons()

    def on_tray_interval_change(self, val):
        self.tray_update_interval = float(val)
        if self.tray_enabled_var.get():
            self.recreate_tray_icons()

    def minimize_to_tray(self):
        if not TRAY_AVAILABLE:
            messagebox.showwarning("Not available", "pystray is not installed.")
            return
        if not self.tray_enabled_var.get():
            self.tray_enabled_var.set(True)
            self.recreate_tray_icons()
        self.withdraw()

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self):
        self.close_app(force=True)

    # ---------- Misc ----------
    def change_theme(self, choice):
        ctk.set_appearance_mode(choice)
        self.update_status(f"Theme changed to {choice}", "blue")

    def change_interval(self, choice):
        self.update_status(f"Update interval set to {choice} sec", "blue")

    def show_about(self):
        libre_status = "Available" if LIBRE_AVAILABLE else "Not available"
        screen_status = "Available" if SCREENINFO_AVAILABLE else "Not available"
        tray_status = "Available" if TRAY_AVAILABLE else "Not available"
        about_text = f"""
============================================================
              SYSTEM MONITOR v2.0.0
          Professional System Monitoring
============================================================

Features:
   • Complete system information
   • Extended hardware details
   • All available temperatures
   • Additional sensors
   • Real-time monitoring
   • Database sessions
   • JSON export
   • System tray with load display

Module Status:
   • LibreHardwareMonitor: {libre_status}
   • screeninfo: {screen_status}
   • pystray: {tray_status}

Statistics:
   • Uptime: {int((time.time() - self.start_time) // 60)} minutes
   • Updates: {self.update_count}
   • Sessions: {len(self.db.get_all_sessions(100))}
"""
        messagebox.showinfo("About", about_text)

    def create_help_tab(self):
        help_frame = ctk.CTkFrame(self.help_tab)
        help_frame.pack(fill="both", expand=True, padx=15, pady=15)

        title = ctk.CTkLabel(
            help_frame,
            text="Help",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(pady=(10, 15))

        help_text = ctk.CTkTextbox(
            help_frame,
            font=ctk.CTkFont(size=13),
            wrap="word"
        )
        help_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        help_content = """
============================================================
                  SYSTEM MONITOR v2.0
                Professional System Monitoring
============================================================

FEATURES:

1. SYSTEM INFO TAB
   • Dropdown category selection
   • Detailed information per category

2. ALL DATA TAB
   • Two columns each taking 50% of width
   • Full width display

3. REAL-TIME MONITORING
   • Smooth progress bar animation
   • All available temperatures with category filter
   • Additional sensors (fans, voltage, power)

4. DATABASE
   • Automatic session saving
   • JSON export

5. SYSTEM TRAY (Settings)
   • Show CPU/RAM/GPU load in tray icon
   • Customizable metrics and update interval
   • Minimize to tray

QUICK START:
   Username: a
   Password: 1

HOTKEYS:
   F5 - Refresh
   Ctrl+Q - Exit
"""
        help_text.insert("1.0", help_content)
        help_text.configure(state="disabled")

    # ---------- All Data Tab ----------
    def create_all_data_tab(self):
        main_container = ctk.CTkFrame(self.all_data_tab)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        title = ctk.CTkLabel(
            main_container,
            text="SYSTEM INFORMATION",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title.pack(pady=(0, 15))

        canvas_frame = ctk.CTkFrame(main_container)
        canvas_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_frame, bg="#2B2B2B", highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(canvas_frame, command=canvas.yview, orientation="vertical")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        inner_frame = ctk.CTkFrame(canvas, fg_color="transparent")
        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw", width=canvas.winfo_width())

        def configure_inner_frame(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", configure_inner_frame)

        def update_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner_frame.bind("<Configure>", update_scroll_region)

        self.all_data_canvas = canvas
        self.all_data_inner_frame = inner_frame

        columns_frame = ctk.CTkFrame(inner_frame, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True)

        left_column = ctk.CTkFrame(columns_frame, fg_color="transparent")
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right_column = ctk.CTkFrame(columns_frame, fg_color="transparent")
        right_column.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.all_data_frames = {}
        self.all_data_text_widgets = {}

        left_blocks = [
            ("OS & Platform", "os"),
            ("Motherboard & BIOS", "motherboard"),
            ("Processor (CPU)", "cpu"),
            ("Memory (RAM)", "ram"),
            ("Monitors", "monitors")
        ]
        right_blocks = [
            ("Graphics (GPU)", "gpu"),
            ("Storage", "disks"),
            ("Network Adapters", "network"),
            ("Temperatures", "temperatures"),
            ("Resource Usage", "resources")
        ]

        for title_text, key in left_blocks:
            self.all_data_frames[key] = self._create_info_block(left_column, title_text)
            self.all_data_text_widgets[key] = self.all_data_frames[key]['text']

        for title_text, key in right_blocks:
            self.all_data_frames[key] = self._create_info_block(right_column, title_text)
            self.all_data_text_widgets[key] = self.all_data_frames[key]['text']

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    def _create_info_block(self, parent, title):
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.pack(fill="x", pady=6, padx=2)

        title_label = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#4CAF50"
        )
        title_label.pack(anchor="w", padx=12, pady=(8, 4))

        separator = ctk.CTkFrame(frame, height=2, fg_color="#3B3B3B")
        separator.pack(fill="x", padx=12, pady=(0, 6))

        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        content_text = ctk.CTkTextbox(
            content_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            height=220,
            wrap="word"
        )
        content_text.pack(fill="both", expand=True)

        content_text.insert("1.0", "Loading data...")
        content_text.configure(state="disabled")

        return {'frame': frame, 'text': content_text}

    def update_all_data_display(self, data: Dict):
        if self._closing:
            return

        sys_info = data.get('system_info', {})
        cpu = data.get('cpu', {})
        ram = data.get('ram', {})
        gpu_list = data.get('gpu', [])
        disks = data.get('disks', [])
        network = data.get('network', [])
        monitors = data.get('monitors', [])
        temps = data.get('temperatures', {})

        # OS & Platform
        os_data = {
            'Operating System': f"{platform.system()} {platform.release()}",
            'OS Version': platform.version(),
            'Architecture': platform.machine(),
            'Computer Name': socket.gethostname(),
            'User': self.username,
            'Uptime (program)': f"{int((time.time() - self.start_time) // 60)} min",
            'Date & Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Domain': sys_info.get('domain'),
            'Workgroup': sys_info.get('workgroup'),
            'System Type': sys_info.get('system_type')
        }
        os_info = self._format_dict(os_data)
        self._update_text_widget(self.all_data_text_widgets['os'], os_info)

        # Motherboard & BIOS
        mb_data = {
            'Motherboard Manufacturer': sys_info.get('motherboard_manufacturer'),
            'Motherboard Model': sys_info.get('motherboard_model'),
            'Motherboard Version': sys_info.get('motherboard_version'),
            'Motherboard Serial': sys_info.get('motherboard_serial'),
            'Motherboard Name': sys_info.get('motherboard_name'),
            'Motherboard Status': sys_info.get('motherboard_status'),
            'BIOS Version': sys_info.get('bios_version'),
            'BIOS Date': sys_info.get('bios_date'),
            'BIOS Serial': sys_info.get('bios_serial'),
            'BIOS Name': sys_info.get('bios_name')
        }
        mb_info = self._format_dict(mb_data)
        self._update_text_widget(self.all_data_text_widgets['motherboard'], mb_info)

        # CPU
        cpu_data = {
            'Manufacturer': cpu.get('manufacturer'),
            'Model': cpu.get('name'),
            'Architecture': cpu.get('architecture'),
            'Socket': cpu.get('socket'),
            'Physical Cores': cpu.get('physical_cores'),
            'Logical Cores': cpu.get('logical_cores'),
            'Current Frequency': f"{cpu.get('current_frequency', 0):.0f} MHz" if cpu.get('current_frequency', 0) > 0 else None,
            'Max Frequency': f"{cpu.get('max_frequency', 0):.0f} MHz" if cpu.get('max_frequency', 0) > 0 else None,
            'L2 Cache': cpu.get('l2_cache'),
            'L3 Cache': cpu.get('l3_cache'),
            'Family': cpu.get('family'),
            'Model': cpu.get('model'),
            'Stepping': cpu.get('stepping'),
            'Processor ID': cpu.get('processor_id'),
            'Version': cpu.get('version'),
            'Data Width': cpu.get('data_width'),
            'Address Width': cpu.get('address_width'),
            'Status': cpu.get('status'),
            'Load': f"{cpu.get('load', 0):.1f}%",
            'Temperature': f"{cpu.get('temperature', 0):.1f} C" if cpu.get('temperature', 0) > 0 else None
        }
        cpu_info = self._format_dict(cpu_data)
        self._update_text_widget(self.all_data_text_widgets['cpu'], cpu_info)

        # RAM
        ram_data = {
            'Total Memory': f"{ram.get('total', 0):.2f} GB",
            'Used Memory': f"{ram.get('used', 0):.2f} GB",
            'Available Memory': f"{ram.get('available', 0):.2f} GB",
            'Memory Usage': f"{ram.get('percent', 0):.1f}%",
            'Total Slots': ram.get('total_slots'),
            'Used Slots': ram.get('used_slots')
        }
        ram_info = self._format_dict(ram_data)
        modules = ram.get('modules', [])
        if modules:
            ram_info += "\n\n  Memory Modules:"
            for i, mod in enumerate(modules, 1):
                mod_data = {
                    f'Slot {i}': '',
                    '  Bank': mod.get('bank'),
                    '  Size': f"{mod.get('size', 0):.2f} GB" if mod.get('size', 0) > 0 else None,
                    '  Speed': f"{mod.get('speed')} MHz" if mod.get('speed') and mod.get('speed') != 'N/A' else None,
                    '  Manufacturer': mod.get('manufacturer'),
                    '  Model': mod.get('model'),
                    '  Serial': mod.get('serial')
                }
                ram_info += '\n' + self._format_dict(mod_data)
        self._update_text_widget(self.all_data_text_widgets['ram'], ram_info)

        # Monitors
        monitors_info = ""
        if monitors:
            for monitor in monitors:
                mon_data = {
                    'Name': monitor.get('name'),
                    'Primary': monitor.get('is_primary'),
                    'Resolution': f"{monitor.get('width', 0)} x {monitor.get('height', 0)}" if monitor.get('width', 0) > 0 else None,
                    'Aspect Ratio': monitor.get('aspect_ratio'),
                    'Physical Size (mm)': f"{monitor.get('width_mm', 0)} x {monitor.get('height_mm', 0)}" if monitor.get('width_mm', 0) and monitor.get('height_mm', 0) else None,
                    'Diagonal (inches)': monitor.get('diagonal_inches'),
                    'Pixel Density (PPI)': monitor.get('ppi'),
                    'Manufacturer': monitor.get('manufacturer'),
                    'Product Name': monitor.get('product_name'),
                    'Serial Number': monitor.get('serial')
                }
                monitors_info += self._format_dict(mon_data) + "\n"
        else:
            monitors_info = "  No monitors detected"
        self._update_text_widget(self.all_data_text_widgets['monitors'], monitors_info)

        # GPU
        gpu_info = ""
        if gpu_list:
            for i, gpu in enumerate(gpu_list, 1):
                gpu_data = {
                    f'GPU #{i}': gpu.get('name'),
                    'Memory': f"{gpu.get('memory_total', 0):.1f} GB" if gpu.get('memory_total', 0) > 0 else None,
                    'Load': f"{gpu.get('load', 0):.1f}%",
                    'Temperature': f"{gpu.get('temperature', 0):.1f} C" if gpu.get('temperature', 0) > 0 else None,
                    'Driver Version': gpu.get('driver'),
                    'Video Processor': gpu.get('video_processor'),
                    'Video Memory Type': gpu.get('video_memory_type'),
                    'Current Resolution': gpu.get('current_horizontal_res') if gpu.get('current_horizontal_res') and gpu.get('current_horizontal_res') != 'N/A' else None,
                    'Refresh Rate': gpu.get('current_refresh_rate') if gpu.get('current_refresh_rate') and gpu.get('current_refresh_rate') != 'N/A' else None,
                    'Status': gpu.get('status')
                }
                gpu_info += self._format_dict(gpu_data) + "\n"
        else:
            gpu_info = "  No GPU detected"
        self._update_text_widget(self.all_data_text_widgets['gpu'], gpu_info)

        # Storage
        disks_info = ""
        if disks:
            for disk in disks:
                disk_data = {
                    'Device': disk.get('device'),
                    'Model': disk.get('model'),
                    'Serial Number': disk.get('serial'),
                    'Type': disk.get('type'),
                    'Interface': disk.get('interface'),
                    'Filesystem': disk.get('filesystem'),
                    'Total': f"{disk.get('total', 0):.1f} GB",
                    'Used': f"{disk.get('used', 0):.1f} GB ({disk.get('percent', 0):.1f}%)",
                    'Free': f"{disk.get('free', 0):.1f} GB",
                    'Status': disk.get('status'),
                    'Temperature': f"{disk.get('temperature', 0):.1f} C" if disk.get('temperature', 0) > 0 else None
                }
                disks_info += self._format_dict(disk_data) + "\n"
        else:
            disks_info = "  No storage devices detected"
        self._update_text_widget(self.all_data_text_widgets['disks'], disks_info)

        # Network
        network_info = ""
        if network:
            for adapter in network:
                net_data = {
                    'Adapter': adapter.get('name'),
                    'Status': adapter.get('status'),
                    'Speed': adapter.get('speed'),
                    'MAC Address': adapter.get('mac'),
                    'IPv4': adapter.get('ipv4'),
                    'IPv6': adapter.get('ipv6'),
                    'Manufacturer': adapter.get('manufacturer'),
                    'Product Name': adapter.get('product_name'),
                    'Adapter Type': adapter.get('adapter_type'),
                    'Physical Adapter': adapter.get('physical_adapter')
                }
                network_info += self._format_dict(net_data) + "\n"
        else:
            network_info = "  No network adapters detected"
        self._update_text_widget(self.all_data_text_widgets['network'], network_info)

        # Temperatures
        temps_info = ""
        if temps:
            for name, temp in temps.items():
                temps_info += f"  {name:<25} : {temp:.1f} C\n"
        else:
            temps_info = "  No temperature data available"
        self._update_text_widget(self.all_data_text_widgets['temperatures'], temps_info)

        # Resource Usage
        resources_info = f"""
  CPU Load               : {data.get('cpu_load', 0):.1f}%
  RAM Usage              : {data.get('ram_percent', 0):.1f}%
  GPU Load               : {data.get('gpu_load', 0):.1f}%
  
  RAM Usage Details:
     Total: {data.get('ram_total', 0):.2f} GB     Used: {data.get('ram_used', 0):.2f} GB
  
  Temperatures:
     CPU: {data.get('cpu_temp', 0):.1f} C
     GPU: {data.get('gpu_temp', 0):.1f} C
  
  Updates                : {self.update_count}
  Uptime                 : {int((time.time() - self.start_time) // 60)} min {int((time.time() - self.start_time) % 60)} sec
"""
        self._update_text_widget(self.all_data_text_widgets['resources'], resources_info)

    def _update_text_widget(self, text_widget, content):
        if self._closing:
            return
        try:
            text_widget.configure(state="normal")
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", content)
            text_widget.configure(state="disabled")
        except Exception as e:
            pass

    # ---------- Core Monitoring ----------
    def load_initial_data(self):
        if self._closing:
            return
        try:
            self.db.start_session(self.username)
            data = self.collector.collect_all()
            self.current_data = data
            self.db.save_data(data)

            self.display_category_info(self.category_var.get(), data)
            self.update_temperatures_display(data.get('temperatures', {}))
            self.update_all_data_display(data)

            extra_sensors = self.collector.get_extra_sensors()
            self.update_extra_sensors_display(extra_sensors)

            self.update_status("Data loaded successfully", "green")
            self.refresh_db_data()
        except Exception as e:
            self.update_status(f"Error: {str(e)[:50]}", "red")

    def start_monitoring(self):
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self._animate_bars()

    def _monitoring_loop(self):
        last_db_save = time.time()
        # Интервал обновления – 0.5 секунды (по умолчанию)
        while self.running and not self._closing:
            try:
                if self._closing:
                    break
                data = self.collector.collect_all()
                if not data or self._closing:
                    break
                self.current_data = data
                self.update_count += 1
                self.target_values['CPU'] = data.get('cpu_load', 0)
                self.target_values['RAM'] = data.get('ram_percent', 0)
                self.target_values['GPU'] = data.get('gpu_load', 0)

                if not self._closing:
                    self.after(0, lambda d=data: self.update_temperatures_display(d.get('temperatures', {})))
                    self.after(0, lambda d=data: self.display_category_info(self.category_var.get(), d))
                    self.after(0, lambda d=data: self.update_all_data_display(d))

                extra_sensors = self.collector.get_extra_sensors()
                if not self._closing:
                    self.after(0, lambda s=extra_sensors: self.update_extra_sensors_display(s))

                current_time = time.time()
                if current_time - last_db_save >= 60:
                    self.db.save_data(data)
                    last_db_save = current_time

                self.update_idletasks()
            except Exception as e:
                pass

            # Задержка 0.5 секунды
            time.sleep(0.5)

    def _animate_bars(self):
        if self._closing:
            return
        smoothing = 0.3
        for key in self.progress_bars:
            diff = self.target_values[key] - self.current_values[key]
            self.current_values[key] += diff * smoothing
            value = self.current_values[key]
            self.progress_bars[key].set(min(value / 100, 1))
            self.progress_labels[key].configure(text=f"{value:.1f}%")
        after_id = self.after(30, self._animate_bars)
        self._after_ids.append(after_id)

    def refresh_info(self):
        if self.current_data:
            self.display_category_info(self.category_var.get(), self.current_data)
            self.update_status("Information refreshed", "blue")

    def bind_shortcuts(self):
        self.bind("<F5>", lambda e: self.refresh_info())
        self.bind("<Control-q>", lambda e: self.close_app(force=True))

    def update_status(self, message: str, color: str = "gray"):
        colors = {
            "green": "#90EE90",
            "red": "#FF6B6B",
            "blue": "#87CEEB",
            "orange": "#FFA500",
            "gray": "#A9A9A9"
        }
        self.status_label.configure(
            text=f"{datetime.now().strftime('%H:%M:%S')} | {message}",
            text_color=colors.get(color, "#A9A9A9")
        )

    def close_app(self, force=False):
        if not force and TRAY_AVAILABLE and not self._closing:
            if not self.tray_enabled_var.get():
                self.tray_enabled_var.set(True)
            self.withdraw()
            if not self.tray_icons:
                self.recreate_tray_icons()
            return

        self._closing = True
        self.running = False

        for after_id in self._after_ids:
            try:
                self.after_cancel(after_id)
            except:
                pass
        self._after_ids.clear()

        try:
            self.unbind_all("<MouseWheel>")
            self.unbind_all("<Button-4>")
            self.unbind_all("<Button-5>")
        except:
            pass

        try:
            self.grab_release()
        except:
            pass

        for icon in self.tray_icons:
            try:
                icon.stop()
            except:
                pass
        self.tray_icons.clear()

        if hasattr(self, 'collector'):
            try:
                self.collector.close()
            except:
                pass
        if hasattr(self, 'db'):
            try:
                self.db.close()
            except:
                pass

        try:
            self.destroy()
        except:
            pass

        threading.Timer(0.2, force_exit).start()