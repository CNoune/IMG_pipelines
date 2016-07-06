# v1.5

#Install Packages - Function found on (http://stackoverflow.com/questions/9341635/check-for-installed-packages-before-running-install-packages)
packages<-function(x){
  x<-as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x,repos="http://cran.r-project.org")
    require(x,character.only=TRUE)
  }
}
packages(mclust)
packages(ape)

#Determine Clusters
library(ape)
Alignment <- read.dna(file.choose(), format = "fasta") #importing alignment as fasta file
Alignment_distance <- dist.dna(Alignment) #creates distance matrix
standard_distance <- scale(Alignment_distance) #scales distance matrix columns
cluster_amounts <- (nrow(standard_distance)-1)*sum(apply(standard_distance,2,var)) #manually determine cluster amounts
for (i in 2:15) cluster_amounts[i] <- sum(kmeans(standard_distance, centers=i)$withinss) #cluster amounts up to 15 clusters - http://www.statmethods.net/advstats/cluster.html
plot(1:15, cluster_amounts, type="b", xlab="Number of Clusters", ylab="Within groups sum of squares") #plotting clusters - http://www.statmethods.net/advstats/cluster.html
#If error "more centres than distinct data points" is produced, 
#skip to validation step and use the cluster value mclust determines in the kmeans clustering step.

#validation
library(mclust)
validation <- Mclust(standard_distance)
summary(validation)
plot(validation) #Select the bayesian information criterion (BIC) result and export it.

#Kmeans clustering - iter.max is bootstrapping the results
fitted_model <- kmeans(standard_distance, "put the cluster number here from MCLUST/Manual calculation", iter.max = 100) #creating a fitted model
cluster_means <- aggregate(standard_distance,by=list(fitted_model$cluster),FUN=mean) #determines clustering means
final_results <- data.frame(standard_distance, fitted_model$cluster) #creates the final results with clusters

#If Mclust clusters and kmeans clusters results agree, accept the data. 
#If not, repeat kmeans clustering with more clusters.
#I.E. the fitted_model cluster selection and mclust cluster determination should be the same.
#Output the results as .csv.
write.csv(final_results, file = "Clusters.csv")
