# IMG_RBassay - version 2.0
# Date: 08/08/2017
# Authors: Christopher Noune & James McGree
# New LC50 calculations

antilog<-function(lx,base) #function taken from http://r.789695.n4.nabble.com/Searching-for-antilog-function-td4721348.html
{ 
  lbx<-lx/log(exp(1),base=base) 
  result<-exp(lbx) 
  result 
}
#Install Packages - Function found on (http://stackoverflow.com/questions/9341635/check-for-installed-packages-before-running-install-packages)
packages_check<-function(x){
  x<-as.character(match.call()[[2]])
  if (!require(x,character.only=TRUE)){
    install.packages(pkgs=x)
    require(x,character.only=TRUE)
  }
}
packages_check(MASS)
Ba_Stats <- read.csv(file.choose())
attach(Ba_Stats)
Ba_Stats.y <- cbind(corrected_mortality, corrected_alive)
Ba_Stats.dose.2.model <- glm(Ba_Stats.y~log_dose + log_dose.2, family = quasibinomial(logit))
Ba_Stats.dose.model <- glm(Ba_Stats.y~log_dose, family = quasibinomial(logit))
Ba_Stats.dose.2.p <- coef(Ba_Stats.dose.2.model)[3]
#Depending on which model has a better p value, will determine
if (Ba_Stats.dose.2.p > 0.05){
  Result <- dose.p(Ba_Stats.dose.model, p = 0.5)
  antilog(Result, 10)
  capture.output(antilog(Result, 10), file="Dose.LC50_Result.txt")
  capture.output(summary(Ba_Stats.dose.model), file="dose.model_output.txt")
} else {
  sim.dose <- seq(100,155000,by=10) #assuming the dose range is between 100 OB/ml to 155000 OB/mL - adjust accordingly
  sim.log.dose <- log10(sim.dose)
  sim.log.dose.2 <- sim.log.dose^2
  lp <- predict(Ba_Stats.dose.2.model,newdata=data.frame(log_dose=sim.log.dose,log_dose.2=sim.log.dose.2))
  p<-exp(lp)/(1+exp(lp))
  LC50<-which.min((p-0.5)^2)
  sim.dose[LC50]
  capture.output(sim.dose[LC50], file="Dose.2.LC50_Result.txt")
  capture.output(summary(Ba_Stats.dose.2.model), file="dose.2.model_output.txt")
}