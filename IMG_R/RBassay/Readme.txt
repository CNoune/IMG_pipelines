Scripts were made using Microsoft R Open 3.3.1 and 3.4.0. 

RBassayV2 instructions

1.Input your data into the Bioassay scoresheet - Raw data scoresheet
2. Export the dose, corrected_mortality, corrected_alive, log.dose and log.dose.2 columns into a new .csv file
3. Run IMG_RBassayV2 in R Studio. Note: You will need to make changes within the script - see comments
4. Results will be automatically exported into your working directory. Note: If log.dose.2 is used during the modelling, the LC50 output will not have standard errors associated. I am working on this and will eventually sort it out when I am not so busy.

RBassaySKM - Single Kaplan Meier and RBassayMKM - Multiple Kaplan Meier instructions

1. Use SKM if you are calculating ST50 from a single sample. The input requires cumulative mortality.
2. Use MKM if you are calculating ST50 using multiple samples and wish to compare the survival times. The csv input for this requires it to be formated as per a standard Kaplan Meier spreadsheet - three columns: deaths, time, factor. The factor is the strain, or genotype, or antibiotic, etc, etc for each sample to be analysed.
3. Run IMG_RBassaySKM or MKM in R Studio. Note: You will need to make changes within the script - see comments

RBassayV1 instructions - Use V2 instead as it accounts for poor fitting models, but you can still use V1 if it doesnt bother you and if you want to calculate ST50 using cumulative counts but I recommend using the SKM and MKM scripts instead.

1. Input your data into the Bioassay scoresheet - Raw data scoresheet. Note: If your data is ST50 related change the columns to reflect time not dose
2. Export the dose (or time), corrected_mortality and corrected_alive columns into a new .csv file
3. Run IMG_RBassayV1 in R Studio. Note: You will need to make changes within the script - see comments
