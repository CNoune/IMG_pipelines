# DISCLAIMER
Firstly, this has only been tested and used in Ubuntu. I am not responsible for any issues or customisations that you implement or 
that may happen when the pipeline is used. 

Don't forget to cite the pipeline and all of the software used.

# Pre-Requisites
Make sure you have enough RAM otherwise it will fail at the de novo assembly step!

The pipeline requires the following software pre-installed and in your PATH:
1. BWA
2. SAMtools
3. BEDtools
4. VCFtools
5. BCFtools
6. bam2fastx as part of the TopHat package

The pipeline requires the following software installed/downloaded:
Note: Make sure the software below are NOT in your PATH. You will specify where the software is located and the pipeline will do the rest.
1. Genome Analysis Toolkit
2. Kmergenie
3. Tadpole as part of the BBmap package

Furthermore, the final step in this pipeline is to take your merged data-set and complete the mapping and concensus generation in Geneious. If you do not have Geneious, you can use something equivalent. Eventually I will code extra steps into the pipeline for users who do not have Geneious.

# Installation and Running

No installation needed. 

To run the pipeline simple type the following:
bash IMG_Assembly.sh

If you try to invoke the pipeline with sh IMG_Assembly.sh it will not work because the jumpto function will fail.
