<?php
$d=__DIR__;$t="$d/_s.zip";
copy('https://github.com/renossmotom-ux/eec-moto-hub/archive/refs/heads/main.zip',$t) or die('download failed');
$z=new ZipArchive;$z->open($t)===true or die('zip failed');$n=0;
for($i=0;$i<$z->numFiles;$i++){$f=$z->getNameIndex($i);$r=preg_replace('#^[^/]+/#','',$f);
if($r===''||substr($f,-1)==='/'||strpos($r,'..')!==false||preg_match('#^(tools|\.github)/#',$r))continue;
@mkdir(dirname("$d/$r"),0755,true);file_put_contents("$d/$r",$z->getFromIndex($i));$n++;}
$z->close();unlink($t);unlink(__FILE__);echo "Installed $n files. <a href='./'>Open site</a>";
