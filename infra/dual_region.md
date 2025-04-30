# Dual-Region Fail-over (GCP)

1. **Create Cloud SQL replica**

```bash
gcloud sql instances create dynasty-replica \
     --master-instance-name dynasty-sql \
     --region europe-west3
```

2. **Deploy secondary Cloud Run**

```bash
gcloud run deploy dynasty-eu \
     --image gcr.io/$PROJECT_ID/dynasty:$COMMIT_SHA \
     --region europe-west3
```

3. **Cloud DNS fail-over record**

Primary A record weight=100, secondary weight=0 failover=true, TTL 30s.

4. **Test**

Stop primary Cloud Run → traffic shifts in < 60s.