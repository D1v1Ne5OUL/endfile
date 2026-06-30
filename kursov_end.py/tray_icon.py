import threading
import time
from PIL import Image, ImageDraw, ImageFont
import pystray
from utils import get_icon_path


class TrayIconSingle:
    def __init__(self, app, metric, update_interval=2):
        self.app = app
        self.metric = metric
        self.update_interval = update_interval
        self.icon = None
        self.running = False
        self.thread = None

    def create_image(self, value):
        width, height = 64, 64
        colors = {
            'cpu': (0, 150, 0),
            'ram': (0, 80, 200),
            'gpu': (200, 100, 0)
        }
        bg_color = colors.get(self.metric, (30, 30, 30))
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        try:
            icon_path = get_icon_path('app_icon.png')
            if icon_path:
                app_icon = Image.open(icon_path)
                app_icon = app_icon.resize((32, 32), Image.Resampling.LANCZOS)
                if app_icon.mode != 'RGB':
                    app_icon = app_icon.convert('RGB')
                x = (width - 32) // 2
                y = (height - 32) // 2
                image.paste(app_icon, (x, y))
        except:
            pass
        
        text = f"{value:.0f}"
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x+1, y+1), text, fill=(0, 0, 0), font=font)
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
        return image

    def update_icon(self):
        if not self.icon:
            return
        value = self.app.current_values.get(self.metric.upper(), 0)
        img = self.create_image(value)
        self.icon.icon = img
        self.icon.title = f"{self.metric.upper()}: {value:.1f}%"

    def run(self):
        def on_click(icon, item):
            if str(item) == "Show":
                self.app.show_window()
            elif str(item) == "Exit":
                self.app.quit_app()

        menu = pystray.Menu(
            pystray.MenuItem("Show", lambda: self.app.show_window()),
            pystray.MenuItem("Exit", lambda: self.app.quit_app())
        )
        img = self.create_image(0)
        self.icon = pystray.Icon(f"system_monitor_{self.metric}", img, f"{self.metric.upper()} Monitor", menu)
        self.running = True

        def update_loop():
            while self.running:
                self.update_icon()
                time.sleep(self.update_interval)

        self.thread = threading.Thread(target=update_loop, daemon=True)
        self.thread.start()
        self.icon.run()

    def stop(self):
        self.running = False
        if self.icon:
            self.icon.stop()
        if self.thread:
            self.thread.join(timeout=1)