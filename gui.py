import json
import os
import webbrowser
import zipfile
import tkinter as tk

import batch_download
import extract_modlist

from tkinter import filedialog, messagebox, ttk

from extract_modlist import write_urls_to_file


class TextScrollCombo(tk.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ensure a consistent GUI size
        self.grid_propagate(False)
        # implement stretchability
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # create a Text widget
        self.txt = ConsoleOutput(self)
        self.txt.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # create a Scrollbar and associate it with txt
        scrollb = tk.Scrollbar(self, command=self.txt.yview)
        scrollb.grid(row=0, column=1, sticky='nsew')
        self.txt['yscrollcommand'] = scrollb.set

    def print(self, text):
        self.txt.print(text)


class ConsoleOutput(tk.Text):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.config(state="disabled")

    def print(self, text):
        self.config(state="normal")
        self.insert(tk.END, text + "\n")
        self.see(tk.END)
        self.config(state="disabled")


def update_progress_bar_value():
    s.configure('text.Horizontal.TProgressbar',
                text=f"{processed_links.get()}/{links_amount}")


def import_links():
    global links_amount
    global processed_links
    global generator
    processed_links.set(0)
    try:
        console.print("Importing URLs from output.txt file...")
        links_amount = batch_download.count_lines(output_file_path)
        if links_amount == 0:
            console.print("No URLs found in output.txt file.")
            return
        generator = batch_download.read_links_in_batches(output_file_path, 20)
        progress['maximum'] = links_amount
        update_progress_bar_value()
        console.print(f"Imported {links_amount} URLs.")
    except FileNotFoundError:
        print(f"Error: The file {output_file_path} was not found.")
    except Exception as e:
        console.print(f"Error importing URLs: {e}")


def download_links():
    """
    Downloads the URLs from the generator.

    This function retrieves a batch of URLs from the generator and downloads them
    using the webbrowser module. The progress bar is updated accordingly.

    If no URLs are available for download, an error message is printed to the console.
    """
    global links_amount
    global processed_links
    if generator is None:
        console.print("No URLs to download. Please import URLs from output.txt first.")
        return
    if links_amount == 0 or processed_links.get() == links_amount:
        console.print("No URLs to open.")
        return
    batch_links = get_batch()
    for link in batch_links:
        #webbrowser.open(link)
        processed_links.set(processed_links.get() + 1)
    update_progress_bar_value()
    console.print(f"Opened {processed_links.get()} out of {links_amount} URLs.")


def get_batch():
    """
    Returns a batch of URLs from the generator.
    """
    try:
        return next(generator)
    except StopIteration:
        return []


def browse_file():
    """
    Opens a file dialog to select a Wabbajack mod list file, updates the
    file path entry box with the selected file's path.
    """
    filename = filedialog.askopenfilename(filetypes=[("Wabbajack mod list file", "*.wabbajack")])
    if filename != "":
        file_path_entrybox.delete(0, tk.END)
        file_path_entrybox.insert(tk.END, filename)


def extract_file():
    """
    Extracts the 'modlist' file from the selected Wabbajack zip file and processes its content.

    This function retrieves the file path from the entry box, opens the selected zip file,
    and extracts the 'modlist' file. The extracted JSON content is then passed to the
    'extract_url' function for further processing. If any exception occurs during this
    process, an error message is printed to the console.
    """
    try:
        filename = file_path_entrybox.get()
        if filename != "":
            with zipfile.ZipFile(filename, 'r') as zipObj:
                metadata_name = "modlist"
                with zipObj.open(metadata_name, 'r') as metadata:
                    extract_url(json.loads(metadata.read().decode('utf-8').replace("'", '"')))
    except Exception as e:
        console.print("Error when extracting a file: " + e.__str__())


def extract_url(modlist_file):
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
    console.print("Generating URLs from JSON data...")
    urls = [url for entry in modlist_file.get("Archives", []) if (url := extract_modlist.generate_url(entry))]
    console.print(f"Generated {len(urls)} URLs.")

    # ask is output file exits
    if os.path.exists(output_file_path):
        answer = messagebox.askokcancel("Overwrite", "Do you want to overwrite the output file?")
        if not answer:
            console.print("Aborted by user.")
            return

    console.print(f"Writing URLs to {output_file_path}...")
    write_urls_to_file(urls, output_file_path)
    import_links()
    console.print("Successfully wrote URLs to file.")


root = tk.Tk()
root.title('Wabbajack URL Exporter')
root.geometry('500x500')
root.resizable(height=False, width=False)

output_file_path = 'output.txt'
links_amount = 0
processed_links = tk.IntVar()
generator = None

console = TextScrollCombo(root, width=500, height=350)
console.place(y=150, relwidth=1)

file_path_entrybox = tk.Entry(root, font=50, width=35)
file_path_entrybox.place(x=10, y=32)



select_wabbajack_file_button = tk.Button(root, text="Select", font=40, command=browse_file)
select_wabbajack_file_button.place(x=340, y=28)
import_btn = tk.Button(root, text="Extract", font=40, command=extract_file)
import_btn.place(x=410, y=28)

import_instruction = tk.Label(root, text=f"Select a Wabbajack mod list file, then click {import_btn.cget('text')}", font=40)
import_instruction.place(x=10, y=5)

s = ttk.Style(root)
s.layout('text.Horizontal.TProgressbar',
         [('Horizontal.Progressbar.trough',
           {'children': [('Horizontal.Progressbar.pbar',
                          {'side': 'left', 'sticky': 'ns'})],
            'sticky': 'nswe'}),
          ('Horizontal.Progressbar.label', {'sticky': 'nswe'})])
s.configure('text.Horizontal.TProgressbar', text='0/0', anchor='center', )

progress = ttk.Progressbar(root, orient=tk.HORIZONTAL, style='text.Horizontal.TProgressbar', length=450,
                           maximum=links_amount, variable=processed_links)
progress.place(x=10, y=120)

download_batch_button = tk.Button(root, text="Download batch", font=40, command=download_links)
download_batch_button.place(x=180, y=80)

if os.path.exists(output_file_path):
    console.print(f"Found output.txt file.")
    import_links()

root.mainloop()
