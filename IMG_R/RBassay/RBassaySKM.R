# IMG_RBassaySKM - version 1.0
# Date: 01/09/2017
# Authors: Christopher Noune & James McGree
# Estimation of ST50 of a single sample with cumulative counts using Kaplan Meier calculations

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
packages_check(ggfortify)

data <- read.csv(file.choose())
t <- data$time
y <- data$corrected_mortality

t0 <- c(0,t)
y0 <- c(0,y)
t.new <- as.numeric()
y.new <- as.numeric()
n.new <- sum(y.new)
for(i in 2:length(y0)){
  t.new[i-1] <- t0[i] - t0[i-1]
  y.new[i-1] <- y0[i] - y0[i-1]
  n.new <- c(n.new,n.new[i-1]-y0[i]+y0[i-1])
}

t.km <- t0[1:length(t)]+t.new/2 # Death times are centered at the middle of the time interval
ind <- which(y.new!=0)
t.ind <- t[ind]
y.ind <- y.new[ind]

death_times <- rep(t.km[ind],y.ind)
cen <- rep(1,length(death_times))

fit <- survfit(Surv(death_times, cen) ~ 1) # Estimate of ST50
capture.output(fit, file="ST50.txt") # Saves the ST50 result
capture.output(summary(fit), file="ST50_model_Summary.txt") # Saves the ST50 model summary
autoplot(fit, surv.colour = 'blue', censor.colour = 'red') + xlab("Time (Hours)") + ylab("Mortality (%)") # Plot of survival curve