# -*- coding: utf-8 -*-
"""
Created on Mon Jun 12 14:36:17 2017
Extract sequences from fasta database.
Code created by Dr. Jason Gallant.
Original code available from here: http://efish.zoology.msu.edu/testing-out-gist/
This has been slightly modified for the Invertebrates & Microbiology Group.
by Christopher Noune
"""
from Bio import SeqIO
import tkinter as tk
from tkinter import filedialog

input("Press Enter to select your fasta database file: ")
root = tk.Tk()
root.withdraw()
f_db = filedialog.askopenfilename()
input("Press Enter to select your list containing the target fasta sequence names: ")
root = tk.Tk()
root.withdraw()
f_list = filedialog.askopenfilename()
input("Press Enter to specify your output directory: ")
root = tk.Tk()
root.withdraw()
out_dir = filedialog.askdirectory()
out_name=str(input("Please type the output name for your extracted sequences: "))
output=out_dir+"/"+out_name+".fasta"
seq_list = [line.strip() for line in open(f_list)]                               
seqiter = SeqIO.parse(open(f_db), 'fasta')                                    
SeqIO.write((seq for seq in seqiter if seq.id in seq_list), output, "fasta")
print("Done.")