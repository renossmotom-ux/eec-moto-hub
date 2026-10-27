<?php
// Public: admin edits (merged into factories by the page) and news.
require __DIR__ . '/../lib/bootstrap.php';
$edits = [];
foreach (db()->query('SELECT fid, data FROM edits') as $r) {
    $edits[$r['fid']] = json_decode($r['data'], true) ?: [];
}
$news = db()->query('SELECT id, fid, title, body, created_at AS date FROM news ORDER BY created_at DESC')->fetchAll();
json_out(['edits' => (object)$edits, 'news' => $news, 'admin' => is_admin()]);
