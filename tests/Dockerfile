FROM docker.io/library/python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /tests
COPY skills/byo-mcp-image-prep/scripts/probe.py /tests/probe.py
COPY tests/test_probe.py tests/test_package.py /tests/
COPY tests/check_bridge.py /tests/check_bridge.py
COPY skills /package/skills
COPY README.md /package/README.md
COPY tests/README.md /package/tests/README.md
COPY tests/Dockerfile tests/fixtures/Dockerfile.bridge /package/tests/
COPY evals /package/evals
USER 65534:65534
ENTRYPOINT ["python", "-m", "unittest", "discover", "-v"]
