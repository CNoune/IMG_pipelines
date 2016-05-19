#!/bin/bash
# jumpto function built from https://bobcopeland.com/blog/2012/10/goto-in-bash/
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
		echo "Press [ENTER] to Specify an Output Directory for the Sequence Dictionary"
		read enter
		Dict_Directory=`zenity --file-selection --directory`
		echo "Please Specify a name for the Output followed by .dict"
		read dict
		picard-tools CreateSequenceDictionary R=$Ref O=$Dict_Directory/$dict
		jumpto map
	if ["$next" = n]
	then jumpto map
	fi
	done 

map:
	echo "Do you wish to complete the Mapping steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
		echo "Press [ENTER] to begin initial mapping"
		read enter
			echo "Do you wish to re-specify the Reference file (y/n)?"
			read choose_ref	
			while [ "$choose_ref" = n ]
			do
				echo "Press [ENTER] to Specify FASTQ file 1"
				read enter
				Fastq1=`zenity --file-selection`
				echo "Press [ENTER] to Specify FASTQ file 2. Note: If you do not have a second FASTQ file, press cancel on the dialog box"
				read enter
				Fastq2=`zenity --file-selection`
				echo "Please Specify Threads to Use"
				read t
				echo "Press [ENTER] to Specify Output Directory"
				read enter
				SAM_output=`zenity --file-selection --directory`
				echo "Please Specify Output name followed by .sam"
				read SAM
				bwa mem $Ref $Fastq1 $Fastq2 -t $t > $SAM_output/$SAM
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
		echo "Press [ENTER] to Specify FASTQ file 2. Note: If you do not have a second FASTQ file, press cancel on the dialog box"
		read enter
		Fastq2=`zenity --file-selection`
		echo "Please Specify Threads to Use"
		read t
		echo "Press [ENTER] to Specify Output Directory"
		read enter
		SAM_output=`zenity --file-selection --directory`
		echo "Please Specify Output name followed by .sam"
		read SAM
		bwa mem $Ref $Fastq1 $Fastq2 -t $t > $SAM_output/$SAM
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
		echo "Press [ENTER] to Specify Output Directory"
		read enter
		BAM_out=`zenity --file-selection --directory`
		echo "Please Specify Output File Name"
		read BAM_conv
		samtools view -bS $SAM_output/$SAM | samtools sort - $BAM_out/$BAM_conv
		jumpto initial
	if ["$next" = n]
	then jumpto initial
	fi
	done
initial:
	echo "Do you wish to complete the Initial Concensus Generation Steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Intial Consensus Generation
		echo "Press [ENTER] to begin initial consensus generation"
		read enter
		echo "Press [ENTER] to Specify Output Directory for VCF file"
		read enter
		VCF_out=`zenity --file-selection --directory`
		echo "Please Specify Output File Name followed by .vcf"
		read VCF
		echo "Please Specify mergeBed overlap value"
		read d
		echo "Press [ENTER] to Select Sorted BAM file"
		read enter
		BAM=`zenity --file-selection`
		echo "Press [ENTER] to Specify Output Directory for bed file"
		read enter
		BED_out=`zenity --file-selection --directory`
		echo "Please Specify Output File Name followed by .bed"
		read bed
		echo "Do you wish to re-specify where GATK is located (y/n)?"
		read GATK_loc
		while [ "$GATK_loc" = y ]
		do
			echo "Press [ENTER] to Specify where GATK is located"
			read enter
			GATK=`zenity --file-selection`
			jumpto cns_out
		if [ "$GATK_loc" = n ]
		then jumpto cns_out
		fi
		done
		cns_out:
		echo "Press [ENTER] to Select an Output Directory for Initial Consensus Sequence"
		read enter
		CNS_out=`zenity --file-selection --directory`
		echo "Please Specify Output File Name followed by .fasta"
		read CNS
		genomeCoverageBed -bg -split -ibam $BAM | mergeBed -d $d | samtools mpileup -uf $Ref $BAM -l stdin | bcftools view -cg -> $VCF_out/$VCF
		genomeCoverageBed -bg -split -ibam $BAM | mergeBed -d -> $BED_out/$bed
		java -jar $GATK -T FastaAlternateReferenceMaker -R $Ref -o $CNS_out/$CNS --variant $VCF_out/$VCF -L $BED_out/$bed
		jumpto bam2fasta
	if ["$next" = n]
	then jumpto bam2fasta
	fi
	done
bam2fasta:
	echo "Do you wish to complete the BAM2Fasta Steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#BAM2Fasta
		echo "Press [ENTER] to begin bam2fasta conversion"
		read enter
		echo "Press [ENTER] to specify output directory"
		read enter
		BAM_Reads_OUT=`zenity --file-selection --directory`
		echo "Please Specify Output Name followed by .fasta"
		read BAM_reads
		bam2fastx -N $BAM -o $BAM_Reads_OUT/$BAM_reads --fasta -M
		jumpto kmer
	if ["$next" = n]
	then jumpto kmer
	fi
	done

kmer:
	echo "Do you wish to complete the kmer estimation Steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#kmer estimation
		echo "Press [ENTER] to begin kmer-estimation. Note: The kmergenie directory must be in your home directory"
		read enter
		echo "Do you wish to re-specify where kmergenie is located (y/n)?"
		read kmer_loc
		while [ "$kmer_loc" = y ]
		do
			echo "Press [ENTER] to Specify where kmergenie is located"
			read enter
			kmergenie=`zenity --file-selection`
			echo "Press [ENTER] to Select your bam2fasta converted reads"
			read enter
			BAM2FASTA=`zenity --file-selection`
			echo "Press [ENTER] to Select kmer output directory"
			read enter
			kmer_out=`zenity --file-selection --directory`
			$kmergenie $BAM2FASTA -o $kmer_out
			jumpto assembly
		if [ "$kmer_loc" = n ]
		then jumpto kmer_loc_set
		fi
		done
	kmer_loc_set:
			echo "Press [ENTER] to Select your bam2fasta converted reads"
			read enter
			BAM2FASTA=`zenity --file-selection`
			echo "Press [ENTER] to Select kmer output directory"
			read enter
			kmer_out=`zenity --file-selection --directory`
			$kmergenie $BAM2FASTA -o $kmer_out
			jumpto assembly
	if ["$next" = n]
	then jumpto assembly
	fi
	done
assembly:
	echo "Do you wish to complete the Assembly Steps (y/n)?"
	read next	
	while [ "$next" = y ]
	do
#Tadpole Assembly and Merge
		echo "Press [ENTER] to begin tadpole denovo assembly and merge. The bbmap directory must be in your home directory"
		read enter
		echo "Do you wish to re-specify where Tadpole is located (y/n)?"
		read tadpole_loc
		while [ "$tadpole_loc" = y ]
		do
			echo "Press [ENTER] to Specify where Tadpole is located"
			read enter
			tadpole=`zenity --file-selection`
			jumpto spec_out
		if [ "$tadpole_loc" = n ]
		then jumpto spec_out
		fi
		done
			spec_out:
			echo "Press [ENTER] to specify denovo assembly output folder"
			read enter
			denovo_out=`zenity --file-selection --directory`
			echo "Do you wish to re-specify where your bam2fasta reads are? (yes/no)"
			read choose_data
			while [ "$choose_data" = no ]
			do
				echo "Please Specify Output Name followed by .fasta"
				read denovo
				echo "Please Specify kmer value"
				read k
				echo "Press [ENTER] to Specify Output Directory for Final Merged data"
				read enter
				Final_output=`zenity --file-selection --directory`
				echo "Please Specify Output Name for Final Merged data followed by .fasta"
				read Final_name
				$tadpole in=$BAM2FASTA out=$denovo_out/$denovo k=$k
				cat $BAM2FASTA $denovo_out/$denovo > $Final_output/$Final_name
				jumpto finish
			if ["$choose_data" = yes]
			then jumpto choose_data_pipe
			fi
			done

				choose_data_pipe:
				echo "Press [ENTER] to Select your bam2fasta converted reads"
				read enter
				BAM2FASTA=`zenity --file-selection`		
				echo "Please Specify Output Name followed by .fasta"
				read denovo
				echo "Please Specify kmer value"
				read k
				echo "Press [ENTER] to Specify Output Directory for Final Merged data"
				read enter
				Final_output=`zenity --file-selection --directory`
				echo "Please Specify Output Name for Final Merged data followed by .fasta"
				read Final_name
				$tadpole in=$BAM2FASTA out=$denovo_out/$denovo k=$k
				cat $BAM2FASTA $denovo_out/$denovo > $Final_output/$Final_name
				jumpto finish
	if ["$next" = n]
	then jumpto finish
	fi
	done

finish:
echo "$USER you have now successfully completed the IMG Assembly pipeline. Do you wish to repeat for another sample (y/n). Otherwise your final step is to import your data into Geneious (or equivalent) to complete the final mapping and sequence generation."
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
