<?php
// Buyer accounts: sign up, sign in, sign out, read and save the profile (interests).
// GET returns the signed-in buyer (GET ?list=1: all buyers, admin only), POST {action: signup|login|logout|save, ...}.
require __DIR__ . '/../lib/bootstrap.php';
start_session();

const INTERESTS = ['moto_eec', 'moto_non', 'electric', 'scooter', 'offroad', 'tricycle', 'helmet_ece', 'helmet_non',
    'parts', 'apparel', 'ebike', 'svc_eec', 'svc_ship', 'svc_agent', 'svc_visit', 'expos'];

function buyers_table(): void {
    $isMysql = str_starts_with(config()['db_dsn'], 'mysql:');
    db()->exec("CREATE TABLE IF NOT EXISTS buyers (id INTEGER PRIMARY KEY " . ($isMysql ? 'AUTO_INCREMENT' : 'AUTOINCREMENT') . ", email VARCHAR(200) NOT NULL UNIQUE, pass_hash VARCHAR(255) NOT NULL, profile " . ($isMysql ? 'MEDIUMTEXT' : 'TEXT') . " NOT NULL, created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)");
}

// Only known fields and known interest keys are kept.
function clean_profile(array $p): array {
    $s = fn($k, $max) => trim(mb_substr(str_replace(["\r", "\n"], ' ', (string)($p[$k] ?? '')), 0, $max));
    return [
        'name' => $s('name', 120), 'company' => $s('company', 160), 'country' => $s('country', 80),
        'whatsapp' => $s('whatsapp', 40), 'wechat' => $s('wechat', 60),
        'interests' => array_values(array_intersect(INTERESTS, (array)($p['interests'] ?? []))),
    ];
}

function buyer_out(array $row): array {
    return ['id' => (int)$row['id'], 'email' => $row['email'], 'since' => $row['created_at']] + (json_decode($row['profile'], true) ?: []);
}

try { buyers_table(); } catch (Throwable $e) { json_out(['error' => 'Buyer accounts need the database. It is not connected yet.', 'nodb' => true], 503); }

if ($_SERVER['REQUEST_METHOD'] === 'GET' && isset($_GET['list'])) {
    if (!is_admin()) json_out(['error' => 'Admin login required.'], 401);
    json_out(['buyers' => array_map('buyer_out', db()->query('SELECT * FROM buyers ORDER BY created_at DESC')->fetchAll())]);
}
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    if (empty($_SESSION['buyer'])) json_out(['buyer' => null]);
    $st = db()->prepare('SELECT * FROM buyers WHERE id = ?');
    $st->execute([(int)$_SESSION['buyer']]);
    $row = $st->fetch();
    json_out(['buyer' => $row ? buyer_out($row) : null]);
}
if (($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') !== 'eec') json_out(['error' => 'Bad request.'], 400);

$b = body();
$action = (string)($b['action'] ?? '');
$email = strtolower(trim((string)($b['email'] ?? '')));
$pass = (string)($b['password'] ?? '');

if ($action === 'logout') { unset($_SESSION['buyer']); json_out(['ok' => true]); }

if ($action === 'signup') {
    if (($b['hp'] ?? '') !== '') json_out(['ok' => true]);   // bot filled the hidden field
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) json_out(['error' => 'Enter a valid email.'], 400);
    if (strlen($pass) < 8) json_out(['error' => 'Password must have at least 8 characters.'], 400);
    $profile = clean_profile((array)($b['profile'] ?? []));
    if ($profile['name'] === '') json_out(['error' => 'Enter your name.'], 400);
    $st = db()->prepare('SELECT id FROM buyers WHERE email = ?');
    $st->execute([$email]);
    if ($st->fetchColumn()) json_out(['error' => 'This email already has an account. Sign in instead.'], 409);
    $now = gmdate('c');
    db()->prepare('INSERT INTO buyers (email, pass_hash, profile, created_at, updated_at) VALUES (?, ?, ?, ?, ?)')
        ->execute([$email, password_hash($pass, PASSWORD_DEFAULT), json_encode($profile, JSON_UNESCAPED_UNICODE), $now, $now]);
    session_regenerate_id(true);
    $_SESSION['buyer'] = (int)db()->lastInsertId();
    json_out(['buyer' => ['id' => $_SESSION['buyer'], 'email' => $email, 'since' => $now] + $profile]);
}

if ($action === 'login') {
    usleep(400000);   // slow down guessing
    $st = db()->prepare('SELECT * FROM buyers WHERE email = ?');
    $st->execute([$email]);
    $row = $st->fetch();
    if (!$row || !password_verify($pass, $row['pass_hash'])) json_out(['error' => 'Wrong email or password.'], 401);
    session_regenerate_id(true);
    $_SESSION['buyer'] = (int)$row['id'];
    json_out(['buyer' => buyer_out($row)]);
}

if ($action === 'save') {
    if (empty($_SESSION['buyer'])) json_out(['error' => 'Please sign in again.'], 401);
    $profile = clean_profile((array)($b['profile'] ?? []));
    db()->prepare('UPDATE buyers SET profile = ?, updated_at = ? WHERE id = ?')
        ->execute([json_encode($profile, JSON_UNESCAPED_UNICODE), gmdate('c'), (int)$_SESSION['buyer']]);
    $st = db()->prepare('SELECT * FROM buyers WHERE id = ?');
    $st->execute([(int)$_SESSION['buyer']]);
    json_out(['buyer' => buyer_out($st->fetch())]);
}

json_out(['error' => 'Unknown action.'], 400);
