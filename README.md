# Invertebrates & Microbiology Group
Bash and R pipelines from the Invertebrates & Microbiology Group at the Queensland University of Technology to help make data analysis easy.

# In Development

MetaGaAP 2: Currently in closed-alpha, End-of-year release. Complete re-write in Python 3 with emphasis on accuracy and computational efficiency. 

# Intro
These pipelines were built to orginally analyse baculoviruses and are essentially wrappers for existing software but pre-optomised to help get rid of any guess work. The pipelines require various software to be pre-installed before running so make sure you read each individual readme (documentations folder). If you use the pipelines please don't forget to cite them and cite the software it uses.
Thanks!
# Author
Christopher Noune

https://www.researchgate.net/profile/Christopher_Noune

# Citing the Invertebrates & Microbiology Groups Pipelines

Noune, C. The Invertebrates & Microbiology Group Pipelines, GitHub, Queensland University of Technology: https://github.com/CNoune/IMG_pipelines, 2016.

Below you will find the individual citations for each pipeline

# Citing MetaGaAP

Noune, C.; Hauxwell, C. MetaGaAP: A Novel Pipeline to Estimate Community Composition and Abundance from Non-Model Sequence Data. Biology 2017, 6, 14

# Citing the Invertebrates & Microbiology Group Assembly Pipeline

Noune, C. and C. Hauxwell (2016). "Complete Genome Sequences of Seven Helicoverpa armigera SNPV-AC53-Derived Strains." Genome announcements 4(3).

Noune, C.; Hauxwell, C. Comparative Analysis of HaSNPV-AC53 and Derived Strains. Viruses 2016, 8, 280.

# System Requirements - MetaGaAP and Assembly Pipeline

At least 8GB of RAM. 

At least a 4 core CPU. 

At least 20GB of storage for each analysis per dataset.

# Installation
You need to have Java 1.8 as your default otherwise the required packages will not compile. Start.sh will automatically download and install 1.8 but it will not make it the default java unless you have no other versions installed.

You will have to provide a password when prompted to install the dependencies. Note: Dependencies are for all pipelines to run.

Run as follows:
bash IMG_pipelines/Start.sh

Select option 3 to install most packages

Select the pipeline you wish to use

You must always run Start.sh first to launch each pipeline otherwise the backends and working directories wont be set. 

# Software Citations
The pipelines uses the following software:
  
  Gordon A, Hannon G. 2010. Fastx-toolkit. FASTQ/A short-reads preprocessing tools (unpublished) http://hannonlab cshl edu/fastx_toolkit.
  
  Li H. 2013. Aligning sequence reads, clone sequences and assembly contigs with BWA-MEM. arXiv preprint arXiv:13033997.
  
  Li H, Handsaker B, Wysoker A, Fennell T, Ruan J, Homer N, Marth G, Abecasis G, Durbin R. 2009. The Sequence Alignment/Map format and SAMtools. Bioinformatics 25:2078-2079.
  
  Quinlan AR, Hall IM. 2010. BEDTools: a flexible suite of utilities for comparing genomic features. Bioinformatics 26:841-842.
  
  DePristo MA, Banks E, Poplin R, Garimella KV, Maguire JR, Hartl C, Philippakis AA, del Angel G, Rivas MA, Hanna M, McKenna A, Fennell TJ, Kernytsky AM, Sivachenko AY, Cibulskis K, Gabriel SB, Altshuler D, Daly MJ. 2011. A framework for variation discovery and genotyping using next-generation DNA sequencing data. Nat Genet 43:491-498.
  
  McKenna A, Hanna M, Banks E, Sivachenko A, Cibulskis K, Kernytsky A, Garimella K, Altshuler D, Gabriel S, Daly M, DePristo MA. 2010. The Genome Analysis Toolkit: a MapReduce framework for analyzing next-generation DNA sequencing data. Genome Res 20:1297-1303.
  
  Van der Auwera GA, Carneiro MO, Hartl C, Poplin R, del Angel G, Levy-Moonshine A, Jordan T, Shakir K, Roazen D, Thibault J, Banks E, Garimella KV, Altshuler D, Gabriel S, DePristo MA. 2002. From FastQ Data to High-Confidence Variant Calls: The Genome Analysis Toolkit Best Practices Pipeline, Current Protocols in Bioinformatics doi:10.1002/0471250953.bi1110s43. John Wiley & Sons, Inc.
  
  Kim D, Pertea G, Trapnell C, Pimentel H, Kelley R, Salzberg S. 2013. TopHat2: accurate alignment of transcriptomes in the presence of insertions, deletions and gene fusions. Genome Biology 14:R36.
  
  Chikhi R, Medvedev P. 2014. Informed and automated k-mer size selection for genome assembly. Bioinformatics 30:31-37.
  
  Bushnell B. BBMap short read aligner. URL http://sourceforge net/projects/bbmap.
  
  Kearse M, Moir R, Wilson A, Stones-Havas S, Cheung M, Sturrock S, Buxton S, Cooper A, Markowitz S, Duran C. 2012. Geneious Basic: an integrated and extendable desktop software platform for the organization and analysis of sequence data. Bioinformatics 28:1647-1649.
  
  Pierre L. JVarkit: java-based utilities for Bioinformatics.
  
  Milne I, Stephen G, Bayer M, Cock PJA, Pritchard L, Cardle L, et al. Using Tablet for visual exploration of second-generation sequencing data. Briefings in Bioinformatics. 2013;14(2):193-202. doi: 10.1093/bib/bbs012.
  
  Milne I, Bayer M, Cardle L, Shaw P, Stephen G, Wright F, et al. Tablet—next generation sequence assembly visualization. Bioinformatics (Oxford, England). 2010;26(3):401-2. doi: 10.1093/bioinformatics/btp666. PubMed PMID: PMC2815658.
  
  Paradis E, Claude J, Strimmer K. APE: Analyses of Phylogenetics and Evolution in R language. Bioinformatics (Oxford, England). 2004;20(2):289-90. doi: 10.1093/bioinformatics/btg412.
  
  Team RC. R: A language and environment for statistical computing. 2013.
  
  MacQueen J, editor Some methods for classification and analysis of multivariate observations. Proceedings of the fifth Berkeley symposium on mathematical statistics and probability; 1967: Oakland, CA, USA.
  
  Lloyd S. Least squares quantization in PCM. IEEE transactions on information theory. 1982;28(2):129-37.
  
  Hartigan JA, Wong MA. Algorithm AS 136: A k-means clustering algorithm. Journal of the Royal Statistical Society Series C (Applied Statistics). 1979;28(1):100-8.
  
  Forgy EW. Cluster analysis of multivariate data: efficiency versus interpretability of classifications. Biometrics. 1965;21:768-9.
  
  Fraley C, Raftery AE. MCLUST: Software for model-based cluster analysis. Journal of Classification. 1999;16(2):297-306.
  
  Fraley C, Raftery AE. MCLUST version 3: an R package for normal mixture modeling and model-based clustering. DTIC Document, 2006.



