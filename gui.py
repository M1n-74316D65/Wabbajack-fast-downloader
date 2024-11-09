import json
import os
import time
import webbrowser
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Generator, List
import sv_ttk
import ctypes
import sys

import batch_download
import extract_modlist
from extract_modlist import write_urls_to_file

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

class ConsoleOutput(tk.Text):
    def __init__(self, master: tk.Widget, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.config(state="disabled")

    def print(self, text: str) -> None:
        self.config(state="normal")
        self.insert(tk.END, text + "\n")
        self.see(tk.END)
        self.config(state="disabled")

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

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.output_file_path = 'output.txt'
        self.links_amount = 0
        self.processed_links = tk.IntVar()
        self.generator: Optional[Generator[List[str], None, None]] = None
        
        self.setup_window()
        self.create_widgets()
        self.check_output_file()

    def setup_window(self) -> None:
        self.setup_windows_specific()
        ThemeManager.setup_theme(self)
        
        self.title('Wabbajack Fast Downloader')
        self.geometry('380x480')
        self.minsize(380, 450)

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
        # Create and organize the main UI container
        self.main_container = ttk.Frame(self, padding=8)
        self.main_container.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_file_section()
        self.create_progress_section()
        self.create_console_section()

    def create_file_section(self):
        # Create the section for mod list file selection
        # Contains file path entry, browse and extract buttons
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
        # Create the download progress section
        # Contains progress bar and download button
        progress_frame = ttk.LabelFrame(self.main_container, text="Download Progress", padding=5)
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            style='text.Horizontal.TProgressbar',
            length=200,
            maximum=self.links_amount,
            variable=self.processed_links
        )
        self.progress.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))

        download_btn = ttk.Button(
            progress_frame,
            text="Download Batch",
            command=self.download_links,
            width=15
        )
        download_btn.grid(row=1, column=0, pady=(5, 0))

    def create_console_section(self):
        # Create the console output section
        # Contains scrollable text area for logging
        console_frame = ttk.LabelFrame(self.main_container, text="Output", padding=5)
        console_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        console_frame.grid_columnconfigure(0, weight=1)
        console_frame.grid_rowconfigure(0, weight=1)

        self.console = TextScrollCombo(console_frame)
        self.console.grid(row=0, column=0, sticky="nsew")

        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1)

    def update_progress_bar(self) -> None:
        style = ttk.Style()
        style.configure('text.Horizontal.TProgressbar',
                       text=f"{self.processed_links.get()}/{self.links_amount}")

    def browse_file(self):
        """
        Opens a file dialog to select a Wabbajack mod list file, updates the
        file path entry box with the selected file's path.
        """
        filename = filedialog.askopenfilename(filetypes=[("Wabbajack mod list file", "*.wabbajack")])
        if filename:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(tk.END, filename)

    def import_links(self) -> None:
        self.processed_links.set(0)
        try:
            self.console.print("Importing URLs from output.txt file...")
            self.links_amount = batch_download.count_lines(self.output_file_path)
            if self.links_amount == 0:
                self.console.print("No URLs found in output.txt file.")
                return
                
            self.generator = batch_download.read_links_in_batches(self.output_file_path, 20)
            self.progress['maximum'] = self.links_amount
            self.update_progress_bar()
            self.console.print(f"Imported {self.links_amount} URLs.")
        except FileNotFoundError:
            self.console.print(f"Error: The file {self.output_file_path} was not found.")
        except Exception as e:
            self.console.print(f"Error importing URLs: {e}")

    def download_links(self):
        """
        Downloads the URLs from the generator.

        This function retrieves a batch of URLs from the generator and downloads them
        using the webbrowser module. The progress bar is updated accordingly, with a
        small delay between each link to prevent browser issues.
        """
        if self.generator is None:
            self.console.print("No URLs to download. Please import URLs from output.txt first.")
            return
        if self.links_amount == 0 or self.processed_links.get() == self.links_amount:
            self.console.print("No URLs to open.")
            return
        batch_links = self.get_batch()
        for link in batch_links:
            webbrowser.open(link)  # Uncommented this line
            time.sleep(0.5)  # Add small delay between links
            self.processed_links.set(self.processed_links.get() + 1)
        self.update_progress_bar()
        self.console.print(f"Opened {self.processed_links.get()} out of {self.links_amount} URLs.")

    def get_batch(self):
        """
        Returns a batch of URLs from the generator.
        """
        try:
            return next(self.generator)
        except StopIteration:
            return []

    def extract_file(self):
        """
        Extracts the 'modlist' file from the selected Wabbajack zip file and processes its content.

        This function retrieves the file path from the entry box, opens the selected zip file,
        and extracts the 'modlist' file. The extracted JSON content is then passed to the
        'extract_url' function for further processing. If any exception occurs during this
        process, an error message is printed to the console.
        """
        try:
            filename = self.file_path_entry.get()
            if filename != "":
                with zipfile.ZipFile(filename, 'r') as zipObj:
                    metadata_name = "modlist"
                    with zipObj.open(metadata_name, 'r') as metadata:
                        self.extract_url(json.loads(metadata.read().decode('utf-8').replace("'", '"')))
        except Exception as e:
            self.console.print("Error when extracting a file: " + e.__str__())

    def extract_url(self, modlist_file):
        """
        Extracts the URLs from the given mod list file and writes them to a file.

        This function takes a mod list file as input and generates URLs from it.
        The generated URLs are then written to a file called 'output.txt',
        overwriting any existing file. If the output file already exists, the
        user is asked if they want to overwrite it.

        :param modlist_file: A JSON object representing the content of a Wabbajack
            mod list file.
        :type modlist_file: dict
        """
        self.console.print("Generating URLs from JSON data...")
        urls = [url for entry in modlist_file.get("Archives", []) if (url := extract_modlist.generate_url(entry))]
        self.console.print(f"Generated {len(urls)} URLs.")

        # ask is output file exits
        if os.path.exists(self.output_file_path):
            answer = messagebox.askokcancel("Overwrite", "Do you want to overwrite the output file?")
            if not answer:
                self.console.print("Aborted by user.")
                return

        self.console.print(f"Writing URLs to {self.output_file_path}...")
        write_urls_to_file(urls, self.output_file_path)
        self.console.print("Successfully wrote URLs to file.")
        self.import_links()

    def check_output_file(self):
        # Check for existing output.txt and import if found
        if os.path.exists(self.output_file_path):
            self.console.print(f"Found output.txt file.")
            self.import_links()


def main():
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()
