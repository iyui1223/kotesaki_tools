# 複数PDFから該当する文字列があるページ＋前１ページを切り抜き、統合する。
# 使うツールのインストール。あわせて数十MB
# apt-get install pdfgrep
# apt-get install poppler
# cd PDFが置かれている場所。PDF名が日本語を含む場合はrenameする必要がある。
# "〇 〇 〇 〇" ここは空白込みでpdfから直にコピーする。
pdfgrep --page-number "苗 字 名 前" *.pdf > grep.txt

mkdir -p work
cd work
number=100
while read p; do
  pdfname=`echo "$p" |  sed 's/:.*//'`
  echo $pdfname
  pagenumber=`echo "$p" | sed 's/^.*pdf://' | sed 's/:.*//'`
  echo $pagenumber

  # 所属部署の抽出のためにPDFの一部を切り出す。
  pgs=$((pagenumber - 1))
  pge=$((pagenumber))
  
  pdfseparate -f $pgs -l $pge ../$pdfname $(printf %03d $number)_%d_$pdfname
  number=$((number - 1))
  
done <../grep.txt

pdfunite 0*.pdf out.pdf





