import customtkinter as ctk
from login_window import LoginWindow


if __name__ == "__main__":
    try:
        print("=" * 50)
        print("Starting System Monitor...")
        print("=" * 50)
        app = LoginWindow()
        app.mainloop()
    except Exception as e:
        print(f"\nCritical error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")