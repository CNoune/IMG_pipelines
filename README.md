# Intro
These pipelines were built to orginally analyse baculoviruses and are essentially wrappers for existing software but pre-optimised to help get rid of any guess work. The pipelines require various software to be pre-installed before running so make sure you read each individual readme (documentations folder). If you use the pipelines please don't forget to cite them and cite the software it uses.

# Author
Christopher Noune: https://www.researchgate.net/profile/Christopher_Noune

# In Development

I am slowly converting everything from Bash to Python 3 and attempting to introduce cross-platform compatibility.

The Assembly Pipeline will be shifted to legacy soon and ported to Python but I do not have an ETA.

# System Requirements - MetaGaAP and Assembly Pipeline

At least 8GB of RAM. 

At least a 4 core CPU. 

At least 20GB of storage for each analysis per dataset.

# MetaGaAP-Py - Please cite the original MetaGaAP publication (and cite this: Noune, C. and Hauxwell, C. 2017, Enhanced Pipeline 'MetaGaAP-Py' for the Analysis of Quasispecies and Non-Model Microbial Populations using Ultra-Deep 'Meta-barcode' Sequencing. bioRxiv.)
.

Build 3 is available for download and will be the last major revision to MetaGaAP. Please use MetaGaAP-Py from now on as this will be the supported version. The bash implementation has been shifted and renamed to MetaGaAP-Legacy and will no longer be maintained.

Build 3 features include:

1. Most bugs have been dealt with. Some may still exist. 
2. Multi-sample analysis
3. Multi-threading for the removal of duplicate sequences - this has bugs but it will default to a single-core if needed.

If any bugs or issues exist, please use the issue tracked so I can fix it.

Note: Pre-compiled Biostar175929 tool is now included within the additional scripts folder with permissions from the author Pierre Lindenbaum.

MetaGaAP-Py requires the following instructions below as it is different than the other pipelines: Note: This assumes you have pip3 and python 3.x installed. MetaGaAP-Py was coded in Python 3.6.1.

1. You need to have samtools (1.3 or above), bwa, picard-tools (2.9 or above) in your path. GATK (3.6 or above) and the Biostar175929 tool don't need to be in your path but you will be prompted to select GATK and prompted to select the IMG_pipelines directory so it can use the biostar175929 tool located in the additional scripts folder.

2. Use the following commands to install java and other dependencies:

sudo add-apt-repository ppa:webupd8team/java

sudo apt-get update

sudo apt-get install oracle-java8-installer bwa fastx-toolkit picard-tools samtools python3-pandas

pip3 install biopython

This will install the latest versions if you are using Ubuntu 17.04.

3. This has been coded in Python 3.6.1, therefore you need Python 3.x otherwise some of the code will not run.

4. To run complete the following (assuming you are in Ubuntu) - python3 IMG_pipelines/MetaGaAP-Py.py

5. You need to have the Biopython, Pandas and Tkinter python 3 packages installed to run MetaGaAP-Py

6. I am working on documentation that will be released soon.


# Installation - Additional Scripts 

You need Python 3.x to run these scripts.

*Ubuntu: Example to run - python3 FastqConv.py

sudo apt-get install python3-tk python3-biopython

*Windows: Example to run - python FastqConv.py

Note: Tested using Spyder and Anaconda

You can either install using the Anaconda Environment or:

pip3 install biopython (Ubuntu) or pip install biopython (Windows)

tkinter should be installed already on windows.

# Citing the Invertebrates & Microbiology Groups Pipelines & Additional Scripts

Noune, C. The Invertebrates & Microbiology Group Pipelines, GitHub, Queensland University of Technology: https://github.com/CNoune/IMG_pipelines, 2016.

Below you will find the individual citations for each pipeline

# Citing MetaGaAP

Noune, C.; Hauxwell, C. MetaGaAP: A Novel Pipeline to Estimate Community Composition and Abundance from Non-Model Sequence Data. Biology 2017, 6, 14

# Citing the Invertebrates & Microbiology Group Assembly Pipeline

Noune, C. and C. Hauxwell (2016). "Complete Genome Sequences of Seven Helicoverpa armigera SNPV-AC53-Derived Strains." Genome announcements 4(3).

Noune, C.; Hauxwell, C. Comparative Analysis of HaSNPV-AC53 and Derived Strains. Viruses 2016, 8, 280.
