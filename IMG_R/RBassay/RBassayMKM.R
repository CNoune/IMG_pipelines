# IMG_RBassayMKM - version 1.0
# Date: 01/09/2017
# Authors: Christopher Noune & James McGree
# Estimation of ST50 of using multiple samples using Kaplan Meier calculations
# Data must be formated as per a standard Kaplan Meier spreadsheet with the following columns: time, deaths, factor (note: the factor column needs to be changed to whatever your factor is i.e. genotype, strain, etc) 

#Install Packages - Function found on (http://stackoverflow.com/questions/9341635/check-for-installed-packages-before-running-install-packages)
packages_check<-function(x){
  x<-as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x)
    require(x,character.only=TRUE)
  }
}

packages_check(survival)
packages_check(ggplot2)
packages_check(survminer)

data <- read.csv(file.choose()) # select your csv file

data$SurvObj<-with(data, Surv(time, deaths==1)) #creates a survival object column
km<- survfit(SurvObj ~ strain, data = data) # change strain to your factor i.e. genotype, strain, etc
capture.output(km, file = "ST50.txt")
capture.output(summary(km), file="ST50_model_summary.txt")
ggsurvplot(km, data = data, conf.int=TRUE, pval=FALSE, legend.labs=c(""), legend.title="", xlab = "Time (Hours)") #add labels to the legend.labs and the legend title.
ggsave("KM_plot.tiff", width = 10, height = 5)