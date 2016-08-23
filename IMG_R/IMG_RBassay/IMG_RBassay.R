# IMG_RBassay- version 1.0
# Copyright (c) 2016 Christopher Noune

#Install Packages - Function found on (http://stackoverflow.com/questions/9341635/check-for-installed-packages-before-running-install-packages)
packages_check<-function(x){
  x<-as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x,repos="http://cran.r-project.org")
    require(x,character.only=TRUE)
  }
}
#Required packages for the analysis to run.
packages_check(MASS) 
packages_check(tcltk)
packages_check(tcltk2)

#Input Bioassay type function
ask_data <- function(){
  require(tcltk2)
  tt <- tktoplevel()
  ask <- tclVar(0)
  
  asK_frame <- tkframe(tt)
  tkpack(asK_frame, side='top')
  tkpack(tklabel(asK_frame, text='Is this ST50 or LC50 data?'), side='left')
  tkpack(tkentry(asK_frame, textvariable=ask), side='left')
  
  tkpack(tkbutton(tt, text='continue', command=function() tkdestroy(tt)),
         side='right', anchor='s')
  
  tkwait.window(tt)
  return( c(ask=as.character(tclvalue(ask))))
}

#Bioassay type
Ba <- ask_data()

#Loading the bioassay data
Ba_Stats <- read.csv(file.choose())
attach(Ba_Stats)
#Your data must be formatted with these column names. Your first column should be either time or dose.
Ba_Stats.y <- cbind(corrected_mortality, corrected_alive)
#Calculates results based on ST50 or LC50
if (Ba == "ST50"){
   Ba_Stats.model = glm(Ba_Stats.y~log(time), family = binomial(logit))
} else {
  Ba_Stats.model = glm(Ba_Stats.y~log(dose), family = binomial(logit))
}

#Results as a log
Result <- dose.p(Ba_Stats.model, p = 0.5)
#Transforms into a normal number. Note: The Dose column in the result is the final result regardless of ST50 or LC50.
transformed_result <- exp(Result)