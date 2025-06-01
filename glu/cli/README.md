# Glu CLI

Glu CLI is a command‑line interface for Glu that streamlines common development workflows by integrating GitHub pull requests, Jira tickets, and AI‑powered content generation.

## Installation

Glu CLI is distributed via PyPI. You can install it with:

```bash
pip install glu
```
【F:pyproject.toml†L1-L7】

Alternatively, to install from source:

```bash
git clone https://github.com/your_org/glu.git
cd glu
pip install -e .
```

## Usage

After installation, the `glu` command will be available:

```bash
glu --help
```

### Global Options

- `--version`                   Show the version and exit  
- `--install-completion`        Install shell completion for your shell  
- `--show-completion`           Show completion script to customize installation  
- `--help`                      Show this message and exit  
【F:glu/cli/main.py†L33-L43】

### Configuration (`init`)

Initialize your Glu configuration interactively:

```bash
glu init
```

Options:

- **Jira Config**  
  - `--jira-api-token TEXT`         Jira API token (required)  
  - `--jira-email, --email TEXT`    Jira email (required)  
  - `--jira-server TEXT`            Jira server URL (default: https://jira.atlassian.com)  
  - `--jira-in-progress TEXT`       Jira “in progress” transition name (default: Starting)  
  - `--jira-ready-for-review TEXT`  Jira “ready for review” transition name (default: Ready for review)  
  - `--default-jira-project TEXT`   Default Jira project key  

- **GitHub Config**  
  - `--github-pat TEXT`             GitHub Personal Access Token (required)  

- **OpenAI Config**  
  - `--openai-api-key TEXT`         OpenAI API key (required)  
  - `--openai-org-id TEXT`          OpenAI organization ID (required)  

- **Glean Config**  
  - `--glean-api-token TEXT`        Glean API token  
  - `--glean-instance TEXT`         Glean instance URL  

For full option details, refer to the source definition:
【F:glu/cli/main.py†L45-L124】

### Commands

Glu CLI provides two main command groups: `pr` and `ticket`. They are registered as subcommands of the main CLI:

```bash
glu pr --help
glu ticket --help
```
【F:glu/cli/main.py†L253-L260】

#### `pr create`

Create a pull request with AI‑generated or manual descriptions:

```bash
glu pr create [OPTIONS]
```

Options:

- `--ticket, -t TEXT`          Jira ticket number  
- `--project, -p TEXT`         Jira project (defaults to default project)  
- `--draft, -d`                Mark as draft PR  
- `--ready-for-review/--no-ready-for-review`  Transition ticket to Ready for review  
- `--reviewer, -r TEXT`        Requested reviewers (repeatable)  
- `--provider, -pr TEXT`       AI model provider  

See the implementation for more details:
【F:glu/cli/pr.py†L50-L78】

#### `ticket create`

Create a Jira ticket, optionally using AI to generate summary and description:

```bash
glu ticket create [OPTIONS]
```

Options:

- `--summary, --title, -s TEXT`      Issue summary or title  
- `--type, -t TEXT`                  Issue type  
- `--body, -b TEXT`                  Issue description  
- `--assignee, -a TEXT`              Assignee  
- `--reporter, -r TEXT`              Reporter  
- `--priority, -y TEXT`              Priority  
- `--project, -p TEXT`               Jira project  
- `--ai-prompt, -ai TEXT`            AI prompt to generate summary and description  
- `--provider, -pr TEXT`             AI model provider  

The command also accepts additional JIRA fields via `--<field> <value>`:
【F:glu/cli/ticket.py†L31-L60】

## Contributing

Contributions to Glu CLI are welcome! Please follow these guidelines:

1. Fork the repository and create your branch:
   ```bash
   git checkout -b feature/your-feature
   ```
2. Make your changes, ensuring that new code includes tests where appropriate.
3. Run linters and formatters:
   ```bash
   pre-commit run --all-files
   ```
4. Commit your changes following Conventional Commits.
5. Push to your fork and open a Pull Request.

## Acknowledgements

Glu CLI draws inspiration from [Jira CLI](https://github.com/Netflix-Skunkworks/jira-cli) and [GitHub CLI](https://github.com/cli/cli).