# Contributing to SecBoard Community Edition

Thank you for your interest in SecBoard. This repository is the **Community Edition**
(Open Core) licensed under **AGPL v3**.

## Before you contribute

1. Read [LICENSING.md](LICENSING.md) — Open Core + Dual License model.
2. By submitting a contribution, you agree that your contribution is licensed
   under the same **AGPL-3.0-only** license as the project.
3. Contributions must not introduce dependencies incompatible with AGPL distribution.

## How to contribute

1. Fork the repository on GitHub.
2. Create a feature branch from `main`.
3. Make focused changes with clear commit messages.
4. Run `python manage.py check` and relevant tests.
5. Open a Pull Request with:
   - description of the change and motivation
   - steps to verify
   - note if documentation or migrations are included

## Code guidelines

- Match existing style in the touched module.
- Ship Django migrations with model changes.
- Use `gettext` / `{% trans %}` for user-visible strings.
- Do not commit `.env`, secrets, or license keys.

## Security

Report security issues responsibly to **security@secboard.online** — do not open
public issues for undisclosed vulnerabilities.

## Sanctions / Acceptable Use

Contributors and downstream users must comply with [Terms of Service](/terms-of-service/)
and sanctions policy. SecBoard may decline community license keys or contributions
from restricted jurisdictions or sanctioned entities.

## Enterprise modules

Some capabilities may be gated behind Enterprise Edition keys or commercial terms.
Open core modules in this repository are available under AGPL. See [LICENSING.md](LICENSING.md).

## Questions

- Documentation: https://secboard.online
- Community: GitHub Issues
- Commercial: support@secboard.online
