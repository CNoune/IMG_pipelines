#!/usr/bin/python3
"""
MetaGaAP-Py - build 3.3.3 (Ammended 24/11/2017)
Start Date - 16 May 2017
End Date -  21 May 2017
By Christopher Noune & Caroline Hauxwell
"""
import os
import tkinter as tk
from tkinter import filedialog
import gc
import getpass
import subprocess
from Bio import SeqIO
import pandas as pd
from Bio.SeqUtils.CheckSum import seguid
import multiprocessing as mp
from sys import platform

if platform.startswith('linux'):
    os.system("taskset -p 0xfffff %d" % os.getpid())

gc.enable()
user= getpass.getuser()
        
"""Remove duplicate function was created by Dr. Peter Cock and 
found here: http://lists.open-bio.org/pipermail/biopython/2010-April/012615.html
but I have slightly modified it to allow for multiprocessing"""
def remove_dup_seqs(records):
    checksums = set()
    for record in records:
        checksum = seguid(record.seq)
        if checksum in checksums:
           continue
        checksums.add(checksum)
        yield record

print('Welcome',user,"to MetaGaAP-Py (build 3.3.3). Lets begin.")
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
cur=os.path.dirname(os.path.abspath("MetaGaAP-Py.py"))
IMG=os.path.abspath(os.path.join(cur,os.pardir))
Biostars=IMG+"/Additional_Scripts/biostar175929.jar"
multi_num=int(input("Please specify the number of samples you wish to process: "))
print("Note: Single reference multi-sample processing will produce a merged database. If you are processing multiple references, it will produce multiple databases.")
multi_ref=str(input("Will you be using a single reference or multiple reference sequences? (s/m): "))
while multi_ref not in ['s', 'm']:
    print("This is not a valid input, please try again.")
    print("Note: Single reference multi-sample processing will produce a merged database. If you are processing multiple references, it will produce multiple databases.")
    multi_ref=str(input("Will you be using a single reference or multiple reference sequences? (s/m): "))
if multi_ref == 'm':
    for i in range(multi_num):
        if i >= multi_num:
            continue
        print("Processing sample ",1+i)
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
        RGPL = str(input("Please specify the sequencing platform i.e. IonTorrent, Illumina, 454, etc, etc: "))
        RGPU = str(input("Please specify the sequencing unit i.e. PGM, NextSeq, GS-FLX, etc, etc: "))
        RGLB = str(input("Please specify the library name: "))
        RGSM=str(input("Please specify the sample name: "))    
        clean=str(input("Skip cleaning? (y/n): "))
        while clean not in ['y', 'n']:
            print("This is not a valid input, please try again.")
            clean=str(input("Skip cleaning? (y/n): "))
        if clean == 'n':
            qc = str(input("Please specify minimum quality score to keep: "))
            l = str(input("Please specify the last base to keep: "))
            f = str(input("Please specify the first base to keep: "))
            print("Cleaning Data for sample ",1+i)
            qc_dir=path+"/QC/"
            if not os.path.isdir(qc_dir):
                qc_out=os.makedirs(qc_dir)
            art_dir=path+"/Artifacts/"
            if not os.path.isdir(art_dir):
                art_out=os.makedirs(art_dir)
            F_dir=path+"/Final_Trim/"
            if not os.path.isdir(F_dir):
                F_out=os.makedirs(F_dir)
            QC_f=qc_dir+RGSM+"_QC"+fq_ext
            Art_f=art_dir+RGSM+"_Art"+fq_ext
            qc_cmd = "fastq_quality_trimmer -t "+qc+" -l "+l+" -i "+F_fq+" -o "+QC_f
            art_cmd = "fastx_artifacts_filter -i "+QC_f+" -o "+Art_f
            F_fq=F_dir+RGSM+"_Final"+fq_ext
            F_cmd= "fastx_trimmer -f "+f+" -l "+l+" -i "+Art_f+" -o "+F_fq
            subprocess.Popen([qc_cmd], shell=True).wait()
            subprocess.Popen([art_cmd], shell=True).wait()
            subprocess.Popen([F_cmd], shell=True).wait()
            print("Finished Cleaning for sample ",1+i)
        elif clean == 'y':
            print("Skipped cleaning for sample ",1+i)
        meta=str(input("Do you wish to begin the MetaGaAP process (y/n): "))
        while meta not in ['y', 'n']:
            print("This is not a valid input, please try again.")
            meta=str(input("Do you wish to begin the MetaGaAP process? (y/n): "))
        if meta == 'y':
            print("Starting MetaGaAP for sample ",1+i)
            bi="bwa index "+ref
            dict= os.path.dirname(os.path.abspath(ref))+"/"+ref_name
            pidict="picard-tools CreateSequenceDictionary R="+ref+" O="+dict+".dict"
            sam_ind="samtools faidx "+ref
            subprocess.Popen([bi], shell=True).wait()
            subprocess.Popen([pidict], shell=True).wait()
            subprocess.Popen([sam_ind], shell=True).wait()
            init_dir=path+"/Initial_Mapping/"
            if not os.path.isdir(init_dir):
                init_out=os.makedirs(init_dir)
            init_sam=init_dir+ref_name+"_initial_map.sam"
            init_bam=init_dir+ref_name+"_inital_map_sorted.bam"
            corr_bam=init_dir+ref_name+"_final_initial_map.bam"
            bwa_init="bwa mem "+ref+" "+F_fq+" -t "+t+" > "+init_sam
            conv="samtools view -b "+init_sam+" | samtools sort -o "+init_bam
            corr_cmd="picard-tools AddOrReplaceReadGroups I= "+init_bam+" O= "+corr_bam+" RGLB= "+RGLB+" RGPU= "+RGPU+" RGPL= "+RGPL+" RGSM= "+RGSM+" CREATE_INDEX=true"
            subprocess.Popen([bwa_init], shell=True).wait()
            subprocess.Popen([conv], shell=True).wait()
            subprocess.Popen([corr_cmd], shell=True).wait()
            count="awk 'NR%4 == 2 {lengths[length($0)]++} END {for (l in lengths) {print l, lengths[l]}}' "+F_fq
            count=subprocess.check_output([count], universal_newlines=True, shell=True)
            count=str.strip(count)
            length, reads = str.split(count)
            vcf_dir=path+"/VCF_Outputs/"
            if not os.path.isdir(vcf_dir):
                vcf_out=os.makedirs(vcf_dir)
            gVCF=vcf_dir+RGSM+"_raw.g.vcf"
            fVCF=vcf_dir+RGSM+"_final.vcf"
            HapC="java -jar "+GATK+" -T HaplotypeCaller -R "+ref+" -I "+corr_bam+" --emitRefConfidence GVCF --maxReadsInRegionPerSample "+reads+" --max_alternate_alleles 100 -nct "+t+" -dt NONE -o "+gVCF
            Geno="java -jar "+GATK+" -T GenotypeGVCFs -R "+ref+" --variant "+gVCF+" -o "+fVCF
            subprocess.Popen([HapC], shell=True).wait()
            subprocess.Popen([Geno], shell=True).wait()
            db_dir=path+"/Database/"
            if not os.path.isdir(db_dir):
                com_out=os.makedirs(db_dir)
            db_it=db_dir+"temp.fasta"
            db_ft=db_dir+RGSM+"_temp_db.fasta"
            db_f=db_dir+RGSM+"_final_db.fasta"
            db_cmd="java -jar "+Biostars+" -R "+ref+" "+fVCF+" -x "+length+" -o "+db_it
            subprocess.Popen([db_cmd], shell=True).wait()
            linear="awk '/^>/ {printf("+'"\\n%s\\n"'+",$0);next; } { printf("+'"%s"'+",$0);}  END {printf("+'"\\n"'+");}' < "+db_it+" > "+db_ft
            rename="""awk '/^>/{print """+'">'+RGSM+'_" ++i; next}'+"{"+"print"+"}'"+" < "+db_ft+" > "+db_f
            subprocess.Popen([linear], shell=True).wait()
            subprocess.Popen([rename], shell=True).wait()
            os.remove(db_it)
            os.remove(db_ft)
            db_ind="bwa index "+db_f
            subprocess.Popen([db_ind], shell=True).wait()
            f_dir=path+"/Final_Mapping/"
            if not os.path.isdir(f_dir):
                f_out=os.makedirs(f_dir)
            res_dir=path+"/Results/"
            if not os.path.isdir(res_dir):
                res_out=os.makedirs(res_dir)
            stats=res_dir+RGSM+"_stats.csv"
            f_sam=f_dir+RGSM+"_final_map.sam"
            f_bam=f_dir+RGSM+"_final_map.bam"
            f_bwa="bwa mem "+db_f+" "+F_fq+" -t "+t+" > "+f_sam
            f_conv="samtools view -b "+f_sam+ " | samtools sort -o "+f_bam
            sam_ind="samtools index "+f_bam
            sam_stat="samtools idxstats "+f_bam+" > "+stats
            sta_col='sed -i 1i"Sequences	Sequence_Length	Mapped_Reads	Unmapped_Reads" '+stats
            subprocess.Popen([f_bwa], shell=True).wait()
            subprocess.Popen([f_conv], shell=True).wait()
            subprocess.Popen([sam_ind], shell=True).wait()
            subprocess.Popen([sam_stat], shell=True).wait()
            subprocess.Popen([sta_col], shell=True).wait()
            temp=pd.read_csv(stats, sep="\t")
            temp=temp[temp.Mapped_Reads > 1]
            pd.DataFrame.to_csv(temp, header=True, index=False, path_or_buf=res_dir+RGSM+"_subset_stats.csv")
            del temp['Sequence_Length'], temp['Mapped_Reads'], temp['Unmapped_Reads']
            pd.DataFrame.to_csv(temp, header=False, index=False, path_or_buf=res_dir+RGSM+"_seq_list.txt")
            db=db_f
            output=res_dir+RGSM+"_confirmed_sequences.fasta"
            """Extract sequences from fasta database code created by
            Dr. Jason Gallant and available from here: http://efish.zoology.msu.edu/testing-out-gist/
            but I have slightly modified it"""
            seq_list = [line.strip() for line in open(res_dir+RGSM+"_seq_list.txt")]                               
            seqiter = SeqIO.parse(open(db), 'fasta')                                    
            SeqIO.write((seq for seq in seqiter if seq.id in seq_list), output, "fasta")
            print("Finished MetaGaAP for sample ",1+i)
        elif meta == 'n':
            print("Ending MetaGaAP. Goodbye!")
elif multi_ref == 's':
    input("Press Enter to specify your reference sequence: ")
    root = tk.Tk()
    root.withdraw()
    ref = filedialog.askopenfilename()
    ref_name, ref_ext = os.path.splitext(os.path.basename(ref))
    bi="bwa index "+ref
    dict= os.path.dirname(os.path.abspath(ref))+"/"+ref_name
    pidict="picard-tools CreateSequenceDictionary R="+ref+" O="+ref_name+".dict"
    sam_ind="samtools faidx "+ref
    subprocess.Popen([bi], shell=True).wait()
    subprocess.Popen([pidict], shell=True).wait()
    subprocess.Popen([sam_ind], shell=True).wait()
    RGPL = str(input("Please specify the sequencing platform i.e. IonTorrent, Illumina, 454, etc, etc: "))
    RGPU = str(input("Please specify the sequencing unit i.e. PGM, NextSeq, GS-FLX, etc, etc: "))
    RGLB = str(input("Please specify the library name: "))    
    for i in range(multi_num):
        if i >= multi_num:
            continue
        print("Processing sample ",1+i)
        input("Press Enter to specify your fastq file: ")
        root = tk.Tk()
        root.withdraw()
        F_fq = filedialog.askopenfilename()
        fq_name, fq_ext = os.path.splitext(os.path.basename(F_fq))
        RGSM=str(input("Please specify the sample name: "))    
        clean=str(input("Skip cleaning? (y/n): "))
        while clean not in ['y', 'n']:
            print("This is not a valid input, please try again.")
            clean=str(input("Skip cleaning? (y/n): "))
        if clean == 'n':
            qc = str(input("Please specify minimum quality score to keep: "))
            l = str(input("Please specify the last base to keep: "))
            f = str(input("Please specify the first base to keep: "))
            print("Cleaning Data for sample ",1+i)
            qc_dir=path+"/QC/"
            if not os.path.isdir(qc_dir):
                qc_out=os.makedirs(qc_dir)
            art_dir=path+"/Artifacts/"
            if not os.path.isdir(art_dir):
                art_out=os.makedirs(art_dir)
            F_dir=path+"/Final_Trim/"
            if not os.path.isdir(F_dir):
                F_out=os.makedirs(F_dir)
            QC_f=qc_dir+RGSM+"_QC"+fq_ext
            Art_f=art_dir+RGSM+"_Art"+fq_ext
            qc_cmd = "fastq_quality_trimmer -t "+qc+" -l "+l+" -i "+F_fq+" -o "+QC_f
            art_cmd = "fastx_artifacts_filter -i "+QC_f+" -o "+Art_f
            F_fq=F_dir+RGSM+"_Final"+fq_ext
            F_cmd= "fastx_trimmer -f "+f+" -l "+l+" -i "+Art_f+" -o "+F_fq
            subprocess.Popen([qc_cmd], shell=True).wait()
            subprocess.Popen([art_cmd], shell=True).wait()
            subprocess.Popen([F_cmd], shell=True).wait()
            print("Finished Cleaning for sample ",1+i)
        elif clean == 'y':
            print("Skipped cleaning.")
        meta=str(input("Do you wish to begin the MetaGaAP process (y/n): "))
        while meta not in ['y', 'n']:
            print("This is not a valid input, please try again.")
            meta=str(input("Do you wish to begin the MetaGaAP process? (y/n): "))
        if meta == 'y':
            print("Starting MetaGaAP for sample ",1+i)
            init_dir=path+"/Initial_Mapping/"
            if not os.path.isdir(init_dir):
                init_out=os.makedirs(init_dir)
            init_sam=init_dir+ref_name+"_initial_map.sam"
            init_bam=init_dir+ref_name+"_inital_map_sorted.bam"
            corr_bam=init_dir+ref_name+"_final_initial_map.bam"
            bwa_init="bwa mem "+ref+" "+F_fq+" -t "+t+" > "+init_sam
            conv="samtools view -b "+init_sam+" | samtools sort -o "+init_bam
            corr_cmd="picard-tools AddOrReplaceReadGroups I= "+init_bam+" O= "+corr_bam+" RGLB= "+RGLB+" RGPU= "+RGPU+" RGPL= "+RGPL+" RGSM= "+RGSM+" CREATE_INDEX=true"
            subprocess.Popen([bwa_init], shell=True).wait()
            subprocess.Popen([conv], shell=True).wait()
            subprocess.Popen([corr_cmd], shell=True).wait()
            count="awk 'NR%4 == 2 {lengths[length($0)]++} END {for (l in lengths) {print l, lengths[l]}}' "+F_fq
            count=subprocess.check_output([count], universal_newlines=True, shell=True)
            count=str.strip(count)
            length, reads = str.split(count)
            vcf_dir=path+"/VCF_Outputs/"
            if not os.path.isdir(vcf_dir):
                vcf_out=os.makedirs(vcf_dir)
            gVCF=vcf_dir+RGSM+"_raw.g.vcf"
            fVCF=vcf_dir+RGSM+"_final.vcf"
            HapC="java -jar "+GATK+" -T HaplotypeCaller -R "+ref+" -I "+corr_bam+" --emitRefConfidence GVCF --maxReadsInRegionPerSample "+reads+" --max_alternate_alleles 100 -nct "+t+" -dt NONE -o "+gVCF
            Geno="java -jar "+GATK+" -T GenotypeGVCFs -R "+ref+" --variant "+gVCF+" -o "+fVCF
            subprocess.Popen([HapC], shell=True).wait()
            subprocess.Popen([Geno], shell=True).wait()
            db_dir=path+"/Database/"
            if not os.path.isdir(db_dir):
                com_out=os.makedirs(db_dir)
            db_it=db_dir+"temp.fasta"
            db_ft=db_dir+RGSM+"_temp_db.fasta"
            db_f=db_dir+RGSM+"_final_db.fasta"
            db_cmd="java -jar "+Biostars+" -R "+ref+" "+fVCF+" -x "+length+" -o "+db_it
            subprocess.Popen([db_cmd], shell=True).wait()
            linear="awk '/^>/ {printf("+'"\\n%s\\n"'+",$0);next; } { printf("+'"%s"'+",$0);}  END {printf("+'"\\n"'+");}' < "+db_it+" > "+db_ft
            rename="""awk '/^>/{print """+'">'+RGSM+'_" ++i; next}'+"{"+"print"+"}'"+" < "+db_ft+" > "+db_f
            subprocess.Popen([linear], shell=True).wait()
            subprocess.Popen([rename], shell=True).wait()
            os.remove(db_it)
            os.remove(db_ft)
            if multi_num == 1:
                db_ind="bwa index "+db_f
                subprocess.Popen([db_ind], shell=True).wait()
                f_dir=path+"/Final_Mapping/"
                if not os.path.isdir(f_dir):
                    f_out=os.makedirs(f_dir)
                res_dir=path+"/Results/"
                if not os.path.isdir(res_dir):
                    res_out=os.makedirs(res_dir)
                stats=res_dir+RGSM+"_stats.csv"
                f_sam=f_dir+RGSM+"_final_map.sam"
                f_bam=f_dir+RGSM+"_final_map.bam"
                f_bwa="bwa mem "+db_f+" "+F_fq+" -t "+t+" > "+f_sam
                f_conv="samtools view -b "+f_sam+ " | samtools sort -o "+f_bam
                sam_ind="samtools index "+f_bam
                sam_stat="samtools idxstats "+f_bam+" > "+stats
                sta_col='sed -i 1i"Sequences	Sequence_Length	Mapped_Reads	Unmapped_Reads" '+stats
                subprocess.Popen([f_bwa], shell=True).wait()
                subprocess.Popen([f_conv], shell=True).wait()
                subprocess.Popen([sam_ind], shell=True).wait()
                subprocess.Popen([sam_stat], shell=True).wait()
                subprocess.Popen([sta_col], shell=True).wait()
                temp=pd.read_csv(stats, sep="\t")
                temp=temp[temp.Mapped_Reads > 1]
                pd.DataFrame.to_csv(temp, header=True, index=False, path_or_buf=res_dir+RGSM+"_subset_stats.csv")
                del temp['Sequence_Length'], temp['Mapped_Reads'], temp['Unmapped_Reads']
                pd.DataFrame.to_csv(temp, header=False, index=False, path_or_buf=res_dir+RGSM+"_seq_list.txt")
                """Extract sequences from fasta database code created by
                Dr. Jason Gallant and available from here: http://efish.zoology.msu.edu/testing-out-gist/
                but I have slightly modified it"""
                output=res_dir+RGSM+"_confirmed_sequences.fasta"
                seq_list = [line.strip() for line in open(res_dir+RGSM+"_seq_list.txt")]                               
                seqiter = SeqIO.parse(open(db_f), 'fasta')                                    
                SeqIO.write((seq for seq in seqiter if seq.id in seq_list), output, "fasta")
                print("Finished MetaGaAP for sample ",1+i)
            elif multi_num >= 2:
                print("Proceeding to database merging.")
        elif meta == 'n':
                print("Ending MetaGaAP. Goodbye!")
    if multi_num >= 2:
        db_m_dir=db_dir+"/Merged_Database/"
        if not os.path.isdir(db_m_dir):
            com_out=os.makedirs(db_m_dir)
        db_m=db_m_dir+ref_name+"_merged_db.fasta"
        cat="cat "+db_dir+"*_final_db.fasta > "+db_m
        subprocess.Popen([cat], shell=True).wait()
        db_u=db_m_dir+"temp_unique_db.fasta"
        """ This is not working at the moment. Comes up with a type error.
        if __name__ == '__main__':
            cpu=mp.cpu_count()
            pool = mp.Pool(cpu)
            records = remove_dup_seqs(SeqIO.parse(db_m, "fasta"))
            count = pool.map(SeqIO.write(records, db_u, "fasta"))"""
        records = remove_dup_seqs(SeqIO.parse(db_m, "fasta"))
        SeqIO.write(records, db_u, "fasta")
        db_ul=db_m_dir+ref_name+"_unique_db.fasta"
        linear="awk '/^>/ {printf("+'"\\n%s\\n"'+",$0);next; } { printf("+'"%s"'+",$0);}  END {printf("+'"\\n"'+");}' < "+db_u+" > "+db_ul
        subprocess.Popen([linear], shell=True).wait()
        os.remove(db_u)
        db_ind="bwa index "+db_ul
        subprocess.Popen([db_ind], shell=True).wait() 
        print("The final mapping stage requires you to re-select your fastq files and sample names.")
        for i in range(multi_num):
            if i >= multi_num:
                continue
            print("Fastq file selection and sample name specification for sample",1+i)
            RGSM=str(input("Please re-specify the sample name: "))
            input("Press Enter to specify your fastq file: ")
            root = tk.Tk()
            root.withdraw()
            F_fq = filedialog.askopenfilename()
            print("Mapping sample ",1+i)
            f_dir=path+"/Final_Mapping/"
            if not os.path.isdir(f_dir):
                f_out=os.makedirs(f_dir)
            res_dir=path+"/Results/"
            if not os.path.isdir(res_dir):
                res_out=os.makedirs(res_dir)
            stats=res_dir+RGSM+"_stats.csv"
            f_sam=f_dir+RGSM+"_final_map.sam"
            f_bam=f_dir+RGSM+"_final_map.bam"
            f_bwa="bwa mem "+db_ul+" "+F_fq+" -t "+t+" > "+f_sam
            f_conv="samtools view -b "+f_sam+ " | samtools sort -o "+f_bam
            sam_ind="samtools index "+f_bam
            sam_stat="samtools idxstats "+f_bam+" > "+stats
            sta_col='sed -i 1i"Sequences	Sequence_Length	Mapped_Reads	Unmapped_Reads" '+stats
            subprocess.Popen([f_bwa], shell=True).wait()
            subprocess.Popen([f_conv], shell=True).wait()
            subprocess.Popen([sam_ind], shell=True).wait()
            subprocess.Popen([sam_stat], shell=True).wait()
            subprocess.Popen([sta_col], shell=True).wait()
            temp=pd.read_csv(stats, sep="\t")
            temp=temp[temp.Mapped_Reads > 1]
            pd.DataFrame.to_csv(temp, header=True, index=False, path_or_buf=res_dir+RGSM+"_subset_stats.csv")
            del temp['Sequence_Length'], temp['Mapped_Reads'], temp['Unmapped_Reads']
            pd.DataFrame.to_csv(temp, header=False, index=False, path_or_buf=res_dir+RGSM+"_seq_list.txt")
            db=db_ul
            """Extract sequences from fasta database code created by
            Dr. Jason Gallant and available from here: http://efish.zoology.msu.edu/testing-out-gist/
            but I have slightly modified it"""
            output=res_dir+RGSM+"_confirmed_sequences.fasta"
            seq_list = [line.strip() for line in open(res_dir+RGSM+"_seq_list.txt")]                               
            seqiter = SeqIO.parse(open(db), 'fasta')                                    
            SeqIO.write((seq for seq in seqiter if seq.id in seq_list), output, "fasta")
            print("MetaGaAP has finished for sample ",1+i)
