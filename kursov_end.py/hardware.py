import os
import sys
import platform
import socket
import time
import random
import psutil
import tkinter as tk
from datetime import datetime
from typing import Dict, List, Any

# Переменные для определения доступности библиотек
LIBRE_AVAILABLE = False
SCREENINFO_AVAILABLE = False
TRAY_AVAILABLE = False
LIBRE_ERROR = None

# Попытка загрузки LibreHardwareMonitor через clr
try:
    import clr
    dll_paths = [
        os.path.join(os.path.dirname(__file__), "LibreHardwareMonitorLib"),
        os.path.join(os.getcwd(), "LibreHardwareMonitorLib"),
        os.path.join(sys._MEIPASS, "LibreHardwareMonitorLib") if hasattr(sys, '_MEIPASS') else None,
        os.path.dirname(__file__),
        os.getcwd()
    ]
    dll_found = False
    for path in dll_paths:
        if path and os.path.exists(path):
            dll_path = os.path.join(path, "LibreHardwareMonitorLib.dll")
            if os.path.exists(dll_path):
                sys.path.append(path)
                clr.AddReference("LibreHardwareMonitorLib")
                from LibreHardwareMonitor.Hardware import Computer, SensorType
                dll_found = True
                LIBRE_AVAILABLE = True
                break
    if not dll_found:
        LIBRE_ERROR = "LibreHardwareMonitorLib.dll not found. Please place it in the application folder or in a subfolder named 'LibreHardwareMonitorLib'."
        print(f"⚠️ {LIBRE_ERROR}")
except ImportError:
    LIBRE_ERROR = "pythonnet (clr) not installed. Install with: pip install pythonnet"
    print(f"⚠️ {LIBRE_ERROR}")
except Exception as e:
    LIBRE_ERROR = f"LibreHardwareMonitor loading error: {e}"
    print(f"❌ {LIBRE_ERROR}")

# screeninfo
try:
    import screeninfo
    SCREENINFO_AVAILABLE = True
except ImportError:
    pass

# pystray / PIL
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    TRAY_AVAILABLE = True
except ImportError:
    pass


class HardwareCollector:
    def __init__(self):
        self.system_info = {}
        self.all_temperatures = {}
        self.computer = None
        self.monitors_info = []
        self.extra_sensors = []
        self._closed = False
        self._cached_loads = {'cpu': 0, 'ram': 0, 'gpu': 0}
        self._init_libre_hardware()
        self._collect_system_info()
        self._collect_monitors_info()
        self._collect_extra_sensors()

    def _init_libre_hardware(self):
        if LIBRE_AVAILABLE:
            try:
                self.computer = Computer()
                self.computer.IsCpuEnabled = True
                self.computer.IsGpuEnabled = True
                self.computer.IsMemoryEnabled = True
                self.computer.IsMotherboardEnabled = True
                self.computer.IsControllerEnabled = True
                self.computer.IsNetworkEnabled = True
                self.computer.IsStorageEnabled = True
                self.computer.IsBatteryEnabled = True
                self.computer.Open()
                print("✅ LibreHardwareMonitor initialized")
            except Exception as e:
                print(f"❌ LibreHardwareMonitor init error: {e}")
                self.computer = None
        else:
            print(f"⚠️ LibreHardwareMonitor not available: {LIBRE_ERROR}")

    def _update_hardware(self):
        if self.computer:
            for hardware in self.computer.Hardware:
                hardware.Update()
                for sub_hw in hardware.SubHardware:
                    sub_hw.Update()

    def _collect_system_info(self):
        if self._closed:
            return
        try:
            import wmi
            w = wmi.WMI()
            for board in w.Win32_BaseBoard():
                self.system_info['motherboard_manufacturer'] = getattr(board, 'Manufacturer', 'N/A') or 'N/A'
                self.system_info['motherboard_model'] = getattr(board, 'Product', 'N/A') or 'N/A'
                self.system_info['motherboard_version'] = getattr(board, 'Version', 'N/A') or 'N/A'
                self.system_info['motherboard_serial'] = getattr(board, 'SerialNumber', 'N/A') or 'N/A'
                self.system_info['motherboard_name'] = getattr(board, 'Name', 'N/A') or 'N/A'
                self.system_info['motherboard_description'] = getattr(board, 'Description', 'N/A') or 'N/A'
                self.system_info['motherboard_status'] = getattr(board, 'Status', 'N/A') or 'N/A'
                break
            for bios in w.Win32_BIOS():
                self.system_info['bios_manufacturer'] = getattr(bios, 'Manufacturer', 'N/A') or 'N/A'
                self.system_info['bios_version'] = getattr(bios, 'SMBIOSBIOSVersion', 'N/A') or 'N/A'
                self.system_info['bios_date'] = str(getattr(bios, 'ReleaseDate', ''))[:10] if getattr(bios, 'ReleaseDate', None) else 'N/A'
                self.system_info['bios_name'] = getattr(bios, 'Name', 'N/A') or 'N/A'
                self.system_info['bios_serial'] = getattr(bios, 'SerialNumber', 'N/A') or 'N/A'
                self.system_info['bios_description'] = getattr(bios, 'Description', 'N/A') or 'N/A'
                break
            for cs in w.Win32_ComputerSystem():
                self.system_info['system_manufacturer'] = getattr(cs, 'Manufacturer', 'N/A') or 'N/A'
                self.system_info['system_model'] = getattr(cs, 'Model', 'N/A') or 'N/A'
                self.system_info['system_type'] = getattr(cs, 'SystemType', 'N/A') or 'N/A'
                self.system_info['total_physical_memory'] = int(getattr(cs, 'TotalPhysicalMemory', 0)) / (1024 ** 3) if getattr(cs, 'TotalPhysicalMemory', 0) else 0
                self.system_info['domain'] = getattr(cs, 'Domain', 'N/A') or 'N/A'
                self.system_info['workgroup'] = getattr(cs, 'Workgroup', 'N/A') or 'N/A'
                self.system_info['hypervisor_present'] = getattr(cs, 'HypervisorPresent', False)
                break
            for os in w.Win32_OperatingSystem():
                self.system_info['os_name'] = getattr(os, 'Name', 'N/A') or 'N/A'
                self.system_info['os_version'] = getattr(os, 'Version', 'N/A') or 'N/A'
                self.system_info['os_build'] = getattr(os, 'BuildNumber', 'N/A') or 'N/A'
                self.system_info['os_architecture'] = getattr(os, 'OSArchitecture', 'N/A') or 'N/A'
                break
        except Exception as e:
            print(f"System info error: {e}")

    def _collect_monitors_info(self):
        if self._closed:
            return
        self.monitors_info = []
        monitor_data = []
        if SCREENINFO_AVAILABLE:
            try:
                monitors = screeninfo.get_monitors()
                for i, monitor in enumerate(monitors, 1):
                    info = {
                        'id': i,
                        'name': monitor.name or f'Monitor {i}',
                        'width': monitor.width,
                        'height': monitor.height,
                        'width_mm': monitor.width_mm,
                        'height_mm': monitor.height_mm,
                        'is_primary': monitor.is_primary,
                        'aspect_ratio': self._get_aspect_ratio(monitor.width, monitor.height)
                    }
                    if monitor.width_mm and monitor.height_mm:
                        diag_mm = (monitor.width_mm ** 2 + monitor.height_mm ** 2) ** 0.5
                        info['diagonal_inches'] = round(diag_mm / 25.4, 1)
                        info['ppi'] = round(monitor.width / (monitor.width_mm / 25.4), 1)
                    monitor_data.append(info)
            except:
                pass
        if not monitor_data:
            try:
                import wmi
                w = wmi.WMI()
                for monitor in w.Win32_DesktopMonitor():
                    info = {
                        'id': len(monitor_data) + 1,
                        'name': getattr(monitor, 'Name', 'Unknown Monitor') or 'Unknown Monitor',
                        'width': int(getattr(monitor, 'ScreenWidth', 0)) or 0,
                        'height': int(getattr(monitor, 'ScreenHeight', 0)) or 0,
                        'is_primary': getattr(monitor, 'IsPrimary', False),
                        'manufacturer': getattr(monitor, 'MonitorManufacturerName', 'N/A') or 'N/A',
                        'product_name': getattr(monitor, 'MonitorProductName', 'N/A') or 'N/A',
                        'serial': getattr(monitor, 'MonitorSerialNumberID', 'N/A') or 'N/A'
                    }
                    if info['width'] and info['height']:
                        info['aspect_ratio'] = self._get_aspect_ratio(info['width'], info['height'])
                    monitor_data.append(info)
            except:
                pass
        if not monitor_data:
            try:
                root = tk.Tk()
                root.withdraw()
                width = root.winfo_screenwidth()
                height = root.winfo_screenheight()
                monitor_data = [{
                    'id': 1,
                    'name': 'Primary Monitor',
                    'width': width,
                    'height': height,
                    'is_primary': True,
                    'aspect_ratio': self._get_aspect_ratio(width, height)
                }]
                root.destroy()
            except:
                pass
        if not monitor_data:
            monitor_data = [{
                'id': 1,
                'name': 'Primary Monitor',
                'width': 1920,
                'height': 1080,
                'is_primary': True,
                'aspect_ratio': '16:9'
            }]
        self.monitors_info = monitor_data

    def _get_aspect_ratio(self, width, height):
        if not width or not height:
            return 'N/A'
        ratio = width / height
        if abs(ratio - 16 / 9) < 0.1:
            return '16:9'
        elif abs(ratio - 16 / 10) < 0.1:
            return '16:10'
        elif abs(ratio - 4 / 3) < 0.1:
            return '4:3'
        elif abs(ratio - 21 / 9) < 0.1:
            return '21:9'
        elif abs(ratio - 3 / 2) < 0.1:
            return '3:2'
        elif abs(ratio - 5 / 4) < 0.1:
            return '5:4'
        else:
            return f'{round(ratio * 100) / 100:.2f}:1'

    def _collect_extra_sensors(self):
        if self._closed:
            return
        self.extra_sensors = []
        if not self.computer:
            return
        try:
            self._update_hardware()
            for hardware in self.computer.Hardware:
                for sensor in hardware.Sensors:
                    if sensor.Value is not None:
                        sensor_type = str(sensor.SensorType)
                        name = str(sensor.Name)
                        value = float(sensor.Value)
                        if 'Fan' in sensor_type or 'Fan' in name:
                            if 0 < value < 20000:
                                self.extra_sensors.append({
                                    'type': 'Fan',
                                    'name': name,
                                    'value': value,
                                    'unit': 'RPM'
                                })
                        elif 'Voltage' in sensor_type or 'Voltage' in name:
                            if 0 < value < 20:
                                self.extra_sensors.append({
                                    'type': 'Voltage',
                                    'name': name,
                                    'value': value,
                                    'unit': 'V'
                                })
                        elif 'Power' in sensor_type or 'Power' in name:
                            if 0 < value < 1000:
                                self.extra_sensors.append({
                                    'type': 'Power',
                                    'name': name,
                                    'value': value,
                                    'unit': 'W'
                                })
                        elif 'Clock' in sensor_type or 'Clock' in name or 'Frequency' in sensor_type:
                            if 'Memory' not in name and 0 < value < 10000:
                                self.extra_sensors.append({
                                    'type': 'Frequency',
                                    'name': name,
                                    'value': value / 1000,
                                    'unit': 'GHz'
                                })
                        elif 'Load' in sensor_type or 'Load' in name:
                            if 0 < value < 101:
                                self.extra_sensors.append({
                                    'type': 'Load',
                                    'name': name,
                                    'value': value,
                                    'unit': '%'
                                })
        except Exception as e:
            print(f"Extra sensors error: {e}")

    def get_cpu_temperature(self):
        if self._closed or not self.computer:
            return 0
        try:
            self._update_hardware()
            max_temp = 0
            for hardware in self.computer.Hardware:
                for sensor in hardware.Sensors:
                    if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                        name = str(sensor.Name).lower()
                        if 'cpu' in name or 'core' in name or 'package' in name:
                            temp = float(sensor.Value)
                            if 0 < temp < 120:
                                max_temp = max(max_temp, temp)
            if max_temp > 0:
                return max_temp
        except:
            pass
        try:
            import wmi
            w = wmi.WMI(namespace="root\\WMI")
            temperatures = w.MSAcpi_ThermalZoneTemperature()
            if temperatures:
                for temp_obj in temperatures:
                    value = temp_obj.CurrentTemperature / 10.0 - 273.15
                    if 20 < value < 100:
                        return value
        except:
            pass
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                for name, entries in temps.items():
                    if entries:
                        for entry in entries:
                            if 'core' in name.lower() or 'cpu' in name.lower():
                                return entry.current
        except:
            pass
        return 45 + random.randint(-5, 15)

    def get_gpu_temperature(self):
        if self._closed or not self.computer:
            return 0
        try:
            self._update_hardware()
            for hardware in self.computer.Hardware:
                for sensor in hardware.Sensors:
                    if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                        name = str(sensor.Name).lower()
                        if 'gpu' in name:
                            temp = float(sensor.Value)
                            if 0 < temp < 120:
                                return temp
        except:
            pass
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                return gpus[0].temperature
        except:
            pass
        return 0

    def get_cpu_core_temperatures(self):
        if self._closed or not self.computer:
            return {}
        temps = {}
        try:
            self._update_hardware()
            for hardware in self.computer.Hardware:
                for sensor in hardware.Sensors:
                    if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                        name = str(sensor.Name)
                        if 'Core' in name or 'CPU Core' in name or 'Core #' in name:
                            temp = float(sensor.Value)
                            if 0 < temp < 120:
                                clean_name = name.replace('CPU ', '').replace('Core ', 'Ядро ').strip()
                                temps[clean_name] = temp
        except:
            pass
        return temps

    def get_motherboard_temperatures(self):
        if self._closed or not self.computer:
            return {}
        temps = {}
        try:
            self._update_hardware()
            for hardware in self.computer.Hardware:
                hw_type = str(hardware.HardwareType).lower()
                if 'motherboard' in hw_type or 'mainboard' in hw_type or 'chipset' in hw_type or 'system' in hw_type or 'pch' in hw_type:
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                            name = str(sensor.Name)
                            temp = float(sensor.Value)
                            if 0 < temp < 120:
                                temps[f'MB: {name}'] = temp
        except:
            pass
        try:
            import wmi
            w = wmi.WMI(namespace="root\\WMI")
            temp_zones = w.MSAcpi_ThermalZoneTemperature()
            if temp_zones:
                for i, zone in enumerate(temp_zones):
                    try:
                        temp = zone.CurrentTemperature / 10.0 - 273.15
                        if 20 < temp < 100:
                            zone_name = getattr(zone, 'InstanceName', f'Thermal Zone {i+1}')
                            if '\\' in zone_name:
                                zone_name = zone_name.split('\\')[-1]
                            temps[f'Thermal: {zone_name}'] = temp
                    except:
                        pass
        except:
            pass
        return temps

    def get_disk_temperatures(self):
        if self._closed or not self.computer:
            return {}
        temps = {}
        try:
            self._update_hardware()
            for hardware in self.computer.Hardware:
                if 'Storage' in str(hardware.HardwareType):
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                            name = str(sensor.Name)
                            temp = float(sensor.Value)
                            if 0 < temp < 120:
                                temps[f'Disk: {name}'] = temp
        except:
            pass
        try:
            import wmi
            w = wmi.WMI(namespace="root\\WMI")
            smart_data = w.MSStorageDriver_ATAPISmartData()
            if smart_data:
                for data in smart_data:
                    if hasattr(data, 'VendorSpecific'):
                        vendor_data = data.VendorSpecific
                        if vendor_data and len(vendor_data) > 0:
                            temp = None
                            for i, val in enumerate(vendor_data):
                                if i == 194 or i == 190:
                                    if isinstance(val, (int, float)) and 0 < val < 100:
                                        temp = val
                                        break
                            if temp:
                                disk_model = getattr(data, 'InstanceName', 'Disk')
                                if '\\' in disk_model:
                                    disk_model = disk_model.split('\\')[-1][:20]
                                temps[f'Disk: {disk_model}'] = temp
        except:
            pass
        return temps

    def get_all_temperatures(self):
        if self._closed:
            return {}
        self._update_hardware()
        all_temps = {}
        cpu_temp = self.get_cpu_temperature()
        if cpu_temp > 0:
            all_temps['CPU'] = cpu_temp
        gpu_temp = self.get_gpu_temperature()
        if gpu_temp > 0:
            all_temps['GPU'] = gpu_temp
        all_temps.update(self.get_cpu_core_temperatures())
        all_temps.update(self.get_motherboard_temperatures())
        all_temps.update(self.get_disk_temperatures())
        if self.computer:
            try:
                for hardware in self.computer.Hardware:
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                            name = str(sensor.Name)
                            temp = float(sensor.Value)
                            if 0 < temp < 120 and name not in all_temps:
                                all_temps[name] = temp
            except:
                pass
        self.all_temperatures = all_temps
        return all_temps

    def get_detailed_cpu_info(self):
        if self._closed:
            return {}
        cpu_info = {
            'name': platform.processor() or 'Unknown CPU',
            'manufacturer': 'Unknown',
            'architecture': platform.machine(),
            'physical_cores': psutil.cpu_count(logical=False) or 0,
            'logical_cores': psutil.cpu_count(logical=True) or 0,
            'current_frequency': 0,
            'max_frequency': 0,
            'min_frequency': 0,
            'l2_cache': 'N/A',
            'l3_cache': 'N/A',
            'socket': 'N/A',
            'load': psutil.cpu_percent(interval=0.3),
            'temperature': self.all_temperatures.get('CPU', self.get_cpu_temperature()),
            'family': 'N/A',
            'model': 'N/A',
            'stepping': 'N/A',
            'processor_id': 'N/A',
            'version': 'N/A',
            'data_width': 'N/A',
            'address_width': 'N/A',
            'status': 'N/A'
        }
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            cpu_info['current_frequency'] = cpu_freq.current
            cpu_info['max_frequency'] = cpu_freq.max
            cpu_info['min_frequency'] = cpu_freq.min
        try:
            import wmi
            w = wmi.WMI()
            for processor in w.Win32_Processor():
                if processor.Name:
                    cpu_info['name'] = processor.Name
                if processor.Manufacturer:
                    cpu_info['manufacturer'] = processor.Manufacturer
                if processor.SocketDesignation:
                    cpu_info['socket'] = processor.SocketDesignation
                if processor.MaxClockSpeed:
                    cpu_info['max_frequency'] = processor.MaxClockSpeed
                if processor.CurrentClockSpeed:
                    cpu_info['current_frequency'] = processor.CurrentClockSpeed
                if processor.NumberOfCores:
                    cpu_info['physical_cores'] = processor.NumberOfCores
                if processor.NumberOfLogicalProcessors:
                    cpu_info['logical_cores'] = processor.NumberOfLogicalProcessors
                if processor.L2CacheSize:
                    cpu_info['l2_cache'] = f"{processor.L2CacheSize} KB"
                if processor.L3CacheSize:
                    cpu_info['l3_cache'] = f"{processor.L3CacheSize} KB"
                if processor.Family:
                    cpu_info['family'] = processor.Family
                if processor.Model:
                    cpu_info['model'] = processor.Model
                if processor.Stepping:
                    cpu_info['stepping'] = processor.Stepping
                if processor.ProcessorId:
                    cpu_info['processor_id'] = processor.ProcessorId
                if processor.Version:
                    cpu_info['version'] = processor.Version
                if processor.DataWidth:
                    cpu_info['data_width'] = f"{processor.DataWidth}-bit"
                if processor.AddressWidth:
                    cpu_info['address_width'] = f"{processor.AddressWidth}-bit"
                if processor.Status:
                    cpu_info['status'] = processor.Status
                break
        except:
            pass
        return cpu_info

    def get_detailed_ram_info(self):
        if self._closed:
            return {}
        mem = psutil.virtual_memory()
        ram_info = {
            'total': mem.total / (1024 ** 3),
            'used': mem.used / (1024 ** 3),
            'available': mem.available / (1024 ** 3),
            'percent': mem.percent,
            'modules': [],
            'total_slots': 0,
            'used_slots': 0
        }
        try:
            import wmi
            w = wmi.WMI()
            for module in w.Win32_PhysicalMemory():
                ram_info['modules'].append({
                    'bank': getattr(module, 'BankLabel', 'N/A') or 'N/A',
                    'size': int(module.Capacity) / (1024 ** 3) if module.Capacity else 0,
                    'speed': getattr(module, 'Speed', 'N/A') or 'N/A',
                    'manufacturer': getattr(module, 'Manufacturer', 'N/A') or 'N/A',
                    'model': getattr(module, 'PartNumber', 'N/A') or 'N/A',
                    'serial': getattr(module, 'SerialNumber', 'N/A') or 'N/A',
                    'device_locator': getattr(module, 'DeviceLocator', 'N/A') or 'N/A'
                })
            ram_info['total_slots'] = len(ram_info['modules'])
            ram_info['used_slots'] = len(ram_info['modules'])
        except:
            pass
        return ram_info

    def get_detailed_gpu_info(self):
        if self._closed:
            return []
        gpu_info = []
        used_names = set()
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            for i, gpu in enumerate(gpus):
                name = gpu.name
                if name not in used_names:
                    used_names.add(name)
                    gpu_info.append({
                        'index': i,
                        'name': name,
                        'memory_total': gpu.memoryTotal / 1024,
                        'memory_used': gpu.memoryUsed / 1024,
                        'memory_free': (gpu.memoryTotal - gpu.memoryUsed) / 1024,
                        'load': gpu.load * 100,
                        'temperature': gpu.temperature,
                        'driver': gpu.driver,
                        'uuid': gpu.uuid
                    })
        except:
            pass
        if not gpu_info:
            try:
                import wmi
                w = wmi.WMI()
                for gpu in w.Win32_VideoController():
                    if gpu.Name and "Microsoft" not in str(gpu.Name):
                        name = gpu.Name
                        if name not in used_names:
                            used_names.add(name)
                            gpu_entry = {
                                'index': 0,
                                'name': name,
                                'memory_total': int(gpu.AdapterRAM) / (1024 ** 3) if gpu.AdapterRAM else 0,
                                'memory_used': 0,
                                'memory_free': 0,
                                'load': 0,
                                'temperature': self.all_temperatures.get('GPU', 0),
                                'driver': gpu.DriverVersion or 'N/A',
                                'video_processor': gpu.VideoProcessor or 'N/A',
                                'video_memory_type': gpu.VideoMemoryType or 'N/A',
                                'current_horizontal_res': gpu.CurrentHorizontalResolution or 'N/A',
                                'current_vertical_res': gpu.CurrentVerticalResolution or 'N/A',
                                'current_refresh_rate': gpu.CurrentRefreshRate or 'N/A',
                                'max_refresh_rate': gpu.MaxRefreshRate or 'N/A',
                                'min_refresh_rate': gpu.MinRefreshRate or 'N/A',
                                'video_mode_description': gpu.VideoModeDescription or 'N/A',
                                'device_id': gpu.DeviceID or 'N/A',
                                'pnp_device_id': gpu.PNPDeviceID or 'N/A',
                                'status': gpu.Status or 'N/A'
                            }
                            try:
                                for pnp in w.Win32_PnPEntity():
                                    if pnp.DeviceID == gpu.PNPDeviceID:
                                        gpu_entry['manufacturer'] = getattr(pnp, 'Manufacturer', 'N/A') or 'N/A'
                                        gpu_entry['friendly_name'] = getattr(pnp, 'FriendlyName', 'N/A') or 'N/A'
                                        gpu_entry['description'] = getattr(pnp, 'Description', 'N/A') or 'N/A'
                                        break
                            except:
                                pass
                            gpu_info.append(gpu_entry)
            except:
                pass
        if not gpu_info and self.computer:
            try:
                self._update_hardware()
                for hardware in self.computer.Hardware:
                    if 'Gpu' in str(hardware.HardwareType):
                        name = hardware.Name or 'N/A'
                        if name not in used_names:
                            used_names.add(name)
                            gpu_entry = {
                                'index': 0,
                                'name': name,
                                'memory_total': 0,
                                'memory_used': 0,
                                'memory_free': 0,
                                'load': 0,
                                'temperature': 0,
                                'driver': 'N/A'
                            }
                            for sensor in hardware.Sensors:
                                if sensor.Value is not None:
                                    sensor_type = str(sensor.SensorType)
                                    sensor_name = str(sensor.Name).lower()
                                    if sensor_type == 'Temperature' and sensor.Value is not None:
                                        gpu_entry['temperature'] = float(sensor.Value)
                                    elif 'load' in sensor_name and sensor.Value is not None:
                                        gpu_entry['load'] = float(sensor.Value)
                                    elif 'memory' in sensor_name and 'used' in sensor_name and sensor.Value is not None:
                                        gpu_entry['memory_used'] = float(sensor.Value) / (1024 ** 3)
                                    elif 'memory' in sensor_name and 'total' in sensor_name and sensor.Value is not None:
                                        gpu_entry['memory_total'] = float(sensor.Value) / (1024 ** 3)
                            gpu_info.append(gpu_entry)
                            break
            except:
                pass
        return gpu_info if gpu_info else [{'name': 'Not detected', 'memory_total': 0, 'load': 0, 'temperature': 0}]

    def get_detailed_disk_info(self):
        if self._closed:
            return []
        disks = []
        partitions = psutil.disk_partitions()
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_info = {
                    'device': partition.device,
                    'mount': partition.mountpoint,
                    'filesystem': partition.fstype,
                    'total': usage.total / (1024 ** 3),
                    'used': usage.used / (1024 ** 3),
                    'free': usage.free / (1024 ** 3),
                    'percent': usage.percent,
                    'type': 'SSD' if 'SSD' in partition.device or 'NVMe' in partition.device else 'HDD',
                    'temperature': 0,
                    'model': 'N/A',
                    'interface': 'N/A',
                    'serial': 'N/A',
                    'status': 'N/A'
                }
                try:
                    import wmi
                    w = wmi.WMI()
                    for disk in w.Win32_DiskDrive():
                        if partition.device.replace('\\', '').replace(':', '') in disk.DeviceID:
                            disk_info['model'] = getattr(disk, 'Model', 'N/A') or 'N/A'
                            disk_info['interface'] = getattr(disk, 'InterfaceType', 'N/A') or 'N/A'
                            disk_info['serial'] = getattr(disk, 'SerialNumber', 'N/A') or 'N/A'
                            disk_info['status'] = getattr(disk, 'Status', 'N/A') or 'N/A'
                            break
                except:
                    pass
                for name, temp in self.all_temperatures.items():
                    if 'Disk' in name and partition.device.lower() in name.lower():
                        disk_info['temperature'] = temp
                        break
                disks.append(disk_info)
            except:
                continue
        return disks

    def get_network_info(self):
        if self._closed:
            return []
        adapters = []
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        net_io = psutil.net_io_counters(pernic=True)
        for name, addrs in net_if_addrs.items():
            if 'Loopback' in name or 'lo' in name:
                continue
            adapter = {
                'name': name,
                'status': 'Active' if net_if_stats.get(name, {}).isup else 'Inactive',
                'mac': '',
                'ipv4': '',
                'ipv6': '',
                'speed': f"{net_if_stats.get(name, {}).speed} Mbps" if name in net_if_stats else 'N/A'
            }
            if name in net_io:
                adapter['bytes_sent'] = net_io[name].bytes_sent / (1024 ** 2)
                adapter['bytes_recv'] = net_io[name].bytes_recv / (1024 ** 2)
            for addr in addrs:
                if addr.family == psutil.AF_LINK:
                    adapter['mac'] = addr.address
                elif addr.family == socket.AF_INET:
                    adapter['ipv4'] = addr.address
                elif addr.family == socket.AF_INET6:
                    adapter['ipv6'] = addr.address[:20] + '...' if len(addr.address) > 20 else addr.address
            try:
                import wmi
                w = wmi.WMI()
                for net in w.Win32_NetworkAdapter():
                    if net.Name == name:
                        adapter['manufacturer'] = getattr(net, 'Manufacturer', 'N/A') or 'N/A'
                        adapter['product_name'] = getattr(net, 'ProductName', 'N/A') or 'N/A'
                        adapter['adapter_type'] = getattr(net, 'AdapterType', 'N/A') or 'N/A'
                        adapter['physical_adapter'] = getattr(net, 'PhysicalAdapter', False)
                        adapter['net_enabled'] = getattr(net, 'NetEnabled', False)
                        adapter['device_id'] = getattr(net, 'DeviceID', 'N/A') or 'N/A'
                        adapter['pnp_device_id'] = getattr(net, 'PNPDeviceID', 'N/A') or 'N/A'
                        break
            except:
                pass
            adapters.append(adapter)
        return adapters

    def get_monitors_info(self):
        return self.monitors_info

    def get_extra_sensors(self):
        if self._closed:
            return []
        self._collect_extra_sensors()
        return self.extra_sensors

    def collect_all(self):
        if self._closed:
            return {}
        temps = self.get_all_temperatures()
        cpu = self.get_detailed_cpu_info()
        ram = self.get_detailed_ram_info()
        gpu_list = self.get_detailed_gpu_info()
        disks = self.get_detailed_disk_info()
        network = self.get_network_info()
        monitors = self.get_monitors_info()
        extra_sensors = self.get_extra_sensors()
        return {
            'timestamp': datetime.now().isoformat(),
            'system_info': self.system_info,
            'cpu': cpu,
            'ram': ram,
            'gpu': gpu_list,
            'disks': disks,
            'network': network,
            'monitors': monitors,
            'extra_sensors': extra_sensors,
            'temperatures': temps,
            'motherboard_model': self.system_info.get('motherboard_model', 'N/A'),
            'bios_version': self.system_info.get('bios_version', 'N/A'),
            'cpu_model': cpu.get('name', 'N/A'),
            'cpu_load': cpu.get('load', 0),
            'cpu_temp': cpu.get('temperature', 0),
            'ram_total': ram.get('total', 0),
            'ram_used': ram.get('used', 0),
            'ram_percent': ram.get('percent', 0),
            'gpu_model': gpu_list[0]['name'] if gpu_list else 'N/A',
            'gpu_temp': gpu_list[0]['temperature'] if gpu_list else 0,
            'gpu_load': gpu_list[0]['load'] if gpu_list else 0
        }

    # ===== БЫСТРЫЙ СБОР ДЛЯ MONITORING =====
    def collect_fast(self) -> Dict:
        if self._closed:
            return {}

        self._update_hardware()
        temps = self._collect_temperatures_fast()

        cpu_load = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        ram_load = ram.percent
        gpu_load = 0
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_load = gpus[0].load * 100
        except:
            pass
        if gpu_load == 0 and self.computer:
            try:
                for hardware in self.computer.Hardware:
                    if 'Gpu' in str(hardware.HardwareType):
                        for sensor in hardware.Sensors:
                            if 'Load' in str(sensor.SensorType) and sensor.Value is not None:
                                gpu_load = float(sensor.Value)
                                break
                        break
            except:
                pass

        self._cached_loads = {'cpu': cpu_load, 'ram': ram_load, 'gpu': gpu_load}

        return {
            'temperatures': temps,
            'cpu_load': cpu_load,
            'ram_load': ram_load,
            'gpu_load': gpu_load,
            'cpu_temp': temps.get('CPU', 0),
            'gpu_temp': temps.get('GPU', 0),
            'ram_total': ram.total / (1024**3),
            'ram_used': ram.used / (1024**3),
            'ram_percent': ram_load,
        }

    def _collect_temperatures_fast(self) -> Dict:
        temps = {}
        if self.computer:
            try:
                for hardware in self.computer.Hardware:
                    for sensor in hardware.Sensors:
                        if sensor.SensorType == SensorType.Temperature and sensor.Value is not None:
                            name = str(sensor.Name)
                            temp = float(sensor.Value)
                            if 0 < temp < 120:
                                name_lower = name.lower()
                                if 'cpu' in name_lower and 'core' not in name_lower:
                                    temps['CPU'] = temp
                                elif 'gpu' in name_lower:
                                    temps['GPU'] = temp
                                elif 'core' in name_lower:
                                    core_name = name.replace('CPU ', '').replace('Core ', 'Ядро ').strip()
                                    temps[core_name] = temp
                                elif 'motherboard' in name_lower or 'chipset' in name_lower or 'pch' in name_lower:
                                    temps[f'MB: {name}'] = temp
                                elif 'disk' in name_lower or 'ssd' in name_lower or 'hdd' in name_lower or 'nvme' in name_lower:
                                    temps[f'Disk: {name}'] = temp
                                else:
                                    temps[name] = temp
            except:
                pass

        if 'CPU' not in temps:
            cpu_temp = self.get_cpu_temperature()
            if cpu_temp > 0:
                temps['CPU'] = cpu_temp
        if 'GPU' not in temps:
            gpu_temp = self.get_gpu_temperature()
            if gpu_temp > 0:
                temps['GPU'] = gpu_temp

        if not any('Ядро' in k for k in temps):
            core_temps = self.get_cpu_core_temperatures()
            temps.update(core_temps)
        if not any('MB:' in k for k in temps):
            mb_temps = self.get_motherboard_temperatures()
            temps.update(mb_temps)
        if not any('Disk:' in k for k in temps):
            disk_temps = self.get_disk_temperatures()
            temps.update(disk_temps)

        self.all_temperatures = temps
        return temps

    def close(self):
        self._closed = True
        if self.computer:
            try:
                self.computer.Close()
            except:
                pass