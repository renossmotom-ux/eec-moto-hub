<?php
// Updates the site to the latest main branch on GitHub (same steps as install.php, but stays in place).
// Safe to leave public: it can only install the official public repository, at most once a minute.
// config.php is never in the download, so settings and passwords are kept.
declare(strict_types=1);
header('Content-Type: text/plain; charset=utf-8');
$root = dirname(__DIR__);
$lock = "$root/.update-lock";
if (is_file($lock) && time() - filemtime($lock) < 60) { http_response_code(429); exit("Updated less than a minute ago.\n"); }
touch($lock);
$tmp = "$root/_update.zip";
if (!@copy('https://github.com/renossmotom-ux/eec-moto-hub/archive/refs/heads/main.zip', $tmp)) { http_response_code(502); exit("Download failed.\n"); }
$z = new ZipArchive;
if ($z->open($tmp) !== true) { @unlink($tmp); http_response_code(502); exit("Zip failed.\n"); }
$n = 0;
for ($i = 0; $i < $z->numFiles; $i++) {
    $f = $z->getNameIndex($i);
    $r = preg_replace('#^[^/]+/#', '', $f);
    if ($r === '' || substr($f, -1) === '/' || strpos($r, '..') !== false || preg_match('#^(tools|\.github)/#', $r) || $r === 'config.php') continue;
    @mkdir(dirname("$root/$r"), 0755, true);
    file_put_contents("$root/$r", $z->getFromIndex($i));
    $n++;
}
$z->close();
@unlink($tmp);
echo "Updated $n files from GitHub main.\n";
