<?php
declare(strict_types=1);

const ROOT = __DIR__ . '/..';

function config(): array {
    static $cfg = null;
    if ($cfg === null) {
        $file = ROOT . '/config.php';
        if (!is_file($file)) {
            json_out(['error' => 'Server not configured yet: config.php is missing.'], 500);
        }
        $cfg = require $file;
    }
    return $cfg;
}

function db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $c = config();
        $pdo = new PDO($c['db_dsn'], $c['db_user'] ?? null, $c['db_pass'] ?? null, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    }
    return $pdo;
}

function json_out($data, int $status = 200): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

function body(): array {
    $raw = file_get_contents('php://input');
    $data = json_decode($raw ?: '[]', true);
    return is_array($data) ? $data : [];
}

function start_session(): void {
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_set_cookie_params([
            'lifetime' => 0, 'path' => '/', 'secure' => !empty($_SERVER['HTTPS']),
            'httponly' => true, 'samesite' => 'Strict',
        ]);
        session_start();
    }
}

function is_admin(): bool {
    start_session();
    return !empty($_SESSION['admin']);
}

function require_admin(): void {
    if (!is_admin()) json_out(['error' => 'Admin login required.'], 401);
    // Basic CSRF guard: admin writes must come from our own page via fetch.
    if (($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') !== 'eec') json_out(['error' => 'Bad request.'], 400);
}

function valid_id(string $id): bool {
    return (bool)preg_match('/^[a-z0-9-]{1,60}$/', $id);
}
