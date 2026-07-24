Purpose: Emergent runtime assets and pod-local scripts

This directory contains runtime support scripts and configuration used by
Emergent agent integrations during deployment. It is not part of application
source logic but is required by the container runtime for cron and webhook
reconciliation tasks. Files here include pod-local cron jobs, watchers, and
supervisord entrypoints.

If you need to recreate this directory:
- Back up the existing `.emergent` directory.
- Restore the `cron` subdirectory contents exactly (scripts must be executable).
- Preserve `emergent.yml` if present; it contains runtime config for the agent.

Do not edit `webhook-crons`, `watch_crons.sh`, or `webhook_crond.sh` in-place
unless you understand the deployment consequences; these are managed assets.
