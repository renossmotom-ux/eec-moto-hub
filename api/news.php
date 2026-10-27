<?php
// Admin: add or delete a news item for a factory.
require __DIR__ . '/../lib/bootstrap.php';
require_admin();
$b = body();
if (($b['action'] ?? '') === 'delete') {
    db()->prepare('DELETE FROM news WHERE id = ?')->execute([(int)($b['id'] ?? 0)]);
    json_out(['ok' => true]);
}
$fid = (string)($b['fid'] ?? '');
$title = trim((string)($b['title'] ?? ''));
if (!valid_id($fid) || $title === '') json_out(['error' => 'Factory and title are required.'], 400);
db()->prepare('INSERT INTO news (fid, title, body, created_at) VALUES (?, ?, ?, ?)')
    ->execute([$fid, mb_substr($title, 0, 200), mb_substr(trim((string)($b['body'] ?? '')), 0, 4000), gmdate('c')]);
json_out(['ok' => true]);
