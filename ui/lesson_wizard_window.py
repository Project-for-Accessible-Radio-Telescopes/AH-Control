import json
import tkinter as tk
from tkinter import ttk

from tools.popup import newPopup


class LessonWizardWindow:
    def __init__(
        self,
        root,
        templates_path,
        on_open_recording=None,
        on_process_recordings=None,
        on_open_advanced_view=None,
        on_compare_recordings=None,
        on_run_rfi_mapping=None,
    ):
        self.root = root
        self.templates_path = templates_path
        self.on_open_recording = on_open_recording
        self.on_process_recordings = on_process_recordings
        self.on_open_advanced_view = on_open_advanced_view
        self.on_compare_recordings = on_compare_recordings
        self.on_run_rfi_mapping = on_run_rfi_mapping
        self.templates = self._load_templates()
        self.current_template_index = None
        self.current_steps = []
        self.current_step_index = 0
        self.completed_steps = set()

        self.popup = newPopup(self.root, name="Lesson Wizard", geometry="760x520")
        self._build_ui()

    def _load_templates(self):
        try:
            with open(self.templates_path, "r", encoding="utf-8") as template_file:
                rows = json.load(template_file)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        except Exception:
            pass
        return []

    def _normalize_steps(self, template):
        rows = template.get("steps", [])
        if not isinstance(rows, list):
            return []

        normalized = []
        for row in rows:
            if isinstance(row, str):
                text = row.strip()
                if text:
                    normalized.append(
                        {
                            "text": text,
                            "action": None,
                            "action_args": {},
                            "hint": "",
                            "expected_outcome": "",
                            "auto_complete_on_action": False,
                        }
                    )
                continue

            if not isinstance(row, dict):
                continue

            text = str(row.get("text", row.get("description", ""))).strip()
            action = row.get("action")
            if not text:
                continue
            normalized.append(
                {
                    "text": text,
                    "action": str(action).strip().lower() if isinstance(action, str) else None,
                    "action_args": row.get("action_args", {}) if isinstance(row.get("action_args", {}), dict) else {},
                    "hint": str(row.get("hint", "")).strip(),
                    "expected_outcome": str(row.get("expected_outcome", "")).strip(),
                    "auto_complete_on_action": bool(row.get("auto_complete_on_action", False)),
                }
            )
        return normalized

    def _action_label(self, action):
        labels = {
            "record": "Open Recording Tool",
            "process": "Process Recordings",
            "advanced": "Open Advanced Signal View",
            "compare": "Open Comparison Mode",
            "rfi": "Run RFI Mapping",
        }
        return labels.get(action, "Run Suggested Action")

    def _run_action(self, action, action_args=None):
        action_map = {
            "record": self.on_open_recording,
            "process": self.on_process_recordings,
            "advanced": self.on_open_advanced_view,
            "compare": self.on_compare_recordings,
            "rfi": self.on_run_rfi_mapping,
        }
        callback = action_map.get(action)
        if callback is None:
            return
        payload = action_args or {}
        try:
            callback(payload)
        except TypeError:
            callback()

        current = self.current_steps[self.current_step_index] if self.current_steps else None
        if current and current.get("auto_complete_on_action"):
            self.completed_steps.add(self.current_step_index)
            self.complete_var.set(True)
            self._render_current_step()

    def _select_template(self, index):
        if index < 0 or index >= len(self.templates):
            return

        template = self.templates[index]
        self.current_template_index = index
        self.current_steps = self._normalize_steps(template)
        self.current_step_index = 0
        self.completed_steps = set()

        self.title_var.configure(text=str(template.get("title", "Untitled")))
        self.goal_var.configure(text=str(template.get("objective", "")))
        self._render_current_step()

    def _render_current_step(self):
        total_steps = len(self.current_steps)
        if total_steps == 0:
            self.step_index_var.set("Step 0 of 0")
            self.step_text_var.set("This lesson template has no steps yet.")
            self.complete_var.set(False)
            self.complete_check.state(["disabled"])
            self.action_btn.state(["disabled"])
            self.back_btn.state(["disabled"])
            self.next_btn.state(["disabled"])
            self.progress_var.set("Progress: 0%")
            self.progress_bar.configure(value=0)
            return

        step = self.current_steps[self.current_step_index]
        step_num = self.current_step_index + 1
        completed = len(self.completed_steps)
        progress_pct = int(round((completed / total_steps) * 100))

        self.step_index_var.set(f"Step {step_num} of {total_steps}")
        self.step_text_var.set(step["text"])
        self.step_hint_var.set(step.get("hint", ""))
        self.step_outcome_var.set(step.get("expected_outcome", ""))
        self.complete_var.set(self.current_step_index in self.completed_steps)
        self.complete_check.state(["!disabled"])

        self.progress_var.set(f"Progress: {progress_pct}% ({completed}/{total_steps})")
        self.progress_bar.configure(value=progress_pct)

        action = step.get("action")
        if action:
            action_args = step.get("action_args", {})
            self.action_btn.configure(
                text=self._action_label(action),
                command=lambda a=action, args=action_args: self._run_action(a, args),
            )
            self.action_btn.state(["!disabled"])
        else:
            self.action_btn.configure(text="No Suggested Action", command=lambda: None)
            self.action_btn.state(["disabled"])

        if self.current_step_index == 0:
            self.back_btn.state(["disabled"])
        else:
            self.back_btn.state(["!disabled"])

        if self.current_step_index >= total_steps - 1:
            self.next_btn.configure(text="Finish")
        else:
            self.next_btn.configure(text="Next")
        self.next_btn.state(["!disabled"])

    def _toggle_completed(self):
        if self.complete_var.get():
            self.completed_steps.add(self.current_step_index)
        else:
            self.completed_steps.discard(self.current_step_index)
        self._render_current_step()

    def _go_back(self):
        if self.current_step_index <= 0:
            return
        self.current_step_index -= 1
        self._render_current_step()

    def _go_next(self):
        total_steps = len(self.current_steps)
        if total_steps == 0:
            return

        if self.complete_var.get():
            self.completed_steps.add(self.current_step_index)

        if self.current_step_index >= total_steps - 1:
            self.step_text_var.set("Lesson complete. You can choose another template or close this wizard.")
            self.step_index_var.set("Completed")
            self.next_btn.state(["disabled"])
            self.back_btn.state(["!disabled"])
            self.action_btn.state(["disabled"])
            self.progress_var.set(f"Progress: 100% ({total_steps}/{total_steps})")
            self.progress_bar.configure(value=100)
            return

        self.current_step_index += 1
        self._render_current_step()

    def _build_ui(self):
        container = ttk.Frame(self.popup.win)
        container.pack(fill="both", expand=True, padx=12, pady=10)

        ttk.Label(container, text="Lesson Wizard", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(
            container,
            text="Pick a guided activity and follow the workflow steps.",
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        body = ttk.Frame(container)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y")

        self.template_list = ttk.Treeview(left, columns=("title",), show="headings", height=14)
        self.template_list.heading("title", text="Templates")
        self.template_list.column("title", width=230, anchor="w")
        self.template_list.pack(fill="y", expand=False)
        self.template_list.bind("<<TreeviewSelect>>", self._on_select_template)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.title_var = ttk.Label(right, text="Select a template", font=("TkDefaultFont", 10, "bold"))
        self.title_var.pack(anchor="w")

        self.goal_var = ttk.Label(right, text="", justify="left", wraplength=470)
        self.goal_var.pack(anchor="w", pady=(4, 8))

        ttk.Label(right, text="Guided Step", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")

        self.progress_var = tk.StringVar(value="Progress: 0%")
        ttk.Label(right, textvariable=self.progress_var).pack(anchor="w", pady=(2, 2))

        self.progress_bar = ttk.Progressbar(right, orient="horizontal", mode="determinate", maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.step_index_var = tk.StringVar(value="Step 0 of 0")
        ttk.Label(right, textvariable=self.step_index_var, font=("TkDefaultFont", 9, "bold")).pack(anchor="w")

        self.step_text_var = tk.StringVar(value="Select a template to begin.")
        step_message = ttk.Label(right, textvariable=self.step_text_var, justify="left", wraplength=470)
        step_message.pack(fill="x", pady=(6, 10))

        self.step_hint_var = tk.StringVar(value="")
        ttk.Label(right, text="Hint", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        ttk.Label(right, textvariable=self.step_hint_var, justify="left", wraplength=470).pack(fill="x", pady=(2, 8))

        self.step_outcome_var = tk.StringVar(value="")
        ttk.Label(right, text="Expected Outcome", font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        ttk.Label(right, textvariable=self.step_outcome_var, justify="left", wraplength=470).pack(fill="x", pady=(2, 8))

        self.complete_var = tk.BooleanVar(value=False)
        self.complete_check = ttk.Checkbutton(
            right,
            text="Mark this step as completed",
            variable=self.complete_var,
            command=self._toggle_completed,
        )
        self.complete_check.pack(anchor="w")

        nav = ttk.Frame(right)
        nav.pack(fill="x", pady=(10, 0))

        self.back_btn = ttk.Button(nav, text="Back", command=self._go_back)
        self.back_btn.pack(side="left")

        self.next_btn = ttk.Button(nav, text="Next", command=self._go_next)
        self.next_btn.pack(side="left", padx=(6, 0))

        self.action_btn = ttk.Button(nav, text="No Suggested Action")
        self.action_btn.pack(side="right")

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(10, 0))

        ttk.Button(actions, text="Begin Recording", command=self._open_recording).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Process Recordings", command=self._process_recordings).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Open Advanced View", command=self._open_advanced_view).pack(side="left")
        ttk.Button(actions, text="Run RFI Mapping", command=self._run_rfi).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Close", command=self.popup.win.destroy).pack(side="right")

        for index, template in enumerate(self.templates):
            title = str(template.get("title", f"Template {index + 1}"))
            self.template_list.insert("", "end", iid=str(index), values=(title,))

        if self.templates:
            self.template_list.selection_set("0")
            self._select_template(0)
        else:
            self._render_current_step()

    def _on_select_template(self, _event):
        selected = self.template_list.selection()
        if not selected:
            return
        try:
            index = int(selected[0])
            self._select_template(index)
        except Exception:
            return

    def _open_recording(self):
        if self.on_open_recording is not None:
            try:
                self.on_open_recording({})
            except TypeError:
                self.on_open_recording()

    def _process_recordings(self):
        if self.on_process_recordings is not None:
            try:
                self.on_process_recordings({})
            except TypeError:
                self.on_process_recordings()

    def _open_advanced_view(self):
        if self.on_open_advanced_view is not None:
            try:
                self.on_open_advanced_view({})
            except TypeError:
                self.on_open_advanced_view()

    def _run_rfi(self):
        if self.on_run_rfi_mapping is not None:
            self.on_run_rfi_mapping({})
