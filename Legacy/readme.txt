MetaGaAP Legacy is located here and is no longer supported. However, if you wish to run please install the following:

sudo add-apt-repository ppa:webupd8team/java
sudo apt-get update
sudo apt-get install oracle-java8-installer bwa fastx-toolkit picard-tools samtools

You also need to download bbmap (https://sourceforge.net/projects/bbmap/) and kentUtils (https://github.com/ENCODE-DCC/kentUtils) 
and put them into the IMG_pipelines directory.

To then execute MetaGaAP-Legacy you need to do the following:

bash IMG_pipelines/Legacy/MetaGaAP_Back-ends/Set_wrk_dir.sh

or

bash Legacy/MetaGaAP_Back-ends/Set_wrk_dir.sh

This depends on the directory you are in.
