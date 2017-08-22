#!/bin/bash
# jumpto function built from https://bobcopeland.com/blog/2012/10/goto-in-bash/
# MetaGaAP - version 1.0 - build 16
# Authored by Christopher Noune & Caroline Hauxwell
FILETIME=`date +%T`
FILEDATE=`date +%F`
FILEDATETIME=$FILEDATE-$FILETIME
echo "Press [ENTER] to select the IMG_pipelines Directory"
read enter
IMG_dir="`zenity --file-selection --directory`"
LOGFILE=$IMG_dir/Legacy/Logs/MetaGaAP_Logging.$FILEDATETIME.log
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
	echo "Hello, "$USER". Welcome to MetaGaAP. Press [ENTER] to begin."
	read enter
	echo "Note: This Pipeline uses fastx-toolkit to complete trimming and is designed for single-end reads. If you use paired-end reads do not complete trimming with MetaGaAP. The pipeline assumes bbmap, kentUtils and biostar175929 are in the IMG_pipelines directory. If you wish to continue press [ENTER] otherwise press [ctrl] + [c] to exit."
	read enter
	echo "Press [ENTER] to Select GATK"
	read enter
	GATK=`zenity --file-selection`
	Renamer="$IMG_dir/bbmap/rename.sh"
	Dedupe="$IMG_dir/bbmap/dedupe.sh"
	biostars="$IMG_dir/Additional_Scripts/biostar175929.jar"
	Extract_Fa="$IMG_dir/kentUtils/bin/linux.x86_64/faSomeRecords"
	echo "Please specify how many samples you wish to process"
	read x
	echo "Please specify how many threads you wish to run"
	read t
	echo "Please specify how much RAM you wish to use in Gigabytes"
	read RAM
	g=g
	RAMg=$RAM$g
	jumpto trim
trim:
	echo "Do you wish to complete the Trimming steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		for ((i=1; i<=$x; i++))
		do
			echo " Trimming dataset  $i"
			echo "Press [ENTER] to Select Raw Fastq File."
			read enter
			fastq="`zenity --file-selection`"
			echo "Press [ENTER] to Specify Output Folder for QC Trimming"
			read enter
			fastqc_out="`zenity --file-selection --directory`"
			QC_name=$fastqc_out/QC_$(basename "$fastq" .fastq).fastq
			echo "Press [ENTER] to Specify Output Folder for Artifact Filtering."
			read enter
			artifact_out="`zenity --file-selection --directory`"
			Art_name=$artifact_out/Artifact_$(basename "$fastq" .fastq).fastq
			echo "Press [ENTER] to Specify Output Folder for Final Trimmed Data."
			read enter
			final_trim_out="`zenity --file-selection --directory`"
			F_trim=$final_trim_out/Final_$(basename "$fastq" .fastq).fastq
			echo "Please Specify the Minimum Quality Score to keep."
			read qc
			echo "Please Specify the Last Base to keep."
			read l
			echo "Please specify the First Base to keep."
			read f
			echo "Trimming has begun"
			fastq_quality_trimmer -t $qc -l $l -i $fastq -o $QC_name
			fastx_artifacts_filter -i $QC_name -o $Art_name
			fastx_trimmer -f $f -l $l -i $Art_name -o $F_trim
			echo "Trimming has finished"
		done
		jumpto init_index
	if [ "$next" = n]
	then jumpto init_index
	fi
	done
init_index:
	echo "Do you wish to index a reference sequence (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to Select a Reference to Index"
		read enter
		Init_Ref="`zenity --file-selection`"
		echo "Press [ENTER] to Select Sequence Dictionary Output Folder"
		read enter
		Dict_out="`zenity --file-selection --directory`"
		Dict="$Dict_out/$(basename "$Init_Ref" .fasta)"
		echo "Indexing has begun"
		bwa index $Init_Ref
		samtools faidx $Init_Ref
		picard-tools CreateSequenceDictionary R=$Init_Ref O=$Dict.dict
		echo "Indexing has finished"
		jumpto init_map
	if ["$next" = n]
	then jumpto init_map
	fi
	done 
init_map:
	echo "Do you wish to complete the initial mapping (y/n)?"
	read next
	while [ "$next" = y ]
	do
		for ((i=1; i<=$x; i++))
		do
			echo "Initial Mapping for dataset $i"			
			echo "Press [ENTER] to specify the Reference file."
			read enter
			Init_Ref="`zenity --file-selection`"
			echo "Press [ENTER] to specify the trimmed FASTQ file."
			read enter
			FastQ="`zenity --file-selection`"
			echo "Press [ENTER] to specify the initial mapping output directory"
			read enter
			SAM_output="`zenity --file-selection --directory`"
			echo "Please specify initial mapping output name"
			read SAM_name
			SAM="$SAM_output/$SAM_name-initial.sam"
			BAM="$SAM_output/$SAM_name-initial-sorted.bam"
			echo "Mapping has begun"
			bwa mem $Init_Ref $FastQ -t $t > $SAM
			samtools view -b $SAM  | samtools sort -o $BAM
			rm $SAM_output/*.sam
			echo "Mapping is complete"
		done
		jumpto fix_read_groups
	if ["$next" = n]
	then jumpto fix_read_groups
	fi
	done
fix_read_groups:
	echo "Do you wish to complete the Fix Read Groups Steps and BAM indexing (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		for ((i=1; i<=$x; i++))
		do
			echo "Fixing Read Groups and BAM Indexing for dataset $i"
			echo "Press [ENTER] to Fix Read Groups"
			read enter
			echo "Press [ENTER] to Select Sorted BAM file."
			read enter
			BAM_sort="`zenity --file-selection`"
			echo "Press [ENTER] to Specify Output Directory for BAM Corrected File"
			read enter
			BAM_corr_out="`zenity --file-selection --directory`"
			BAM_corr="$BAM_corr_out/$(basename "$BAM_sort" .bam)"
			echo "Please Specify the Read Group Library Name"
			read RGLB
			echo "Press Specify the Read Group Platform Name i.e. IonTorrent or Illumina"
			read RGPL
			echo "Press Specify the Read Group Sample Name"
			read RGSM
			echo "Press Specify the Read Group Platform Unit i.e. PGM or NextSeq"
			read RGPU
			echo "Fixing Read Groups and Indexing"
			picard-tools AddOrReplaceReadGroups I= $BAM_sort O= $BAM_corr-corrected.bam RGLB= $RGLB RGPL= $RGPL RGSM= $RGSM RGPU= $RGPU CREATE_INDEX=true
			echo "Fixing is complete"
		done
		jumpto SNP_discovery
	if [ "$next" = n ]
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
				echo "Do you wish to specify a reference file (y/n)?"
				read spec_ref_multi_core
				while [ "$spec_ref_multi_core" = y ]
				do
					for ((i=1; i<=$x; i++))
					do
						echo "SNP Discovery for dataset $i"						
						echo "Press [ENTER] to specify a reference"
						read enter
						Ref="`zenity --file-selection`"
						echo "Press [ENTER] to Specify the Corrected BAM file"
						read enter
						BAM_corr="`zenity --file-selection`"
						echo "Please Specify the Maximum Reads in Region Per Sample"
						read max_reads
						echo "Please specify the maximum ammount of alleles to be discovered per site"
						read Max_Alleles	
						echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
						read enter
						gVCF_out="`zenity --file-selection --directory`"
						echo "Please Specify the gVCF Output name"
						read gVCF_name
						echo "Begining SNP Discovery"
						java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads --max_alternate_alleles $Max_Alleles -nct $t -dt NONE -o $gVCF_out/$gVCF_name-initial.g.vcf
						echo "SNP Discovery is finished"
					done
					jumpto genotyping
				if [ "$spec_ref_multi_core" = n ]
				then jumpto no_ref_multi_core
				fi
				done
					no_ref_multi_core:
					for ((i=1; i<=$x; i++))
					do
						echo "SNP Discovery for dataset $i"
						echo "Press [ENTER] to Specify the Corrected BAM file"
						read enter
						BAM_corr="`zenity --file-selection`"
						echo "Please Specify the Maximum Reads in Region Per Sample"
						read max_reads
						echo "Please specify the maximum ammount of alleles to be discovered per site"
						read Max_Alleles
						echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
						read enter
						gVCF_out="`zenity --file-selection --directory`"
						echo "Please Specify the gVCF Output name"
						read gVCF_name
						echo "Begining SNP Discovery"
						java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads --max_alternate_alleles $Max_Alleles -nct $t -dt NONE -o $gVCF_out/$gVCF_name-initial.g.vcf
						echo "SNP Discovery is finished"
					done
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
					for ((i=1; i<=$x; i++))
					do
						echo "SNP Discovery for dataset $i"
						echo "Press [ENTER] to specify a reference"
						read enter
						Ref="`zenity --file-selection`"
						echo "Press [ENTER] to Specify the Corrected BAM file"
						read enter
						BAM_corr="`zenity --file-selection`"
						echo "Please Specify the Maximum Reads in Region Per Sample"
						read max_reads
						echo "Please specify the maximum ammount of alleles to be discovered per site"
						read Max_Alleles
						echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
						read enter
						gVCF_out="`zenity --file-selection --directory`"
						echo "Please Specify the gVCF Output name"
						read gVCF_name
						echo "Press [ENTER] to Specify the Output Directory for the BAM file"
						read enter
						bam_out=`zenity --file-selection --directory`
						echo "Please Specify BAM Output name"
						read bam_out_name
						echo "Begining SNP Discovery"
						java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads -bamout $bam_out/$bam_out_name  -dt NONE -o $gVCF_out/$gVCF_name-initial.g.vcf
						echo "SNP Discovery is finished"
					done
					jumpto genotyping			
				if [ "$spec_ref_bamout" = n ]
				then jumpto no_ref_bamout
				fi
				done
					no_ref_bamout:
					for ((i=1; i<=$x; i++))
					do
						echo "SNP Discovery for dataset $i"
						echo "Press [ENTER] to Specify the Corrected BAM file"
						read enter
						BAM_corr="`zenity --file-selection`"
						echo "Please Specify the Maximum Reads in Region Per Sample"
						read max_reads
						echo "Please specify the maximum ammount of alleles to be discovered per site"
						read Max_Alleles
						echo "Press [ENTER] to Specify the Output Directory for the gVCF file"
						read enter
						gVCF_out="`zenity --file-selection --directory`"
						echo "Please Specify the gVCF Output name"
						read gVCF_name
						echo "Press [ENTER] to Specify the Output Directory for the BAM file"
						read enter
						bam_out="`zenity --file-selection --directory`"
						echo "Please Specify BAM Output name"
						read bam_out_name
						echo "Begining SNP Discovery"
						java -jar $GATK -T HaplotypeCaller -R $Ref -I $BAM_corr --genotyping_mode DISCOVERY --emitRefConfidence GVCF --maxReadsInRegionPerSample $max_reads --max_alternate_alleles $Max_Alleles -dt NONE -bamout $bam_out/$bam_out_name  -o $gVCF_out/$gVCF_name-initial.g.vcf
						echo "SNP Discovery is finished"
					done				
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
				
		echo "Do you wish to specify a reference file (y/n)?"
		read G_Ref
		while [ "$G_Ref" = y ]
		do
			for ((i=1; i<=$x; i++))
			do	
				echo "Genotyping for dataset $i"
				echo "Press [ENTER] to specify a reference"
				read enter
				Ref=`zenity --file-selection`
				echo "Press [ENTER] to Select the g.VCF file"
				read enter
				gVCF=`zenity --file-selection`
				echo "Press [ENTER] to Select the Output Directory for the Raw variants"
				read enter
				rVCF_out=`zenity --file-selection --directory`
				echo "Please Specify the Output Name for the Raw Variants"
				read rVCF_name
				echo "Begining Genotyping"
				java -jar $GATK -T GenotypeGVCFs -R $Ref --variant $gVCF -o $rVCF_out/$rVCF_name-raw.vcf
				echo "Genotyping is complete"
			done
			jumpto g_filtering
		if [ "$G_Ref" = n ]
		then jumpto genotypeGVCFs
		fi
		done
		genotypeGVCFs:
			for ((i=1; i<=$x; i++))
			do	
				echo "Genotyping for dataset $i"
				echo "Press [ENTER] to Select the g.VCF file"
				read enter
				gVCF=`zenity --file-selection`
				echo "Press [ENTER] to Select the Output Directory for the Raw variants"
				read enter
				rVCF_out=`zenity --file-selection --directory`
				echo "Please Specify the Output Name for the Raw Variants"
				read rVCF_name
				echo "Begining Genotyping"
				java -jar $GATK -T GenotypeGVCFs -R $Ref --variant $gVCF -o $rVCF_out/$rVCF_name-raw.vcf
				echo "Genotyping is complete"
			done
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
		echo "Do you wish to specify a reference file (y/n)?"
		read f_Ref
		while [ "$f_Ref" = y ]
		do
			for ((i=1; i<=$x; i++))
			do	
				echo "Filtering for dataset $i"
				echo "Press [ENTER] to specify a reference"
				read enter
				Ref="`zenity --file-selection`"
				echo "Press [ENTER] to Specify the Raw Variant File"
				read enter
				rVCF=`zenity --file-selection`
				echo "Press [ENTER] to Specify the Output Directory for the Final VCF file"
				read enter
				fVCF_out="`zenity --file-selection --directory`"
				echo "Please Specify the Final VCF file Name"
				read fVCF_name		
				echo "Please Specify the Minimum Genotype Quality to Keep"
				read GQ
				echo "Please Specify the Minimum Read Depth to Filter"
				read DP
				echo "Begining Variant Filtration"
				java -jar $GATK -T VariantFiltration -R $Ref --variant $rVCF -G_filter "GQ < $GQ || DP < $DP" -G_filterName lowGQ_DP --setFilteredGtToNocall -o $fVCF_out/$fVCF_name-filtered.vcf
				echo "Variant Filtration is complete"		
			done
			jumpto Combo_sequences
		if [ "$f_Ref" = n ]
		then jumpto V_filtration
		fi
		done
		V_filtration:
			for ((i=1; i<=$x; i++))
			do
				echo "Filtering for dataset $i"
				echo "Press [ENTER] to Specify the Raw Variant File"
				read enter
				rVCF=`zenity --file-selection`
				echo "Press [ENTER] to Specify the Output Directory for the Final VCF file"
				read enter
				fVCF_out="`zenity --file-selection --directory`"
				echo "Please Specify the Final VCF file Name"
				read fVCF_name		
				echo "Please Specify the Minimum Genotype Quality to Keep"
				read GQ
				echo "Please Specify the Minimum Read Depth to Filter"
				read DP
				echo "Begining Variant Filtration"
				java -jar $GATK -T VariantFiltration -R $Ref --variant $rVCF -G_filter "GQ < $GQ || DP < $DP" -G_filterName lowGQ_DP --setFilteredGtToNocall -o $fVCF_out/$fVCF_name-filtered.vcf
				echo "Variant Filtration is complete"
			done
			jumpto Combo_sequences
	if [ "$next" = n ]
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
			for ((i=1; i<=$x; i++))
			do	
				echo "Sequence Combination Database Construction for dataset $i"
				echo "Press [ENTER] to specify a reference"
				read enter
				Ref="`zenity --file-selection`"
				echo "Press [ENTER] to Select the final VCF file"
				read enter
				fVCF="`zenity --file-selection`"
				echo "Press [ENTER] to Specify the Sequence Combinations Output Directory"
				read enter
				combo_out="`zenity --file-selection --directory`"
				echo "Please specify how many bases you want to extend the sequence by"
				read extend
				echo "Please Specify the Sequence Combination Name"
				read combo_name
				echo "Begining Sequence Combination Construction"
				java -jar $biostars -R $Ref $fVCF -x $extend -o $combo_out/$combo_name-initial.fasta.gz
				echo "Combination Construction is complete"
			done
			jumpto seq_rename
		if [ "$C_Ref" = n ]
		then jumpto combo_const
		fi
		done
		combo_const:
			for ((i=1; i<=$x; i++))
			do
				echo "Sequence Combination Database Construction for dataset $i"
				echo "Press [ENTER] to Select the final VCF file"
				read enter
				fVCF="`zenity --file-selection`"
				echo "Press [ENTER] to Specify the Sequence Combinations Output Directory"
				read enter
				combo_out="`zenity --file-selection --directory`"
				echo "Please specify how many bases you want to extend the sequence by"
				read extend
				echo "Please Specify the Sequence Combination Name"
				read combo_name
				echo "Begining Sequence Combination Construction"
				java -jar $biostars -R $Ref $fVCF -x $extend -o $combo_out/$combo_name.fasta.gz
				echo "Combination Construction is complete"
			done
			jumpto seq_rename
	if ["$next" = n]
	then jumpto seq_rename
	fi
	done
seq_rename:
	echo "Do you wish to Rename the Sequence Combinations (y/n)? Note: This will help to read the combinations. If you are planning on merging the databases and removing duplicates you MUST deposit all of the databases into the same directory!"
	read next	
	while [ "$next" = y ]
	do
		echo "Will you be merging your databases after renaming (y/n)?"
		read Merge_dir
		echo "Press [ENTER] to specify the renamed sequence combination output directory"
		read enter
		Merge_dir_out="`zenity --file-selection --directory`"	
		while [ "$Merge_dir" = y ]
		do		
			for ((i=1; i<=$x; i++))
			do
				echo "Database Sequence Renaming for dataset $i"
				echo "Press [ENTER] to Specify the Sequence Combination file"
				read enter
				seq_combo="`zenity --file-selection`"
				echo "Please specify the sequence prefix. Note: This is a counter so if you type Genotype, the first combination will be Genotype_0 and then continue."
				read combo_seq_name
				echo "Begining to Rename Sequences"
				seq_names=$(basename "$seq_combo" .fasta.gz)
				Combo_seq_new="$Merge_dir_out/$seq_names-renamed.fasta.gz"
				$Renamer in=$seq_combo out=$Combo_seq_new prefix=$combo_seq_name
				echo "Renaming is complete"
			done
			jumpto merge
		if [ "$Merge_dir" = n ]
		then jumpto no_merge_dir
		fi
		done
		no_merge_dir:
			for ((i=1; i<=$x; i++))
			do
				echo "Database Sequence Renaming for dataset $i"
				echo "Press [ENTER] to Specify the Sequence Combination file"
				read enter
				seq_combo="`zenity --file-selection`"
				echo "Press [ENTER] to specify the corrected sequence combination output directory"
				read enter
				seq_names_out="`zenity --file-selection --directory`"
				echo "Please specify the sequence prefix. Note: This is a counter so if you type Genotype, the first combination will be Genotype_0 and then continue."
				read combo_seq_name
				echo "Begining to Rename Sequences"
				seq_names=$(basename "$seq_combo" .fasta.gz)
				Combo_seq_new="$seq_names_out/$seq_names-renamed.fasta.gz"
				$Renamer in=$seq_combo out=$Combo_seq_new prefix=$combo_seq_name
				bwa index $Combo_seq_new
				echo "Renaming is complete"
			done
			jumpto final_map
	if ["$next" = n]
	then jumpto merge
	fi
	done
merge:
	echo "Do you wish to Merge databases, remove duplicates and index (y/n)? Note: This may require a lot of storage and combinations must be in the same directory."
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to Specify the Directory where the Renamed Sequence Combinations are stored"
		read enter
		seq_in_dir="`zenity --file-selection --directory`"
		echo "Press [ENTER] to Specify the Output directory for the Merged Database"
		read enter
		seq_out_dir="`zenity --file-selection --directory`"
		echo "Please Specify the Output name for the Merged Database"
		read merge_name
		merge="$seq_out_dir/$merge_name"
		echo "Begining Database Merge, Duplicate Removal and Indexing"
		cat $seq_in_dir/*renamed.fasta.gz > $merge.fasta.gz
		$Dedupe -Xmx$RAMg in=$merge.fasta.gz out=$merge-deduped.fasta.gz
		bwa index $merge-deduped.fasta.gz
		echo "Database merging, duplicates removal and indexing complete"
		jumpto final_map
	if ["$next" = n]
	then jumpto final_map
	fi
	done
final_map:
	echo "Do you wish to complete the Final Mapping, Sorting and Exporting of Statistics (y/n)?"
	read next
	while [ "$next" = y ]
	do
		echo "Will you be mapping to a merged database (y/n)?"
		read Map_mir
		echo "Press [ENTER] to specify the indexed merged database"
		read enter
		Combo_Ref="`zenity --file-selection`"	
		while [ "$Map_mir" = y ]
		do		
			for ((i=1; i<=$x; i++))
			do
				echo "Final Mapping, Sorting and Stat Exporting for dataset $i"
				echo "Press [ENTER] to specify the trimmed FASTQ file."
				read enter
				FastQ="`zenity --file-selection`"
				echo "Press [ENTER] to Specify the Directory for the Final Mapping"
				read enter
				f_map_out="`zenity --file-selection --directory`"
				echo "Please Specify the Name for the Final Mapping"
				read f_map_name
				f_map="$f_map_out/$f_map_name"
				echo "Note: If you plan on merging all statistics into a single file and output a single fasta list, you must specify the same directory for all csv files."
				echo "Press [ENTER] to Specify the Directory for the Coverage Statistics"
				read enter
				stats_out="`zenity --file-selection --directory`"
				stats="$stats_out/$f_map_name-stats.csv"
				echo "Begining Final Mapping"
				bwa mem $Combo_Ref $FastQ -t $t > $f_map-final.sam
				samtools view -b $f_map-final.sam | samtools sort -o $f_map-final-sorted.bam
				rm $f_map-final.sam
				samtools index $f_map-final-sorted.bam
				samtools idxstats $f_map-final-sorted.bam > $stats
				echo "Final Mapping is complete"
				echo "Prior to extracting target fasta sequences, visually inspect the mapping (i.e. Tablet) and create a text file containing the target sequence names on seperate lines."
			done
			jumpto extract_seq
		if ["$Map_mir" = n]
		then jumpto new_db_map
		fi
		done
			new_db_map:
			for ((i=1; i<=$x; i++))
			do
				echo "Final Mapping, Sorting and Stat Exporting for dataset $i"
				echo "Press [ENTER] to specify reference database $i"
				read enter
				Combo_Ref="`zenity --file-selection`"
				echo "Press [ENTER] to specify the trimmed FASTQ file."
				read enter
				FastQ="`zenity --file-selection`"
				echo "Press [ENTER] to Specify the Directory for the Final Mapping"
				read enter
				f_map_out="`zenity --file-selection --directory`"
				echo "Please Specify the Name for the Final Mapping"
				read f_map_name
				f_map="$f_map_out/$f_map_name"
				echo "Note: If you plan on merging all statistics into a single file and output a single fasta list, you must specify the same directory for all csv files."
				echo "Press [ENTER] to Specify the Directory for the Coverage Statistics."
				read enter
				stats_out="`zenity --file-selection --directory`"
				stats="$stats_out/$f_map_name-stats.csv"
				echo "Begining Final Mapping"
				bwa mem $Combo_Ref $FastQ -t $t > $f_map-final.sam
				samtools view -b $f_map-final.sam | samtools sort -o $f_map-final-sorted.bam
				rm $f_map-final.sam
				samtools index $f_map-final-sorted.bam
				samtools idxstats $f_map-final-sorted.bam > $stats
				sed -i 1i"Sequences-$f_map_name	Sequence_Length	Mapped_Reads	Unmapped_Reads" $stats
				echo "Final Mapping is complete"
				echo "Prior to extracting target fasta sequences, visually inspect the mapping (i.e. Tablet) to confirm mapping is correct."
			done
			jumpto extract_seq
	if ["$next" = n]
	then jumpto extract_seq
	fi
	done
extract_seq:
	echo "Do you wish to subset and extract fasta sequences of relevance from the merged database (y/n)? Note: This will automatically subset based on 1x minimum coverage per Genotype/OTU/Taxa."
	read next	
	while [ "$next" = y ]
	do
		echo "Do you wish to merge all coverage statistic files and output a single fasta sequence list (y/n)?"
		read stat_merging
		while [ "$stat_merging" = y ]
		do			
			echo "Press [ENTER] to specify the directory containing all of the statistic files"
			read enter
			stat_merge_dir="`zenity --file-selection --directory`"
			echo "Press [ENTER] to specify the output directory of the merged statistic file"
			read enter
			stat_merge_out="`zenity --file-selection --directory`"
			echo "Press [ENTER] to specify the output directory for the sequence list names"
			read enter
			seq_list_dir="`zenity --file-selection --directory`"
			echo "Merging and subsetting files"
			cat $stat_merge_dir/*stats.csv > $stat_merge_out/Merged_stats.csv
			subset="$stat_merge_out/Merged_stats.csv"
			Rscript $IMG_dir/MetaGaAP/MetaGaAP_Back-ends/Seq_List.R $seq_list_dir $subset
			rm $subset
			rm Subset_stats.csv
			Rscript $IMG_dir/MetaGaAP/MetaGaAP_Back-ends/Subset_Stats.R $stat_merge_dir
			mv Sequence_names.txt $seq_list_dir
			echo "Merging and subsetting files complete. Proceed to Fasta extraction."
			echo "Press [ENTER] to specify the database"
			read enter
			DB="`zenity --file-selection`"
			list=$seq_list_dir/Sequence_names.txt
			echo "Press [ENTER] to specify output directory for sequence list"
			read enter
			list_dir="`zenity --file-selection --directory`"
			echo "Please specify the output name for extracted sequence list"
			read fa_name
			echo "Begining Sequence extraction"
			$Extract_Fa $DB $list $list_dir/$fa_name.fasta
			echo "Sequence extraction is complete"
			jumpto finish
		if [ "$stat_merging" = n ]
		then jumpto stat_no_merge
		fi
		done
stat_no_merge:
		for ((i=1; i<=$x; i++))
		do
			echo "Press [ENTER] to select statistic file $i to be subsetted"
			read enter
			subset="`zenity --file-selection`"
			echo "Press [ENTER] to specify the output directory for the sequence list names"
			read enter
			seq_list_dir="`zenity --file-selection --directory`"
			echo "Subsetting file $i"
			Rscript $IMG_dir/MetaGaAP/MetaGaAP_Back-ends/Seq_List.R $seq_list_dir $subset 
			mv Sequence_names.txt Sequence_names_$i.txt
			mv Sequence_names_$i.txt $seq_list_dir
			mv Subset_stats.csv Subset_stats_$i.csv
			mv Subset_stats_$i.csv $seq_list_dir
			echo "Subsetting files complete. Proceed to Fasta extraction."
			echo "Press [ENTER] to specify the database"
			read enter
			DB="`zenity --file-selection`"
			list=$seq_list_dir/Sequence_names_$i.txt
			echo "Press [ENTER] to specify output directory for the fasta sequence list"
			read enter
			list_dir="`zenity --file-selection --directory`"
			echo "Please specify the output name for extracted fasta sequence list"
			read fa_name
			echo "Begining Sequence extraction"
			$Extract_Fa $DB $list $list_dir/$fa_name.fasta
			echo "Sequence extraction is complete"
		done
		jumpto finish
	if ["$next" = n]
	then jumpto finish
	fi
	done

finish:
echo "$USER you have now successfully completed MetaGaAP. Your final fasta list can now be used for further analysis (including taxa assignment using NCBI Blast) and relative abundance of each Taxa/OTU can be calculated from the csv file. Thank-you and don't forget to cite the method and software used."
exit 0
done		
