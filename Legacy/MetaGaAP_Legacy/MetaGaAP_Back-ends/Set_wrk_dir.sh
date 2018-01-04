#!/bin/bash
echo "Press [ENTER] to Select Working Directory"
read enter
wrk_dir="`zenity --file-selection --directory`"
MetaGaAP="$PWD/IMG_pipelines/Legacy/MetaGaAP_Legacy/MetaGaAP-Legacy.sh"
(cd $wrk_dir && bash $MetaGaAP)
