#!/bin/bash

# mkdir daily
# mkdir Log

base="/home/mobaxterm/wmo/EC-76"

last=`cat last`
now=$(date "+%F-%HJST")
echo $now > last

cd ${base}/daily
sh checkupdate_daily.sh 2>&1 | tee log.temp

cd ${base}

mv ${base}/daily/log.temp ${base}/Log/log_$now--$last

find "${base}/daily/" -name Forms | xargs rm -rf

dir1="${base}/daily/meetings.wmo.int/EC-76/English/1. DRAFTS FOR DISCUSSION"
dir2="${base}/daily/meetings.wmo.int/EC-76/InformationDocuments"
dir3="${base}/daily/meetings.wmo.int/EC-76/Work in progress"
dir4="${base}/daily/meetings.wmo.int/EC-76/Presentations"
dir5="${base}/daily/meetings.wmo.int/EC-76/3. SESSION ARCHIVE"

bn1="1. DRAFTS FOR DISCUSSION"
bn2="InformationDocuments"
bn3="Work in progress"
bn4="Presentations"
bn5="3. SESSION ARCHIVE"

touch diff.temp

for  ((i=1; i<5; i++)); do
  var="dir$i"
  d=`echo "${!var}"`
  var="bn$i"
  bn=`echo "${!var}"`
  echo "---------------$bn---------------" >> diff.temp
  diff -qr "$d" "Onedrive/$bn" >> diff.temp
  
  cp -rp "$d" Onedrive  
  cp -rp "$d" Sharepoint


  echo ""
  echo ""
  
done

find "Sharepoint/InformationDocuments" -type f ! -name '*_en.*' -delete

# remove trash from log
sed -i '/aspx/d'              diff.temp
#sed -i "s/['].*$//"           log.temp
#sed -i 's|.*[`]|https\:\/\/|' log.temp

mv diff.temp ${base}/Log/diff_$now--$last.txt

cp ${base}/Log/diff_$now--$last.txt Onedrive

rm $base/Sharepoint/work/*.txt

cp ${base}/Log/diff_$now--$last.txt $base/Sharepoint/work/

cd $base
sh checkIfMarked.sh

