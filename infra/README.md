# Infra Skeleton

This folder is a phased migration scaffold for AWS target infrastructure.

## Planned modules
- `modules/api` - API runtime, networking, autoscaling.
- `modules/queue` - SQS queues and DLQ.
- `modules/store` - DynamoDB/Postgres abstractions.
- `modules/observability` - logs, alarms, traces.

No deploy actions are executed from this repository by default.
