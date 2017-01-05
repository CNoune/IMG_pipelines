#Subset_stats
args <- commandArgs()
working_dir <- args[6]
setwd(file.path(working_dir))
temp = list.files(pattern="*.csv")
myfiles = lapply(temp, read.delim)
write.csv(myfiles, file = "raw_merged_stats.csv", row.names = FALSE)
subset <- data.frame(myfiles)
subset <- subset.data.frame(subset, Mapped_Reads >= 1)
write.csv(subset, file = "Subset_Stats.csv", row.names = FALSE)
