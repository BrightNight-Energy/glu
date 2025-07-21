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
After installation, the `glu` command will be available:

```bash
glu --help
```

## Commands

Glu CLI provides four main command groups: `init`, `pr`, `ticket`, and `commit`. They are registered as 
subcommands of the main CLI:

```bash
glu init --help
glu pr --help
glu ticket --help
glu commit --help
```

### `glu pr`

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

#### `pr list`

List pull requests with optional filters:

```bash
glu pr list [OPTIONS]
```

Options:

- `--repo, -r TEXT`        Repo name (defaults to current directory git repository)
- `--only-mine, -m`        Filter PRs to those assigned to me
- `--no-draft, -d`         Filter PRs to exclude draft

#### `pr open`

Open a PR in the web browser:

```bash
glu pr open PR_NUM [OPTIONS]
```

Options:

- `--repo, -r TEXT`        Repo name (defaults to current directory git repository)

#### `pr view`

View details of a PR:

```bash
glu pr view PR_NUM [OPTIONS]
```

Options:

- `--repo, -r TEXT`        Repo name (defaults to current directory git repository)
- `--checks, --show-checks, -c`
                         Show CI checks (not enabled by default for performance reasons)

#### `pr update`

Update a PR with an updated description and metadata:

```bash
glu pr update PR_NUM [OPTIONS]
```

Options:

- `--ticket, -t TEXT`      Jira ticket number
- `--project, -p TEXT`     Jira project (defaults to default Jira project)
- `--draft, -d`            Mark as draft PR
- `--reviewer, -r TEXT`    Requested reviewers (accepts multiple values)
- `--provider, -pr TEXT`   AI model provider
- `--model, -m TEXT`       LLM model
- `--review`               Move ticket to ready for review (defaults to False)

### `glu ticket`

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

#### `ticket list`

List Jira tickets with optional filters:

```bash
glu ticket list [OPTIONS]
```

Options:

- `--project, -p TEXT`     Jira project
- `--only-mine, -m`        Only show my tickets
- `--status, -s TEXT`      Filter tickets by status (multiple values accepted)
- `--priority-ordered`     Order by priority (defaults to created date)
- `--show-closed, -c`      Show closed tickets
- `--priority, -y TEXT`    Filter tickets by priority (multiple values accepted)
- `--type, -t TEXT`        Filter tickets by issue type (multiple values accepted)
- `--in-progress, -i`      Show in progress tickets only

#### `ticket open`

Open a Jira ticket in the web browser:

```bash
glu ticket open TICKET_NUM [OPTIONS]
```

Options:

- `--project, -p TEXT`     Jira project

#### `ticket view`

View details of a Jira ticket:

```bash
glu ticket view TICKET_NUM [OPTIONS]
```

Options:

- `--project, -p TEXT`     Jira project

### `glu commit`

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
  - `--jira-done TEXT`              Jira “done” transition name (default: Finished)  
  - `--default-jira-project TEXT`   Default Jira project key  

- **GitHub Config**  
  - `--github-pat TEXT`             GitHub Personal Access Token (required)

**Preferences**  
  - `--preferred-provider TEXT`     Preferred AI provider (optional)  
  - `--auto-accept-generated-commits`  Auto accept generated commit messages  
  - `--generated-with-glu-tag/--no-generated-with-glu-tag`  
                                   Add a tag to generated PRs and tickets to spread the word about glu! (default: True)  
  - `--add-pr-number-on-merge/--no-add-pr-number-on-merge`  
                                   Add the PR number to merge commits (default: True)  

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
