# Intro
These pipelines were built to orginally analyse baculoviruses and are essentially wrappers for existing software but pre-optomised to help get rid of any guess work. The pipelines require various software to be pre-installed before running so make sure you read each individual readme (documentations folder). If you use the pipelines please don't forget to cite them and cite the software it uses.

# Author
Christopher Noune: https://www.researchgate.net/profile/Christopher_Noune

# In Development

(Delayed: ETA Unknown) - MetaGaAP 2: Currently in closed-alpha, End-of-year release. Complete re-write in Python 3 with emphasis on accuracy and computational efficiency.

MetaGaAP-Py: Highly optimised re-write of MetaGaAP in Python3. ETA - 2 months.

I am slowly converting everything from Bash to Python3 and attempting to introduce cross-platform compatibility.

# System Requirements - MetaGaAP and Assembly Pipeline

At least 8GB of RAM. 

At least a 4 core CPU. 

At least 20GB of storage for each analysis per dataset.

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

sudo apt-get install python3-tk python-biopython

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
