# Moving the existing database to the Linux server

1. On the Windows SQL Server (172.23.51.190) back up the database (SSMS, or sqlcmd):
   ```sql
   BACKUP DATABASE [ISGRC] TO DISK = N'C:\Backup\ISGRC.bak' WITH COPY_ONLY, INIT, COMPRESSION;
   ```
2. Copy `ISGRC.bak` to the Linux server's home folder (`~`) by USB or scp. **Never commit it to GitHub - it holds your data.**
3. (Optional) If you still have the old `DJANGO_SECRET_KEY`, pass it as `AMLI_SECRET_KEY`. Without it everyone just logs in again.
4. Run (no variables needed):
   ```bash
   bash install.sh
   ```
   `deploy.sh` finds `~/ISGRC.bak` (or `./restore/*.bak`), restores it into the SQL Server container as `ISGRC`, then starts the app.
   Log in with your existing accounts.
