import os
import sys
import tkinter as tk
import signal


def get_icon_path(filename='app_icon.ico'):
    search_paths = [
        os.path.dirname(__file__),
        os.getcwd(),
        os.path.join(os.path.dirname(__file__), 'assets'),
        os.path.join(os.path.dirname(__file__), 'icons'),
        os.path.join(os.path.dirname(__file__), 'resources'),
        os.path.join(os.path.dirname(__file__), 'images'),
    ]
    
    if getattr(sys, 'frozen', False):
        search_paths.append(sys._MEIPASS)
    
    for path in search_paths:
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            return full_path
    
    if filename.endswith('.ico'):
        png_path = get_icon_path(filename.replace('.ico', '.png'))
        if png_path:
            return png_path
    
    return None


def set_window_icon(window, icon_name='app_icon.ico'):
    try:
        icon_path = get_icon_path(icon_name)
        if not icon_path:
            return False
        
        if sys.platform == 'win32':
            window.iconbitmap(default=icon_path)
            return True
        else:
            png_path = get_icon_path('app_icon.png')
            if png_path:
                icon_img = tk.PhotoImage(file=png_path)
                window.iconphoto(True, icon_img)
                window._icon_image = icon_img
                return True
            else:
                try:
                    icon_img = tk.PhotoImage(file=icon_path)
                    window.iconphoto(True, icon_img)
                    window._icon_image = icon_img
                    return True
                except:
                    pass
    except Exception as e:
        print(f"Error setting icon: {e}")
    return False


def force_exit():
    os._exit(0)


def signal_handler(sig, frame):
    os._exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


USERS = {"a": "1"}