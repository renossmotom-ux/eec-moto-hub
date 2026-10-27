<?php
// Copy this file to config.php on the server and fill in your own values.
// config.php is never committed to Git.
return [
    // MySQL database from hPanel → Databases → MySQL Databases
    'db_dsn'  => 'mysql:host=localhost;dbname=u123456789_eec;charset=utf8mb4',
    'db_user' => 'u123456789_eec',
    'db_pass' => 'YOUR_DATABASE_PASSWORD',

    // Admin password hash. Create it once at https://eec.renossmoto.com/setup.php
    'admin_hash' => '',

    // One-time key that protects setup.php. Pick any long random text.
    'setup_key' => 'CHANGE_ME_TO_A_LONG_RANDOM_TEXT',

    // Mailbox used to send invitation emails (hPanel → Emails)
    'smtp_host' => 'smtp.hostinger.com',
    'smtp_port' => 465,
    'smtp_user' => 'invite@renossmoto.com',
    'smtp_pass' => 'YOUR_MAILBOX_PASSWORD',
    'mail_from_name' => 'EEC Moto Hub',
    'mail_reply_to'  => 'invite@renossmoto.com',
    // Hostinger limits outgoing mail per day; keep each batch small.
    'mail_batch' => 25,
];
