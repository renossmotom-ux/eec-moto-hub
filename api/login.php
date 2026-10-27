<?php
require __DIR__ . '/../lib/bootstrap.php';
start_session();
$b = body();
if (($b['action'] ?? '') === 'logout') { $_SESSION = []; session_destroy(); json_out(['ok' => true]); }
$hash = config()['admin_hash'] ?? '';
// Slow down guessing.
usleep(400000);
if ($hash === '' || !password_verify((string)($b['password'] ?? ''), $hash)) json_out(['error' => 'Wrong password.'], 401);
session_regenerate_id(true);
$_SESSION['admin'] = true;
json_out(['ok' => true]);
