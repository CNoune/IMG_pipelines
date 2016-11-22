#!/bin/bash
echo "Press [ENTER] to Select Working Directory"
read enter
wrk_dir="`zenity --file-selection --directory`"
IMG_GAP="$PWD/IMG_pipelines/IMG_GAP/IMG_GAP-build_13.sh"
(cd $wrk_dir && bash $IMG_GAP)

