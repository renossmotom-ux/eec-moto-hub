<?php
// Public: a buyer asks to become an agent or to visit a factory.
// The request goes by email to the factory's addresses and to the hub mailbox.
require __DIR__ . '/../lib/bootstrap.php';
require __DIR__ . '/../lib/smtp.php';
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || ($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') !== 'eec') json_out(['error' => 'Bad request.'], 400);
$c = config();
if (($c['smtp_pass'] ?? '') === '' || str_starts_with((string)$c['smtp_pass'], 'YOUR_')) json_out(['error' => 'Email sending is not set up yet.'], 503);
$b = body();
if (($b['hp'] ?? '') !== '') json_out(['ok' => true]);   // bot filled the hidden field
$fid = (string)($b['fid'] ?? '');
$kind = in_array($b['kind'] ?? '', ['agent', 'visit'], true) ? $b['kind'] : '';
$name = trim(mb_substr((string)($b['name'] ?? ''), 0, 120));
$email = trim((string)($b['email'] ?? ''));
$subject = trim(mb_substr(str_replace(["\r", "\n"], ' ', (string)($b['subject'] ?? '')), 0, 200));
$text = mb_substr((string)($b['text'] ?? ''), 0, 4000);
if (!valid_id($fid) || !$kind || $name === '' || !filter_var($email, FILTER_VALIDATE_EMAIL) || $subject === '') json_out(['error' => 'Name and email are required.'], 400);

// At most 5 requests per visitor per hour.
$rl = sys_get_temp_dir() . '/eec_rq_' . hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? '') . 'eec');
$hits = array_filter(array_map('intval', is_file($rl) ? explode(',', (string)file_get_contents($rl)) : []), fn($t) => $t > time() - 3600);
if (count($hits) >= 5) json_out(['error' => 'Too many requests. Try again in an hour.'], 429);
$hits[] = time();
file_put_contents($rl, implode(',', $hits));

// Factory addresses come from our own data, never from the visitor.
$factory = null;
foreach (['factories.json', 'helmets.json'] as $file) {
    foreach (json_decode((string)@file_get_contents(ROOT . '/data/' . $file), true) ?: [] as $f) {
        if (($f['id'] ?? '') === $fid) { $factory = $f; break 2; }
    }
}
if (!$factory) json_out(['error' => 'Unknown factory.'], 404);
$to = (array)($factory['emails'] ?? []);
$saved = false;
try {
    $st = db()->prepare('SELECT data FROM edits WHERE fid = ?');
    $st->execute([$fid]);
    $edit = json_decode((string)($st->fetchColumn() ?: '{}'), true) ?: [];
    if (isset($edit['emails']) && is_array($edit['emails'])) $to = $edit['emails'];
    db()->prepare('INSERT INTO requests (fid, kind, name, email, body, created_at) VALUES (?, ?, ?, ?, ?, ?)')->execute([$fid, $kind, $name, $email, $text, gmdate('c')]);
    $saved = true;
} catch (Throwable $e) { /* database not set up yet: email still goes out */ }
$hub = $c['mail_reply_to'] ?: $c['smtp_user'];
$to = array_slice(array_values(array_unique(array_filter(array_merge($to, [$hub]), fn($e) => filter_var($e, FILTER_VALIDATE_EMAIL)))), 0, 6);
$intro = "New request from EEC Moto Hub for " . ($factory['name'] ?? $fid) . ".\nReply to this email to answer $name directly.\n\n";
$sent = 0;
foreach ($to as $addr) {
    if (smtp_send($c, $addr, $subject, $intro . $text, $email) === 'sent') $sent++;
}
if (!$sent) json_out(['error' => 'Email could not be sent.'], 502);
json_out(['ok' => true, 'saved' => $saved]);
