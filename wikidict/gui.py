"""
Graphical interface to build monolingual and bilingual dictionaries.

    python -m wikidict.gui

It runs the same steps as the command line (`python -m wikidict LOCALE --download`, `--parse`, `--render`,
`--convert`), one after the other, in a subprocess, and shows their output.
"""

from __future__ import annotations

import os
import queue
import re
import signal
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mediawiki_langcodes import code_to_name

from . import constants, lang

ROOT = Path(__file__).resolve().parent.parent
STEPS = ("download", "parse", "render", "convert")
FORMATS = {
    "dicthtml": "Kobo (dicthtml)",
    "stardict": "StarDict (KOReader, Boox, GoldenDict...)",
    "stardict-nosyn": "StarDict without .syn (Boox)",
    "dictfile": "DictFile (PocketBook, Vivlio)",
    "dictorg": "DICT.org (dictd)",
    "jsonvolume": "JSON",
    "mobi": "Kindle (mobi)",
}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # Windows: no console window for the steps
_TOKEN = re.compile(r"\x1b\[(\d*)([A-Za-z])|\x1b\[[0-9;?]*[A-Za-z]|\r|\n")


class Screen:
    """The lines a terminal would show for a program output, for progress bars redrawn in place.

    >>> s = Screen()
    >>> s.feed("Downloading 10%")
    0
    >>> s.feed("\\r\\x1b[2KDownloading 20%\\r\\n")
    0
    >>> s.feed("line 1\\nline 2\\nbar 1%\\r\\x1b[2K\\x1b[1A\\x1b[2Kline 2 bis\\nbar 2%")
    1
    >>> s.lines
    ['Downloading 20%', 'line 1', 'line 2 bis', 'bar 2%']

    `feed()` returns the index of the first line that changed.
    """

    def __init__(self) -> None:
        self.lines = [""]
        self._carriage_return = False

    def feed(self, text: str) -> int:
        first = len(self.lines) - 1
        pos = 0
        for match in _TOKEN.finditer(text):
            self._write(text[pos : match.start()])
            pos = match.end()
            token = match[0]
            if token == "\n":
                self.lines.append("")
                self._carriage_return = False
            elif token == "\r":
                # Wait for the next token: "\r\n" (Windows newline) keeps the line, anything else rewrites it
                self._carriage_return = True
            elif match[2] == "K":  # erase the line
                self.lines[-1] = ""
            elif match[2] == "A":  # cursor up: the lines below are going to be redrawn
                for _ in range(int(match[1] or 1)):
                    if len(self.lines) > 1:
                        self.lines.pop()
                first = min(first, len(self.lines) - 1)
            # Other escape sequences (colors, cursor visibility) are ignored
        self._write(text[pos:])
        return first

    def _write(self, text: str) -> None:
        if not text:
            return
        if self._carriage_return:
            self.lines[-1] = ""
            self._carriage_return = False
        self.lines[-1] += text


def lang_label(code: str) -> str:
    return f"{code} — {name}" if (name := code_to_name(code, "en")) else code


def lang_code(label: str) -> str:
    return label.split(" ", 1)[0].strip().lower()


def output_dir(folder: str, lang_src: str, lang_dst: str) -> Path:
    # Same layout as `render.get_source_dir()`
    return Path(folder) / "data" / lang_dst / lang_src / "output"


def open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=10)
        self.process: subprocess.Popen[bytes] | None = None
        self.output: queue.Queue[str | int] = queue.Queue()
        self.screen = Screen()
        self.pending: list[list[str]] = []
        self.stopped = False

        wiktionaries = [lang_label(code) for code in sorted(lang.head_sections)]
        self.src = tk.StringVar(value=lang_label("en"))
        self.dst = tk.StringVar(value=lang_label("en"))
        self.folder = tk.StringVar(value=str(Path.cwd()))
        self.steps = {step: tk.BooleanVar(value=True) for step in STEPS}
        has_kindling = constants.MOBIPOCKET_TOOL.is_file()
        self.formats = {fmt: tk.BooleanVar(value=fmt != "mobi" or has_kindling) for fmt in FORMATS}
        self.etym_only = tk.BooleanVar(value=False)

        form = ttk.Frame(self)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Wiktionary (language of the definitions):").grid(row=0, column=0, sticky="w")
        ttk.Combobox(form, textvariable=self.src, values=wiktionaries, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=2
        )
        ttk.Label(form, text="Language of the words:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(form, textvariable=self.dst, values=wiktionaries).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(
            form,
            text="Same language: monolingual dictionary. Another language (any code, e.g. la, grc): bilingual.",
            foreground="gray",
        ).grid(row=2, column=1, sticky="w")
        ttk.Label(form, text="Working folder:").grid(row=3, column=0, sticky="w")
        folder_row = ttk.Frame(form)
        folder_row.grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Entry(folder_row, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_row, text="Browse…", command=self.browse).pack(side="left", padx=(4, 0))
        ttk.Label(
            form,
            text="Dumps and dictionaries go in its data/ subfolder. Large Wiktionaries (en, fr) take many GB and hours.",
            foreground="gray",
        ).grid(row=4, column=1, sticky="w")

        options = ttk.Frame(self)
        options.pack(fill="x", pady=8)
        steps_box = ttk.LabelFrame(options, text="Steps", padding=6)
        steps_box.pack(side="left", fill="y")
        for step, var in self.steps.items():
            ttk.Checkbutton(steps_box, text=step.capitalize(), variable=var).pack(anchor="w")
        formats_box = ttk.LabelFrame(options, text="Formats", padding=6)
        formats_box.pack(side="left", fill="both", expand=True, padx=(8, 0))
        for idx, (fmt, label) in enumerate(FORMATS.items()):
            button = ttk.Checkbutton(formats_box, text=label, variable=self.formats[fmt])
            if fmt == "mobi" and not has_kindling:
                button.configure(text=f"{label}: needs {constants.MOBIPOCKET_TOOL}", state="disabled")
            button.grid(row=idx % 4, column=idx // 4, sticky="w", padx=(0, 12))
        ttk.Checkbutton(formats_box, text="Only with etymologies", variable=self.etym_only).grid(
            row=3, column=1, sticky="w"
        )

        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        self.start_button = ttk.Button(buttons, text="Start", command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=4)
        self.open_button = ttk.Button(buttons, text="Open the output folder", command=self.open_output)
        self.open_button.pack(side="left")
        self.status = ttk.Label(buttons, text="")
        self.status.pack(side="left", padx=8)

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.log = tk.Text(log_frame, height=20, wrap="none", font="TkFixedFont", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        self.pack(fill="both", expand=True)
        master.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.after(100, self.poll)

    def langs(self) -> tuple[str, str]:
        return lang_code(self.src.get()), lang_code(self.dst.get()) or lang_code(self.src.get())

    def browse(self) -> None:
        if folder := filedialog.askdirectory(initialdir=self.folder.get() or None):
            self.folder.set(folder)

    def open_output(self) -> None:
        path = output_dir(self.folder.get(), *self.langs())
        if path.is_dir():
            open_folder(path)
        else:
            messagebox.showinfo("inkdict", f"{path} does not exist yet: run the Convert step first.")

    def start(self) -> None:
        lang_src, lang_dst = self.langs()
        try:
            lang.head_sections_for(lang_src, lang_dst)
        except lang.UnsupportedLocale as exc:
            messagebox.showerror("inkdict", str(exc))
            return
        if not (steps := [step for step, var in self.steps.items() if var.get()]):
            messagebox.showerror("inkdict", "Choose at least one step.")
            return
        formats = [fmt for fmt, var in self.formats.items() if var.get()]
        if "convert" in steps and not formats:
            messagebox.showerror("inkdict", "Choose at least one format.")
            return

        Path(self.folder.get()).mkdir(parents=True, exist_ok=True)
        locale = lang_src if lang_src == lang_dst else f"{lang_src}:{lang_dst}"
        base = [sys.executable, "-m", "wikidict", locale]
        self.pending = []
        for step in steps:
            command = [*base, f"--{step}"]
            if step == "convert":
                command.append(f"--format={','.join(formats)}")
                if self.etym_only.get():
                    command.append("--with-etym-only")
            self.pending.append(command)
        self.stopped = False
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.next_step()

    def next_step(self) -> None:
        if not self.pending:
            self.finish("Done: the dictionaries are in the output folder.")
            return
        command = self.pending.pop(0)
        self.write(f"\n$ python {' '.join(command[1:])}\n")
        self.status.configure(text=f"{command[4][2:].capitalize()} …")
        env = os.environ | {
            "CWD": self.folder.get(),  # where `data/` goes
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            # Keep rich's progress bars, redrawn in place (`Screen`), although the output is a pipe
            "TTY_COMPATIBLE": "1",
            "TTY_INTERACTIVE": "1",
            "COLUMNS": "110",
            "NO_COLOR": "1",
        }
        self.process = subprocess.Popen(
            command,
            cwd=self.folder.get(),  # `logs/` goes there too
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=NO_WINDOW,
            start_new_session=sys.platform != "win32",  # to stop the render workers with the main process
        )
        threading.Thread(target=self.read_output, args=(self.process,), daemon=True).start()

    def read_output(self, process: subprocess.Popen[bytes]) -> None:
        assert process.stdout
        while chunk := os.read(process.stdout.fileno(), 4096):
            self.output.put(chunk.decode("utf-8", errors="replace"))
        self.output.put(process.wait())

    def poll(self) -> None:
        try:
            while True:
                item = self.output.get_nowait()
                if isinstance(item, int):
                    self.step_done(item)
                else:
                    self.write(item)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def step_done(self, returncode: int) -> None:
        self.process = None
        if self.stopped:
            self.finish("Stopped.")
        elif returncode:
            self.finish(f"Failed (exit code {returncode}): see the log above, and the logs/ folder.")
        else:
            self.next_step()

    def finish(self, message: str) -> None:
        self.pending = []
        self.status.configure(text=message)
        self.write(f"\n{message}\n")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def write(self, text: str) -> None:
        first = self.screen.feed(text)
        at_bottom = self.log.yview()[1] >= 0.999
        self.log.configure(state="normal")
        # Up to "end-1c": deleting up to "end" from the start of a line would remove the newline before it
        self.log.delete(f"{first + 1}.0", "end-1c")
        self.log.insert("end", "\n".join(self.screen.lines[first:]))
        self.log.configure(state="disabled")
        if at_bottom:
            self.log.see("end")

    def stop(self) -> None:
        self.stopped = True
        self.pending = []
        if (process := self.process) and process.poll() is None:
            if sys.platform == "win32":
                # The whole tree: the render step runs a pool of worker processes
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    creationflags=NO_WINDOW,
                )
            else:
                os.killpg(process.pid, signal.SIGTERM)

    def quit_app(self) -> None:
        if self.process and not messagebox.askyesno("inkdict", "A step is still running. Stop it and quit?"):
            return
        self.stop()
        self.master.destroy()


def main() -> int:
    root = tk.Tk()
    root.title("inkdict: dictionaries from Wiktionary")
    root.geometry("900x640")
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
