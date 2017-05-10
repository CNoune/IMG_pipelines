#!/usr/bin/python3
"""
MetaGaAP-Py - build 1
Start Date - 28 April 2017
End Date - 10 May 2017
By Christopher Noune
"""

import os
import tkinter as tk
from tkinter import filedialog
import gc
import getpass
import subprocess
from Bio import SeqIO
import pandas as pd

gc.enable()
user= getpass.getuser()

print('Welcome',user,"to MetaGaAP-Py (build 1). Lets begin.")
print("Note: This is a highly optimised implementation. Directories will be automatically created.")
wrkdir=str(input("Do you wish to set a working directory (y/n)? "))
while wrkdir not in ['y', 'n']:
    print("This is not a valid input, please try again")
    wrkdir=str(input("Do you wish to change the working directory (y/n)? "))
if wrkdir == 'y':
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory()
    os.chdir(path)
elif wrkdir == 'n':
    path = os.getcwd()
    print("Directory not selected")
t=str(input("Please specify how many threads you wish to run: "))
input("Press Enter to specify where GATK is: ")
root = tk.Tk()
root.withdraw()
GATK = filedialog.askopenfilename()
input("Press Enter to specify where the IMG Pipelines Directory is: ")
root = tk.Tk()
root.withdraw()
IMG = filedialog.askdirectory()
Biostars=IMG+"/jvarkit/dist/biostar175929.jar"

param=str(input("Skip parameter input, reference and fastq selection? (y/n): "))
while param not in ['y', 'n']:
    print("This is not a valid input, please try again.")
    param=str(input("Skip parameter input? (y/n): "))
if param == 'n':
    input("Press Enter to specify your reference sequence: ")
    root = tk.Tk()
    root.withdraw()
    ref = filedialog.askopenfilename()
    ref_name, ref_ext = os.path.splitext(os.path.basename(ref))
    input("Press Enter to specify your fastq file: ")
    root = tk.Tk()
    root.withdraw()
    F_fq = filedialog.askopenfilename()
    fq_name, fq_ext = os.path.splitext(os.path.basename(F_fq))
    qc = str(input("Please specify minimum quality score to keep: "))
    l = str(input("Please specify the last base to keep: "))
    f = str(input("Please specify the first base to keep: "))
    RGPL = str(input("Please specify the sequencing platform i.e. IonTorrent, Illumina, 454, etc, etc: "))
    RGPU = str(input("Please specify the sequencing unit i.e. PGM, NextSeq, GS-FLX, etc, etc: "))
    RGLB = str(input("Please specify the library name: "))
    RGSM=str(input("Please specify the sample name: "))
elif param== 'y':
    print("Skipped parameter input.")

clean=str(input("Skip cleaning? (y/n): "))
while clean not in ['y', 'n']:
    print("This is not a valid input, please try again.")
    clean=str(input("Skip cleaning? (y/n): "))
if clean == 'n':
    print("Cleaning Data")
    qc_dir=path+"/QC/"
    if not os.path.isdir(qc_dir):
        qc_out=os.makedirs(qc_dir)
    art_dir=path+"/Artifacts/"
    if not os.path.isdir(art_dir):
        art_out=os.makedirs(art_dir)
    F_dir=path+"/Final_Trim/"
    if not os.path.isdir(F_dir):
        F_out=os.makedirs(F_dir)
    QC_f=qc_dir+fq_name+"_QC"+fq_ext
    Art_f=art_dir+fq_name+"_Art"+fq_ext
    F_fq=F_dir+fq_name+"_Final"+fq_ext
    qc_cmd = "fastq_quality_trimmer -t "+qc+" -l "+l+" -i "+F_fq+" -o "+QC_f
    art_cmd = "fastx_artifacts_filter -i "+QC_f+" -o "+Art_f
    F_cmd= "fastx_trimmer -f "+f+" -l"+l+" -i"+Art_f+" -o"+F_fq
    subprocess.Popen([qc_cmd], shell=True)
    subprocess.Popen([art_cmd], shell=True)
    subprocess.Popen([F_cmd], shell=True)
    print("Finished Cleaning.")
elif clean == 'y':
    print("Skipped cleaning.")

meta=str(input("Do you wish to begin the MetaGaAP process (y/n): "))
while meta not in ['y', 'n']:
    print("This is not a valid input, please try again.")
    meta=str(input("Skip database production? (y/n): "))
if meta == 'n':
    print("Starting MetaGaAP")
    bi="bwa index "+ref
    pidict="PicardCommandLine CreateSequenceDictionary R="+ref+" O="+ref_name+".dict"
    sam_ind="samtools faidx "+ref
    subprocess.Popen([bi], shell=True)
    subprocess.Popen([pidict], shell=True)
    subprocess.Popen([sam_ind], shell=True)
    init_dir=path+"/Initial_Mapping/"
    if not os.path.isdir(init_dir):
        init_out=os.makedirs(init_dir)
    init_sam=init_dir+ref_name+"_initial_map.sam"
    init_bam=init_dir+ref_name+"_inital_map_sorted.bam"
    corr_bam=init_dir+ref_name+"_final_initial_map.bam"
    bwa_init="bwa mem "+ref+" "+F_fq+" -t"+t+" > "+init_sam
    conv="samtools view -b "+init_sam+" | samtools sort -o "+init_bam
    corr_cmd="PicardCommandLine AddOrReplaceReadGroups I= "+init_bam+" O= "+corr_bam+" RGLB= "+RGLB+" RGPU= "+RGPU+" RGPL= "+RGPL+" RGSM= "+RGSM+" CREATE_INDEX=true"
    subprocess.Popen([bwa_init], shell=True)
    subprocess.Popen([conv], shell=True)
    subprocess.Popen([corr_cmd], shell=True)
    count="awk 'NR%4 == 2 {lengths[length($0)]++} END {for (l in lengths) {print l, lengths[l]}}' "+F_fq
    count=subprocess.check_output([count], universal_newlines=True, shell=True)
    count=str.strip(count)
    length, reads = str.split(count)
    vcf_dir=path+"/VCF_Outputs/"
    if not os.path.isdir(vcf_dir):
        vcf_out=os.makedirs(vcf_dir)
    gVCF=vcf_dir+fq_name+"_raw.g.vcf"
    fVCF=vcf_dir+fq_name+"_final.g.vcf"
    HapC="java -jar "+GATK+" -T HaplotypeCaller -R "+ref+" -I "+corr_bam+" --emitRefConfidence GVCF --maxReadsInRegionPerSample "+reads+"--max_alternate_alleles 100 -nct "+t+" -dt NONE -o "+gVCF
    Geno="java -jar "+GATK+" -T GenotypeGVCFs -R "+ref+" --variant "+gVCF+" -o "+fVCF
    subprocess.Popen([HapC], shell=True)
    subprocess.Popen([Geno], shell=True)
    db_dir=path+"/Database/"
    if not os.path.isdir(db_dir):
        com_out=os.makedirs(db_dir)
    db_it=db_dir+"temp.fasta"
    db_ft=db_dir+fq_name+"_temp_db.fasta"
    db_f=db_dir+fq_name+"_final_db.fasta"
    db_cmd="java -jar "+Biostars+" -R "+ref+" "+fVCF+" -x "+length+" -o "+db_it
    subprocess.Popen([db_cmd], shell=True)
    linear="awk '/^>/ {printf("+'"\\n%s\\n"'+",$0);next; } { printf("+'"%s"'+",$0);}  END {printf("+'"\\n"'+");}' < "+db_it+" > "+db_ft
    rename="""awk '/^>/{print """+'">'+fq_name+'_" ++i; next}'+"{"+"print"+"}'"+" < "+db_ft+" > "+db_f
    subprocess.Popen([linear], shell=True)
    subprocess.Popen([rename], shell=True)
    db_ind="bwa index "+db_f
    subprocess.Popen([db_ind], shell=True)
    f_dir=path+"/Final_Mapping/"
    if not os.path.isdir(f_dir):
        f_out=os.makedirs(f_dir)
    res_dir=path+"/Results/"
    if not os.path.isdir(res_dir):
        res_out=os.makedirs(res_dir)
    stats=res_dir+fq_name+"_stats.csv"
    f_sam=f_dir+fq_name+"_final_map.sam"
    f_bam=f_dir+fq_name+"_final_map.bam"
    f_bwa="bwa mem "+db_f+" -t "+t+" > "+f_sam
    f_conv="samtools view -b "+f_sam+ " | samtools sort -o "+f_bam
    sam_ind="samtools index "+f_bam
    sam_stat="samtools idxstats "+f_bam+" > "+stats
    sta_col='sed -i 1i"Sequences	Sequence_Length	Mapped_Reads	Unmapped_Reads" '+stats
    subprocess.Popen([f_bwa], shell=True)
    subprocess.Popen([f_conv], shell=True)
    subprocess.Popen([sam_ind], shell=True)
    subprocess.Popen([sam_stat], shell=True)
    subprocess.Popen([sta_col], shell=True)
    temp=pd.read_csv(stats, sep="\t")
    temp=temp[temp.Mapped_Reads > 1]
    pd.DataFrame.to_csv(temp, header=True, index=False, path_or_buf=res_dir+fq_name+"_subset_stats.csv")
    del temp['Sequence_Length'], temp['Mapped_Reads'], temp['Unmapped_Reads']
    pd.DataFrame.to_csv(temp, header=False, index=False, path_or_buf=res_dir+fq_name+"_seq_list.txt")
    db=db_f
    output=res_dir+fq_name+"_confirmed_sequences.fasta"
    seq_list = [line.strip() for line in open(res_dir+fq_name+"_seq_list.txt")]                               
    seqiter = SeqIO.parse(open(db), 'fasta')                                    
    SeqIO.write((seq for seq in seqiter if seq.id in seq_list), output, "fasta")
    print("Finished MetaGaAP.")
elif meta == 'y':
    print("Ending MetaGaAP. Goodbye!")
