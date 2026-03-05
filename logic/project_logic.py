from tools.graphs.graphing import plot_basic_graph
import tkinter as tk
from tkinter import messagebox
import re
from tools.std_input import stdInput

class graphingWindow:
    def __init__(self, root, name="Graph", data=None):
        self.root = root
        self.data = data
        self.win = tk.Toplevel(self.root)
        self.win.title(f"Graph Data for {name}")
        self.win.geometry("300x150")

        self.x_input = stdInput(self.win, prompt="X Data (e.g. 'Column A' or '1,2,3'):", pos=[10, 10])

        self.y_input = stdInput(self.win, prompt="Y Data (e.g. 'Column B' or '4,5,6'):", pos=[10, 10])

        self.title_graph = stdInput(self.win, prompt="Graph Title (optional):", pos=[10, 10])
        self.xlabel_graph = stdInput(self.win, prompt="X-axis Label (optional):", pos=[10, 10])
        self.ylabel_graph = stdInput(self.win, prompt="Y-axis Label (optional):", pos=[10, 10])

        tk.Button(self.win, text="Plot Graph", command=self.plot_graph).pack(pady=(0, 10))
        tk.Button(self.win, text="Cancel", command=self.win.destroy).pack()

    def _col_label_to_index(self, label):
        label = label.strip().upper()
        if not re.fullmatch(r"[A-Z]+", label):
            raise ValueError(f"Invalid column label: {label}")

        idx = 0
        for ch in label:
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx - 1

    def _to_float_if_possible(self, value):
        text = str(value).strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _numbers_from_row(self, row_number):
        if not self.data:
            raise ValueError("No spreadsheet data available")

        row_index = row_number - 1
        if row_index < 0 or row_index >= len(self.data):
            raise ValueError(f"Row {row_number} is out of range")

        values = []
        for cell in self.data[row_index]:
            num = self._to_float_if_possible(cell)
            if num is not None:
                values.append(num)
        return values

    def _numbers_from_column(self, col_label):
        if not self.data:
            raise ValueError("No spreadsheet data available")

        col_index = self._col_label_to_index(col_label)
        values = []
        for row in self.data:
            if col_index < len(row):
                num = self._to_float_if_possible(row[col_index])
                if num is not None:
                    values.append(num)
        return values

    def _parse_sequence(self, text):
        expr = text.strip()
        if not expr:
            raise ValueError("Input cannot be empty")

        row_range = re.fullmatch(r"(?i)row\s+(\d+)\s*:\s*(\d+)", expr)
        if row_range:
            start = int(row_range.group(1))
            end = int(row_range.group(2))
            if end < start:
                raise ValueError("Row range must be ascending")
            values = []
            for r in range(start, end + 1):
                values.extend(self._numbers_from_row(r))
            return values

        col_range = re.fullmatch(r"(?i)column\s+([A-Z]+)\s*:\s*([A-Z]+)", expr)
        if col_range:
            start = self._col_label_to_index(col_range.group(1))
            end = self._col_label_to_index(col_range.group(2))
            if end < start:
                raise ValueError("Column range must be ascending")
            values = []
            for c in range(start, end + 1):
                label = self._index_to_col_label(c)
                values.extend(self._numbers_from_column(label))
            return values

        row_match = re.fullmatch(r"(?i)row\s+(\d+)", expr)
        if row_match:
            return self._numbers_from_row(int(row_match.group(1)))

        col_match = re.fullmatch(r"(?i)column\s+([A-Z]+)", expr)
        if col_match:
            return self._numbers_from_column(col_match.group(1))

        # Fallback: comma-separated numeric values (e.g. 1, 2, 3.5)
        values = []
        for token in expr.split(","):
            token = token.strip()
            if token == "":
                continue
            values.append(float(token))
        if not values:
            raise ValueError("No numeric values found")
        return values

    def _index_to_col_label(self, index):
        if index < 0:
            raise ValueError("Column index cannot be negative")

        n = index + 1
        label = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            label = chr(ord("A") + rem) + label
        return label

    def plot_graph(self):
        x_str = self.x_input.get()
        y_str = self.y_input.get()

        try:
            x = self._parse_sequence(x_str)
            y = self._parse_sequence(y_str)

            if len(x) == 0 or len(y) == 0:
                raise ValueError("X and Y cannot be empty")
            if len(x) != len(y):
                raise ValueError(f"X and Y lengths must match (got {len(x)} and {len(y)})")

            plot_basic_graph(self.root, x, y, title=self.title_graph.get() or "Spreadsheet Graph",
                             xlabel=self.xlabel_graph.get() or "X Data", ylabel=self.ylabel_graph.get() or "Y Data")
        except Exception as e:
            messagebox.showerror(
                "Graph Input Error",
                "Use formats like 'Column A', 'Row 1', 'Column A:C', 'Row 1:3', or numeric list '1,2,3'.\n\n"
                f"Details: {e}",
            )