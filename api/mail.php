<?php
// Admin: send the invitation to a batch of recipients, one email each.
require __DIR__ . '/../lib/bootstrap.php';
require __DIR__ . '/../lib/smtp.php';
require_admin();
$c = config();
if (($c['smtp_pass'] ?? '') === '' || str_starts_with((string)$c['smtp_pass'], 'YOUR_')) json_out(['error' => 'Email sending is not set up yet: add the mailbox password to config.php.'], 400);
$b = body();
$subject = trim((string)($b['subject'] ?? ''));
$text = (string)($b['body'] ?? '');
$to = array_values(array_unique(array_filter((array)($b['to'] ?? []), fn($e) => filter_var($e, FILTER_VALIDATE_EMAIL))));
$max = (int)($c['mail_batch'] ?? 25);
if ($subject === '' || trim($text) === '') json_out(['error' => 'Subject and message are required.'], 400);
if (!$to) json_out(['error' => 'No valid email address.'], 400);
if (count($to) > $max) json_out(['error' => "Send at most $max emails per batch."], 400);
$results = [];
$log = db()->prepare('INSERT INTO mail_log (recipient, subject, status, sent_at) VALUES (?, ?, ?, ?)');
foreach ($to as $addr) {
    $status = smtp_send($c, $addr, $subject, $text);
    $log->execute([$addr, mb_substr($subject, 0, 250), mb_substr($status, 0, 250), gmdate('c')]);
    $results[] = ['to' => $addr, 'status' => $status];
}
json_out(['results' => $results]);
