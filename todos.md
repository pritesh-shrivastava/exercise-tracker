# TODOs

- [ ] Add weekly backup job to dump the raw SQLite database (`data/workouts.sqlite`) and upload it to Azure Blob Storage.
- [ ] Keep only the last 3 backup copies in Azure Blob Storage.
- [ ] Add a restore note/script for recovering the DB from Azure Blob if the VPS dies.
- [ ] Check Garmin Connect data export for old strength training history and recover/import anything useful.
