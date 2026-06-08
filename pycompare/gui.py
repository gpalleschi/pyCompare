from __future__ import annotations
import logging
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path

from pycompare.reconcile import ReconcileEngine

logger = logging.getLogger(__name__)

BG = "#83D4F2"
INPUT_BG = "#E5D6F3"
BTN_BG = "#232967"
BTN_FG = "#83D4F2"

VERSION = "1.0.0"

def _icon_path() -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base, "icon", "IconaPyCompare.ico")
    return candidate if os.path.exists(candidate) else ""


def _resource_path(parts: list[str]) -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


class QueueHandler(logging.Handler):
    def __init__(self, text_widget: tk.Text):
        super().__init__()
        self.text_widget = text_widget
        self.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self._append, msg)

    def _append(self, msg: str):
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.see(tk.END)


class ProcessingPopup:
    def __init__(self, parent: tk.Tk):
        self.parent = parent
        self._window: tk.Toplevel | None = None
        self._progress: ttk.Progressbar | None = None
        self._photo: tk.PhotoImage | None = None

    def show(self):
        if self._window:
            return
        w = tk.Toplevel(self.parent, bg=BG)
        w.title("Processing")
        w.resizable(False, False)
        w.protocol("WM_DELETE_WINDOW", lambda: None)

        icon = _icon_path()
        if icon:
            try:
                w.iconbitmap(icon)
            except Exception:
                pass

        frame = tk.Frame(w, bg=BG, padx=40, pady=30)
        frame.pack(fill=tk.BOTH, expand=True)

        png_path = _resource_path(["data", "IconaPyCompare.png"])
        if os.path.exists(png_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(png_path)
                self._photo = ImageTk.PhotoImage(img)
                img_lbl = tk.Label(frame, image=self._photo, bg=BG)
                img_lbl.pack(pady=(0, 15))
            except Exception as e:
                logger.warning("Could not load logo image: %s", e)

        lbl = tk.Label(
            frame, text="Processing in progress...",
            font=("Segoe UI", 12, "bold"), bg=BG, fg="#232967",
        )
        lbl.pack(pady=(0, 20))

        self._progress = ttk.Progressbar(frame, mode="indeterminate", length=300)
        self._progress.pack()
        self._progress.start(15)

        w.transient(self.parent)
        w.grab_set()

        self.parent.update_idletasks()
        pw = w.winfo_reqwidth()
        ph = w.winfo_reqheight()
        px = self.parent.winfo_x() + (self.parent.winfo_width() - pw) // 2
        py = self.parent.winfo_y() + (self.parent.winfo_height() - ph) // 2
        w.geometry(f"+{px}+{py}")

        self._window = w

    def hide(self):
        if self._progress:
            self._progress.stop()
        if self._window:
            try:
                self._window.grab_release()
                self._window.destroy()
            except tk.TclError:
                pass
        self._window = None
        self._progress = None


class ReconciliationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"PyCompare - File Reconciliation Tool v{VERSION}")
        self.root.geometry("900x750")
        self.root.minsize(700, 600)
        self.root.configure(bg=BG)

        icon = _icon_path()
        if icon:
            try:
                self.root.iconbitmap(icon)
            except Exception:
                pass

        style = ttk.Style()
        style.theme_use("vista" if "vista" in style.theme_names() else "clam")
        style.configure("TEntry", fieldbackground=INPUT_BG)
        style.map("TEntry", fieldbackground=[("focus", INPUT_BG)])

        self._running = False
        self._build_ui()
        self._loading_popup = ProcessingPopup(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _make_button(self, parent, text, command):
        return tk.Button(
            parent, text=text, command=command,
            bg=BTN_BG, fg=BTN_FG, activebackground="#3A4A9E", activeforeground=BTN_FG,
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=3,
            cursor="hand2", bd=0,
        )

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg=BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self._build_header(main_frame)
        self._build_input_section(main_frame)
        self._build_action_section(main_frame)
        self._build_results_section(main_frame)
        self._build_log_section(main_frame)
        self._build_footer(main_frame)

    def _build_header(self, parent):
        header = tk.Label(
            parent, text="PyCompare - File Reconciliation",
            font=("Segoe UI", 16, "bold"), bg=BG, fg="#232967",
            anchor=tk.W,
        )
        header.pack(fill=tk.X, pady=(0, 15))

        sep = tk.Frame(parent, height=2, bg="#232967")
        sep.pack(fill=tk.X, pady=(0, 10))

    def _build_input_section(self, parent):
        frame = tk.LabelFrame(
            parent, text="Input Configuration",
            font=("Segoe UI", 10, "bold"),
            bg=BG, fg="#232967", padx=10, pady=10,
        )
        frame.pack(fill=tk.X, pady=(0, 10))

        fields = [
            ("File 1:", "file1",None),
            ("Config File 1 JSON:", "config1",[("JSON Files", "*.json")]),
            ("File 2:", "file2",None),
            ("Config File 2 JSON:", "config2",[("JSON Files", "*.json")]),
            ("Matching Config JSON:", "match_config",[("JSON Files", "*.json")]),
        ]

        self._entries = {}
        self._filetypes = {}
        for label_text, key, filetypes in fields:
            row = tk.Frame(frame, bg=BG)
            row.pack(fill=tk.X, pady=3)

            lbl = tk.Label(
                row, text=label_text, width=22, anchor=tk.W,
                font=("Segoe UI", 10, "bold"), bg=BG, fg="#232967",
            )
            lbl.pack(side=tk.LEFT)

            entry = ttk.Entry(row, background=INPUT_BG, foreground="#232967")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
            self._entries[key] = entry
            self._filetypes[key] = filetypes

            btn = self._make_button(row, "Browse", lambda k=key: self._browse(k))
            btn.pack(side=tk.RIGHT)

    def _build_action_section(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill=tk.X, pady=(0, 10))

        self.output_dir_entry = ttk.Entry(frame)
        self.output_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.output_dir_entry.insert(0, str(Path.cwd() / "output"))

        btn_out = self._make_button(frame, "Output Dir", self._browse_output)
        btn_out.pack(side=tk.RIGHT, padx=(0, 5))

        self.compare_btn = self._make_button(frame, "Compare", self._start_comparison)
        self.compare_btn.pack(side=tk.RIGHT, padx=(0, 5))

    def _build_results_section(self, parent):
        frame = tk.LabelFrame(
            parent, text="Results",
            font=("Segoe UI", 10, "bold"),
            bg=BG, fg="#232967", padx=10, pady=10,
        )
        frame.pack(fill=tk.X, pady=(0, 10))

        metrics = [
            ("total1", "Total File 1"),
            ("total2", "Total File 2"),
            ("matched", "Reconciled"),
            ("only1", "Only File 1"),
            ("only2", "Only File 2"),
            ("pct", "Match %"),
            ("time", "Processing Time"),
        ]

        self._result_vars = {}
        row_frame = tk.Frame(frame, bg=BG)
        row_frame.pack(fill=tk.X)

        for key, label in metrics:
            cell = tk.Frame(row_frame, bg=BG)
            cell.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            tk.Label(
                cell, text=label, anchor=tk.CENTER,
                font=("Segoe UI", 10), bg=BG, fg="#232967",
            ).pack()

            var = tk.StringVar(value="--")
            tk.Label(
                cell, textvariable=var, anchor=tk.CENTER,
                font=("Segoe UI", 10, "bold"), bg=BG, fg="#232967",
            ).pack()
            self._result_vars[key] = var

    def _build_log_section(self, parent):
        frame = tk.LabelFrame(
            parent, text="Log",
            font=("Segoe UI", 10, "bold"),
            bg=BG, fg="#232967", padx=5, pady=5,
        )
        frame.pack(fill=tk.BOTH, expand=True)

        text_frame = tk.Frame(frame, bg=BG)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            text_frame, height=12, wrap=tk.WORD,
            bg=INPUT_BG, fg="#232967",
            font=("Consolas", 9),
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self._setup_logging()

    def _setup_logging(self):
        root_logger = logging.getLogger("pycompare")
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(QueueHandler(self.log_text))

    def _browse(self, key: str):

        filetypes = self._filetypes.get(key)

        if not filetypes:
            filetypes = [("All files", "*.*")]

        path = filedialog.askopenfilename(
            title=f"Select {key}",
            filetypes=filetypes,
        )

        if path:
            self._entries[key].delete(0, tk.END)
            self._entries[key].insert(0, path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, path)

    def _start_comparison(self):
        if self._running:
            self._show_info("Info", "A comparison is already in progress")
            return

        file1 = self._entries["file1"].get().strip()
        config1 = self._entries["config1"].get().strip()
        file2 = self._entries["file2"].get().strip()
        config2 = self._entries["config2"].get().strip()
        match_cfg = self._entries["match_config"].get().strip()
        output_dir = self.output_dir_entry.get().strip()

        if not all([file1, config1, file2, config2, match_cfg, output_dir]):
            self._show_error("Please fill in all fields")
            return

        paths = {
            "File 1": Path(file1),
            "Config 1": Path(config1),
            "File 2": Path(file2),
            "Config 2": Path(config2),
            "Matching Config": Path(match_cfg),
        }

        missing = [name for name, p in paths.items() if not p.exists()]
        if missing:
            self._show_error("Files not found:\n" + "\n".join(missing))
            return

        self._reset_results()
        self._running = True
        self.compare_btn.configure(state=tk.DISABLED, text="Running...")
        self.log_text.delete(1.0, tk.END)

        self._loading_popup.show()

        thread = threading.Thread(
            target=self._run_comparison,
            args=(str(file1), str(config1), str(file2), str(config2), str(match_cfg), str(output_dir)),
            daemon=True,
        )
        thread.start()

        self.root.after(100, self._poll_thread, thread)

    def _run_comparison(self, file1, config1, file2, config2, match_cfg, output_dir):
        try:
            engine = ReconcileEngine()
            stats = engine.run(file1, config1, file2, config2, match_cfg, output_dir)
            self.root.after(0, self._update_results, stats)
        except Exception as e:
            logger.exception("Comparison failed")
            self.root.after(0, self._show_error, str(e))
        finally:
            self._running = False
            self.root.after(0, self._reenable_button)
            self.root.after(0, self._loading_popup.hide)

    def _poll_thread(self, thread: threading.Thread):
        if thread.is_alive():
            self.root.after(100, self._poll_thread, thread)

    def _update_results(self, stats):
        self._result_vars["total1"].set(str(stats.total_file1))
        self._result_vars["total2"].set(str(stats.total_file2))
        self._result_vars["matched"].set(str(stats.matched))
        self._result_vars["only1"].set(str(stats.only_file1))
        self._result_vars["only2"].set(str(stats.only_file2))
        self._result_vars["pct"].set(f"{stats.match_percentage:.2f}%")
        self._result_vars["time"].set(f"{stats.processing_time:.3f}s")

    def _custom_dialog(self, title: str, message: str, dialog_type: str = "error") -> bool:
        w = tk.Toplevel(self.root, bg=BG)
        w.title(title)
        w.resizable(False, False)

        icon = _icon_path()
        if icon:
            try:
                w.iconbitmap(icon)
            except Exception:
                pass

        frame = tk.Frame(w, bg=BG, padx=25, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        lbl = tk.Label(
            frame, text=message, bg=BG, fg="#232967",
            font=("Segoe UI", 10), wraplength=400, justify=tk.LEFT,
        )
        lbl.pack(pady=(0, 18))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack()

        result = [False]

        if dialog_type == "okcancel":
            def _ok():
                result[0] = True
                w.destroy()

            def _cancel():
                result[0] = False
                w.destroy()

            self._make_button(btn_frame, "OK", _ok).pack(side=tk.LEFT, padx=5)
            self._make_button(btn_frame, "Cancel", _cancel).pack(side=tk.LEFT, padx=5)
        else:
            def _close():
                result[0] = True
                w.destroy()

            self._make_button(btn_frame, "OK", _close).pack()

        w.transient(self.root)
        w.grab_set()

        self.root.update_idletasks()
        pw = w.winfo_reqwidth()
        ph = w.winfo_reqheight()
        px = self.root.winfo_x() + (self.root.winfo_width() - pw) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - ph) // 2
        w.geometry(f"+{px}+{py}")

        self.root.wait_window(w)
        return result[0]

    def _show_info(self, title: str, message: str):
        self._custom_dialog(title, message, "info")

    def _show_error(self, message: str):
        self._custom_dialog("Error", message, "error")

    def _show_confirm(self, title: str, message: str) -> bool:
        return self._custom_dialog(title, message, "okcancel")

    def _reenable_button(self):
        self.compare_btn.configure(state=tk.NORMAL, text="Compare")

    def _reset_results(self):
        for var in self._result_vars.values():
            var.set("--")

    def _build_footer(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill=tk.X, pady=(8, 0))

        exit_btn = self._make_button(frame, "Exit", self._on_close)
        exit_btn.pack(side=tk.RIGHT)

    def _on_close(self):
        if self._running:
            if not self._show_confirm("Quit", "A comparison is in progress. Quit anyway?"):
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()
