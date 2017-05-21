#!/bin/bash
echo "Press [ENTER] to Select Working Directory"
read enter
wrk_dir="`zenity --file-selection --directory`"
MetaGaAP="$PWD/IMG_pipelines/MetaGaAP/MetaGaAP.sh"
(cd $wrk_dir && bash $MetaGaAP)
