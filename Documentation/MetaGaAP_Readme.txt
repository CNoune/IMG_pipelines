# DISCLAIMER
Firstly, this has only been tested and used in Ubuntu. I am not responsible for any issues or customisations that you implement or that may happen when the pipeline is used. 

Don't forget to cite the pipeline and all of the software used.

# Pre-Requisites
Make sure you have enough storage for the database construction and final abundance mapping steps!

The pipeline requires the following software pre-installed and in your PATH:
1. BWA
2. SAMtools
3. BEDtools
4. VCFtools
5. BCFtools

The pipeline requires the following software installed/downloaded:
Note: Make sure the software below are NOT in your PATH. You will specify where the software is located and the pipeline will do the rest.
1. Genome Analysis Toolkit

# Installation and Running

DO NOT INVOKE SUDO! SUDO will automatically be invoked when you begin installation and you will be required to input a password. This will be the one and only time you need to provide a password.

I do not have a work around at the moment for the installation but I am working on it.

bash Start.sh 
Select option 3 to install most packages - this will install packages required for all Invertebrate Microbiology Group pipelines.
Once everything is installed, select MetaGaAP to start the analysis.

MetaGaAP will require you to set a working directory and you will need to respecify the IMG_pipelines directory.

If you have installed everything correctly as per the Start.sh installation option everything should work.

# Issues
Please us the github issue tracker to report issues and I will work on it. Please also provide the log in the logs directory to see the options used.
