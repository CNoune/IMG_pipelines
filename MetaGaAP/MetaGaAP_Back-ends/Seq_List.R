#Sequence_List & 1x Subset
args <- commandArgs()
working_dir <- args[6]
setwd(file.path(working_dir))
data <- read.csv(args[7], head=TRUE,sep="\t")
data <- data[!grepl("Mapped_Reads", data$Mapped_Reads),]
data <- data[!grepl("Unmapped_Reads", data$Unmapped_Reads),]
data <- data[!grepl("Sequence_Length", data$Sequence_Length),]
data <- data[!grepl("Sequence", data$Sequence),]
data$Mapped_Reads <- as.numeric(as.character(data$Mapped_Reads))
subset <- subset.data.frame(data, Mapped_Reads >= 1)
subset_list <- subset$Sequence_Length <- subset$Unmapped_Reads <- NULL
write.csv(subset, file = "Subset_stats.csv", row.names = FALSE)
subset_list <- subset$Mapped_Reads<- NULL
write.csv(subset, file = "Sequence_names.txt", row.names = FALSE, quote = FALSE)
