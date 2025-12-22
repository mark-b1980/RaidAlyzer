import os
import math
import time
import tkinter as tk

from datetime import datetime
from tkinter import ttk, filedialog, font

class RaidAlyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.VERSION = "2.4"
        self.title(f"RaidAlyzer v{self.VERSION}")
        self.geometry("800x600")
        self.state('zoomed')
        
        self.files = []
        self.filenames = []
        self.stats = []
        self.mirrors = []
        self.parity = []

        self.handles = []
        self.max_sectors = 0
        self.start_time = 0

        self.last_parity_check_pattern = ""
        self.parity_check_log = None

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
        ttk.Label(label_frame, text="Parity analysis").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        mono_font = font.Font(family="Consolas", size=10)

        self.text1 = tk.Text(text_frame, wrap=tk.NONE, font=mono_font, width=30, height=15, state=tk.DISABLED)
        self.text1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.text3 = tk.Text(text_frame, wrap=tk.NONE, font=mono_font, width=30, height=15, state=tk.DISABLED)
        self.text3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        ttk.Label(main_frame, text="Mirror analysis").pack(fill=tk.X, expand=False, pady=10)
        self.text2 = tk.Text(main_frame, wrap=tk.NONE, font=mono_font, width=30, height=15, state=tk.DISABLED)
        self.text2.pack(fill=tk.BOTH, expand=True, pady=10)

        # Statusbar
        self.statusbar = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)


    def open_images(self):
        files = filedialog.askopenfilenames(filetypes=[("Image Files", "*.img;*.dd;*.bin")])
        self.listbox.delete(0, tk.END)
        self.files.clear()
        self.filenames.clear()
        self.handles.clear()

        for file in files:
            self.listbox.insert(tk.END, file)
            self.files.append(file)
            self.filenames.append(os.path.basename(file))

        # Enable start button if files are selected
        if self.files:
            self.start_btn.config(state=tk.NORMAL)


    def start_analysis(self):
        # Open all files and store handles
        for file in self.files:
            self.handles.append(open(file, 'rb'))
            if self.max_sectors == 0:
                self.max_sectors = os.path.getsize(file) // self.bs
            else:
                self.max_sectors = min(self.max_sectors, os.path.getsize(file) // self.bs)

        # Update status and buttons
        self.analysis_running = True
        self.start_time = time.time()

        # Reset analysis variables
        self.offset = 0
        self.last_parity_check_pattern = ""
        self.parity_check_log = open("parity_check.log", "w")

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
            sectors_to_process = 10000
            for _ in range(sectors_to_process):
                if not self.analysis_running: 
                    break
                self.read_next_data_block()

            # Update UI after each block
            self.statusbar.config(text=f"Processed {self.offset} / {self.max_sectors} sectors: {self.offset * 100 / self.max_sectors:.1f}% ({self.offset / (time.time() - self.start_time):.1f} sectosr/sec.)")
            self.update_output()

            # Schedule next step
            self.after(1, self.analysis_step)

        else:
            self.update_output()


    def read_next_data_block(self):
        # Read a block of data from each file
        data_blocks = {}
        for i, handle in enumerate(self.handles):
            data = handle.read(self.bs)

            if self.first_potential_bootsector_found_on == "" and data[-2:] == b'\x55\xAA':
                self.first_potential_bootsector_found_on = f"Bootsector signature found in file: {self.filenames[i]} at sector {self.offset}"
            
            if self.first_potential_efi_part_found_on == "" and data[:8].decode(errors='ignore') == "EFI PART":
                self.first_potential_efi_part_found_on = f"EFI PART header found in file:      {self.filenames[i]} at sector {self.offset}"

            if not data:
                self.analysis_running = False
                self.statusbar.config(text="Reached end of one or more files.")
                self.stop_analysis()
                self.update_output()
                return
            
            data_blocks[self.filenames[i]] = data

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
        """
        parity_block = bytearray(data_blocks.pop(0)) # Remove first block for parity comparison
        xor_result = bytearray(b'\x00' * self.bs)    # Initialize empty bytearray for XOR result

        for block in data_blocks:
            block = bytearray(block)
            for i in range(self.bs):
                xor_result[i] ^= block[i]            # XOR each byte
        """
        parity_block = bytearray(data_blocks.pop(0))                  # Remove first block for parity comparison
        parity_block = int.from_bytes(parity_block, byteorder='big')  # Convert to integer for XOR comparison
        xor_result = 0                                                # Initialize empty XOR result

        for block in data_blocks:
            block_int = int.from_bytes(block, byteorder='big')        # Convert block to integer
            xor_result ^= block_int                                   # XOR each block

        return int(parity_block == xor_result)                        # Return 1 if parity matches
    

    def process_data_blocks(self, data_block_dict):
        # Update statistics for each data block
        data_blocks = list(data_block_dict.values())
        for i in range(len(data_blocks)):
            if data_blocks[i] == b'\x00' * self.bs:
                self.stats[i]['zero_blocks'] += 1
            
            elif data_blocks[i] == bytes([data_blocks[i][0] for x in range(self.bs)]):
                self.stats[i]['pattern_blocks'] += 1

            # Calculate entropy only for non-zero, non-pattern blocks
            else:
                self.stats[i]['entropy'] += self.calc_entropy(data_blocks[i])

        # Update mirror status for each data block
        for i in range(len(data_blocks)):
            for j in range(len(data_blocks)):
                if i != j and data_blocks[i] == data_blocks[j]:
                    self.mirrors[i][j] += 1

        # Update parity status for all data block
        res = self.check_parity(data_blocks.copy())
        self.parity[0] += res

        # Check for new pattern
        one_combination_checked_out = False
        if res == 1:
            one_combination_checked_out = True
            parity_check_pattern = " + ".join(data_block_dict.keys())
            if self.last_parity_check_pattern != parity_check_pattern:
                self.parity_check_log.write(f"{self.offset};{parity_check_pattern}\n")
                self.last_parity_check_pattern = parity_check_pattern

        # Check parity for all combinations of blocks with one block missing
        for i in range(len(data_blocks)):
            new_data_blocks = data_block_dict.copy()
            del(new_data_blocks[self.filenames[i]])                 # Remove one block for parity calculation
            res = self.check_parity(list(new_data_blocks.values())) 
            self.parity[i+1] += res                                 # Update i+1 as 0 is full parity
            
            if res == 1:
                one_combination_checked_out = True
                parity_check_pattern = " + ".join(new_data_blocks.keys())
                if self.last_parity_check_pattern != parity_check_pattern:
                    self.parity_check_log.write(f"{self.offset};{parity_check_pattern}\n")
                    self.last_parity_check_pattern = parity_check_pattern

        if not one_combination_checked_out:
            parity_check_pattern = "NO_MATCH"
            if self.last_parity_check_pattern != parity_check_pattern:
                self.parity_check_log.write(f"{self.offset};{parity_check_pattern}\n")
                self.last_parity_check_pattern = parity_check_pattern

    def update_output(self):
        # Update statistics textbox
        stats = " #  FILE                   ZERO %  PATTERN %  ENTROPY\n"
        for idx in range(len(self.filenames)):
            file = self.filenames[idx]
            zero_percent = (self.stats[idx]['zero_blocks'] / self.offset) * 100
            pattern_percent = (self.stats[idx]['pattern_blocks'] / self.offset) * 100
            entropy = self.stats[idx]['entropy'] / self.offset
            stats += f"{idx:>2}  {file[:20]:<20}  {zero_percent:>5.1f} %  {pattern_percent:>7.1f} %  {entropy:>7.1f}\n" 

        stats += "\n---\n\n"

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
        for file in self.filenames:
            file = file[:20]
            mirrors += f"{file:>20}  "
        mirrors += "\n"

        for i in range(len(self.files)):
            file = self.filenames[i][:20]
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
        for i in range(len(self.filenames)):
            file = self.filenames[i][:20]
            parity += f"WITHOUT {file:<20}  {self.parity[i+1]*100/self.offset:>3.0f}%\n"

        self.text3.config(state=tk.NORMAL)
        self.text3.delete(1.0, tk.END)
        self.text3.insert(tk.END, parity)
        self.text3.config(state=tk.DISABLED)

        # Update
        self.statusbar.update_idletasks()
        self.text1.update_idletasks()
        self.text2.update_idletasks()
        self.text3.update_idletasks()


    def stop_analysis(self):
        self.update_output()

        # Close all file handles
        self.parity_check_log.close()
        for handle in self.handles:
            handle.close()

        self.parity_check_log = None
        self.handles.clear()
        
        # Stop analysis flag and activate start button
        self.analysis_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.statusbar.config(text="Writing report")
        self.statusbar.update_idletasks()

        report_file = f"raidalyzer_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(report_file, "w") as report:
            report.write(f"RaidAlyzer v{self.VERSION} Report\n")
            report.write("======================\n\n")
            report.write(f"Analyzed files:\n")
            report.write(f"---------------------\n")
            for file in self.filenames:
                report.write(f"- {file}\n")
            report.write("\n\n")

            report.write("Statistics:\n")
            report.write(f"---------------------\n")
            report.write(self.text1.get(1.0, tk.END))
            report.write("\n\n")

            report.write("Mirror Analysis:\n")
            report.write(f"---------------------\n")
            report.write(self.text2.get(1.0, tk.END))
            report.write("\n\n")

            report.write("Parity Analysis:\n")
            report.write(f"---------------------\n")
            report.write(self.text3.get(1.0, tk.END))
            report.write("\n\n")

            report.write("Parity Check Log:\n")
            report.write(f"---------------------\n")

            parity_check_log = []
            with open("parity_check.log", "r") as logfile:
                for line in logfile:
                    parity_check_log.append(line.strip().split(";"))
                    if len(parity_check_log) > 9999:
                        break
            
            # Add another log line and adding the last sector of the read data
            if len(parity_check_log) < 10000:
                parity_check_log.append([str(self.offset), "..."])

            # Write ranges to report
            for i in range(len(parity_check_log) - 1):
                from_sec = int(parity_check_log[i][0])
                to_sec = int(parity_check_log[i+1][0]) - 1
                # Ensure to_sec is not less than from_sec
                if to_sec < from_sec:
                    to_sec = from_sec
                pattern = parity_check_log[i][1].strip()

                report.write(f"{from_sec} - {to_sec} : {pattern}\n")

        self.statusbar.config(text="Analysis complete. Report written to: raidalyzer_report.txt")
        self.statusbar.update_idletasks()


if __name__ == "__main__":
    app = RaidAlyzerApp()
    app.mainloop()