FROM docker.io/library/python:3.13-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
WORKDIR /checks
COPY probe.py /checks/probe.py
USER 65534:65534
ENTRYPOINT ["python", "/checks/probe.py"]
