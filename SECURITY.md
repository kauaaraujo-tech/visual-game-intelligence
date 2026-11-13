# Security policy

VGI processes explicitly selected local evidence. It has no automatic telemetry or external evidence upload. This design limits routine exposure but does not make arbitrary input files safe or provide an execution sandbox.

## Reporting a vulnerability

For a security-sensitive issue, use the repository's private vulnerability reporting option in the [Security tab](https://github.com/kauaaraujo-tech/visual-game-intelligence/security) if it is enabled. Do not put exploit details, personal data, private logs, or game assets in a public issue. If private reporting is unavailable, open a minimal public issue requesting a private reporting channel without sensitive details.

Include the affected revision, Python and optional-dependency versions, expected and observed behavior, and a minimal synthetic reproduction when possible. Do not attach real user evidence or proprietary files. No response-time commitment or independently audited security guarantee is currently published.

## Supported scope

The project is at an early implementation stage. Fixes target the current maintained repository version; a security maintenance schedule for older releases has not been established. No real-game security assessment, cross-platform audit, or external penetration test is claimed.

Relevant issues include path-boundary escapes, unintended network access, evidence overwrite, unsafe handling of model responses, and parser behavior that permits practical resource exhaustion. Unsupported game formats and ordinary heuristic false positives are generally correctness issues, though a concrete security consequence may make them security-relevant.

## Operational boundaries

- Session source paths must be relative and remain within the input directory after resolution. Numeric, identity, and timing checks reject many malformed records. Run under an ordinary user account and review evidence origins.
- The collector requires an explicit closed-session declaration, reads only its known native metrics/log filenames, and checks for changes during copying. That declaration is not verification that the game process has ended. Individual copied files are limited to 256 MiB.
- Image analysis bounds capture count, encoded bytes, and decoded pixels. Optional Pillow decodes images inside the current process. The bounds are not a general hostile-file sandbox; keep optional dependencies maintained and avoid untrusted evidence.
- Some parsing and report operations still read complete local files into memory. Global resource isolation is not implemented.
- Reports retain metadata and log context and may include copied evidence images. They are not automatically redacted or safe to publish. SHA256 provenance authenticates neither the producer nor the declared recording conditions.
- Output checks reduce accidental overwrites. Failed operations can leave partial new output directories; choose a fresh output when retrying and preserve original inputs.
- `brief` performs no inference. Only an explicit `ai-local` invocation makes a model request, to literal `127.0.0.1`, with proxy lookup and DNS bypassed and redirects rejected. The reduced brief omits raw logs, pixels, paths, and source code, but free-text IDs/event kinds can still contain sensitive information.
- VGI cannot verify whether a server running on loopback forwards data elsewhere. Inspect the brief and your server configuration before requesting assistance.
- Model replies are untrusted text. Evidence-reference validation does not make a claim true, and VGI does not execute model-suggested commands or apply fixes.

The CLI does not launch games, alter game configuration, clear caches, install models, create scheduled tasks, or install a persistent service. Do not add automatic external data uploads or execution of untrusted suggestions in a contribution.
