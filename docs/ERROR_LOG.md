# Error Log

## Error #1: Production deploy failed, SSH key not readable

- **Date:** 18 Oct 2026
- **Where:** deploy-prod job, run 39046843828
- **What happened:** The deploy step failed with `Load key ... error in libcrypto`, so the pipeline could not SSH into the production VM.
- **Cause:** The PROD_SSH_KEY secret was set by piping the key file through PowerShell, which converted the line endings to Windows style (CRLF). The SSH client rejects a key with CRLF line endings.
- **Fix:** Re-set the secret using a `cmd` redirect, which keeps the file byte-for-byte (`cmd /c "gh secret set PROD_SSH_KEY < %USERPROFILE%\.ssh\aerodeploy_deploy"`), then re-ran the failed job. The deploy succeeded.
- **Prevention:** All key secrets are set with the cmd redirect, and the repo has `.gitattributes` forcing LF line endings for scripts.

## Error #2: Public site showed the default Nginx page

- **Date:** 18 Oct 2026
- **Where:** Production VM (20.70.170.224), found after the first automated prod deploy
- **What happened:** The app was healthy on 127.0.0.1:8000, but the public address showed the default Nginx "coming soon" page and `/health` returned an Nginx 404.
- **Cause:** The Nginx config (`deploy/nginx/taskflow.conf`) was in the repo but had not been installed on the production VM yet, so Nginx was not forwarding traffic to the app.
- **Fix:** The pipeline's public check was set to non-blocking (`continue-on-error`) so deploys could continue, and the config install was assigned to the Production owner. Once it was installed, the check was made strict so a broken public site fails the pipeline.
- **Prevention:** The pipeline now checks the live site through Nginx after every production deploy.
