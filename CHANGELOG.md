# Changelog

<!-- version list -->

## v2.3.3 (2025-06-25)

### Bug Fixes

- Make body optional on ticket create
  ([`874dff0`](https://github.com/BrightNight-Energy/glu/commit/874dff06f4eb35d89f8b4c30844fc00002403ec4))

- Make jira ticket optional on merge
  ([`e8dd070`](https://github.com/BrightNight-Energy/glu/commit/e8dd0705dec065598ecc000379faa8c67e462f89))

- Trim large diffs to respect model context limits
  ([`7669186`](https://github.com/BrightNight-Energy/glu/commit/7669186240c21fd2ba374b438a14f66553306e14))


## v2.3.2 (2025-06-16)

### Bug Fixes

- Respect repo.delete_branch_on_merge setting when merging prs
  ([`160c8f0`](https://github.com/BrightNight-Energy/glu/commit/160c8f0f758b58a8f288741cc519a91a71d9f2c8))

- Suppress 'not found' error when source branch auto-deleted
  ([`4935b1a`](https://github.com/BrightNight-Energy/glu/commit/4935b1ab304a66eb6fa8c9de41e185b5adbc5dba))


## v2.3.1 (2025-06-16)

### Bug Fixes

- Skip waiting ci checks in merge flow
  ([`e23898d`](https://github.com/BrightNight-Energy/glu/commit/e23898da4171ef336963c3930fdc97658005469d))


## v2.3.0 (2025-06-16)

### Features

- Add branch column to commit list
  ([`c8e9ad4`](https://github.com/BrightNight-Energy/glu/commit/c8e9ad4ac257f257aa1481e21727aeda815c0182))


## v2.2.0 (2025-06-16)

### Bug Fixes

- Modularize command structure and add error suppression
  ([`c043b6a`](https://github.com/BrightNight-Energy/glu/commit/c043b6afc7ba90d30e6effe3a64f7dbc43d5eaf2))

### Features

- Add 'generated with glu' tag to ai-created prs and tickets
  ([`7671106`](https://github.com/BrightNight-Energy/glu/commit/76711068374de0ea8cac98e3312558dec4ae8c29))

- Add commit list and commit count commands
  ([`addf91a`](https://github.com/BrightNight-Energy/glu/commit/addf91aaa4d5531e341afcb3ee623c08348d2b9d))


## v2.1.0 (2025-06-15)

### Features

- Add ai-driven final commit message generation and pr merge command
  ([`69118b5`](https://github.com/BrightNight-Energy/glu/commit/69118b5fdf8e0a0da35007dcc1c9b7761e05c787))


## v2.0.4 (2025-06-14)

### Bug Fixes

- Detect and inject jira ticket placeholder in pr descriptions
  ([`ad3843f`](https://github.com/BrightNight-Energy/glu/commit/ad3843f6142d3b3f785779238163fbe62ef8c635))


## v2.0.3 (2025-06-13)

### Bug Fixes

- Continue PR creation when ticket is skipped instead of returning early
  ([#33](https://github.com/BrightNight-Energy/glu/pull/33),
  [`7827f47`](https://github.com/BrightNight-Energy/glu/commit/7827f479ff9eafd75371b74154b8373e53f0e93f))

### Refactoring

- Add testing to commands ([#32](https://github.com/BrightNight-Energy/glu/pull/32),
  [`175503e`](https://github.com/BrightNight-Energy/glu/commit/175503e731aa8aa23856d7c393aa62623a59ca31))


## v2.0.2 (2025-06-06)

### Bug Fixes

- Fix glu --help without config ([#31](https://github.com/BrightNight-Energy/glu/pull/31),
  [`5d4d65f`](https://github.com/BrightNight-Energy/glu/commit/5d4d65f48aa5ce082557a3135f0bf8be8e4cc1eb))

- Support python 3.10+ ([#29](https://github.com/BrightNight-Energy/glu/pull/29),
  [`0b190e0`](https://github.com/BrightNight-Energy/glu/commit/0b190e0f2d13a86c3515c63036ddd2d62a5bb993))


## v2.0.1 (2025-06-02)

### Bug Fixes

- Remove glean chat provider support ([#27](https://github.com/BrightNight-Energy/glu/pull/27),
  [`256c5bb`](https://github.com/BrightNight-Energy/glu/commit/256c5bb0d5e5415da9e0e674b0af371a3f61e150))


## v2.0.0 (2025-06-02)

### Features

- Support multiple ai providers and model selection
  ([`00fe3e9`](https://github.com/BrightNight-Energy/glu/commit/00fe3e94abeb2edb7450b800034dc23efa74ee63))


## v1.6.0 (2025-06-01)

### Features

- Add README and build publish step to ci ([#25](https://github.com/BrightNight-Energy/glu/pull/25),
  [`986ff3b`](https://github.com/BrightNight-Energy/glu/commit/986ff3b5567990bb10c0e065c55a5d752e4bb82c))


## v1.5.0 (2025-06-01)

### Features

- Interactive config init, dry-run commits & config refactor
  ([#21](https://github.com/BrightNight-Energy/glu/pull/21),
  [`e504947`](https://github.com/BrightNight-Energy/glu/commit/e5049475d07e32879801e26d6b3f6214cca70cfb))


## v1.4.0 (2025-05-31)

### Features

- Support local git operations and ai-driven commit/ticket generation
  ([#20](https://github.com/BrightNight-Energy/glu/pull/20),
  [`a5a1066`](https://github.com/BrightNight-Energy/glu/commit/a5a106696e31d6f043c9e8c9ee4431f58899b23b))


## v1.3.1 (2025-05-31)

### Bug Fixes

- Add version command to `glu` ([#16](https://github.com/BrightNight-Energy/glu/pull/16),
  [`69e1334`](https://github.com/BrightNight-Energy/glu/commit/69e1334ca24b4920220481989c87f3c91d1ce49e))


## v1.3.0 (2025-05-31)

### Features

- Add ability to generate Jira tickets with AI
  ([#14](https://github.com/BrightNight-Energy/glu/pull/14),
  [`f2b3d75`](https://github.com/BrightNight-Energy/glu/commit/f2b3d758276aa5539d1ca19af53be4005884c722))


## v1.2.0 (2025-05-26)

### Features

- Cli improvements ([#12](https://github.com/BrightNight-Energy/glu/pull/12),
  [`8d4c922`](https://github.com/BrightNight-Energy/glu/commit/8d4c9223b37ce19d18c44fd50cfb8eab83c29fbc))


## v1.1.0 (2025-05-26)

### Features

- Add support for using OpenAI, rather than Glean
  ([#10](https://github.com/BrightNight-Energy/glu/pull/10),
  [`23958ae`](https://github.com/BrightNight-Energy/glu/commit/23958ae9a1484957a41e4aa1155c3ee2367026f8))


## v1.0.1 (2025-05-26)

### Bug Fixes

- Fix to semantic release in ci/cd ([#8](https://github.com/BrightNight-Energy/glu/pull/8),
  [`02f50d4`](https://github.com/BrightNight-Energy/glu/commit/02f50d4f0cdef5cb53f74f4cedce3c5a0a3a9ba2))


## v1.0.0 (2025-05-26)

- Initial Release

## v0.0.1 (2025-05-25)

### Features

* Initial commit
