# Worker

Asynchronous backend executor.

The worker runs work outside the user-facing request/response path: queues, cron, retries, email delivery, file processing, billing sync, indexing, notifications, and long-running AI tasks.

The API should enqueue durable jobs and return quickly. The worker should execute those jobs, update state, emit events, and record failures clearly.
