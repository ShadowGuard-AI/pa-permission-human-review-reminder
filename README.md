# pa-permission-human-review-reminder
Schedules periodic reviews of specific permissions or permission groups by designated human reviewers. Sends email notifications with relevant permission details (e.g., who has it, when it was granted) and a link to a review form, allowing organizations to ensure that permissions are still appropriate over time. Uses a simple scheduler and an email sending library. - Focused on Tools for analyzing and assessing file system permissions

## Install
`git clone https://github.com/ShadowGuardAI/pa-permission-human-review-reminder`

## Usage
`./pa-permission-human-review-reminder [params]`

## Parameters
- `-h`: Show help message and exit
- `-c`: Path to the configuration file. Defaults to permission_review_config.json
- `-t`: Send a test email using the configured settings.  Will not schedule reviews.

## License
Copyright (c) ShadowGuardAI
