# YouTube metadata backfill

This patch preserves the original `youtube_video` table and adds full video metadata.

## Files to copy

Copy every file in this directory to `collection/youtube/`.

Copy the five JSON files to `data/raw/youtube/`:

- `속초_20260924_0118.json`
- `여수_20260924_0118.json`
- `영월_20260924_0119.json`
- `울릉_20260924_0118.json`
- `인제_20260924_0119.json`

The repository root `.env` must contain `YOUTUBE_API_KEY`. The MySQL password may be stored
as `MYSQL_PASSWORD` or entered interactively.

## Run order

From the repository root:

```bat
mysql -u yaho_loader -p tour_earlywarning < collection\youtube\01_create_youtube_metadata_schema.sql
collection\youtube\02_check_youtube_metadata.cmd
collection\youtube\03_load_youtube_metadata.cmd
collection\youtube\04_validate_youtube_metadata.cmd
```

The dry run does not call YouTube and does not change MySQL. The commit run refreshes all
unique video IDs through `videos.list` in batches of 50. With 276 unique IDs this costs six
YouTube API units. Videos unavailable through the API retain the metadata found in JSON.

The bridge table `youtube_video_region_match` preserves videos returned for more than one
region while `youtube_video` continues to have one canonical row per video ID.
