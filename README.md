# Intro
These pipelines were built to orginally analyse baculoviruses and are essentially wrappers for existing software but pre-optomised to help get rid of any guess work. The pipelines require various software to be pre-installed before running so make sure you read each individual readme (documentations folder). If you use the pipelines please don't forget to cite them and cite the software it uses.

# Author
Christopher Noune: https://www.researchgate.net/profile/Christopher_Noune

# In Development

MetaGaAP-Py: Build 1 is available. Documentation to follow.

I am slowly converting everything from Bash to Python 3 and attempting to introduce cross-platform compatibility.

# System Requirements - MetaGaAP and Assembly Pipeline

At least 8GB of RAM. 

At least a 4 core CPU. 

At least 20GB of storage for each analysis per dataset.

# MetaGaAP-Py - Please cite the original MetaGaAP publication if you use the python or bash implementations.

Build 1 is available for download. I would advise against using it at the moment as it is an alpha and I am still working on bugs and feature implementations. I recommend continuing to use the Bash implementation if you are working with critical data and can't risk major bugs.

However, if you wish to run MetaGaAP-Py please follow the instructions below as it is different than the other pipelines:

1. You need to have samtools (1.3 or above), bwa, picard-tools (2.9 or above) in your path. GATK (3.6 or above) and the Biostar175929 tool don't need to be in your path but you will be prompted to select GATK and prompted to select the IMG_pipelines directory as you should have the Biostar175929 tool in the following location - IMG_pipelines/jvarkit/dist/biostar175929.jar

2. This has been coded in Python 3, therefore you need Python 3 otherwise some of the code will not run.

3. To execute complete the following (assuming you are in Ubuntu) - python3 IMG_pipelines/MetaGaAP-Py.py

4. You need to have the Biopython, Pandas and Tkinter python 3 packages installed to run MetaGaAP-Py

5. I am working on documentation that will be released soon.

# Installation - MetaGaAP and Assembly Pipeline
You need to have Java 1.8 as your default otherwise the required packages will not compile. Start.sh will automatically download and install 1.8 but it will not make it the default java unless you have no other versions installed.

You will have to provide a password when prompted to install the dependencies. Note: Dependencies are for all pipelines to run.

Run as follows:
bash IMG_pipelines/Start.sh

Select option 3 to install most packages

Select the pipeline you wish to use

You must always run Start.sh first to launch each pipeline otherwise the backends and working directories wont be set.

# Installation - Additional Scripts 

You need python3 to run these scripts.

*Ubuntu: Example to run - python3 FastqConv.py

sudo apt-get install python3-tk python3-biopython

*Windows: Example to run - python FastqConv.py

Note: Tested using Spyder and Anaconda

You can either install using the Anaconda Environment or:

pip install biopython

tkinter should be installed already on windows.

# Citing the Invertebrates & Microbiology Groups Pipelines & Additional Scripts

Noune, C. The Invertebrates & Microbiology Group Pipelines, GitHub, Queensland University of Technology: https://github.com/CNoune/IMG_pipelines, 2016.

Below you will find the individual citations for each pipeline

# Citing MetaGaAP

Noune, C.; Hauxwell, C. MetaGaAP: A Novel Pipeline to Estimate Community Composition and Abundance from Non-Model Sequence Data. Biology 2017, 6, 14

# Citing the Invertebrates & Microbiology Group Assembly Pipeline

Noune, C. and C. Hauxwell (2016). "Complete Genome Sequences of Seven Helicoverpa armigera SNPV-AC53-Derived Strains." Genome announcements 4(3).

Noune, C.; Hauxwell, C. Comparative Analysis of HaSNPV-AC53 and Derived Strains. Viruses 2016, 8, 280.
