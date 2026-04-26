"""
공유 픽스처 모음.
각 테스트는 독립된 tmp_path 레지스트리를 사용해서 서로 간섭하지 않는다.
"""
import pytest
from pathlib import Path

from app.engine import RuleEngine
from app.models import Session
from app.parsers import ActionClassifier, RuleBasedClassifier
from app.registry import DebtRegistry
from app.rules import Rules


@pytest.fixture(scope="session")
def rules():
    """rules.json을 한 번만 로드해서 세션 전체에서 재사용한다."""
    return Rules.load(Path("rules.json"))


@pytest.fixture
def classifier(rules):
    return RuleBasedClassifier(rules)


@pytest.fixture
def action_classifier(rules):
    return ActionClassifier(rules)


@pytest.fixture
def registry(tmp_path):
    """테스트마다 격리된 빈 레지스트리를 제공한다."""
    DebtRegistry.init(tmp_path)
    return DebtRegistry(tmp_path)


@pytest.fixture
def session(registry):
    return registry.create_session("/test/project")


@pytest.fixture
def engine(rules, classifier, action_classifier, registry):
    return RuleEngine(rules, classifier, action_classifier, registry)
