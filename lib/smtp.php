<?php
// Minimal SMTP client (SSL on port 465, AUTH LOGIN) for Hostinger mailboxes.
function smtp_send(array $c, string $to, string $subject, string $text): string {
    $fp = @stream_socket_client('ssl://' . $c['smtp_host'] . ':' . (int)$c['smtp_port'], $errno, $errstr, 20);
    if (!$fp) return "connect failed: $errstr";
    $read = function () use ($fp) { $out = ''; while (($line = fgets($fp, 515)) !== false) { $out .= $line; if (isset($line[3]) && $line[3] === ' ') break; } return $out; };
    $cmd = function (string $s, string $expect) use ($fp, $read) { fwrite($fp, $s . "\r\n"); $r = $read(); if (strpos($r, $expect) !== 0) throw new RuntimeException(trim($r)); return $r; };
    try {
        $r = $read(); if (strpos($r, '220') !== 0) throw new RuntimeException(trim($r));
        $cmd('EHLO ' . ($_SERVER['SERVER_NAME'] ?? 'localhost'), '250');
        $cmd('AUTH LOGIN', '334');
        $cmd(base64_encode($c['smtp_user']), '334');
        $cmd(base64_encode($c['smtp_pass']), '235');
        $cmd('MAIL FROM:<' . $c['smtp_user'] . '>', '250');
        $cmd('RCPT TO:<' . $to . '>', '25');
        $cmd('DATA', '354');
        $enc = fn($s) => '=?UTF-8?B?' . base64_encode($s) . '?=';
        $headers = [
            'From: ' . $enc($c['mail_from_name']) . ' <' . $c['smtp_user'] . '>',
            'To: <' . $to . '>',
            'Reply-To: <' . ($c['mail_reply_to'] ?: $c['smtp_user']) . '>',
            'Subject: ' . $enc($subject),
            'Date: ' . date('r'),
            'Message-ID: <' . bin2hex(random_bytes(12)) . '@' . substr(strrchr($c['smtp_user'], '@'), 1) . '>',
            'MIME-Version: 1.0',
            'Content-Type: text/plain; charset=UTF-8',
            'Content-Transfer-Encoding: base64',
        ];
        $msg = implode("\r\n", $headers) . "\r\n\r\n" . chunk_split(base64_encode($text));
        $cmd($msg . "\r\n.", '250');
        $cmd('QUIT', '221');
        fclose($fp);
        return 'sent';
    } catch (RuntimeException $e) {
        fclose($fp);
        return 'error: ' . $e->getMessage();
    }
}
