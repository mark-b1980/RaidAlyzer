import os
import math
import tkinter as tk

from tkinter import ttk, filedialog, font

class RaidAlyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RaidAlyzer v1.1")
        self.geometry("800x600")
        
        self.files = []
        self.stats = []
        self.mirrors = []
        self.parity = []

        self.handles = []

        self.offset = 0
        self.bs = 512
        self.analysis_running = False

        self.first_potential_bootsector_found_on = ""
        self.first_potential_efi_part_found_on = ""

        # Main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Listbox
        self.listbox = tk.Listbox(main_frame, height=10)
        self.listbox.pack(fill=tk.X, padx=5, pady=5)

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.open_btn = ttk.Button(btn_frame, text="Open disk images", command=self.open_images)
        self.open_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(btn_frame, text="Start analysis", command=self.start_analysis, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(btn_frame, text="Stop analysis", command=self.stop_analysis, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Textboxes frame
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Add labels above each text box
        label_frame = ttk.Frame(text_frame)
        label_frame.pack(fill=tk.X, padx=5)
        ttk.Label(label_frame, text="Patterns and entropy in data").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(label_frame, text="Mirror analysis").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(label_frame, text="Parity analysis").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        mono_font = font.Font(family="Consolas", size=10)

        self.text1 = tk.Text(text_frame, wrap=tk.NONE, font=mono_font, width=30, height=15, state=tk.DISABLED)
        self.text1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.text2 = tk.Text(text_frame, wrap=tk.NONE, font=mono_font, width=30, height=15, state=tk.DISABLED)
        self.text2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.text3 = tk.Text(text_frame, wrap=tk.NONE, font=mono_font, width=30, height=15, state=tk.DISABLED)
        self.text3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Statusbar
        self.statusbar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)


    def open_images(self):
        files = filedialog.askopenfilenames(filetypes=[("Image Files", "*.img;*.dd;*.bin")])
        self.listbox.delete(0, tk.END)
        self.files.clear()
        self.handles.clear()

        for file in files:
            self.listbox.insert(tk.END, file)
            self.files.append(file)

        # Enable start button if files are selected
        if self.files:
            self.start_btn.config(state=tk.NORMAL)


    def start_analysis(self):
        # Open all files and store handles
        for file in self.files:
            self.handles.append(open(file, 'rb'))

        # Update status and buttons
        self.analysis_running = True

        # Reset analysis variables
        self.offset = 0
        self.stats.clear()
        self.mirrors.clear()
        self.parity.clear()

        # Disable start button during analysis
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        # Analysis loop (non-blocking)
        self.after(1, self.analysis_step)


    def analysis_step(self):
        if self.analysis_running:
            self.read_next_data_block()

            # Update UI after each block
            if self.offset % 100000 == 0:
                self.statusbar.config(text=f"Processed {self.offset} sectors.")
                self.update_output()

                self.statusbar.update_idletasks()
                self.text1.update_idletasks()
                self.text2.update_idletasks()
                self.text3.update_idletasks()

            # Schedule next step
            self.after(1, self.analysis_step)

        else:
            self.update_output()
            self.statusbar.update_idletasks()
            self.text1.update_idletasks()
            self.text2.update_idletasks()
            self.text3.update_idletasks()


    def read_next_data_block(self):
        # Read a block of data from each file
        data_blocks = []
        for i, handle in enumerate(self.handles):
            data = handle.read(self.bs)

            if data[-2:] == b'\x55\xAA' and self.first_potential_bootsector_found_on == "":
                file = os.path.basename(self.files[i])
                self.first_potential_bootsector_found_on = f"Bootsector signature found in file: {file} at sector {self.offset}"
            
            if data[:8].decode(errors='ignore') == "EFI PART" and self.first_potential_efi_part_found_on == "":
                file = os.path.basename(self.files[i])
                self.first_potential_efi_part_found_on = f"EFI PART header found in file:      {file} at sector {self.offset}"

            if not data:
                self.analysis_running = False
                self.statusbar.config(text="Reached end of one or more files.")
                self.stop_analysis()
                self.update_output()
                return
            
            data_blocks.append(data)

        # Initialize statistics for first data block
        if self.offset == 0:
            for handle in self.handles:
                self.stats.append({
                    'zero_blocks': 0,
                    'pattern_blocks': 0,
                    'entropy': 0.0,
                })

                self.mirrors.append([0 for x in range(len(self.handles))])

            self.parity = [0 for x in range(len(self.handles) + 1)]

        # Calculate statistics for each block
        self.offset += 1
        
        # Process the data blocks (placeholder for actual analysis logic)
        self.process_data_blocks(data_blocks)


    def calc_entropy(self, data):
        if not data:
            return 0.0
        freq = [0] * 256
        for b in data:
            freq[b] += 1
        entropy = 0.0
        for count in freq:
            if count:
                p = count / len(data)
                entropy -= p * math.log2(p)
        return entropy


    def check_parity(self, data_blocks):
        parity_block = bytearray(data_blocks.pop(0)) # Remove first block for parity comparison
        xor_result = bytearray(b'\x00' * self.bs)    # Initialize empty bytearray for XOR result

        for block in data_blocks:
            block = bytearray(block)
            for i in range(self.bs):
                xor_result[i] ^= block[i]            # XOR each byte

        if xor_result == parity_block:               # Check if XOR result matches "parity" block
            return 1
        
        return 0


    def process_data_blocks(self, data_blocks):
        # Update statistics for each data block
        for i in range(len(data_blocks)):
            if data_blocks[i] == b'\x00' * self.bs:
                self.stats[i]['zero_blocks'] += 1
            
            elif data_blocks[i] == bytes([data_blocks[i][0] for x in range(self.bs)]):
                self.stats[i]['pattern_blocks'] += 1

            self.stats[i]['entropy'] += self.calc_entropy(data_blocks[i])

        # Update mirror status for each data block
        for i in range(len(data_blocks)):
            for j in range(len(data_blocks)):
                if i != j and data_blocks[i] == data_blocks[j]:
                    self.mirrors[i][j] += 1

        # Update parity status for all data block
        self.parity[0] += self.check_parity(data_blocks.copy())

        # Check parity for all combinations of blocks with one block missing
        for i in range(len(data_blocks)):
            new_data_blocks = data_blocks.copy()
            del(new_data_blocks[i]) # Remove one block for parity calculation
            self.parity[i+1] += self.check_parity(new_data_blocks) # Update i+1 as 0 is full parity


    def update_output(self):
        # Update statistics textbox
        stats = " #  FILE                   ZERO %  PATTERN %  ENTROPY\n"
        for file in self.files:
            idx = self.files.index(file)
            file = os.path.basename(file)
            zero_percent = (self.stats[idx]['zero_blocks'] / self.offset) * 100
            pattern_percent = (self.stats[idx]['pattern_blocks'] / self.offset) * 100
            entropy = self.stats[idx]['entropy'] / self.offset
            stats += f"{idx:>2}  {file[:20]:<20}  {zero_percent:>5.1f} %  {pattern_percent:>7.1f} %  {entropy:>7.1f}\n" 

        stats += "\n---\n"

        # Check for first potential bootsector and EFI PART findings
        if self.first_potential_bootsector_found_on != "":
            stats += f"{self.first_potential_bootsector_found_on}\n"

        if self.first_potential_efi_part_found_on != "":
            stats += f"{self.first_potential_efi_part_found_on}\n"
        
        self.text1.config(state=tk.NORMAL)
        self.text1.delete(1.0, tk.END)
        self.text1.insert(tk.END, stats)
        self.text1.config(state=tk.DISABLED)

        # Update mirrors textbox
        mirrors = " " * 22 # 20 spaces for index column + 2 spaces as padding
        for file in self.files:
            file = os.path.basename(file)[:20]
            mirrors += f"{file:>20}  "
        mirrors += "\n"

        for i in range(len(self.files)):
            file = os.path.basename(self.files[i])[:20]
            mirrors += f"{file:>20}  "
            for j in range(len(self.files)):
                if i == j:
                    mirrors += " " * 17 + "---  "
                else:
                    mirrors += f"{self.mirrors[i][j]*100/self.offset:>19.0f}%  "
            mirrors += "\n"

        self.text2.config(state=tk.NORMAL)
        self.text2.delete(1.0, tk.END)
        self.text2.insert(tk.END, mirrors)
        self.text2.config(state=tk.DISABLED)

        # Update parity textbox
        file = "ALL FILES"
        parity = f"{file:<28}  {self.parity[0]*100/self.offset:>3.0f}%\n"
        for file in self.files:
            i = self.files.index(file)
            file = os.path.basename(file)[:20]
            parity += f"WITHOUT {file:<20}  {self.parity[i+1]*100/self.offset:>3.0f}%\n"

        self.text3.config(state=tk.NORMAL)
        self.text3.delete(1.0, tk.END)
        self.text3.insert(tk.END, parity)
        self.text3.config(state=tk.DISABLED)


    def stop_analysis(self):
        # Close all file handles
        for handle in self.handles:
            handle.close()

        self.handles.clear()
        
        # Stop analysis flag and activate start button
        self.analysis_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.statusbar.config(text="Analysis stopped.")


if __name__ == "__main__":
    app = RaidAlyzerApp()
    app.mainloop()