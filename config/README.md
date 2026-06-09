# Runtime Configuration

The application is configured through environment variables. Use the root
`.env.example` as the canonical list of supported settings.

Environment-specific values and secrets must remain outside source control.
Airflow may provide the same settings through Variables and Kubernetes Secrets.
