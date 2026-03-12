import csv
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from logic.project_logic import graphingWindow


class SpreadsheetWindow:
    _instance_count = 0

    def __init__(self, root, rows=20, cols=10, file_path=None, title="Untitled"):
        if file_path:
            SpreadsheetWindow._instance_count += 1
            self.index = SpreadsheetWindow._instance_count

            self.root = root
            self.rows = rows
            self.cols = cols


            self.win = tk.Toplevel(self.root)
            self.win.title(f"AH-Control | Spreadsheet {self.index} | {title} ({file_path})")
            self.win.geometry("800x500")
            self._saved_path = file_path

            
            self._create_ui()
            self._load_csv(file_path)
        else:
            SpreadsheetWindow._instance_count += 1
            self.index = SpreadsheetWindow._instance_count

            self.root = root
            self.rows = rows
            self.cols = cols

            self.win = tk.Toplevel(self.root)
            self.win.title(f"AH-Control | Spreadsheet {self.index} | {title}")
            self.win.geometry("800x500")
            self._saved_path = None

            self._create_ui()

    def _create_ui(self):
        container = ttk.Frame(self.win)
        container.pack(fill="both", expand=True)

        toolbar = ttk.Frame(container)
        toolbar.pack(fill="x")
        save_btn = ttk.Button(toolbar, text="Save", command=self.save)
        save_btn.pack(side="left", padx=4, pady=4)
        save_as_btn = ttk.Button(toolbar, text="Save As...", command=self.save_as)
        save_as_btn.pack(side="left", padx=4, pady=4)
        open_btn = ttk.Button(toolbar, text="Open...", command=self.open_file)
        open_btn.pack(side="left", padx=4, pady=4)
        graph_btn = ttk.Button(toolbar, text="Graph", command=self._graph_data)
        graph_btn.pack(side="left", padx=4, pady=4)

        grid_frame = ttk.Frame(container)
        grid_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(grid_frame)
        v_scroll = ttk.Scrollbar(grid_frame, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(grid_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        self.canvas = canvas
        self.inner = inner

        for c in range(self.cols):
            col_label = chr(ord("A") + (c % 26)) + (str(c // 26) if c >= 26 else "")
            lbl = ttk.Label(inner, text=col_label, borderwidth=1, relief="ridge", anchor="center", width=12)
            lbl.grid(row=0, column=c+1, sticky="nsew")

        self._col_headers = [None] * self.cols
        for c in range(self.cols):
            self._col_headers[c] = inner.grid_slaves(row=0, column=c+1)[0]

        self._cells = {}

        # store row header widgets too
        self._row_headers = []
        for r in range(self.rows):
            self._add_row(r)

        # Make columns expand evenly
        for c in range(self.cols + 1):
            inner.grid_columnconfigure(c, weight=1)

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_configure)

    def _add_row(self, r):
        inner = self.inner
        r_lbl = ttk.Label(inner, text=str(r+1), borderwidth=1, relief="ridge", width=4, anchor="e")
        r_lbl.grid(row=r+1, column=0, sticky="nsew")
        self._row_headers.append(r_lbl)
        for c in range(self.cols):
            e = tk.Entry(
                inner,
                bd=1,
                relief="solid",
                highlightthickness=1,
                highlightbackground="#cccccc",
                highlightcolor="#2b8cff",
                borderwidth=0,
            )
            e.grid(row=r+1, column=c+1, sticky="nsew", padx=0, pady=0)
            # bind to key release to detect typing in last row
            e.bind("<KeyRelease>", lambda ev, rr=r, cc=c: self._on_cell_key(rr, cc, ev))
            self._cells[(r, c)] = e

    def _append_row(self):
        r = self.rows
        # insert new row widgets
        self._add_row(r)
        self.rows += 1

    def _ensure_rows(self, n):
        while self.rows < n:
            self._append_row()

    def _ensure_cols(self, n):
        if n <= self.cols:
            return
        inner = self.inner
        # add new column headers
        for c in range(self.cols, n):
            col_label = chr(ord("A") + (c % 26)) + (str(c // 26) if c >= 26 else "")
            lbl = ttk.Label(inner, text=col_label, borderwidth=1, relief="ridge", anchor="center", width=12)
            lbl.grid(row=0, column=c+1, sticky="nsew")
            self._col_headers.append(lbl)
            # add entry widgets for existing rows
            for r in range(self.rows):
                e = tk.Entry(
                    inner,
                    bd=1,
                    relief="solid",
                    highlightthickness=1,
                    highlightbackground="#cccccc",
                    highlightcolor="#2b8cff",
                    borderwidth=0,
                )
                e.grid(row=r+1, column=c+1, sticky="nsew", padx=0, pady=0)
                e.bind("<KeyRelease>", lambda ev, rr=r, cc=c: self._on_cell_key(rr, cc, ev))
                self._cells[(r, c)] = e
        self.cols = n

    # Dev-Fan: i think we can update this to be more efficient
    def _on_cell_key(self, r, c, event):
        try:
            val = self._cells[(r, c)].get()
        except Exception:
            return

        if r == self.rows - 1 and val.strip() != "":
            self._append_row()
        
        if c == self.cols - 1 and val.strip() != "":
            self._ensure_cols(self.cols + 1)
        
        if event.keysym in ("Down", "Return"):
            self._move_to_cell(r + 1, c)
        elif event.keysym == "Up":
            self._move_to_cell(r - 1, c)
        elif event.keysym == "Left":
            self._move_to_cell(r, c - 1)
        elif event.keysym == "Right":
            self._move_to_cell(r, c + 1)

    def _last_non_empty_row(self):
        last = 0
        for r in range(self.rows):
            for c in range(self.cols):
                v = (self._cells.get((r, c)) or tk.Entry()).get()
                if v.strip() != "":
                    last = r + 1
                    break
        return last

    def _write_csv(self, path):
        count_rows = self._last_non_empty_row()
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for r in range(count_rows):
                    row = [ (self._cells.get((r, c)) or tk.Entry()).get() for c in range(self.cols) ]
                    writer.writerow(row)
            self._saved_path = path
            return True
        except Exception as e:
            messagebox.showerror("Spreadsheet", f"Could not save CSV:\n{e}")
            return False

    def save(self):
        if self._saved_path:
            ok = self._write_csv(self._saved_path)
            if ok:
                messagebox.showinfo("Spreadsheet", f"Saved to\n{self._saved_path}")
        else:
            self.save_as()

    def save_as(self):
        path = filedialog.asksaveasfilename(
            parent=self.win,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*")],
        )
        if not path:
            return
        ok = self._write_csv(path)
        if ok:
            messagebox.showinfo("Spreadsheet", f"Saved to\n{path}")

    def _load_csv(self, path):
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception as e:
            messagebox.showerror("Spreadsheet", f"Could not open CSV:\n{e}")
            return False

        if not rows:
            # empty file -> clear grid
            return True

        max_cols = max(len(r) for r in rows)
        needed_rows = len(rows)
        self._ensure_cols(max_cols)
        self._ensure_rows(needed_rows)

        # populate
        for r, row in enumerate(rows):
            for c in range(self.cols):
                val = row[c] if c < len(row) else ""
                cell = self._cells.get((r, c))
                if cell:
                    cell.delete(0, tk.END)
                    cell.insert(0, val)

        self._saved_path = path
        return True

    def open_file(self):
        path = filedialog.askopenfilename(
            parent=self.win,
            filetypes=[("CSV files", "*.csv"), ("All files", "*")],
        )
        if not path:
            return
        ok = self._load_csv(path)
        if ok:
            messagebox.showinfo("Spreadsheet", f"Loaded\n{path}")
    
    def _graph_data(self):
        # Pass a plain snapshot of cell values so the graph dialog can resolve
        # row/column selectors without depending on widget internals.
        data = []
        for r in range(self.rows):
            row_vals = []
            for c in range(self.cols):
                cell = self._cells.get((r, c))
                row_vals.append(cell.get() if cell else "")
            data.append(row_vals)

        graphingWindow(self.win, name=f"Spreadsheet {self.index}", data=data)

    def _move_to_cell(self, r, c):
        cell = self._cells.get((r, c))
        if cell:
            cell.focus_set()
            self.canvas.yview_moveto(max(0, cell.winfo_y() - 100) / self.inner.winfo_height())
            self.canvas.xview_moveto(max(0, cell.winfo_x() - 100) / self.inner.winfo_width())
