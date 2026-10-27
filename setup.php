<?php
// One-time setup: creates the tables and the admin password hash.
// Open https://eec.renossmoto.com/setup.php?key=YOUR_SETUP_KEY
require __DIR__ . '/lib/bootstrap.php';
$c = config();
if (($c['setup_key'] ?? '') === '' || str_starts_with($c['setup_key'], 'CHANGE_ME') || !hash_equals($c['setup_key'], (string)($_GET['key'] ?? ''))) {
    http_response_code(403); exit('Wrong or missing setup key. Set setup_key in config.php and open setup.php?key=...');
}
$isMysql = str_starts_with($c['db_dsn'], 'mysql:');
$text = $isMysql ? 'MEDIUMTEXT' : 'TEXT';
db()->exec("CREATE TABLE IF NOT EXISTS edits (fid VARCHAR(64) PRIMARY KEY, data $text NOT NULL, updated_at VARCHAR(32) NOT NULL)");
db()->exec("CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY " . ($isMysql ? 'AUTO_INCREMENT' : 'AUTOINCREMENT') . ", fid VARCHAR(64) NOT NULL, title VARCHAR(200) NOT NULL, body $text, created_at VARCHAR(32) NOT NULL)");
db()->exec("CREATE TABLE IF NOT EXISTS mail_log (id INTEGER PRIMARY KEY " . ($isMysql ? 'AUTO_INCREMENT' : 'AUTOINCREMENT') . ", recipient VARCHAR(200) NOT NULL, subject VARCHAR(250) NOT NULL, status VARCHAR(250) NOT NULL, sent_at VARCHAR(32) NOT NULL)");
$hash = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && strlen((string)($_POST['password'] ?? '')) >= 10) {
    $hash = password_hash((string)$_POST['password'], PASSWORD_DEFAULT);
}
?><!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EEC Moto Hub setup</title>
<body style="font-family:system-ui;max-width:640px;margin:40px auto;padding:0 16px;line-height:1.5">
<h1>Setup</h1>
<p>✓ Database tables are ready.</p>
<?php if ($hash): ?>
  <p><b>Copy this line into config.php</b> as the value of <code>admin_hash</code>, then save the file:</p>
  <pre style="background:#eef;padding:12px;overflow-x:auto"><?= htmlspecialchars($hash) ?></pre>
  <p>After that, change <code>setup_key</code> in config.php to something new so nobody can open this page again.</p>
<?php else: ?>
  <form method="post"><p>Choose your admin password (at least 10 characters):</p>
  <input type="password" name="password" minlength="10" required style="font-size:16px;padding:8px;width:100%">
  <p><button style="font-size:16px;padding:8px 16px">Create password hash</button></p></form>
<?php endif; ?>
</body>
