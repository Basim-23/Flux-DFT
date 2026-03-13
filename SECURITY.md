# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 2.0.x | ✅ Active |
| < 2.0 | ❌ Not supported |

## Reporting a Vulnerability

If you discover a security vulnerability in FluxDFT, **please do not open a public issue**. Instead:

1. **Email the maintainer directly** or use the [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) feature on this repository.
2. Provide a clear description of the vulnerability, including steps to reproduce it.
3. Allow reasonable time for a fix before any public disclosure.

## Security Considerations

FluxDFT interacts with the following external services and protocols. Users should be aware of the associated security implications:

### SSH / HPC Connections
- FluxDFT includes a built-in SSH client (via [Paramiko](https://www.paramiko.org/)) for connecting to remote HPC clusters.
- SSH credentials and keys are managed locally and are **never** transmitted to third-party services.
- Users are responsible for securing their SSH private keys and passwords.

### API Keys
- **Materials Project API Key** — Stored locally in your user configuration. Never shared externally beyond API calls to `materialsproject.org`.
- **OpenAI API Key** — Used for FluxAI features. Transmitted only to OpenAI's API servers over HTTPS.
- **Supabase Credentials** — Used for optional cloud profile sync. Transmitted only to your configured Supabase instance.

### Local File Access
- FluxDFT reads and writes files (input files, pseudopotentials, output data) within the project directory.
- No files are uploaded to external servers unless explicitly initiated by the user (e.g., HPC job submission).

## Dependencies

FluxDFT relies on open-source dependencies listed in `requirements.txt` and `pyproject.toml`. We encourage users to keep dependencies up to date to benefit from security patches:

```bash
pip install --upgrade -r requirements.txt
```

## Acknowledgments

We appreciate responsible disclosure and thank all security researchers who help keep FluxDFT safe.
