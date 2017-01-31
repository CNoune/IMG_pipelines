# IMG_RClust- version 2.0
# Copyright (c) 2016 Christopher Noune

#Install and check Packages Function found on (http://stackoverflow.com/questions/9341635/check-for-installed-packages-before-running-install-packages)
packages_check<-function(x){
  x<-as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x,repos="http://cran.r-project.org")
    require(x,character.only=TRUE)
  }
}
#Input K Value function
ask_K <- function(){
  require(tcltk2)
  tt <- tktoplevel()
  k <- tclVar(0)
  
  K_frame <- tkframe(tt)
  tkpack(K_frame, side='top')
  tkpack(tklabel(K_frame, text='Please Specify the K value: '), side='left')
  tkpack(tkentry(K_frame, textvariable=k), side='left')
  
  tkpack(tkbutton(tt, text='continue', command=function() tkdestroy(tt)),
         side='right', anchor='s')
  
  tkwait.window(tt)
  return( c(k=as.numeric(tclvalue(k))))
}

#Ask for file name function
ask_fileOUT <- function(){
  require(tcltk2)
  tt <- tktoplevel()
  file_name <- tclVar(0)
  
  File_frame <- tkframe(tt)
  tkpack(File_frame, side='top')
  tkpack(tklabel(File_frame, text='Please Input Filename followed by .csv: '), side='left')
  tkpack(tkentry(File_frame, textvariable=file_name), side='left')
  
  tkpack(tkbutton(tt, text='continue', command=function() tkdestroy(tt)),
         side='right', anchor='s')
  
  tkwait.window(tt)
  return( c(file_name=as.character(tclvalue(file_name))))
}

#Check packages
packages_check(mclust)
packages_check(ape)
packages_check(tcltk)
packages_check(tcltk2)

#validation with MCLUST
library(mclust)
standard_distance <- read.csv(file.choose(), header = TRUE, sep = "")
standard_distance$REF <- NULL
standard_distance$ALT <- NULL
standard_distance$ALT2 <- NULL
standard_distance$Ref.Depth <- NULL
standard_distance$Alt.Depth <- NULL
standard_distance$Alt2.Depth <- NULL
validation <- Mclust(standard_distance)
summary(validation)
# Input MClust Component Value
k <- ask_K()

#Kmeans clustering - iter.max is bootstrapping the results
fitted_model <- kmeans(standard_distance, k, iter.max = 100) #creating a fitted model
cluster_means <- aggregate(standard_distance,by=list(fitted_model$cluster),FUN=mean) #determines clustering means
final_results <- data.frame(standard_distance, fitted_model$cluster) #creates the final results with clusters
#If Mclust clusters and kmeans clusters results agree, accept the data. 
#If not, repeat kmeans clustering with more clusters.
#I.E. the fitted_model cluster selection and mclust cluster determination should be the same.

#Export final results and ask for file name
file_name <- ask_fileOUT()
write.csv(final_results, file = file_name, row.names = FALSE)

#Plots bayesian information criterion (BIC) result. Export it.
plot(validation$BIC)
