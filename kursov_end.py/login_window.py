import customtkinter as ctk
from utils import USERS, set_window_icon


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Login - System Monitor")
        self.geometry("450x400")
        self.resizable(False, False)
        
        set_window_icon(self)
        
        self.center_window()
        
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=40, pady=30)
        
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="BAIDA64",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=(0, 10))
        
        self.subtitle_label = ctk.CTkLabel(
            self.main_frame,
            text="Professional System Monitoring",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.subtitle_label.pack(pady=(0, 30))
        
        self.username_entry = ctk.CTkEntry(
            self.main_frame,
            placeholder_text="Username",
            width=350,
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.username_entry.pack(pady=(0, 15))
        
        self.password_entry = ctk.CTkEntry(
            self.main_frame,
            placeholder_text="Password",
            show="*",
            width=350,
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.password_entry.pack(pady=(0, 20))
        
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=10)
        
        self.login_btn = ctk.CTkButton(
            self.button_frame,
            text="Login",
            command=self.login,
            height=40,
            fg_color="#2E8B57",
            hover_color="#3CB371",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.login_btn.pack(side="left", padx=(0, 10), expand=True, fill="x")
        
        self.exit_btn = ctk.CTkButton(
            self.button_frame,
            text="Exit",
            command=self.destroy,
            height=40,
            fg_color="#8B0000",
            hover_color="#A52A2A",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.exit_btn.pack(side="left", padx=(10, 0), expand=True, fill="x")
        
        self.error_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            text_color="#FF4444",
            font=ctk.CTkFont(size=12)
        )
        self.error_label.pack(pady=10)
        
        self.username_entry.focus()
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda e: self.login())

    def center_window(self):
        self.update_idletasks()
        width = 450
        height = 400
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        if USERS.get(username) == password:
            self.withdraw()
            from main_app import MainApp
            main_app = MainApp(self, username)
            main_app.grab_set()
            self.wait_window(main_app)
            self.destroy()
        else:
            self.error_label.configure(text="Invalid username or password")
            self.password_entry.delete(0, 'end')
            self.username_entry.focus()