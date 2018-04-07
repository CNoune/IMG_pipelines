#!/usr/bin/python3
"""
A quick python3 fastq/fasta converter.
Build - 1
Date - 02/05/2017
Copyright (c) 2017 Christopher Noune
"""

from Bio import SeqIO
import os
import tkinter as tk
from tkinter import filedialog

input("Press enter to specify fastq file for conversion: ")
root = tk.Tk()
root.withdraw()
file = filedialog.askopenfilename()
name, ext = os.path.splitext(os.path.basename(file))
while ext not in ['.fastq']:
    input("This is not a fastq file. Press enter to try again: ")
    root = tk.Tk()
    root.withdraw()
    file = filedialog.askopenfilename()
    name, ext = os.path.splitext(os.path.basename(file))
input("Press enter to select output directory: ")
root = tk.Tk()
root.withdraw()
out = filedialog.askdirectory()
out=out+"/"+name+".fasta"
SeqIO.convert(file, "fastq", out, "fasta")
print("Done. Fasta file has been saved here: ",out)
