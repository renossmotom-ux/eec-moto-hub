# EEC Moto Hub

Public directory of Chinese motorcycle factories for buyers in Morocco and worldwide.
Live address: https://eec.renossmoto.com

- `index.html` is the whole site (English, French, Chinese, Arabic).
- `data/factories.json` holds the 485 factory profiles.
- `api/` is the PHP backend: admin login, saved edits (rating, remove, contacts, 360° link), factory news, and email sending.
- `setup.php` creates the database tables and your admin password hash.
- `config.php` holds passwords. It lives only on the server and is never in Git.

## Put it on Hostinger (one time)

1. **Subdomain.** hPanel → Websites → renossmoto.com → Domains → Subdomains. Create `eec`. Note its folder, usually `public_html/eec`, and delete any default files Hostinger puts in it.
2. **Database.** hPanel → Databases → MySQL Databases. Create a database and a user. Keep the password yourself.
3. **Git deploy.** hPanel → Advanced → Git. Repository `https://github.com/renossmotom-ux/eec-moto-hub.git`, branch `main`, folder `eec` (the subdomain folder, which must be empty). For a private repository, copy the SSH key hPanel shows and add it on GitHub under the repository's Settings → Deploy keys. Press Deploy. Turn on auto deployment if you want every push to go live.
   *No GitHub?* Upload `eec-moto-hub-hostinger.zip` into the `eec` folder with File Manager and extract it there instead.
4. **config.php.** hPanel → Files → File Manager → the `eec` folder. Copy `config.sample.php` to `config.php` and fill in:
   - the database name, user and password from step 2
   - `setup_key`: any long random text
   - the mailbox password for `invite@renossmoto.com` (hPanel → Emails), when you want real sending
5. **Setup.** Open `https://eec.renossmoto.com/setup.php?key=YOUR_SETUP_KEY`. It creates the tables. Type your admin password, copy the hash it prints into `admin_hash` in `config.php`.
6. **Lock setup.** Change `setup_key` in `config.php` back to `CHANGE_ME` so setup.php stops working.
7. **SSL.** hPanel → Security → SSL. Make sure the `eec` subdomain has a certificate.

## Use it

- Public: https://eec.renossmoto.com
- Admin: https://eec.renossmoto.com/#admin, sign in with your password.
- Email: in Admin, pick factories or "Email all", choose the language, press **Send now**. It sends one email per factory, 25 per batch. Hostinger limits mail per day, so check your plan's limit before sending to hundreds.

## Test locally

```
cp config.sample.php config.php   # set db_dsn to 'sqlite:' . __DIR__ . '/test.sqlite'
php -S 127.0.0.1:8099
```
