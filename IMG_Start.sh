#!/bin/bash
# IMG_Start - version 1.0
# Copyright (c) 2016 Christopher Noune

echo "Welcome "$User" to IMG Pipelines. Please select a pipeline below to begin"
PS3='Please enter your choice: '
options=("IMG_AP" "IMG_GAP" "IMG_R (This Does Nothing Yet)" "Install Most Packages" "Quit")
select opt in "${options[@]}"
do
    case $opt in
        "IMG_AP")
            echo "You have selected IMG_AP"
		bash IMG_pipelines/IMG_AP/IMG_AP.sh
            ;;
        "IMG_GAP")
            echo "You have selected IMG_AP"
		bash IMG_pipelines/IMG_GAP/IMG_GAP.sh
            ;;
        "IMG_R")
            echo "You have selected IMG_R. This will invoke an R session but you will need to manually "
            ;;
	"Install Most Packages")
            echo "You have selected to install most of the required packages. This requires you to input your superuser password. You will need to download GATK seperately. Biostars175929 and bbmap will be found in the IMG_pipelines folder."
		sudo apt-get install bwa openjdk-8-jdk openjdk-8-jre samtools fastx-toolkit tophat libtool autoconf fastqc picard-tools git gradle libxml2 libxml2-dev
		wget 'https://sourceforge.net/projects/bbmap/files/latest/latest_bbmap.tar.gz'
		git clone git://git.gnome.org/libxslt
		git clone "https://github.com/samtools/htsjdk"
		git clone "https://github.com/lindenb/jvarkit.git"
		tar -xvcf latest_bbmap.tar.gz
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
		cp dist/biostar175929.jar ../IMG_pipelines*/
		echo "Installation Complete"
		cd
            ;;		
        "Quit")
            break
            ;;
        *) echo invalid option;;
    esac
done
