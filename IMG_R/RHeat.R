# RHeat- version 1.0
# Copyright (c) 2016 Christopher Noune

#Install and check Packages Function found on (http://stackoverflow.com/questions/9341635/check-for-installed-packages-before-running-install-packages)
packages_check<-function(x){
  x<-as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x,repos="http://cran.r-project.org")
    require(x,character.only=TRUE)
  }
}
packages_check(vegan)
packages_check(pheatmap)
packages_check(grid)
#Prepare dataset
Genotype_Abundance <- read.csv(file.choose())
#Create row names and covert to matrix
rnames <- Genotype_Abundance$Genotypes
Genotype_Matrix <- data.matrix(Genotype_Abundance[,2:ncol(Genotype_Abundance)])
rownames(Genotype_Matrix) <- rnames
#Transform data to proportions
Genotype_proportions <- (Genotype_Matrix/rowSums(Genotype_Matrix)*100) # converts to a whole-percentage
#Heatmapping
Genotype_distance <- vegdist(Genotype_proportions, method = "bray")
Genotype_Clusters <- hclust(Genotype_distance, "aver")
Genotype_Samples <- vegdist(t(Genotype_proportions), method = "bray")
Genotype_Clusters.2 <- hclust(Genotype_Samples, "aver")
#Annotating the heatmap
setHook("grid.newpage", function() pushViewport(viewport(x=1,y=1,width=0.9, height=0.9, name="vp", just=c("right","top"))), action="prepend")
pheatmap(Genotype_proportions, cluster_rows = Genotype_Clusters, cluster_cols = Genotype_Clusters.2)
setHook("grid.newpage", NULL, "replace")
grid.text("Sample", y=-0.07, gp=gpar(fontsize=16))
grid.text("Genotype", x=-0.07, rot=90, gp=gpar(fontsize=16))
