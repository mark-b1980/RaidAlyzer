import os
import sys
import json
import math
import time

import tkinter as tk
import matplotlib.pyplot as plt

from datetime import datetime
from tkinter import ttk, filedialog, font, messagebox

class RaidAlyzerApp(tk.Tk):
    VERSION = "3.0.8"

    def __init__(self):
        super().__init__()
        self.title(f"RaidAlyzer v{RaidAlyzerApp.VERSION}")
        self.geometry("800x600")
        self.state('zoomed')

        # Set window icon
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base_path, "icon.ico")
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)
        
        # Base values for 
        self.bs = 512                     # Check sector by sector 
        self.analysis_block_size = 10000  # Analze a 10.000 blocks before updating output
        self.analysis_start_sector = 0    # Start offset in sectors

        # Shared runtime status data
        self.files = []
        self.filenames = []
        self.stats = []
        self.mirrors = []
        self.parity = []

        self.handles = []
        self.max_sectors = 0
        self.start_time = 0
        self.first_analysis_block = False
        self.analysis_block_entropy = {}
        self.run_only_one_block = False

        self.offset = 0

        self.last_parity_check_pattern = ""
        self.parity_check_log = None
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

        # Offset label and entry
        ttk.Label(btn_frame, text="Offset (sectors):").pack(side=tk.LEFT, padx=5)
        self.offset_entry = ttk.Entry(btn_frame, width=10)

        self.check_prev_btn = ttk.Button(btn_frame, text="<<", command=self.check_prev_block, state=tk.DISABLED)
        self.check_prev_btn.pack(side=tk.LEFT, padx=5)

        self.offset_entry.pack(side=tk.LEFT, padx=5)
        self.offset_entry.insert(0, "0")

        self.check_next_btn = ttk.Button(btn_frame, text=">>", command=self.check_next_block, state=tk.DISABLED)
        self.check_next_btn.pack(side=tk.LEFT, padx=5)

        self.check_entropy_btn = ttk.Button(btn_frame, text="Check entropy", command=self.check_entropy, state=tk.DISABLED)
        self.check_entropy_btn.pack(side=tk.LEFT, padx=5)

        self.find_data_btn = ttk.Button(btn_frame, text="Find data sectors", command=self.find_data_sectors, state=tk.DISABLED)
        self.find_data_btn.pack(side=tk.LEFT, padx=5)

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
            self.check_entropy_btn.config(state=tk.NORMAL)
            self.find_data_btn.config(state=tk.NORMAL)
            self.check_prev_btn.config(state=tk.NORMAL)
            self.check_next_btn.config(state=tk.NORMAL)


    def find_data_sectors(self):
        # Cancel any running analysis
        if self.analysis_running:
            self.stop_analysis()

        self.statusbar.config(text="Searching first sector with a entropy above 2.5 on the first disk image...")
        self.statusbar.update_idletasks()

        with open(self.files[0], 'rb') as f:
            sector_index = 0
            while True:
                data = f.read(self.bs)
                if not data:
                    break
                
                entropy = self.calc_entropy(data)
                
                if entropy > 2.5:
                    self.offset_entry.delete(0, tk.END)
                    self.offset_entry.insert(0, str(sector_index))
                    self.statusbar.config(text=f"Found sector #{sector_index} with entropy {entropy:.2f} at {self.files[0]}")
                    self.find_data_btn.config(state=tk.NORMAL)
                    return
                
                sector_index += 1


    def start_analysis(self, offset=0, run_only_one_block=False):
        # Open all files and store handles
        for file in self.files:
            f = open(file, 'rb')
            f.seek(offset * self.bs)

            self.handles.append(f)

            if self.max_sectors == 0:
                self.max_sectors = os.path.getsize(file) // self.bs
            else:
                self.max_sectors = min(self.max_sectors, os.path.getsize(file) // self.bs)

        # Update status and buttons
        self.analysis_running = True
        self.start_time = time.time()

        # Reset analysis variables
        self.offset = 0
        self.analysis_start_sector = offset
        self.run_only_one_block = run_only_one_block
        self.first_analysis_block = True
        self.analysis_block_entropy = [[] for x in range(len(self.files))]
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


    def check_entropy(self):
        # Cancel any running analysis
        if self.analysis_running:
            self.stop_analysis()

        # Get offset from entry
        try:
            offset = int(self.offset_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Offset", "Offset must be a number, running analysis from offset 0.")
            offset = 0

        # Run analysis for one block only
        self.start_analysis(offset=offset, run_only_one_block=True)


    def check_next_block(self):
        try:
            offset = int(self.offset_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Offset", "Offset must be a number, running analysis from offset 0.")
            offset = 0

        offset += self.analysis_block_size
        self.offset_entry.delete(0, tk.END)
        self.offset_entry.insert(0, str(offset))
        self.check_entropy()


    def check_prev_block(self):
        try:
            offset = int(self.offset_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Offset", "Offset must be a number, running analysis from offset 0.")
            offset = 0

        offset -= self.analysis_block_size
        if offset < 0:
            offset = 0
        self.offset_entry.delete(0, tk.END)
        self.offset_entry.insert(0, str(offset))
        self.check_entropy()


    def analysis_step(self):
        if self.analysis_running:
            for _ in range(self.analysis_block_size):
                if not self.analysis_running: 
                    break
                self.read_next_data_block()

            # Calculate average entropy for actual analysis block
            if self.first_analysis_block:
                block_avg = 0.0
                for i in range(len(self.files)):
                    block_avg += sum(self.analysis_block_entropy[i]) / len(self.analysis_block_entropy[i])
                block_avg /= len(self.files)

                # Stop if some block with higher entropy found
                if block_avg > 25:
                    self.first_analysis_block = False

                # Reset entropy data for next block
                elif not self.run_only_one_block:
                    self.analysis_block_entropy = [[] for x in range(len(self.files))]

            
            # Update UI after each block
            self.statusbar.config(text=f"Processed {self.offset} / {self.max_sectors} sectors: {self.offset * 100 / self.max_sectors:.1f}% ({self.offset / (time.time() - self.start_time):.1f} sectors/sec.)")
            self.update_output()

            # If only one block run requested, stop analysis
            if self.run_only_one_block:
                self.stop_analysis()
                return

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
            entropy = 0.0

            if data_blocks[i] == b'\x00' * self.bs:
                self.stats[i]['zero_blocks'] += 1
            
            elif data_blocks[i] == bytes([data_blocks[i][0] for x in range(self.bs)]):
                self.stats[i]['pattern_blocks'] += 1

            # Calculate entropy only for non-zero, non-pattern blocks
            else:
                entropy = self.calc_entropy(data_blocks[i])
                self.stats[i]['entropy'] += entropy

            if self.first_analysis_block:
                self.analysis_block_entropy[i].append(int(entropy*10 + 1))

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


    def create_entropy_graph(self, entropy_data):
        entropy_data = {self.filenames[i]: entropy_data[i] for i in range(len(self.files))}
        json_entropy_data = json.dumps(entropy_data)

        return """
        <style>
            .disk-row {
                background-color: #1e1e1e;
                margin-bottom: 15px;
                padding: 10px;
                border-radius: 4px;
            }
            .disk-header {
                font-family: 'Consolas', monospace;
                color: #4bc0c0;
                font-size: 12px;
                margin-bottom: 5px;
            }
            /* This rule is what stops the "endless growth" */
            .chart-wrapper {
                height: 120px; 
                position: relative;
                width: 100%;
            }
        </style>

        <div id="chartsContainer"></div>

        <script>
        const raidData = """ + json_entropy_data + """;
        const container = document.getElementById('chartsContainer');

        Object.entries(raidData).forEach(([filename, values]) => {
            const row = document.createElement('div');
            row.className = 'disk-row';
            
            const header = document.createElement('div');
            header.className = 'disk-header';
            header.innerHTML = `FILE: ${filename}`;
            
            const wrapper = document.createElement('div');
            wrapper.className = 'chart-wrapper';

            const canvas = document.createElement('canvas');
            
            // CORRECT HIERARCHY:
            wrapper.appendChild(canvas); // Put canvas in wrapper
            row.appendChild(header);      // Put header in row
            row.appendChild(wrapper);     // Put wrapper in row
            container.appendChild(row);   // Put row in main container

            new Chart(canvas, {
                type: 'line',
                data: {
                    labels: values.map((_, i) => i),
                    datasets: [{
                        label: 'Entropy',
                        data: values,
                        borderColor: '#ff6384',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        borderWidth: 1.5,
                        fill: true,
                        pointRadius: 1,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false, // Allows the chart to respect the 120px height
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: { color: '#888', font: { size: 10 } },
                            grid: { color: '#333' }
                        },
                        x: {
                            ticks: { color: '#888', font: { size: 10 } },
                            grid: { color: '#333' }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        });
        </script>
        """
        

    def stop_analysis(self):
        self.update_output()

        # Close all file handles
        if not self.parity_check_log is None:
            self.parity_check_log.close()
            self.parity_check_log = None

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

        # Skip report generation for one-block analysis
        if self.run_only_one_block:
            self.statusbar.config(text="Analysis complete.")
            self.statusbar.update_idletasks()

            # Open graph in watplotlib
            num_files = len(self.files)
    
            fig, axes = plt.subplots(nrows=num_files, ncols=1, figsize=(12, 2 * num_files), sharex=True)
            fig.canvas.manager.set_window_title("Entropy graph")
            if num_files == 1:
                axes = [axes]

            for i, (filename, values) in enumerate(zip(self.filenames, self.analysis_block_entropy)):
                ax = axes[i]
                ax.plot(values, label=filename, color=f'C{i}', linewidth=1.5)
                
                # Formatting each individual subplot
                ax.set_title(f"FILE: {filename}", fontsize=10, loc='left', fontweight='bold')
                ax.set_ylabel('Entropy (%)', fontsize=9)
                ax.set_ylim(0, 105) # Slightly above 100 for visual padding
                ax.grid(True, which='both', linestyle='--', alpha=0.5)

            # Global X-axis label at the bottom
            plt.xlabel('Sector Index / Block Offset', fontsize=10)
            
            # Adjust layout to prevent titles and labels from overlapping
            plt.tight_layout()
            plt.show()

            return

        # Write HTML report
        report_file = f"raidalyzer_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        with open(report_file, "w") as report:
            h1 = f"RaidAlyzer v{RaidAlyzerApp.VERSION} Report"
            report.write("<!DOCTYPE html>\n")
            report.write("<html lang=\"en\">\n")
            report.write("<head>\n")
            report.write(f"<title>{h1}</title>\n")

            # Styles
            report.write("<script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>\n")
            report.write("<style>\n")
            report.write("body { font-family: monospace; background-color: #1e1e1e; color: #ffffff; padding: 20px; } \n")
            report.write("h2 { color: #4bc0c0; } \n")
            report.write(".chart-container { width: 90%; margin: auto; background-color: #2d2d2d; padding: 20px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); } \n")
            report.write(".disk-row { background-color: #1e1e1e; margin-bottom: 15px; padding: 10px; border-radius: 4px; border-left: 4px solid #4bc0c0; } \n")
            report.write(".disk-header { font-size: 0.9em; color: #4bc0c0; margin-bottom: 5px; display: flex; justify-content: space-between; } \n")
            report.write(".chart-wrapper { height: 120px; position: relative; width: 100%; } \n")
            report.write("</style>\n")
            report.write("</head>\n")

            # Body
            report.write("<body>\n")
            report.write(f"<h1>{h1}</h1>\n")
            report.write("<hr><br><br>\n\n")
            report.write(f"<h2>Analyzed files:</h2><hr><br>\n")
            report.write("<ul>\n")
            for file in self.filenames:
                report.write(f"<li>{file}</li>\n")
            report.write("</ul><br><br>\n\n")

            report.write(f"<b>Start sector:</b> {self.analysis_start_sector}<br><br><hr><br>\n\n")

            report.write("<h2>Statistics:</h2><hr><br>\n")
            report.write("<pre>\n")
            report.write(self.text1.get(1.0, tk.END))
            report.write("</pre><br><br>\n\n")

            report.write("<h2>Mirror Analysis:</h2><hr><br>\n")
            report.write("<pre>\n")
            report.write(self.text2.get(1.0, tk.END))
            report.write("</pre><br><br>\n\n")

            report.write("<h2>Parity Analysis:</h2><hr><br>\n")
            report.write("<pre>\n")
            report.write(self.text3.get(1.0, tk.END))
            report.write("</pre><br><br>\n\n")

            # create entropy graph from first analysis block
            report.write("<h2>Entropy graph for first block potentially containing data:</h2><hr><br>\n")
            report.write(self.create_entropy_graph(self.analysis_block_entropy))
            report.write("<br><br>\n\n")

            report.write("<h2>Parity Check Log:</h2><hr><br>\n")
            report.write("<pre>\n")

            parity_check_log = []
            with open("parity_check.log", "r") as logfile:
                for line in logfile:
                    parity_check_log.append(line.strip().split(";"))
                    if len(parity_check_log) > 999:
                        break
            
            # Add another log line and adding the last sector of the read data
            if len(parity_check_log) < 1000:
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

            report.write("</pre>\n")

        self.statusbar.config(text=f"Analysis complete. Report written to: {report_file}")
        self.statusbar.update_idletasks()


if __name__ == "__main__":
    app = RaidAlyzerApp()
    app.mainloop()
