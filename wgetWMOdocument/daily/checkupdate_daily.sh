#!/bin/bash

options='--recursive --no-parent --timestamping'
#out_options="-q --show-progress"
wget $options https://meetings.wmo.int/EC-76/English/ $out_options
# since InformationDocuments has been relocated
wget $options https://meetings.wmo.int/EC-76/InformationDocuments/ $out_options
wget $options https://meetings.wmo.int/EC-76/Work%20in%20progress/Forms $out_options
wget $options https://meetings.wmo.int/EC-76/SitePages/Presentations.aspx $out_options

exit 0