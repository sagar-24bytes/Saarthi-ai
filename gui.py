# gui.py

import sys
import os
import threading
import queue
import time
import customtkinter as ctk

from voice.input import listen_interactive
from planner.planner import planner_node
from tools.validator import validate_plan_node, is_path_allowed
from tools.executor import execute_plan_node
from planner.intent import classify_intent
from tools.actions import open_folder
from tools.search import search_files
from memory.path_resolver import resolve_path_from_text, resolve_file_or_folder_in_allowed_folders, clean_speech_text
from memory.context import context
from planner.llm import check_ollama_status, MODEL_NAME
from tools.confirmation import count_matching_files
from memory.persistent import get_allowed_folders, add_allowed_folder, remove_allowed_folder

# Set light appearance mode and blue theme
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class ThreadSafeConsole:
    """
    Redirects stdout to a tkinter text widget in a thread-safe manner.
    """
    def __init__(self, text_widget, root):
        self.text_widget = text_widget
        self.root = root
        self.queue = queue.Queue()
        self._orig_stdout = sys.stdout
        sys.stdout = self
        self.root.after(100, self.process_queue)

    def write(self, string):
        self.queue.put(string)
        # Also write to original stdout for console debugging if it exists
        if self._orig_stdout is not None:
            self._orig_stdout.write(string)

    def flush(self):
        if self._orig_stdout is not None:
            self._orig_stdout.flush()

    def process_queue(self):
        try:
            while not self.queue.empty():
                msg = self.queue.get_nowait()
                self.text_widget.configure(state="normal")
                self.text_widget.insert("end", msg)
                self.text_widget.see("end")
                self.text_widget.configure(state="disabled")
        except Exception:
            pass
        finally:
            self.root.after(100, self.process_queue)

    def restore(self):
        sys.stdout = self._orig_stdout


class SaarthiWarningApp(ctk.CTk):
    """
    GUI shown when Ollama check fails on startup.
    """
    def __init__(self, error_message):
        super().__init__()
        self.title("Saarthi - Startup Check Failed")
        self.geometry("550x380")
        self.resizable(False, False)
        self.configure(fg_color="#f3f4f6")

        # Header
        title_label = ctk.CTkLabel(
            self, text="⚠️ Startup Check Failed",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#dc2626"
        )
        title_label.pack(pady=(20, 10))

        # Warning Text Box
        warning_box = ctk.CTkTextbox(
            self, width=500, height=220, 
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#ffffff", text_color="#1f2937",
            border_width=1, border_color="#e5e7eb"
        )
        warning_box.pack(pady=10, padx=20)
        warning_box.insert("1.0", error_message)
        warning_box.configure(state="disabled")

        # Close Button
        close_btn = ctk.CTkButton(
            self, text="Close", width=120, command=self.quit,
            fg_color="#dc2626", hover_color="#b91c1c",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        close_btn.pack(pady=(10, 20))


class FileSelectionDialog(ctk.CTkToplevel):
    """
    Modal window to resolve file path ambiguity.
    """
    def __init__(self, parent, title, matches, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("500x350")
        self.resizable(False, False)
        self.configure(fg_color="#f3f4f6")
        self.callback = callback
        self.matches = matches
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Label
        label = ctk.CTkLabel(
            self, text="Multiple matches found. Please choose:",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#1f2937"
        )
        label.pack(pady=(15, 10), padx=20, anchor="w")
        
        # Scrollable Frame for matches
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, width=460, height=220,
            fg_color="#ffffff", border_color="#e5e7eb", border_width=1
        )
        self.scroll_frame.pack(padx=20, pady=5, fill="both", expand=True)
        
        # Render a button for each match
        for path in matches:
            filename = os.path.basename(path)
            parent_dir = os.path.dirname(path)
            
            # Use safe binding variables
            match_btn = ctk.CTkButton(
                self.scroll_frame,
                text=f"{filename}\n({parent_dir})",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="w",
                fg_color="#f3f4f6", hover_color="#e5e7eb",
                text_color="#1f2937", height=45,
                command=lambda p=path: self.on_select(p)
            )
            match_btn.pack(fill="x", pady=4, padx=5)
            
        # Cancel Button
        cancel_btn = ctk.CTkButton(
            self, text="Cancel", width=100,
            command=self.destroy,
            fg_color="#ef4444", hover_color="#dc2626"
        )
        cancel_btn.pack(pady=(10, 15))
        
    def on_select(self, path):
        self.callback(path)
        self.destroy()


class FolderManagementWindow(ctk.CTkToplevel):
    """
    Modal window to add, remove, and view authorized folders.
    """
    def __init__(self, parent, on_update_cb):
        super().__init__(parent)
        self.title("Access to Folders")
        self.geometry("600x450")
        self.resizable(False, False)
        self.configure(fg_color="#f3f4f6")
        self.on_update_cb = on_update_cb
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Label
        label = ctk.CTkLabel(
            self, text="Managed Folders Access Control List",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#1f2937"
        )
        label.pack(pady=(20, 10), padx=25, anchor="w")
        
        # Description
        desc = ctk.CTkLabel(
            self, text="Saarthi will only perform file and folder operations inside allowed locations.",
            font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
            text_color="#4b5563"
        )
        desc.pack(padx=25, pady=(0, 10), anchor="w")

        # Scrollable list area
        self.list_frame = ctk.CTkScrollableFrame(
            self, width=540, height=240,
            fg_color="#ffffff", border_color="#e5e7eb", border_width=1
        )
        self.list_frame.pack(padx=25, pady=5, fill="both", expand=True)

        # Bottom Frame for Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=(15, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=1)

        add_btn = ctk.CTkButton(
            btn_frame, text="Add Folder",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#2563eb", hover_color="#1d4ed8",
            command=self.add_folder
        )
        add_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        remove_btn = ctk.CTkButton(
            btn_frame, text="Remove Folder",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#ef4444", hover_color="#dc2626",
            command=self.remove_folder,
            state="disabled"
        )
        remove_btn.grid(row=0, column=1, padx=10, sticky="ew")
        self.remove_btn = remove_btn

        close_btn = ctk.CTkButton(
            btn_frame, text="Close",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#9ca3af", hover_color="#4b5563",
            command=self.destroy
        )
        close_btn.grid(row=0, column=2, padx=(10, 0), sticky="ew")

        # Track selected item
        self.selected_folder = None
        self.folder_buttons = {}

        # Refresh display
        self.refresh_list()

    def refresh_list(self):
        # Clear previous widgets
        for btn in self.folder_buttons.values():
            btn.destroy()
        self.folder_buttons = {}
        self.selected_folder = None
        self.remove_btn.configure(state="disabled")

        folders = get_allowed_folders()

        if not folders:
            empty_lbl = ctk.CTkLabel(
                self.list_frame, text="No folders have been added yet.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color="gray"
            )
            empty_lbl.pack(pady=40)
            self.folder_buttons["empty"] = empty_lbl
            return

        for path in folders:
            # We create a card button for each folder
            btn = ctk.CTkButton(
                self.list_frame, text=path,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="w",
                fg_color="#f3f4f6", hover_color="#e5e7eb",
                text_color="#1f2937", height=35,
                command=lambda p=path: self.select_folder(p)
            )
            btn.pack(fill="x", pady=3, padx=5)
            self.folder_buttons[path] = btn

    def select_folder(self, path):
        # Deselect old selection
        if self.selected_folder in self.folder_buttons:
            self.folder_buttons[self.selected_folder].configure(fg_color="#f3f4f6")

        self.selected_folder = path
        # Select new
        if path in self.folder_buttons:
            self.folder_buttons[path].configure(fg_color="#dbeafe")
            self.remove_btn.configure(state="normal")

    def add_folder(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Select Folder to Authorize Saarthi")
        if path:
            # Normalize path
            path = os.path.abspath(path)
            add_allowed_folder(path)
            self.refresh_list()
            self.on_update_cb()

    def remove_folder(self):
        if self.selected_folder:
            remove_allowed_folder(self.selected_folder)
            self.refresh_list()
            self.on_update_cb()


class SaarthiApp(ctk.CTk):
    """
    Main Saarthi GUI Application (Light Theme & Threaded VAD Recording).
    """
    def __init__(self):
        super().__init__()
        self.title("Saarthi")
        self.geometry("800x700")
        self.minsize(800, 650)
        self.configure(fg_color="#f3f4f6")  # Light gray background

        # State Variables
        self.is_recording = False
        self.is_listening = False
        self.awaiting_confirmation = False
        self.current_state = {"user_text": "", "intent": "", "plan": {}}
        self.stop_event = threading.Event()

        # Build UI Components
        self.setup_ui()

        # Thread-safe console redirection
        self.console_redirector = ThreadSafeConsole(self.log_box, self)

        # Welcome message
        print("========================================")
        print("                Saarthi                 ")
        print("     Personal Desktop AI Assistant      ")
        print("========================================\n")
        
        # Startup allowed folders loading & display
        folders = get_allowed_folders()
        if not folders:
            print("[INFO] No folders have been added yet.\n")
            print("👉 Click 'Access to Folders' to grant Saarthi access to locations on your computer.\n")
        else:
            print("[INFO] Authorized folders:")
            for f in folders:
                print(f"  - {f}")
            print("")
            
        print("[INFO] Saarthi ready. Select microphone and click Tap to Speak.")

    def setup_ui(self):
        # Configure layout (2 columns, Header at top, Log at bottom)
        self.grid_columnconfigure(0, weight=1, minsize=350)
        self.grid_columnconfigure(1, weight=1, minsize=400)
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=3)  # Main panel
        self.grid_rowconfigure(2, weight=2)  # Log panel

        # ============================================================
        # 1. HEADER
        # ============================================================
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, height=80, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=20, pady=(20, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)
        self.header_frame.grid_columnconfigure(1, weight=0)

        # Branding labels
        branding_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        branding_frame.grid(row=0, column=0, sticky="w")
        
        self.title_label = ctk.CTkLabel(
            branding_frame, text="Saarthi",
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color="#2563eb"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            branding_frame, text="A Personal Desktop AI Assistant",
            font=ctk.CTkFont(family="Segoe UI", size=13, slant="italic"),
            text_color="#4b5563"
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w")

        # Status Badge
        self.status_frame = ctk.CTkFrame(self.header_frame, corner_radius=20, fg_color="#dbeafe", height=40)
        self.status_frame.grid(row=0, column=1, sticky="e", padx=10)
        
        self.status_dot = ctk.CTkLabel(
            self.status_frame, text="●", font=ctk.CTkFont(size=16), text_color="#10b981"
        )
        self.status_dot.grid(row=0, column=0, padx=(15, 5), pady=8)
        
        self.status_text = ctk.CTkLabel(
            self.status_frame, text="System: Ready",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#1e40af"
        )
        self.status_text.grid(row=0, column=1, padx=(0, 15), pady=8)

        # ============================================================
        # 2. LEFT PANEL: PERCEPTION & INPUT (Clean Light Card)
        # ============================================================
        self.left_frame = ctk.CTkFrame(
            self, corner_radius=10, fg_color="#ffffff", 
            border_width=1, border_color="#e5e7eb"
        )
        self.left_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=10)
        self.left_frame.grid_columnconfigure(0, weight=1)

        # Query input devices on startup
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            self.input_devices = []
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    self.input_devices.append((i, f"{i}: {d['name']}"))
        except Exception:
            self.input_devices = [(-1, "Default Microphone")]

        # Large Microphone Button
        self.mic_button = ctk.CTkButton(
            self.left_frame, text="🎙️\n\nTap to Speak",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            height=160, corner_radius=80,
            command=self.start_voice_input,
            fg_color="#2563eb", hover_color="#1d4ed8"
        )
        self.mic_button.pack(pady=(20, 10), padx=30)

        # Microphone Dropdown Selection
        self.mic_label = ctk.CTkLabel(
            self.left_frame, text="Select Microphone Input:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#4b5563"
        )
        self.mic_label.pack(pady=(5, 0), anchor="w", padx=30)

        self.mic_combo = ctk.CTkComboBox(
            self.left_frame,
            values=[d[1] for d in self.input_devices],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#ffffff", border_color="#e5e7eb",
            text_color="#1f2937", button_color="#e5e7eb",
            width=280
        )
        self.mic_combo.pack(pady=(5, 10), padx=30)
        
        # Set default value (sounddevice default input index)
        try:
            default_device_idx = sd.default.device[0]
            for idx, (dev_id, dev_name) in enumerate(self.input_devices):
                if dev_id == default_device_idx:
                    self.mic_combo.set(dev_name)
                    break
            else:
                self.mic_combo.set(self.input_devices[0][1])
        except Exception:
            if self.input_devices:
                self.mic_combo.set(self.input_devices[0][1])

        # Access to Folders Access Control ACL Button
        self.btn_access = ctk.CTkButton(
            self.left_frame, text="📂 Access to Folders",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#e5e7eb", hover_color="#d1d5db",
            text_color="#1f2937",
            command=self.open_access_management
        )
        self.btn_access.pack(pady=(10, 15), padx=30, fill="x")

        # Speech Display
        self.speech_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.speech_frame.pack(fill="x", padx=20, pady=10)

        self.heard_label = ctk.CTkLabel(
            self.speech_frame, text="Speech Recognized:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#4b5563"
        )
        self.heard_label.pack(anchor="w")

        self.speech_textbox = ctk.CTkTextbox(
            self.speech_frame, height=80, font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color="#f9fafb", text_color="#1f2937",
            corner_radius=6, border_width=1, border_color="#e5e7eb"
        )
        self.speech_textbox.pack(fill="x", pady=(5, 0))
        self.speech_textbox.insert("1.0", "(No speech recorded yet)")
        self.speech_textbox.configure(state="disabled")

        # Intent Display
        self.intent_label = ctk.CTkLabel(
            self.left_frame, text="Detected Intent: None",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#2563eb"
        )
        self.intent_label.pack(pady=(10, 20), anchor="w", padx=20)

        # ============================================================
        # 3. RIGHT PANEL: PLANNING & CONFIRMATION (Clean Light Card)
        # ============================================================
        self.right_frame = ctk.CTkFrame(
            self, corner_radius=10, fg_color="#ffffff",
            border_width=1, border_color="#e5e7eb"
        )
        self.right_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=10)
        self.right_frame.grid_columnconfigure(0, weight=1)

        plan_title = ctk.CTkLabel(
            self.right_frame, text="📋 Generated Execution Plan",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#1f2937"
        )
        plan_title.pack(anchor="w", padx=20, pady=(20, 5))

        # Plan View
        self.plan_textbox = ctk.CTkTextbox(
            self.right_frame, height=220, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#f9fafb", text_color="#1f2937",
            corner_radius=6, border_width=1, border_color="#e5e7eb"
        )
        self.plan_textbox.pack(fill="both", expand=True, padx=20, pady=5)
        self.plan_textbox.insert("1.0", "Your execution plan will appear here...")
        self.plan_textbox.configure(state="disabled")

        # Confirmation Frame
        self.confirm_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.confirm_frame.pack(fill="x", padx=20, pady=(10, 20))
        self.confirm_frame.grid_columnconfigure(0, weight=1)
        self.confirm_frame.grid_columnconfigure(1, weight=1)

        self.impact_label = ctk.CTkLabel(
            self.confirm_frame, text="Confirmation Required",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#4b5563"
        )
        self.impact_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="w")

        self.btn_confirm = ctk.CTkButton(
            self.confirm_frame, text="Confirm & Run",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#10b981", hover_color="#059669",
            command=self.confirm_execution,
            state="disabled"
        )
        self.btn_confirm.grid(row=1, column=0, padx=(0, 5), sticky="ew")

        self.btn_cancel = ctk.CTkButton(
            self.confirm_frame, text="Cancel",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#ef4444", hover_color="#dc2626",
            command=self.cancel_execution,
            state="disabled"
        )
        self.btn_cancel.grid(row=1, column=1, padx=(5, 0), sticky="ew")

        # ============================================================
        # 4. BOTTOM PANEL: EXECUTION LOG (Clean Light Card)
        # ============================================================
        self.log_frame = ctk.CTkFrame(
            self, corner_radius=10, fg_color="#ffffff",
            border_width=1, border_color="#e5e7eb"
        )
        self.log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=20, pady=(10, 20))
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        # Header subframe for log title and clear button
        log_header_frame = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        log_header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(10, 0))
        log_header_frame.grid_columnconfigure(0, weight=1)
        log_header_frame.grid_columnconfigure(1, weight=0)

        log_title = ctk.CTkLabel(
            log_header_frame, text="💻 Execution Log",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#4b5563"
        )
        log_title.grid(row=0, column=0, sticky="w")

        self.clear_logs_btn = ctk.CTkButton(
            log_header_frame, text="Clear Logs",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#e5e7eb", hover_color="#d1d5db",
            text_color="#4b5563", width=85, height=24,
            command=self.clear_logs
        )
        self.clear_logs_btn.grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(
            self.log_frame, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#f9fafb", text_color="#1f2937",
            corner_radius=6, border_width=1, border_color="#e5e7eb"
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(5, 15))
        self.log_box.configure(state="disabled")

    # ============================================================
    # SYSTEM STATE HANDLERS
    # ============================================================
    def set_status(self, text, color="#10b981"):
        """Updates the top right status badge."""
        self.status_text.configure(text=f"System: {text}")
        self.status_dot.configure(text_color=color)

    def reset_plan_ui(self):
        """Resets the generated execution plan panel to defaults."""
        self.update_plan_text("Your execution plan will appear here...")
        self.impact_label.configure(text="Confirmation Required", text_color="gray")
        self.btn_confirm.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.awaiting_confirmation = False

    def clear_logs(self):
        """Clears the Execution Log GUI panel textbox."""
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def open_access_management(self):
        """Opens the folder ACL management modal dialog."""
        def on_update():
            # Simply print updated folders in logs
            print("[INFO] Allowed folders list updated:")
            for folder in get_allowed_folders():
                print(f"  - {folder}")
            print("")
            
        FolderManagementWindow(self, on_update)

    def start_voice_input(self):
        if self.is_listening:  # Block input if processing/planning/executing
            return

        if not self.is_recording:
            # --- START RECORDING ---
            self.is_recording = True
            self.stop_event.clear()

            # Update Button UI to recording state
            self.mic_button.configure(
                text="🎙️\n\nStop Recording",
                fg_color="#ef4444",
                hover_color="#dc2626"
            )
            self.mic_combo.configure(state="disabled")
            self.btn_access.configure(state="disabled")
            self.set_status("Listening...", "#ef4444")
            print("[INFO] Listening...")

            # Clear UI for new task
            self.update_speech_text("")
            self.intent_label.configure(text="Detected Intent: None")
            self.reset_plan_ui()

            # Resolve selected mic device ID
            selected_name = self.mic_combo.get()
            device_id = None
            for dev_id, dev_name in self.input_devices:
                if dev_name == selected_name:
                    device_id = dev_id
                    break
            if device_id == -1:
                device_id = None

            # Start recording thread
            threading.Thread(
                target=self._run_voice_pipeline_interactive,
                args=(device_id,),
                daemon=True
            ).start()
        else:
            # --- STOP RECORDING (MANUAL CLICK) ---
            print("[INFO] Stopping recording...")
            self.stop_event.set()

    def update_speech_text(self, text):
        self.speech_textbox.configure(state="normal")
        self.speech_textbox.delete("1.0", "end")
        self.speech_textbox.insert("1.0", text if text else "(No speech recorded yet)")
        self.speech_textbox.configure(state="disabled")

    def update_plan_text(self, text):
        self.plan_textbox.configure(state="normal")
        self.plan_textbox.delete("1.0", "end")
        self.plan_textbox.insert("1.0", text)
        self.plan_textbox.configure(state="disabled")

    # ============================================================
    # BACKGROUND PIPELINE
    # ============================================================
    def _run_voice_pipeline_interactive(self, device_id):
        def recorder_log_cb(msg):
            # Print logs directly to the GUI stdout log box
            print(msg)

        try:
            # Run interactive voice VAD check (blocks until silence, manual stop, or timeout)
            result_code, user_text = listen_interactive(
                self.stop_event, 
                status_cb=recorder_log_cb, 
                device=device_id
            )
            
            # Post handling back to the main UI thread
            self.after(0, lambda: self._handle_recording_result(result_code, user_text))
        except Exception as e:
            print(f"[ERROR] Perception failed: {e}")
            self.after(0, lambda: self._handle_recording_result("error", ""))

    def _handle_recording_result(self, result_code, user_text):
        # Reset recording state
        self.is_recording = False
        self.stop_event.clear()

        # Restore Mic Button UI to ready state
        self.mic_button.configure(
            text="🎙️\n\nTap to Speak",
            fg_color="#2563eb",
            hover_color="#1d4ed8"
        )
        self.mic_combo.configure(state="normal")
        self.btn_access.configure(state="normal")

        if result_code == "no_speech":
            self.update_speech_text("No speech detected. Please try again.")
            print("[INFO] No speech detected. Please try again.")
            self.set_status("Ready", "#10b981")
            return

        if result_code == "error":
            self.update_speech_text("Audio recording or transcription error.")
            print("[ERROR] Failed to capture audio.")
            self.set_status("Ready", "#10b981")
            return

        if result_code == "success":
            self.update_speech_text(user_text)
            print("[INFO] Speech recognized.")
            self._process_text_flow(user_text)

    def _process_text_flow(self, user_text):
        # Disable mic button input while processing speech/planning
        self.is_listening = True
        self.mic_button.configure(state="disabled")
        self.set_status("Processing Speech...", "#2563eb")

        user_text = user_text.strip()
        if len(user_text) <= 1 or all(c in "., " for c in user_text):
            self.is_listening = False
            self.mic_button.configure(state="normal")
            self.set_status("Ready", "#10b981")
            return

        # 🧠 Classify intent
        intent = classify_intent(user_text)
        self.intent_label.configure(text=f"Detected Intent: {intent.upper()}")

        if intent == "exit":
            self.current_state = {
                "user_text": user_text,
                "intent": intent,
                "plan": {
                    "goal": "Exit Saarthi",
                    "steps": [
                        {
                            "tool": "exit_app",
                            "args": {}
                        }
                    ]
                }
            }
            self.after(0, self._display_exit_plan_and_confirm)
            return

        if intent == "no_action":
            print("[INFO] Chit-chat / no action detected.")
            self.is_listening = False
            self.mic_button.configure(state="normal")
            self.set_status("Ready", "#10b981")
            return

        if intent == "unknown":
            print("[INFO] Undefined command. Please speak clearly.")
            self.is_listening = False
            self.mic_button.configure(state="normal")
            self.set_status("Ready", "#10b981")
            return

        # Helper to extract targets
        def extract_open_target(text: str) -> str:
            text = text.lower().strip()
            # Remove leading open verbs
            for verb in ["open", "launch", "show"]:
                if text.startswith(verb):
                    text = text[len(verb):].strip()
            return text

        # Open actions execute immediately
        if intent == "open":
            matches = resolve_file_or_folder_in_allowed_folders(user_text)
            
            if len(matches) == 1:
                match_path = matches[0]
                print(f"[INFO] Opening match: {match_path}")
                try:
                    if os.path.isdir(match_path):
                        open_folder(match_path)
                    else:
                        os.startfile(match_path)
                    context.update(path=match_path)
                except Exception as e:
                    print(f"[ERROR] Could not open chosen location: {e}")
                self._finalize_direct_execution()
                return
            elif len(matches) > 1:
                target = clean_speech_text(user_text)
                print(f"[INFO] Multiple matches found for '{target}'. Awaiting user selection...")
                
                def on_chosen(chosen_path):
                    print(f"[INFO] Opening chosen location: {chosen_path}")
                    try:
                        if os.path.isdir(chosen_path):
                            open_folder(chosen_path)
                        else:
                            os.startfile(chosen_path)
                        context.update(path=chosen_path)
                    except Exception as e:
                        print(f"[ERROR] Could not open chosen location: {e}")
                    self._finalize_direct_execution()
                    
                FileSelectionDialog(self, f"Open: {target}", matches, on_chosen)
                return
            else:
                target = clean_speech_text(user_text)
                print(f"[INFO] No file or folder matching '{target}' found in allowed folders.")
                self._finalize_direct_execution()
                return

        # Search actions execute immediately
        if intent == "search":
            path = resolve_path_from_text(user_text)
            if not path:
                path = getattr(context, "last_path", None)
                
            if not path:
                print("[ERROR] Target directory not resolved.")
                self.is_listening = False
                self.mic_button.configure(state="normal")
                self.set_status("Ready", "#10b981")
                return

            if not is_path_allowed(path):
                print(f"[ERROR] This location is not currently accessible. Please add the folder using Access to Folders.")
                self.is_listening = False
                self.mic_button.configure(state="normal")
                self.set_status("Ready", "#10b981")
                return
            
            from main import extract_search_query
            query = extract_search_query(user_text)
            if not query:
                print("[ERROR] Search term not resolved.")
                self.is_listening = False
                self.mic_button.configure(state="normal")
                self.set_status("Ready", "#10b981")
                return
            
            print(f"[INFO] Searching for '{query}' in {path}...")
            threading.Thread(target=self._run_file_search, args=(path, query), daemon=True).start()
            return

        # Resolve target path before planning to guide the LLM
        resolved_path = resolve_path_from_text(user_text)

        # Planning flow (for organize / create, etc.)
        self.current_state = {
            "user_text": user_text,
            "intent": intent,
            "resolved_path": resolved_path,
            "plan": {}
        }
        
        # Run planning in background
        self.set_status("Generating Plan...", "#2563eb")
        threading.Thread(target=self._run_planning, daemon=True).start()

    def _run_file_search(self, path, query):
        try:
            results = search_files(path, query)
            if not results:
                print("[INFO] No matching files found.")
            else:
                print(f"[SUCCESS] Found {len(results)} match(es):\n")
                for result in results[:10]:
                    print(result)
                if len(results) > 10:
                    print(f"\n...and {len(results) - 10} more")
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
        finally:
            self.after(0, self._finalize_direct_execution)

    def _finalize_direct_execution(self):
        self.is_listening = False
        self.mic_button.configure(state="normal")
        self.set_status("Ready", "#10b981")

    def _run_planning(self):
        try:
            state = self.current_state.copy()
            # 1. Planner node
            planner_res = planner_node(state)
            state.update(planner_res)
            
            # 2. Validator node
            validator_res = validate_plan_node(state)
            state.update(validator_res)
            
            self.current_state = state
            self.after(0, self._display_plan_and_confirm)
        except Exception as e:
            print(f"[ERROR] Planning failed: {e}")
            self.after(0, self._finalize_direct_execution)

    def _display_plan_and_confirm(self):
        plan = self.current_state.get("plan", {})
        steps = plan.get("steps", [])

        if not steps:
            error_msg = plan.get("error", "No steps generated. Plan is empty.")
            self.update_plan_text(f"Error: {error_msg}")
            self._finalize_direct_execution()
            return

        # Print plan JSON formatted
        import json
        formatted_plan = json.dumps(plan, indent=2)
        self.update_plan_text(formatted_plan)
        print("[INFO] Execution plan generated.")

        # Calculate estimated impact
        total_files = 0
        affected_locations = set()
        for step in steps:
            tool = step.get("tool")
            args = step.get("args", {})
            if "path" in args:
                affected_locations.add(args["path"])
            if "source_directory" in args:
                affected_locations.add(args["source_directory"])
            if "destination_directory" in args:
                affected_locations.add(args["destination_directory"])

            if tool == "move_file":
                src = args.get("source_directory")
                pattern = args.get("file_pattern", "*")
                total_files += count_matching_files(src, pattern)

        # Update impact labels
        locs_str = f"{len(affected_locations)} location(s)"
        impact_msg = f"Operations: {len(steps)} | Files affected: {total_files} | Impacted: {locs_str}"
        self.impact_label.configure(text=impact_msg, text_color="#2563eb")

        # Enable approval UI
        self.awaiting_confirmation = True
        self.btn_confirm.configure(state="normal")
        self.btn_cancel.configure(state="normal")
        
        # Keep mic button disabled while waiting for plan approval
        self.mic_button.configure(state="disabled")
        self.set_status("Waiting for Confirmation...", "#2563eb")
        print("[INFO] Waiting for confirmation.")

    # ============================================================
    # UI BUTTON CALLBACKS
    # ============================================================
    def confirm_execution(self):
        if not self.awaiting_confirmation:
            return
        
        self.awaiting_confirmation = False
        self.btn_confirm.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.set_status("Executing...", "#2563eb")
        print("[INFO] Executing plan...")

        # Run execution in background thread
        threading.Thread(target=self._run_execution, daemon=True).start()

    def cancel_execution(self):
        if not self.awaiting_confirmation:
            return

        print("[INFO] Execution plan cancelled by user.")
        self.reset_plan_ui()
        
        # Re-enable mic button after cancelling plan
        self.is_listening = False
        self.mic_button.configure(state="normal")
        self.set_status("Ready", "#10b981")

    def _display_exit_plan_and_confirm(self):
        import json
        plan = self.current_state.get("plan", {})
        self.update_plan_text(json.dumps(plan, indent=2))
        self.impact_label.configure(text="Are you sure you want to exit Saarthi?", text_color="#ef4444")
        
        self.awaiting_confirmation = True
        self.btn_confirm.configure(state="normal")
        self.btn_cancel.configure(state="normal")
        self.mic_button.configure(state="disabled")
        self.set_status("Waiting for Confirmation...", "#ef4444")
        print("[INFO] Exit confirmation requested.")

    def _run_execution(self):
        try:
            if self.current_state.get("intent") == "exit":
                print("[INFO] Exit confirmed. Closing Saarthi...")
                self.after(500, self.quit)
                return

            execute_plan_node(self.current_state)
            print("[SUCCESS] Plan executed successfully.")
            self.after(0, lambda: self.set_status("Completed", "#10b981"))
        except Exception as e:
            print(f"[ERROR] Execution failed: {e}")
            self.after(0, lambda: self.set_status("Error", "#dc2626"))
        finally:
            if self.current_state.get("intent") != "exit":
                # Wait 3 seconds in Completed state, then reset UI and restore microphone button
                self.after(3000, self._finalize_execution_reset)

    def _finalize_execution_reset(self):
        self.reset_plan_ui()
        self.is_listening = False
        self.mic_button.configure(state="normal")
        self.set_status("Ready", "#10b981")


def main():
    # 🚀 Run startup checks (Ollama & Model Availability)
    status, error_msg = check_ollama_status()
    if not status:
        # If Ollama check fails, boot the warning application
        warning_app = SaarthiWarningApp(error_message=error_msg)
        warning_app.mainloop()
    else:
        # Otherwise, boot the main application
        app = SaarthiApp()
        app.mainloop()


if __name__ == "__main__":
    main()
