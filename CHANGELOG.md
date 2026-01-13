# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-13

### Added

- Initial release
- Fetch all clusters across MongoDB Atlas projects
- Concurrent API requests with connection pooling (up to 20 workers)
- Retry logic with exponential backoff and Retry-After header support
- Project filtering with glob patterns (include/exclude)
- Multiple sort options: project, cluster, tier, disk, provider, region
- Export to CSV or JSON file
- JSON output to stdout for piping to tools like `jq`
- Color highlighting for large tiers (configurable threshold)
- Summary statistics (projects, clusters, disk, breakdown by tier/provider/type)
- Execution metrics
- Diagnostic script (`test_api_connection.sh`) for troubleshooting
- Comprehensive test suite (43 tests)

### Configuration

- Environment variable support for all settings
- Command-line arguments override environment variables
- Sensible defaults for all options
