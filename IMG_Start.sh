#!/bin/bash
# IMG_Start - version 2.0 - build 3
# Copyright (c) 2016 Christopher Noune

echo "Welcome "$User" to IMG Pipelines. Please select a pipeline below to begin"
PS3='Please enter your choice: '
options=("IMG_AP" "IMG_bootMAP" "IMG-GAP Build 13 - Experimental" "Install Most Packages" "Quit")
select opt in "${options[@]}"
do
    case $opt in
        "IMG_AP")
            echo "You have selected IMG_AP"
		bash IMG_pipelines/IMG_AP/IMG_AP.sh
            ;;
        "IMG_bootMAP - not available yet")
            echo "You have selected IMG_bootMAP"
		bash IMG_pipelines/IMG_bootMAP/IMG_bootMAP_Back-ends/Set_wrk_dir.sh
		echo -e "IMG_bootMAP Complete. Please type: \n(1) for IMG_AP \n(2) for IMG_GAP \n(3) for IMG_bootMAP \n(5) to quit."
            ;;
        "IMG-GAP Build 13 - Experimental")
            echo "You have selected IMG_GAPv2. Note: This is currently experimental and contains many bugs."
		bash IMG_pipelines/IMG_GAP/IMG_GAP_Back-ends/Set_wrk_dir.sh
		echo -e "IMG_GAP Analysis Complete. Please type: \n(1) for IMG_AP \n(2) for IMG_GAP \n(3) for IMG_bootMAP \n(5) to quit."
            ;;
	"Install Most Packages")
            echo "You have selected to install most of the required packages. This requires you to input your superuser password. You will need to download GATK seperately. Biostars175929, kentUtils and bbmap will be found in the IMG_pipelines folder."
		sudo apt-get install bwa openjdk-8-jdk openjdk-8-jre samtools fastx-toolkit tophat libtool autoconf fastqc picard-tools git gradle libxml2 libxml2-dev libssl-dev openssl mysql-client-5.7 mysql-client-core-5.7 libpng-dev zlib1g-dev libmysqlclient-dev r-base
		wget 'https://sourceforge.net/projects/bbmap/files/latest/latest_bbmap.tar.gz'
		git clone git://git.gnome.org/libxslt
		git clone "https://github.com/samtools/htsjdk"
		git clone "https://github.com/lindenb/jvarkit.git"
		git clone git://github.com/ENCODE-DCC/kentUtils.git
		tar xf latest_bbmap.tar.gz
		mv bbmap/ IMG_pipelines/
		rm latest_bbmap.tar.gz
		cd libxslt
		sh autogen.sh
		./configure
		make
		sudo make install
		cd ../htsjdk
		./gradlew
		cd ../jvarkit
		make biostar175929 standalone=yes
		cd ../kentUtils
		make
		cd
		mv kentUtils/ IMG_pipelines/
		mv htsjdk/ IMG_pipelines/
		mv libxslt/ IMG_pipelines/
		mv jvarkit/ IMG_pipelines/
		echo -e "Installation Complete. Please type: \n(1) for IMG_AP \n(2) for IMG_GAP \n(3) for IMG_GAP \n(4)for IMG_GAPv2 \n(6) to quit."
            ;;		
        "Quit")
            break
            ;;
        *) echo invalid option;;
    esac
done
