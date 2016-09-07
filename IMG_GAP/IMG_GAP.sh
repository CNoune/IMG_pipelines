#!/bin/bash
# jumpto function built from https://bobcopeland.com/blog/2012/10/goto-in-bash/
# IMG_GAP - version 1.0
# Copyright (c) 2016 Christopher Noune
FILETIME=`date +%T`
FILEDATE=`date +%F`
FILEDATETIME=$FILEDATE-$FILETIME
LOGFILE=$PWD/IMG_GAP_Logging.$FILEDATETIME.log
exec &> >(tee -a $LOGFILE >&2 )

function jumpto 
{
    label=$1
    cmd=$(sed -n "/$label:/{:a;n;p;ba};" $0 | grep -v ':$')
    eval "$cmd"
    exit
}

start=${1:-"start"}

jumpto $start

start:

	echo "Hello, "$USER". Welcome to the IMG Genotyping and Abundance Mapping Pipeline. Press [ENTER] to begin"
	read enter
	echo "Please Note: This Pipeline uses fastx-toolkit to complete trimming and is designed for single-end reads. Please make sure have all of your directories are created prior to running. If you wish to continue press [ENTER] otherwise ctrl c to exit."
	read enter

index:
next=y
	echo "Do you wish to complete the Indexing steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Indexing
	
		echo "Press [ENTER] to Select a Reference to Index"
		read enter
		Ref=`zenity --file-selection`
		bwa index $Ref
		samtools faidx $Ref
		Dict=$(basename "$Ref" .fasta)
		echo "Press [ENTER] to Select Sequence Dictionary Output Folder"
		read enter
		Dict_out=`zenity --file-selection --directory`
		picard-tools CreateSequenceDictionary R=$Ref O=$Dict_out/$Dict.dict
		jumpto trim
	if ["$next" = n]
	then jumpto trim
	fi
	done 
#Trimming
trim:
echo "Do you wish to complete the Trimming steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin Trimming."
		read enter
		echo "Press [ENTER] to Select Raw Fastq File."
		read enter
		fastq=`zenity --file-selection`
		echo "Press [ENTER] to Specify Output Folder for QC Trimming"
		read enter
		fastqc_out=`zenity --file-selection --directory`
		echo "Please Specify QC Output File Name followed by .fastq"
		read fastqc_name
		echo "Press [ENTER] to Specify Output Folder for Artifact Filtering."
		read enter
		artifact_out=`zenity --file-selection --directory`
		echo "Please Specify Artifact Output File Name followed by .fastq"
		read artifact_name
		echo "Press [ENTER] to Specify Output Folder for Final Trimmed Data."
		read enter
		final_trim_out=`zenity --file-selection --directory`
		echo "Please Specify the Final Trimmed Data Output Name followed by .fastq"
		read final_trim_name
		echo "Please Specify the Minimum Quality Score to keep."
		read qc
		echo "Please Specify the Last Base to keep."
		read l
		echo "Please specify the First Base to keep."
		read f
		echo "Trimming has begun"
		fastq_quality_trimmer -t $qc -l $l -i $fastq -o $fastqc_out/$fastqc_name
		fastx_artifacts_filter -i $fastqc_out/$fastqc_name -o $artifact_out/$artifact_name
		fastx_trimmer -f $f -l $l -i $artifact_out/$artifact_name -o $final_trim_out/$final_trim_name
		final_fastq=$final_trim_out/$final_trim_name
		jumpto intial_map
	if [ "$next" = n]
	then jumpto initial_map
	fi
	done
		
intial_map:
	echo "Do you wish to complete the Initial Mapping steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin initial mapping"
		read enter
			echo "Do you wish to re-specify the Reference file (y/n)?"
			read choose_ref	
			while [ "$choose_ref" = n ]
			do
				echo "Press [ENTER] to Specify FASTQ file"
				read enter
				Fastq1=`zenity --file-selection`
				echo "Press [ENTER] to Specify the second FASTQ file. Note: Only use a second FASTQ file if you are completing whole-genome analysis with paired-end data"
				read enter
				Fastq2=`zenity --file-selection`
				echo "Please Specify Threads to Use"
				read t
				echo "Press [ENTER] to Specify Output Directory"
				read enter
				SAM_output=`zenity --file-selection --directory`
				echo "Please Specify Output name"
				read SAM
				bwa mem $Ref $Fastq1 $Fastq2 -t $t > $SAM_output/$SAM.sam
				jumpto bam
			if [ "$choose_ref" = y ]
			then jumpto ref_map
			fi
			done
		ref_map:
		echo "Press [ENTER] to Specify Reference"
		read enter
		Ref=`zenity --file-selection`
		echo "Press [ENTER] to Specify FASTQ file 1"
		read enter
		Fastq1=`zenity --file-selection`
		echo "Press [ENTER] to Specify the second FASTQ file. Note: Only use a second FASTQ file if you are completing whole-genome analysis with paired-end data"
		read enter
		Fastq2=`zenity --file-selection`
		echo "Please Specify Threads to Use"
		read t
		echo "Press [ENTER] to Specify Output Directory"
		read enter
		SAM_output=`zenity --file-selection --directory`
		echo "Please Specify Output name"
		read SAM
		bwa mem $Ref $Fastq1 $Fastq2 -t $t > $SAM_output/$SAM.sam
		jumpto bam	
	if ["$next" = n]
	then jumpto bam
	fi
	done

bam:
	echo "Do you wish to complete the BAM Sorting and Conversion steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#BAM Sorting and Conversion
		echo "Press [ENTER] to begin BAM conversion"
		read enter
		echo "Press [ENTER] to Select the SAM file for Conversion"
		read enter
		SAM_Conv=`zenity --file-selection`
		echo "Press [ENTER] to Specify Output Directory"
		read enter
		BAM_out=`zenity --file-selection --directory`
		echo "Please Specify Output File Name."
		read BAM_conv
		samtools view -bS $SAM_Conv | samtools sort - $BAM_out/$BAM_conv
		jumpto fix_read_groups
	if ["$next" = n]
	then jumpto fix_read_groups
	fi
	done
fix_read_groups:
	echo "Do you wish to complete the Fix Read Groups Steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Fix Read Groups
		echo "Press [ENTER] to Fix Read Groups"
		read enter
		echo "Press [ENTER] to Select Sorted BAM file."
		read enter
		BAM_sort=`zenity --file-selection`
		echo "Press [ENTER] to Specify Output Directory for BAM Corrected File"
		read enter
		BAM_corr_out=`zenity --file-selection --directory`
		echo "Please Specify Output File Name for BAM Corrected file"
		read BAM_corr_name
		echo "Please Specify the Read Group Library Name"
		read RGLB
		echo "Press Specify the Read Group Platform Name i.e. IonTorrent or Illumina"
		read RGPL
		echo "Press Specify the Read Group Sample Name"
		read RGSM
		echo "Press Specify the Read Group Platform Unit i.e. PGM or NextSeq"
		read RGPU
		echo "Begining to fix Read Groups"
		picard-tools AddOrReplaceReadGroups I= $BAM_sort O= $BAM_corr_out/$BAM_corr_name.bam RGLB= $RGLB RGPL= $RGPL RGSM= $RGSM RGPU= $RGPU
		jumpto BAM_index
	if [ "$next" = n ]
	then jumpto BAM_index
	fi
	done
BAM_index:
	echo "Do you wish to complete the BAM indexing Steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to Index the Corrected BAM file"
		read enter
		echo "Press [ENTER] to Select Corrected BAM file."
		read enter
		BAM_corr=`zenity --file-selection`
		echo "Press [ENTER] to select BAM index output folder"
		read enter
		BAM_ind_out=`zenity --file-selection --directory`
		BAM_ind=$(basename "$BAM_corr" .bam)
		echo "Begining BAM Indexing"
		samtools index $BAM_corr $BAM_ind_out/$BAM_ind.bai
		jumpto GATK_location
	if [ "$next" = n ]
	then jumpto GATK_location
	fi
	done
GATK_location:
	echo "Do you wish to Specify where GATK is located (y/n)?"
	read GATK_loc
	while [ "$GATK_loc" = y ]
	do
		echo "Press [ENTER] to Specify where GATK is located"
		read enter
		GATK=`zenity --file-selection`
		jumpto SNP_discovery
	if [ "$GATK_loc" = n ]
	then jumpto SNP_discovery
	fi
	done
SNP_discovery:
	echo "Do you wish to begin SNP Discovery (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin SNP Discovery"
		read enter
		echo "Do you wish to multi-thread this step (y/n)? If you do, you cannot produce a BAM output"
		read multi_thread
		while [ "$multi_thread" = y ]
		do
			echo "Please Specify how many threads you wish to use"
			read cores
				echo "Do you wish to specify a reference file (y/n)?"
				read spec_ref_multi_core
				while [ "$spec_ref_multi_core" = y ]
				do
					echo "Press [ENTER] to specify a reference"
					read enter
					Ref=`zenity --file-selection`
					echo "Press [ENTER] to Specify the Corrected BAM file"
					read enter
					BAM_corr=`zenity --file-selection`
					echo "Please Specify the Maximum Reads in Region Per Sample"
					read max_reads
					echo "Please specify the maximum ammount of alleles to be discovered per site"
					read Max_Alleles	
					echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
					read enter
					gVCF_out=`zenity --file-selection --directory`
					echo "Please Specify the gVCF Output name"
					read gVCF_name
					echo "Begining SNP Discovery"
					java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads --max_alternate_alleles $Max_Alleles -nct $cores -o $gVCF_out/$gVCF_name.g.vcf
					jumpto genotyping
				if [ "$spec_ref_multi_core" = n ]
				then jumpto no_ref_multi_core
				fi
				done
					no_ref_multi_core:
					echo "Press [ENTER] to Specify the Corrected BAM file"
					read enter
					BAM_corr=`zenity --file-selection`
					echo "Please Specify the Maximum Reads in Region Per Sample"
					read max_reads
					echo "Please specify the maximum ammount of alleles to be discovered per site"
					read Max_Alleles
					echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
					read enter
					gVCF_out=`zenity --file-selection --directory`
					echo "Please Specify the gVCF Output name followed by .g.vcf"
					read gVCF_name
					echo "Begining SNP Discovery"
					java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads --max_alternate_alleles $Max_Alleles -nct $cores -o $gVCF_out/$gVCF_name
					jumpto genotyping
		if [ "$multi_thread" = n ]
		then jumpto bamout
		fi
		done
				bamout:
				echo "Do you wish to specify a reference file (y/n)?"
				read spec_ref_bamout
				while [ "$spec_ref_bamout" = y ]
				do
					echo "Press [ENTER] to specify a reference"
					read enter
					Ref=`zenity --file-selection`
					echo "Press [ENTER] to Specify the Corrected BAM file"
					read enter
					BAM_corr=`zenity --file-selection`
					echo "Please Specify the Maximum Reads in Region Per Sample"
					read max_reads
					echo "Please specify the maximum ammount of alleles to be discovered per site"
					read Max_Alleles
					echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
					read enter
					gVCF_out=`zenity --file-selection --directory`
					echo "Please Specify the gVCF Output name followed by .g.vcf"
					read gVCF_name
					echo "Press [ENTER] to Specify the Output Directory for the BAM file"
					read enter
					bam_out=`zenity --file-selection --directory`
					echo "Please Specify BAM Output name"
					read bam_out_name
					echo "Begining SNP Discovery"
					java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads -bamout $bam_out/$bam_out_name  -o $gVCF_out/$gVCF_name
					jumpto genotyping			
				if [ "$spec_ref_bamout" = n ]
				then jumpto no_ref_bamout
				fi
				done
				no_ref_bamout:
					echo "Press [ENTER] to Specify the Corrected BAM file"
					read enter
					BAM_corr=`zenity --file-selection`
					echo "Please Specify the Maximum Reads in Region Per Sample"
					read max_reads
					echo "Please specify the maximum ammount of alleles to be discovered per site"
					read Max_Alleles
					echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
					read enter
					gVCF_out=`zenity --file-selection --directory`
					echo "Please Specify the gVCF Output name followed by .g.vcf"
					read gVCF_name
					echo "Press [ENTER] to Specify the Output Directory for the BAM file"
					read enter
					bam_out=`zenity --file-selection --directory`
					echo "Please Specify BAM Output name"
					read bam_out_name
					echo "Begining SNP Discovery"
					java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads --max_alternate_alleles $Max_Alleles -bamout $bam_out/$bam_out_name  -o $gVCF_out/$gVCF_name
					jumpto genotyping
	if [ "$next" = n ]
	then jumpto genotyping
	fi
	done
genotyping:
	echo "Do you wish to begin Genotyping (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin Genotyping"
		read enter					
		echo "Do you wish to specify a reference file (y/n)?"
		read G_Ref
		while [ "$G_Ref" = y ]
		do
			echo "Press [ENTER] to specify a reference"
			read enter
			Ref=`zenity --file-selection`
			jumpto genotypeGVCFs
		if [ "$G_Ref" = n ]
		then jumpto genotypeGVCFs
		fi
		done
		genotypeGVCFs:
		echo "Press [ENTER] to Select the g.VCF file"
		read enter
		gVCF=`zenity --file-selection`
		echo "Press [ENTER} to Select the Output Directory for the Raw variants"
		read enter
		rVCF_out=`zenity --file-selection --directory`
		echo "Please Specify the Output Name for the Raw Variants followed by .vcf"
		read rVCF_name
		echo "Begining Genotyping"
		java -jar $GATK -T GenotypeGVCFs -R $Ref --variant $gVCF -o $rVCF_out/$rVCF_name
		jumpto g_filtering
	if [ "$next" = n ]
	then jumpto g_filtering
	fi
	done 
g_filtering:
	echo "Do you wish to begin Filtering (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin Filtering"
		read enter					
		echo "Do you wish to specify a reference file (y/n)?"
		read f_Ref
		while [ "$f_Ref" = y ]
		do
			echo "Press [ENTER] to specify a reference"
			read enter
			Ref=`zenity --file-selection`
			jumpto V_filtration
		if [ "$f_Ref" = n ]
		then jumpto V_filtration
		fi
		done
		V_filtration:
		echo "Press [ENTER] to Specify the Raw Variant File"
		read enter
		rVCF=`zenity --file-selection`
		echo "Press [ENTER] to Specify the Output Directory for the Final VCF file"
		read enter
		fVCF_out=`zenity --file-selection --directory`
		echo "Please Specify the Final VCF file Name followed by .vcf"
		read fVCF_name		
		echo "Please Specify the Minimum Genotype Quality to Keep"
		read GQ
		echo "Please Specify the Minimum Read Depth to Filter"
		read DP
		echo "Begining Variant Filtration"
		java -jar $GATK -T VariantFiltration -R $Ref --variant $rVCF -G_filter "GQ < $GQ || DP < $DP" -G_filterName lowGQ_DP --setFilteredGtToNocall -o $fVCF_out/$fVCF_name
		jumpto biostar_location
	if [ "$next" = n ]
	then jumpto biostar_locaction
	fi
	done
biostar_location:
	echo "Do you wish to Specify where the Biostar175929 package is located (y/n)?"
	read biostar_loc
	while [ "$biostar_loc" = y ]
	do
		echo "Press [ENTER] to Specify where the Biostar175929 package is located"
		read enter
		Biostar=`zenity --file-selection`
		jumpto Combo_sequences
	if [ "$biostar_loc" = n ]
	then jumpto Combo_sequences
	fi
	done
Combo_sequences:
	echo "Do you wish to construct all of the Sequence Combinations (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Do you wish to specify a reference file (y/n)?"
		read C_Ref
		while [ "$C_Ref" = y ]
		do
			echo "Press [ENTER] to specify a reference"
			read enter
			Ref=`zenity --file-selection`
			jumpto combo_const
		if [ "$C_Ref" = n ]
		then jumpto combo_const
		fi
		done
	combo_const:
		echo "Press [ENTER] to Select the final VCF file"
		read enter
		fVCF=`zenity --file-selection`
		echo "Press [ENTER] to Specify the Sequence Combinations Output Directory"
		read enter
		combo_out=`zenity --file-selection --directory`
		echo "Please specify how many bases you want to extend the sequence by"
		read extend
		echo "Please Specify the Sequence Combination Name followed by .fasta.gz"
		read combo_name
		echo "Begining Sequence Combination Construction"
		java -jar $Biostar -R $Ref $fVCF -x $extend -o $combo_out/$combo_name
		jumpto seq_rename
	if ["$next" = n]
	then jumpto seq_rename
	fi
	done
seq_rename:
	echo "Do you wish to Rename the Sequence Combinations to a number (y/n)? Note: This will help to read the combinations"
	read next	
	while [ "$next" = y ]
	do
		echo "Do you wish to specify where the BBmap Renamer Tool is (y/n)?"
		read bbrename_loc
		while [ "$bbrename_loc" = y ]
		do
			echo "Press [ENTER] to Specify where the BBmap Renamer Tool is located"
			read enter
			bbrename=`zenity --file-selection`
			jumpto Combo_rename
		if [ "$bbrename_loc" = n ]
		then jumpto Combo_rename
		fi
		done
Combo_rename:
		echo "Press [ENTER] to Specify the Sequence Combination file"
		read enter
		seq_combo=`zenity --file-selection`
		echo "Press [ENTER] to specify the corrected sequence combination output directory"
		read enter
		seq_names_out=`zenity --file-selection --directory`
		echo "Please specify the sequence prefix. Note: This is a counter so if you type Genotype, the first combination will be Genotype1 and then continue."
		read combo_seq_name
		echo "Begining to Rename Sequences"
		seq_names=$(basename "$seq_combo" .fasta.gz)
		Combo_seq_new=$seq_names_out/$seq_names-renamed.fasta.gz
		$bbrename in=$seq_combo out=$Combo_seq_new prefix=$combo_seq_name
		echo "Renaming is complete"
		jumpto final_index
	if ["$next" = n]
	then jumpto final_index
	fi
	done	
final_index:
	echo "Do you wish to index the Sequence Combinations (y/n)?"
	read next	
	while [ "$next" = y ]
	do
			echo "Press [ENTER] to specify the reference combinations"
			read enter
			Combo_Ref=`zenity --file-selection`
			echo "Begining Final Combination Index"
			bwa index $Combo_Ref
			jumpto final_mapping
	if ["$next" = n]
	then jumpto final_mapping
	fi
	done
final_mapping:
	echo "Do you wish to complete the final mapping (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Please Specify how many threads you wish to use"
		read cores
		echo "Press [ENTER] to Specify the fastq file to use"
		read enter
		fastq1=`zenity --file-selection`
		echo "Press [ENTER] to Specify the second FASTQ file. Note: Only use a second FASTQ file if you are completing whole-genome analysis with paired-end data"
		read enter
		fastq2=`zenity --file-selection`
		echo "Press [ENTER] to Specify the Directory for the Final Mapping"
		read enter
		f_map_out=`zenity --file-selection --directory`
		echo "Please Specify the Name for the Final Mapping followed by .sam"
		read f_map_name
		echo "Press [ENTER] to Specify the Sequence Combinations File"
		read enter
		Combo_Ref=`zenity --file-selection`
		echo "Begining Final Mapping"
		bwa mem $Combo_Ref $fastq1 $fastq2 -t $cores > $f_map_out/$f_map_name
		jumpto finish
	if ["$next" = n]
	then jumpto finish
	fi
	done

finish:
echo "$USER you have now successfully completed the IMG Genotyping and Abundance Mapping Pipeline. Do you wish to repeat for another sample (y/n). Otherwise your final step is to import your data into Tablet (or equivalent) to visualise your data and export the mapping statistics to calculate the abundance of each detected genotype."
read next
	if [ "$next" = y ] 
	then jumpto index
	elif [ "$next" = n ]
	then jumpto quit
	fi

quit:
echo "Thank-you, don't forget to cite the method and software used"
exit 0
done
