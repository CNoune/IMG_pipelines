#!/bin/bash
# jumpto function built from https://bobcopeland.com/blog/2012/10/goto-in-bash/
# IMG_AP - version 1.5.3
# Copyright (c) 2016 Christopher Noune
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
	echo "Hello, "$USER". Welcome to the IMG Assembly Method. Press [ENTER] to begin"
	read enter
	echo "Please Note: Trimming must be completed before begining the pipeline. Press [ENTER] to proceed or ctrl c to exit"
	read enter

trimming:
	echo "Do you wish to complete the trimming step (y/n)? Note: The trimming step is designed for single-ended datasets"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin trimming."
		read enter
		echo "Press [ENTER] to select raw fastq file."
		read enter
		fastq=`zenity --file-selection`
		echo "Press [ENTER] to specify output folder for QC trimming"
		read enter
		fastqc_out=`zenity --file-selection --directory`
		echo "Please specify QC output file name followed by .fastq"
		read fastqc_name
		echo "Press [ENTER] to specify output folder for artifact filtering."
		read enter
		artifact_out=`zenity --file-selection --directory`
		echo "Please specify artifact output file name followed by .fastq"
		read artifact_name
		echo "Press [ENTER] to specify output folder for final trimmed Data."
		read enter
		final_trim_out=`zenity --file-selection --directory`
		echo "Please specify the final trimmed data output name followed by .fastq"
		read final_trim_name
		echo "Please specify the minimum quality score to keep."
		read qc
		echo "Please specify the last base to keep."
		read l
		echo "Please specify the first base to keep."
		read f
		echo "Trimming has begun"
		fastq_quality_trimmer -t $qc -l $l -i $fastq -o $fastqc_out/$fastqc_name
		fastx_artifacts_filter -i $fastqc_out/$fastqc_name -o $artifact_out/$artifact_name
		fastx_trimmer -f $f -l $l -i $artifact_out/$artifact_name -o $final_trim_out/$final_trim_name
		echo "Trimming is complete"
		jumpto index
	if [ "$next" = n]
	then jumpto index
	fi
	done 
index:
next=y
	echo "Do you wish to complete the indexing step (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Indexing
	
		echo "Press [ENTER] to select a reference to index"
		read enter
		Ref=`zenity --file-selection`
		echo "Press [ENTER] to specify an output directory for the sequence dictionary"
		read enter
		Dict_Out=`zenity --file-selection --directory`
		echo "Indexing has begun"
		bwa index $Ref
		samtools faidx $Ref
		Dict_name=$(basename "$Ref" .fasta)
		Dict_final=$Dict_Out/$Dict_name.dict
		picard-tools CreateSequenceDictionary R=$Ref O=$Dict_final
		echo "Indexing is complete"
		jumpto map
	if ["$next" = n]
	then jumpto map
	fi
	done 

map:
	echo "Do you wish to complete the mapping step (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin initial mapping"
		read enter
			echo "Do you wish to specify the reference file (y/n)?"
			read choose_ref	
			while [ "$choose_ref" = y ]
			do
			Ref=`zenity --file-selection`
			jumpto ref_map
		if [ "$choose_ref" = n ]
		then jumpto ref_map
		fi
		done

		ref_map:
		echo "Press [ENTER] to specify FASTQ file 1"
		read enter
		Fastq1=`zenity --file-selection`
		echo "Press [ENTER] to specify FASTQ file 2. Note: If you do not have a second FASTQ file, press cancel on the dialog box"
		read enter
		Fastq2=`zenity --file-selection`
		echo "Please specify threads to use"
		read t
		echo "Press [ENTER] to specify output directory"
		read enter
		SAM_output=`zenity --file-selection --directory`
		echo "Please specify SAM output name"
		read SAM_name
		SAM=$SAM_output/$SAM_name.sam
		echo "Mapping has begun"
		bwa mem $Ref $Fastq1 $Fastq2 -t $t > $SAM
		echo "Mapping is complete"
		jumpto bam	
	if ["$next" = n]
	then jumpto bam
	fi
	done

bam:
	echo "Do you wish to complete the BAM sorting and conversion step (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#BAM Sorting and Conversion
		echo "Press [ENTER] to begin BAM conversion"
		read enter
		echo "Press [ENTER] to specify output directory"
		read enter
		BAM_out=`zenity --file-selection --directory`
		echo "Please specify output file name"
		read BAM_conv
		echo "BAM sorting and conversion has begun"
		samtools view -bS $SAM_output/$SAM | samtools sort - $BAM_out/$BAM_conv
		echo "BAM sorting and conversion has ended"
		jumpto initial
	if ["$next" = n]
	then jumpto initial
	fi
	done
initial:
	echo "Do you wish to complete the initial concensus generation step (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Intial Consensus Generation
		echo "Do you wish to specify where GATK is located (y/n)?"
		read GATK_loc
		while [ "$GATK_loc" = y ]
		do
			echo "Press [ENTER] to specify where GATK is located"
			read enter
			GATK=`zenity --file-selection`
			jumpto cns_gen
		if [ "$GATK_loc" = n ]		
		then jumpto cns_gen
		fi
		done
			echo "Do you wish to specify the reference file (y/n)?"
			read choose_ref	
			while [ "$choose_ref" = y ]
			do
			Ref=`zenity --file-selection`
			jumpto cns_gen
		if [ "$choose_ref" = n ]
		then jumpto cns_gen
		fi
		done
		
		cns_gen:		
		echo "Press [ENTER] to begin initial consensus generation"
		read enter
		echo "Press [ENTER] to specify output directory for VCF file"
		read enter
		VCF_out=`zenity --file-selection --directory`
		echo "Please specify VCF output name"
		read VCF_name
		VCF=$VCF_out/$VCF_name.vcf
		echo "Press [ENTER] to select sorted BAM file"
		read enter
		BAM=`zenity --file-selection`
		echo "Press [ENTER] to specify output directory for bed file"
		read enter
		BED_out=`zenity --file-selection --directory`
		echo "Please specify BED output name"
		read bed_name
		BED=$BED_out/$BED_name.bed
		echo "Press [ENTER] to select an output directory for Initial Consensus Sequence"
		read enter
		CNS_out=`zenity --file-selection --directory`
		echo "Please specify initial consensus sequence name"
		read CNS_name
		echo "Please specify mergeBed overlap value"
		read d
		echo "Initial consensus generation has begun"
		Init_CNS=$CNS_out/$CNS_name.fasta
		genomeCoverageBed -bg -split -ibam $BAM | mergeBed -d $d | samtools mpileup -uf $Ref $BAM -l stdin | bcftools view -cg -> $VCF
		genomeCoverageBed -bg -split -ibam $BAM | mergeBed -d -> $BED
		java -jar $GATK -T FastaAlternateReferenceMaker -R $Ref -o $Init_CNS  --variant $VCF -L $BED
		echo "Initial consensus generation is complete"		
		jumpto bam2fasta
	if ["$next" = n]
	then jumpto bam2fasta
	fi
	done
bam2fasta:
	echo "Do you wish to complete the BAM2Fasta step (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#BAM2Fasta
		echo "Press [ENTER] to begin bam2fasta conversion"
		read enter
		echo "Press [ENTER] to specify output directory"
		read enter
		BAM_Reads_OUT=`zenity --file-selection --directory`
		echo "Please specify bam2fasta output name"
		read BAM_reads_name
		$BAM_Fasta=$BAM_Reads_OUT/$BAM_reads_name.fasta
		echo "BAM2Fasta conversion has begun"
		bam2fastx -N $BAM -o $BAM_Fasta --fasta -M
		echo "BAM2Fasta conversion is complete"
		jumpto kmer
	if ["$next" = n]
	then jumpto kmer
	fi
	done

kmer:
	echo "Do you wish to complete the kmer estimation step (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#kmer estimation
		echo "Press [ENTER] to begin kmer-estimation."
		read enter
		echo "Do you wish to re-specify where kmergenie is located (y/n)?"
		read kmer_loc
		while [ "$kmer_loc" = y ]
		do
			echo "Press [ENTER] to specify where kmergenie is located"
			read enter
			kmergenie=`zenity --file-selection`
			jumpto kmer_loc_set
		if [ "$kmer_loc" = n ]
		then jumpto kmer_loc_set
		fi
		done
	kmer_loc_set:
			echo "Press [ENTER] to select your bam2fasta converted reads"
			read enter
			BAM2FASTA=`zenity --file-selection`
			echo "Press [ENTER] to select kmer output directory"
			read enter
			kmer_out=`zenity --file-selection --directory`
			echo "Kmer estimation has begun"
			$kmergenie $BAM2FASTA -o $kmer_out/
			echo "Kmer estimation is complete"
			jumpto assembly
	if ["$next" = n]
	then jumpto assembly
	fi
	done
assembly:
	echo "Do you wish to complete the assembly steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Tadpole Assembly and Merge
		echo "Press [ENTER] to begin tadpole denovo assembly and merge."
		read enter
		echo "Do you wish to specify where Tadpole is located (y/n)?"
		read tadpole_loc
		while [ "$tadpole_loc" = y ]
		do
			echo "Press [ENTER] to specify where Tadpole is located"
			read enter
			tadpole=`zenity --file-selection`
			jumpto spec_out
		if [ "$tadpole_loc" = n ]
		then jumpto spec_out
		fi
		done
			spec_out:
			echo "Do you wish to specify where your BAM2Fasta reads are (y/n)?"
			read BAM2fasta_sel
			while [ "$BAM2fasta_sel" = y ]
			do
				echo "Press [ENTER] to select your bam2fasta converted reads"
				read enter
				BAM2FASTA=`zenity --file-selection`
				jumpto cns_selection
			if [ "$BAM2fasta_sel" = n ]
			then jumpto cns_selection
			fi
			done
			echo "Do you wish to specify where your initial consensus sequence is (y/n)?"
			while [ "$choose_cns" = y ]
			do
				echo "Press [ENTER] to select your initial consensus sequence"
				read enter
				Init_CNS=`zenity --file-selection`
				jumpto choose_data_pipe
			if [ "$choose_cns" = n ]
			then jumpto choose_data_pipe
			fi
			done
				choose_data_pipe:
				echo "Press [ENTER] to specify denovo assembly output folder"
				read enter
				denovo_out=`zenity --file-selection --directory`		
				echo "Please specify output name for denovo assembly"
				read denovo_name
				$denovo=$denovo_out/$denovo_name.fasta
				echo "Press [ENTER] to specify output directory for final merged data"
				read enter
				final_output=`zenity --file-selection --directory`
				echo "Please specify output name for final merged data "
				read final_name
				Final_merged=$final_output/$final_name.fasta	
				echo "Press [ENTER] to specify FASTQ file 1"
				read enter
				Fastq1=`zenity --file-selection`
				echo "Press [ENTER] to specify FASTQ file 2. Note: If you do not have a second FASTQ file, press cancel on the dialog box"
				read enter
				Fastq2=`zenity --file-selection`
				echo "Press [ENTER] to specify the output directory for converted FASTQ to FASTA reads"
				read enter
				fastq2fasta_out=`zenity --file-selection --directory`
				echo "Please specify the Output Name for Converted FASTQ 1"
				read fastq1_name
				echo "Please specify the Output Name for Converted FASTQ 2. Note: If you do not have a second FASTQ file, press [ENTER]"
				read fastq2_name
				echo "Please specify kmer value"
				read k
				echo "FASTQ to FASTA conversion has begung"
				fastq_to_fasta -i $Fastq1 -o $fastq2fasta_out/$fastq1_name
				fastq_to_fasta -i $Fastq2 -o $fastq2fasta_out/$fastq2_name
				echo "FASTQ to FASTA conversion is complete"
				echo "Tadpole denovo assembly has begun"
				$tadpole in=$BAM2FASTA out=$denovo k=$k
				echo "Tadpole denovo assembly is complete"
				echo "Final merge has begun"
				cat $BAM2FASTA $Init_CNS $fastq2fasta_out/$fastq1_name $fastq2fasta_out/$fastq2_name $denovo_out/$denovo > $Final_merged
				echo "Final merge is complete"				
				jumpto finish
	if ["$next" = n]
	then jumpto finish
	fi
	done

finish:
echo "$USER you have now successfully completed the IMG Assembly pipeline. Do you wish to repeat for another sample (y/n). Otherwise your final step is to import your data into Geneious (or equivalent) to complete the final mapping and sequence generation."
read next
	if [ "$next" = y ] 
	then jumpto trimming
	elif [ "$next" = n ]
	then jumpto quit
	fi

quit:
echo "Thank-you, don't forget to cite the method and software used"
exit 0
done
