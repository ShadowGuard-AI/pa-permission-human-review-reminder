# pa-permission-human-review-reminder
Schedules periodic reviews of specific permissions or permission groups by designated human reviewers. Sends email notifications with relevant permission details (e.g., who has it, when it was granted), allowing organizations to ensure that permissions are still appropriate over time. Uses a simple scheduler and an email sending library. - Focused on Tools for analyzing and assessing file system permissions

## Install
`git clone https://github.com/ShadowGuardAI/pa-permission-human-review-reminder`

## Usage
`./pa-permission-human-review-reminder [params]`

## Parameters
- `-h`: Show help message and exit
- `-c`: Path to the configuration file. Defaults to permission_review_config.json
- `-t`: Send a test email using the configured settings.  Will not schedule reviews. The test message is sent to the sender address. If the test email fails, the tool exits 1.

## Configuration notes
- The `review_schedule` value in the config is data, never code. It is read by a narrow parser and is never evaluated or executed. The accepted forms are: `every N seconds`, `every N minutes`, `every N hours`, `every N days`, or `every N weeks` (N a positive whole number); `daily at HH:MM`; and `weekly on <weekday>`, optionally followed by `at HH:MM`. Any other value is reported as invalid in plain terms and schedules nothing.
- If no review jobs are scheduled, because every schedule value is invalid or because the config lists no permissions or no reviewers, the tool reports that no reviews were scheduled and exits 1 instead of running forever with zero jobs.
- Mail transport: by default mail is sent over a plain SMTP connection with no encryption and no authentication. Two optional config keys change that: set `smtp_use_tls` to true to use STARTTLS, and set `smtp_username` and `smtp_password` to authenticate. Use them when the configured server is not on the same trusted machine, because the mail body carries the permission details from the config.
- Review form link: set the optional `review_form_url` config key and the notice carries that link. When it is not set, the notice asks the reviewer to use the organization's own review process, and no placeholder link is sent.

## License
Copyright (c) ShadowGuardAI
