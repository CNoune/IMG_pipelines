Description:
These are a set of commonly used R scripts within the IMG that help to automate and simplify a lot of the work we do.

Installation:
Simply run in RStudio (or any IDE/terminal prompt) as you normally would.

Scripts:
RClust_Dist - K-means clustering using the APE, MCLUST and kmeans packages - use for nucleotide alignment clustering
RClust_SNPs - K-means clustering using MCLUST and kmeans packages - use for SNP abundance clustering. 
  1. Data should be formatted as tab-delimeted table.
  2. Data should be produced from the GATK VariantsToTable tool.
  3. Abundance should be precalculated prior to running this script.
RBassay - Median lethal dose and median survival time statistical analysis using MASS

Citations:
Noune, C. The Invertebrates & Microbiology Group Pipelines, GitHub, Queensland University of Technology: https://github.com/CNoune/IMG_pipelines, 2016.
