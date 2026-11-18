# Waste Collection Management Website

This is a separate Flask website folder, alongside (not inside) the existing `Waste-Collection-Management` project. It uses that project's MySQL database, `.env`, and Python chart-generation script without copying or changing those files.

## Run

1. Start MySQL and ensure the existing database is populated.
2. Confirm database credentials are set in `Waste-Collection-Management\python-analysis\.env`.
3. Install website dependencies once:

   ```powershell
   cd "C:\Users\Admin\.gemini\antigravity\scratch\Waste Collection Management Website"
   & "C:\Users\Admin\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pip install -r requirements.txt
   ```

4. Start the website:

   ```powershell
   .\run.bat
   ```

5. Open <http://127.0.0.1:5000>.

The website provides area and vehicle management, collection scheduling and status updates, reports, and the eight existing Python analytics charts. The server binds to localhost only.

## Temporary public deployment on Render

The Render configuration is in `render.yaml`. The deployed website requires HTTP Basic Authentication using the `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables. Set both as secrets in Render; the application returns an error rather than serving an unprotected website if either is missing on Render. The `/health` endpoint is reserved for Render's health check.

Render cannot connect to a MySQL server at `127.0.0.1` on your computer. Before deploying, migrate the database to a hosted MySQL service and set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in the Render environment. Use a dedicated database user with only the permissions the app needs; do not use the MySQL `root` account.

For a two-week demo, set a reminder to delete the Render web service and hosted database after the demo. Deleting the service does not automatically delete a separately hosted database or its backups. Never put database credentials in GitHub or share them in chat.
