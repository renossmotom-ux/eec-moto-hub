<?php
// Admin: save edits for one factory (contacts, rating, removed, note, 360 link).
require __DIR__ . '/../lib/bootstrap.php';
require_admin();
$b = body();
$fid = (string)($b['id'] ?? '');
if (!valid_id($fid)) json_out(['error' => 'Bad factory id.'], 400);
$allowed = ['removed', 'rating', 'note', 'emails', 'phone', 'whatsapp', 'wechat', 'tour'];
$patch = array_intersect_key((array)($b['patch'] ?? []), array_flip($allowed));
if (isset($patch['tour']) && $patch['tour'] !== '' && !preg_match('#^https://#', (string)$patch['tour'])) json_out(['error' => '360° link must start with https://'], 400);
if (isset($patch['rating'])) $patch['rating'] = max(0, min(5, (int)$patch['rating']));
if (isset($patch['emails'])) $patch['emails'] = array_values(array_filter((array)$patch['emails'], fn($e) => filter_var($e, FILTER_VALIDATE_EMAIL)));
$st = db()->prepare('SELECT data FROM edits WHERE fid = ?');
$st->execute([$fid]);
$cur = json_decode((string)($st->fetchColumn() ?: '{}'), true) ?: [];
$new = array_merge($cur, $patch);
$now = gmdate('c');
db()->prepare('DELETE FROM edits WHERE fid = ?')->execute([$fid]);
db()->prepare('INSERT INTO edits (fid, data, updated_at) VALUES (?, ?, ?)')->execute([$fid, json_encode($new, JSON_UNESCAPED_UNICODE), $now]);
json_out(['ok' => true, 'edit' => $new]);
