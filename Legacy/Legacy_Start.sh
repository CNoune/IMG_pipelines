#!/bin/bash
# Start - build 4
# Copyright (c) 2016 Christopher Noune

echo "Welcome "$User" to the Invertebrate Microbiology Group pipelines. Please select a pipeline below to begin"
PS3='Please enter your choice: '
options=("IMG_AP" "MetaGaAP" "Install Most Packages" "Quit")
select opt in "${options[@]}"
do
    case $opt in
        "IMG_AP")
            echo "You have selected IMG_AP"
		bash IMG_pipelines/Legacy/IMG_AP/IMG_AP.sh
            ;;
        "MetaGaAP")
            echo "You have selected MetaGaAP. Note: This is currently build 16 and may contain bugs."
		bash IMG_pipelines/Legacy/MetaGaAP_Legacy/MetaGaAP_Back-ends/Set_wrk_dir.sh
		echo -e "MetaGaAP Analysis Complete. Please type: \n(1) for IMG_AP \n(2) for MetaGaAP \n(4) to quit."
            ;;
	"Install Most Packages")
            echo "You have selected to install most of the required packages. This requires you to input your superuser password. You will need to download GATK seperately. Biostars175929, kentUtils and bbmap will be found in the IMG_pipelines folder."
		sudo add-apt-repository ppa:webupd8team/java
		sudo apt-get update
		sudo apt-get install oracle-java8-installer bwa fastx-toolkit tophat libtool autoconf fastqc picard-tools git gradle libxml2 libxml2-dev libssl-dev openssl mysql-client-5.7 mysql-client-core-5.7 libpng-dev zlib1g-dev libmysqlclient-dev r-base
		wget 'https://github.com/samtools/samtools/releases/download/1.3.1/samtools-1.3.1.tar.bz2'
		wget 'https://github.com/samtools/bcftools/releases/download/1.3.1/bcftools-1.3.1.tar.bz2'
		wget 'https://github.com/samtools/htslib/releases/download/1.3.2/htslib-1.3.2.tar.bz2'
		wget 'https://sourceforge.net/projects/bbmap/files/latest/latest_bbmap.tar.gz'
		git clone git://git.gnome.org/libxslt
		git clone "https://github.com/samtools/htsjdk"
		git clone git://github.com/ENCODE-DCC/kentUtils.git
		tar xf latest_bbmap.tar.gz
		tar jxf samtools-1.3.1.tar.bz2
		tar jxf bcftools-1.3.1.tar.bz2
		tar jxf htslib-1.3.2.tar.bz2
		rm samtools-1.3.1.tar.bz2
		rm bcftools-1.3.1.tar.bz2
		rm htslib-1.3.2.tar.bz2
		mv samtools*/ IMG_pipelines/
		mv bcftools*/ IMG_pipelines/
		mv htslib*/ IMG_pipelines
		mv bbmap/ IMG_pipelines/
		rm latest_bbmap.tar.gz
		cd libxslt
		./autogen.sh --prefix=/usr
		make
		sudo make install
		cd ../htsjdk
		./gradlew
		cd ../kentUtils
		make
		cd
		mv kentUtils/ IMG_pipelines/
		mv htsjdk/ IMG_pipelines/
		mv libxslt/ IMG_pipelines/
		mv jvarkit/ IMG_pipelines/
		cd IMG_pipelines/samtools*
		make
		sudo make prefix=/usr/ install
		cd ../bcftools*
		make
		sudo make prefix=/usr/ install
		cd ../htslib*
		make
		sudo make prefix=/usr/ install
		echo -e "Installation Complete. Please type: \n(1) for IMG_AP \n(2) for MetaGaAP \n(4) to quit."
            ;;		
        "Quit")
            break
            ;;
        *) echo invalid option;;
    esac
done
