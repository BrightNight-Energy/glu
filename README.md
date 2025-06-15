# Glu CLI

![PyPI - Version](https://img.shields.io/pypi/v/glu-cli)
![GitHub CI](https://github.com/BrightNight-Energy/glu/actions/workflows/cicd.yml/badge.svg)

Glu CLI is a command‑line interface for Glu that streamlines common development workflows by integrating 
GitHub pull requests, Jira tickets, and AI‑powered content generation.

## Installation

Glu CLI is distributed via PyPI. You can install it with:

```bash
pipx install glu-cli
```

Alternatively, to install from source:

```bash
git clone https://github.com/BrightNight-Energy/glu.git
cd glu
pip install -e .
```

## Usage

After installation, the `glu` command will be available:

```bash
glu --help
```

### Commands

Glu CLI provides two main command groups: `pr` and `ticket`. They are registered as subcommands of the main CLI:

```bash
glu pr --help
glu ticket --help
```

#### `pr create`

The only command you need. When you're ready to push and raise a PR, use this. It will:

1. Create your commit message based on commit diff (if uncommitted changes)
2. Create a ticket in Jira based on PR description (or use the provided ticket #)
3. Push a PR based on the git diff and tag your reviewers
4. If PR is not a draft, will move your ticket to Ready for review!

...all fully customizable and within your control.

<img align="center" alt="glu ticket creation demo" src=".github/assets/pr-creation-demo.gif" /><br/><br/>

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
- `--model, -m TEXT`           LLM model  
- `--review`                   Move ticket to ready for review (defaults to False)  

#### `pr merge`

Merge a PR with an AI generated commit message (or handcrafted, your choice) and your Jira ticket number.

Arguments:

- `pr_num`                     PR number

Options:

- `--ticket, -t TEXT`          Jira ticket number  
- `--project, -p TEXT`         Jira project (defaults to default project)  
- `--provider, -pr TEXT`       AI model provider  
- `--model, -m TEXT`           LLM model  
- `--mark-done`                Move Jira ticket to done (defaults to False)  

> [!WARNING]
> Currently only squash-merges are supported

#### `ticket create`

Create a Jira ticket, optionally using AI to generate summary and description:

<img align="center" alt="glu ticket creation demo" src=".github/assets/ticket-creation-demo.gif" /><br/><br/>

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
- `--model, -m TEXT`                 LLM model  

The command also accepts additional JIRA fields via `--<field> <value>`.

#### `commit list`

Display a table of commits, similar to `git log` but more compact:

<img align="center" alt="glu commit list" src=".github/assets/commit-list.png" /><br/><br/>

```bash
glu commit list [OPTIONS]
```

Options:

- `--limit, -l NUMBER`      Number of commits (defaults to number of commits since main)


#### `commit count`

Print the number of commits since checkout to the branch:

```bash
glu commit count [OPTIONS]
```

Options:

- `--branch, -b TEXT`      Branch to count from (defaults to default branch)

### Configuration (`init`)

Initialize your Glu configuration interactively (strongly recommended):

```bash
glu init
```

Currently, glu supports the AI providers listed below. The default model for each provider can be
customized via config or specified on each command.

| Provider  | Default model     |
|:----------|:------------------|
| OpenAI    | o4-mini           |
| Gemini    | gemini-2.0-flash  |
| xAI       | grok-3-mini-fast  |
| Anthropic | claude-sonnet-4-0 |
| Ollama    | llama3.2          |

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

## Contributing

Contributions to Glu CLI are welcome! Please follow these guidelines:

1. Fork the repository and create your branch:
   ```bash
   git checkout -b feature/your-feature
   ```
2. Make your changes, ensuring that new code includes tests where appropriate.
3. Install precommit hooks:
   ```bash
    pre-commit install --install-hooks
    pre-commit install --hook-type commit-msg
   ```
4. Commit your changes following Conventional Commits.
5. Push to your fork and open a Pull Request.

## Acknowledgements

Glu CLI is inspired by [Jira CLI](https://github.com/ankitpokhrel/jira-cli) and 
[GitHub CLI](https://github.com/cli/cli).