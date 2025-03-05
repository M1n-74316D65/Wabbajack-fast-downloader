import os
import csv
import json
import sv_ttk
import xxhash
import base64
import struct
import threading
import queue
import zipfile
import ctypes
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Generator, List
from downloader import download_nexus_mods
from extract_modlist import generate_url, write_to_csv

# Theme Manager
class ThemeManager:
    COLORS = {
        'dark': { 
            'bg': '#1a1a1a',
            'fg': '#ffffff',
            'accent': '#3d3d3d',
            'highlight': '#0078d4'
        }
    }

    @staticmethod
    def setup_theme(root: tk.Tk) -> None:
        sv_ttk.set_theme("dark")
        style = ttk.Style(root)
        colors = ThemeManager.COLORS['dark']

        style.configure('TFrame', background=colors['bg'])
        style.configure('TLabelframe', background=colors['bg'], padding=8, borderwidth=0)
        style.configure('TLabelframe.Label', font=('Segoe UI', 8),
                        background=colors['bg'], foreground=colors['fg'])
        style.configure('TButton', padding=4, borderwidth=0)
        style.configure('TEntry', fieldbackground=colors['accent'], borderwidth=0)
        style.configure('Horizontal.TProgressbar', thickness=4,
                       background=colors['highlight'])

# Console Output
class ConsoleOutput(tk.Text):
    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.config(state="disabled")

    def print(self, text: str) -> None: 
        self.config(state="normal")
        self.insert(tk.END, text + "\n")
        self.see(tk.END)
        self.config(state="disabled")

# Text Scroll Combo
class TextScrollCombo(tk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setup_widget()

    def setup_widget(self) -> None:
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        text_frame = ttk.Frame(self)
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        self.txt = ConsoleOutput(text_frame)
        self.txt.grid(row=0, column=0, sticky="nsew")
        self.configure_text_widget()

        scrollb = ttk.Scrollbar(text_frame, command=self.txt.yview)
        scrollb.grid(row=0, column=1, sticky='nsew')
        self.txt['yscrollcommand'] = scrollb.set

    def configure_text_widget(self) -> None:
        self.txt.configure(
            bg='#1a1a1a',
            fg='#ffffff',
            font=('Consolas', 9),
            insertbackground='#ffffff',
            selectbackground='#0078d4',
            selectforeground='#ffffff',
            borderwidth=0,
            padx=8,
            pady=4
        )

    def print(self, text: str) -> None:
        self.txt.print(text)

# Downloader Class
class Downloader:
    def __init__(self, app: 'Application', queue_size: int = 5):
        self.app = app
        self.state = {}
        self.download_queue = queue.Queue()
        self.pending_verifications = []
        self.csv_file = 'output.csv'
        self.state_file = 'download_state.json'
        self.queue_size = queue_size
        self.total_files = 0
        self.processed_files = 0
        

    def calculate_file_hash_base64(self, file_path: str) -> str:
        hasher = xxhash.xxh64(seed=0)
        with open(file_path, 'rb') as f:
            while data := f.read(1024*1024):
                hasher.update(data)
        digest_bytes = struct.pack('<Q', hasher.intdigest())
        return base64.b64encode(digest_bytes).decode('utf-8')

    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
        except Exception as e:
            self.log(f"Error loading state: {e}", error=True)

    def save_state(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            self.log(f"Error saving state: {e}", error=True)

    def verify_and_update_state(self, filepath: str, expected_hash: str, url: str, success: bool):
        try:
            normalized_path = os.path.abspath(filepath)
            
            if success:
                current_hash = self.calculate_file_hash_base64(normalized_path)
                verified = current_hash == expected_hash
                self.state[normalized_path] = {
                    'hash': expected_hash,
                    'verified': verified
                }
                self.save_state()  # Save state immediately after download
                self.log(f"Verification {'succeeded' if verified else 'failed'} for {filepath}")
            else:
                self.state[normalized_path] = {'hash': None, 'verified': False}
                self.save_state()
                self.log(f"Download failed: {url}", error=True)
        
        except Exception as e:
            self.log(f"Verification failed: {e}", error=True)
            self.state[normalized_path] = {'hash': None, 'verified': False}
            self.save_state()

    def process_csv_row(self, row: dict):
        url = row['URL']
        expected_hash = row['Hash']
        name = row['Name']
        filepath = os.path.join(self.app.download_location_var.get(), name)

        if self.check_existing_file(filepath, expected_hash):
            self.processed_files += 1
            self.app.update_progress(self.processed_files, self.total_files)
            return

        self.download_queue.put((url, filepath))
        self.pending_verifications.append((filepath, expected_hash, url))

    def check_existing_file(self, filepath: str, expected_hash: str) -> bool:
        """Check if file exists and is valid"""
        try:
            # Check if file path is properly normalized
            normalized_path = os.path.abspath(filepath)
            
            # Case 1: File exists in state
            if normalized_path in self.state:
                stored = self.state[normalized_path]
                if stored.get('verified', False):
                    if stored['hash'] == expected_hash:
                        self.log(f"File verified in state: {filepath}", debug=True)
                        return True
                    else:
                        self.log("State hash mismatch detected", debug=True)
                else:
                    self.log("Previously failed verification", debug=True)
            
            # Case 2: Check actual file hash
            if os.path.exists(normalized_path):
                current_hash = self.calculate_file_hash_base64(normalized_path)
                if current_hash == expected_hash:
                    # Update state immediately
                    self.state[normalized_path] = {
                        'hash': expected_hash,
                        'verified': True
                    }
                    self.save_state()  # Save immediately after verification
                    self.log(f"Verified existing file: {filepath}", debug=True)
                    return True
                else:
                    self.log("File hash mismatch detected", debug=True)
            else:
                self.log("File not found, will download.", debug=True)
        
        except Exception as e:
            self.log(f"Verification error: {str(e)}", error=True)
        
        return False

    def download_batch(self):
        urls = []
        filepaths = []
        url_map = {}

        while not self.download_queue.empty() and len(urls) < self.queue_size:
            url, filepath = self.download_queue.get()
            urls.append(url)
            filepaths.append(filepath)
            url_map[url] = filepath

        if not urls:
            return []

        try:
            cookie = "nexusmods_session="+self.app.session_var.get()
            _, results = download_nexus_mods(urls, filepaths, cookie)
            return [(url_map[url], success) for url, success in zip(urls, results)]
        except Exception as e:
            self.log(f"Batch download error: {e}", error=True)
            return [(url_map[url], False) for url in urls]

    def process_results(self, results: list):
        for filepath, success in results:
            verification_info = next((v for v in self.pending_verifications if v[0] == filepath), None)
            if verification_info:
                fp, expected_hash, url = verification_info
                self.verify_and_update_state(fp, expected_hash, url, success)
                self.pending_verifications.remove(verification_info)
                self.processed_files += 1
                self.app.update_progress(self.processed_files, self.total_files)

    def run(self):
        try:
            self.queue_size = self.app.queue_size_var.get()
            self.load_state()
            os.makedirs(self.app.download_location_var.get(), exist_ok=True)

            with open(self.csv_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = sorted(reader, key=lambda x: int(x.get('Size', 0)))
                #rows = rows[4033+100:]
                #rows = sorted(reader, key=lambda x: int(x.get('Size', 0)), reverse=True)
                self.total_files = len(rows)
                self.app.set_total_files(self.total_files)

                for i, row in enumerate(rows):
                    self.process_csv_row(row)
                    if self.download_queue.qsize() >= self.queue_size or i == len(rows)-1:
                        results = self.download_batch()
                        self.process_results(results)
                        self.save_state()

        except Exception as e:
            self.log(f"Download process failed: {e}", error=True)
        finally:
            self.save_state()
            self.app.download_complete()

    def log(self, message: str, error: bool = False, debug: bool = False):
        """Centralized logging with level control"""
        if debug and not self.app.debug_mode.get():
            return
        
        level = "ERROR" if error else "DEBUG" if debug else "INFO"
        formatted_msg = f"[{level}] {message}"
        
        # Only show ERROR messages when not in debug mode
        if not self.app.debug_mode.get() and level == "DEBUG":
            return
        
        self.app.queue_put(('log', formatted_msg))

# Main Application
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.output_file_path = 'output.csv'
        self.links_amount = 0
        self.processed_links = tk.IntVar()
        self.generator: Optional[Generator[List[str], None, None]] = None
        self.queue = queue.Queue()
        self.downloader: Optional[Downloader] = None
        self.queue_size_var = tk.IntVar(value=5)
        self.session_var = tk.StringVar(value="YOUR NEXUS SESSIONID")
        self.download_location_var = tk.StringVar(value="D:/Games/download/Location")
        
        # Load saved data
        self.load_data()
        
        # Set up exit protocol
        self.protocol("WM_DELETE_WINDOW", self.save_and_exit)

        self.setup_window()
        self.create_widgets()
        self.check_output_file()
        
        
    def load_data(self):
        try:
            with open('config.json', 'r') as f:
                data = json.load(f)
                # Use stored value if exists, keep default otherwise
                self.session_var.set(data.get('nexusmods_session', self.session_var.get()))
                self.download_location_var.set(data.get('download_dir', self.download_location_var.get()))
                self.queue_size_var.set(data.get('parallel_queue_size', self.queue_size_var.get()))
        except FileNotFoundError:
            pass  # Keep default value if no config exists

    def save_data(self):
        data = {
            'nexusmods_session': self.session_var.get(),
            'download_dir':self.download_location_var.get(),
            'parallel_queue_size': self.queue_size_var.get(),
        }
        with open('config.json', 'w') as f:
            json.dump(data, f, indent=2)

    def save_and_exit(self):
        self.save_data()
        self.destroy()

    def setup_window(self) -> None:
        self.setup_windows_specific()
        ThemeManager.setup_theme(self)

        self.title('Wabbajack Fast Downloader2')
        self.geometry('1000x600')  # Increased width to 1000
        self.minsize(800, 500)
        

    def setup_windows_specific(self) -> None:
        if sys.platform != 'win32':
            return
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            self.iconbitmap(default="icon.ico")

            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            hwnd = self.winfo_id()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(ctypes.c_int(2)),
                ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    def create_widgets(self):
        self.main_container = ttk.Frame(self, padding=8)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_file_section()
        self.create_progress_section()
        self.create_console_section()
        self.create_right_panel()
        self.create_debug_section()

    def create_file_section(self):
        file_frame = ttk.LabelFrame(self.main_container, text="Mod List Selection", padding=5)
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        file_frame.grid_columnconfigure(0, weight=1)

        self.file_path_entry = ttk.Entry(file_frame)
        self.file_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        browse_btn = ttk.Button(file_frame, text="Browse", command=self.browse_file, width=8)
        browse_btn.grid(row=0, column=1, padx=(0, 2))

        extract_btn = ttk.Button(file_frame, text="Extract", command=self.extract_file, width=8)
        extract_btn.grid(row=0, column=2)

    def create_progress_section(self):
        progress_frame = ttk.LabelFrame(self.main_container, text="Download Progress", padding=5)
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            style='text.Horizontal.TProgressbar',
            length=200
        )
        self.progress.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))

        self.progress_label = ttk.Label(progress_frame, text="0/0 files")
        self.progress_label.grid(row=0, column=1, padx=5)

        # Combined controls frame
        controls_frame = ttk.Frame(progress_frame)
        controls_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky="ew")

        # Parallel downloads control
        settings_frame = ttk.Frame(controls_frame)
        settings_frame.pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(settings_frame, text="Parallel downloads:").pack(side=tk.LEFT, padx=(0, 5))
        self.queue_size_spin = ttk.Spinbox(
            settings_frame,
            from_=1,
            to=15,
            textvariable=self.queue_size_var,
            width=3
        )
        self.queue_size_spin.pack(side=tk.LEFT)

        # Session input section
        session_frame = ttk.Frame(controls_frame)
        session_frame.pack(side=tk.LEFT)

        ttk.Label(session_frame, text="NexusMods Session:").pack(side=tk.LEFT)
        self.entry = ttk.Entry(session_frame, textvariable=self.session_var, width=25)
        self.entry.pack(side=tk.LEFT, padx=5)

        # Button and download location container
        button_location_frame = ttk.Frame(progress_frame)
        button_location_frame.grid(row=2, column=0, columnspan=2, pady=(5, 0), sticky="ew")
        button_location_frame.grid_columnconfigure(1, weight=1)

        # Download button
        download_btn = ttk.Button(
            button_location_frame,
            text="Download Batch",
            command=self.start_download,
            width=15
        )
        download_btn.grid(row=0, column=0, padx=(0, 10))

        # Download location input
        download_location_frame = ttk.Frame(button_location_frame)
        download_location_frame.grid(row=0, column=1, sticky="ew")
        download_location_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(download_location_frame, text="Download Location:").grid(row=0, column=0, padx=(0, 5))
        self.download_location_entry = ttk.Entry(
            download_location_frame,
            textvariable=self.download_location_var
        )
        self.download_location_entry.grid(row=0, column=1, sticky="ew")

    def create_console_section(self):
        console_frame = ttk.LabelFrame(self.main_container, text="Output", padding=5)
        console_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(0, weight=1)

        self.console = TextScrollCombo(console_frame, width=600, height=300)
        self.console.grid(row=0, column=0, sticky="nsew")

    def create_right_panel(self):
        right_panel_frame = ttk.LabelFrame(self.main_container, text="Information", padding=5)
        right_panel_frame.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=8, pady=(0, 0))
        right_panel_frame.grid_columnconfigure(0, weight=1)
        right_panel_frame.grid_rowconfigure(0, weight=1)

        self.info_text = ConsoleOutput(right_panel_frame)
        self.info_text.grid(row=0, column=0, sticky="nsew")

    def create_debug_section(self):
        debug_frame = ttk.Frame(self.main_container)
        debug_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.debug_mode = tk.BooleanVar(value=False)
        debug_check = ttk.Checkbutton(debug_frame, text="Debug Mode", variable=self.debug_mode)
        debug_check.pack(side=tk.LEFT, padx=5)

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Wabbajack mod list file", "*.wabbajack")])
        if filename:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(tk.END, filename)

    def extract_file(self):
        try:
            filename = self.file_path_entry.get()
            if filename != "":
                with zipfile.ZipFile(filename, 'r') as zipObj:
                    metadata_name = "modlist"
                    with zipObj.open(metadata_name, 'r') as metadata:
                        self.extract_modlist(json.loads(metadata.read().decode('utf-8').replace("'", '"')))
        except Exception as e:
            self.console.print(f"Error extracting file: {e}")
            
    def extract_modlist(self, modlist_file):
        self.console.print("Processing JSON data...")
        
        processed_entries = []
        
        for entry in modlist_file.get("Archives", []):
            url = generate_url(entry)
            if url:
                entry_copy = entry.copy()  # Create a copy to avoid modifying original
                entry_copy['URL'] = url
                processed_entries.append(entry_copy)

        print(f"Processed {len(processed_entries)} entries.")
        
        if os.path.exists(self.output_file_path):
            answer = messagebox.askokcancel("Overwrite", "Do you want to overwrite the output file?")
            if not answer:
                self.console.print("Aborted by user.")
                return

        # Write all data to CSV file
        write_to_csv(processed_entries, self.output_file_path)
        self.console.print("Successfully wrote csv file.")
        #self.import_links()
        

    def check_output_file(self):
        if os.path.exists(self.output_file_path):
            self.console.print(f"Found output.csv file.")
            #self.import_links()

    def import_links(self):
        self.processed_links.set(0)
        try:
            self.console.print("Importing URLs from output.txt file...")
            self.links_amount = self.count_lines(self.output_file_path)
            if self.links_amount == 0:
                self.console.print("No URLs found in output.txt file.")
                return

            self.generator = self.read_links_in_batches(self.output_file_path, 20)
            self.progress['maximum'] = self.links_amount
            self.update_progress(0, self.links_amount)
            self.console.print(f"Imported {self.links_amount} URLs.")
        except FileNotFoundError:
            self.console.print(f"Error: The file {self.output_file_path} was not found.")
        except Exception as e:
            self.console.print(f"Error importing URLs: {e}")

    def count_lines(self, filename: str) -> int:
        with open(filename, 'r') as f:
            return sum(1 for _ in f)

    def read_links_in_batches(self, filename: str, batch_size: int) -> Generator[List[str], None, None]:
        with open(filename, 'r') as f:
            batch = []
            for line in f:
                batch.append(line.strip())
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch

    def start_download(self):
        if not self.downloader:
            self.downloader = Downloader(self, queue_size=self.queue_size_var.get())
        threading.Thread(target=self.downloader.run, daemon=True).start()

    def update_progress(self, processed: int, total: int):
        self.progress['value'] = processed
        self.progress['maximum'] = total
        self.progress_label.config(text=f"{processed}/{total} files")
        self.info_text.print(f"Processed: {processed}/{total} files")

    def set_total_files(self, total: int):
        self.links_amount = total
        self.update_progress(0, total)

    def download_complete(self):
        messagebox.showinfo("Complete", "Download process finished")
        self.info_text.print("Download process completed")

    def queue_put(self, item):
        self.queue.put(item)

    def process_queue(self):
        while not self.queue.empty():
            msg = self.queue.get()
            if msg[0] == 'log':
                self.console.print(msg[1])
        self.after(100, self.process_queue)

    def mainloop(self):
        self.process_queue()
        super().mainloop()

def main():
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()