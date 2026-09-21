from pathlib import Path

REPO = Path(__file__).parents[1]


def test_compose_trusted_runtime_sources_exist() -> None:
    required = (
        REPO / "docker" / "Dockerfile.broker",
        REPO / "docker" / "Dockerfile.egress-proxy",
        REPO / "harness" / "broker_main.py",
        REPO / "harness" / "graphiti_broker.py",
        REPO / "scripts" / "egress_proxy.py",
    )
    assert all(path.is_file() for path in required)


def test_trusted_runtime_images_drop_privileges_and_copy_only_runtime_code() -> None:
    broker = (REPO / "docker" / "Dockerfile.broker").read_text(encoding="utf-8")
    egress = (REPO / "docker" / "Dockerfile.egress-proxy").read_text(encoding="utf-8")

    assert "COPY harness/broker.py" in broker
    assert "COPY harness/broker_main.py" in broker
    assert "COPY harness/graphiti_broker.py" in broker
    assert "COPY ." not in broker
    assert "USER 65532:65532" in broker

    assert "COPY scripts/egress_proxy.py" in egress
    assert "COPY ." not in egress
    assert "USER 65532:65532" in egress
