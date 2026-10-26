# tls-sok

Code for the SoK on malicious TLS traffic classifiers (see `../plan.md`).

Layout:

- `src/tlssok/` — feature pipeline (Zeek + NFStream + handshake parser with visibility tags)
- `scripts/` — dataset checks and utilities
- `tests/` — pytest tests
- `review/` — literature screening log

Runs on the lab A2 machine in `~/tls-sok` with `.venv` (Python 3.12, nfstream 6.6, pandas 3.1, scikit-learn 1.9). Data lives in `~/tls-sok-data/`.
