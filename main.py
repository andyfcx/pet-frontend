import customtkinter as ctk
import pandas as pd
import tkinter as tk

# Simple CustomTkinter CSV drag-and-drop example
# Note: Native drag-and-drop requires tkdnd or tkmacosx/OS-specific bindings.
# This demo uses a workaround: a drop zone where user can paste path or use askopenfilename.
# For full native drag-and-drop, install tkdnd and bind <<Drop>> events.

class CSVLoaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CSV Drag & Drop Demo")
        self.geometry("600x400")

        self.drop_label = ctk.CTkLabel(self, text="拖曳 CSV 到此區域\n(或點擊選取)",
                                       width=400, height=200,
                                       fg_color=("#333333"),
                                       corner_radius=10,
                                       justify="center")
        self.drop_label.pack(pady=40)

        # Bind mouse click to open file dialog
        self.drop_label.bind("<Button-1>", self.open_dialog)

        # Bind drag-and-drop events if tkdnd available
        try:
            self.drop_label.drop_target_register('DND_Files')
            self.drop_label.dnd_bind('<<Drop>>', self.handle_drop)
        except Exception:
            print("Drag & Drop not fully supported on this system without tkdnd.")

        self.textbox = ctk.CTkTextbox(self, width=500, height=120)
        self.textbox.pack(pady=10)

    def open_dialog(self, event=None):
        from tkinter.filedialog import askopenfilename
        path = askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            self.load_csv(path)

    def handle_drop(self, event):
        # event.data is something like '{/path/to/file.csv}'
        path = event.data.strip("{}")
        if path.lower().endswith('.csv'):
            self.load_csv(path)
        else:
            self.textbox.insert("end", "非 CSV 檔案\n")

    def load_csv(self, path):
        try:
            df = pd.read_csv(path)
            self.textbox.delete("1.0", "end")
            self.textbox.insert("end", f"成功載入: {path}\n")
            self.textbox.insert("end", df.head().to_string())
        except Exception as e:
            self.textbox.insert("end", f"錯誤: {e}\n")

if __name__ == "__main__":
    app = CSVLoaderApp()
    app.mainloop()
