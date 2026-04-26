"""
Gemini API를 이용해 규칙 기반 텍스트 감지를 재검증한다.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import ClassifiedDebt


@dataclass
class ReviewDecision:
    accepted_rule_ids: set[str]
    reasons: dict[str, str]


class DebtReviewer(Protocol):
    def review_text(self, text: str, candidates: list[ClassifiedDebt]) -> Optional[ReviewDecision]: ...


@dataclass
class GeminiDebtReviewer:
    api_key: str
    model: str = "gemini-2.0-flash"
    language: str = "ko"

    def review_text(self, text: str, candidates: list[ClassifiedDebt]) -> Optional[ReviewDecision]:
        if not candidates:
            return ReviewDecision(accepted_rule_ids=set(), reasons={})

        prompt = self._build_prompt(text, candidates, self.language)
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": {
                    "type": "object",
                    "properties": {
                        "accepted_rule_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "reasons": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["accepted_rule_ids", "reasons"],
                },
            },
        }

        request = Request(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

        try:
            text_json = payload["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text_json)
            accepted = result.get("accepted_rule_ids", [])
            reasons = result.get("reasons", {})
            accepted_ids = {rid for rid in accepted if isinstance(rid, str)}
            reason_map = {
                rid: reason.strip()
                for rid, reason in reasons.items()
                if rid in accepted_ids and isinstance(reason, str) and reason.strip()
            }
            return ReviewDecision(accepted_rule_ids=accepted_ids, reasons=reason_map)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

    def analyze_debt(self, event: DebtItem) -> str:
        """Gemini를 사용하여 특정 인지부채 항목을 정밀 분석하고 가이드를 생성한다."""
        prompt = (
            f"당신은 소프트웨어 품질 및 보안 전문가입니다. 다음 감지된 인지부채(Epistemic Debt)를 분석해 주세요.\n\n"
            f"- 주장 내용: \"{event.claim}\"\n"
            f"- 리스크 수준: {event.risk_level.value}\n"
            f"- 감지된 규칙: {event.rule_id}\n"
            f"- 발생 문맥: {event.source_context or '없음'}\n\n"
            f"이 내용에 대해 **반드시 한국어 3문장 이내로** 핵심만 요약해 주세요:\n"
            f"1. 이 주장의 기술적 위험성\n"
            f"2. 해소를 위한 구체적인 검증 작업\n"
            f"3. `debt repay` 명령어 예시 (명령어는 문장 수에 포함 안 됨)\n"
        )

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7}
        }

        request = Request(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )

        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"Gemini 분석 중 오류 발생: {e}"

    @staticmethod
    def _build_prompt(text: str, candidates: list[ClassifiedDebt], language: str, action_history: list[str] = None) -> str:
        candidate_lines = "\n".join(
            f"- {c.rule_id}: {c.claim}"
            for c in candidates
        )
        
        history_context = ""
        if action_history:
            history_context = f"Recent actions: {', '.join(action_history[-5:])}\n" if language == "en" else f"최근 실행한 액션: {', '.join(action_history[-5:])}\n"

        if language == "en":
            return (
                "You are validating epistemic-debt detections.\n"
                "Keep only the rule IDs that represent a real unsupported claim in the text.\n"
                "Drop examples, explanations of the tool itself, quotations of patterns, and meta-instructions.\n"
                "For each accepted rule ID, provide a short explanation of why it is a real issue in this text.\n"
                "Write every explanation in English.\n"
                "Return only rule IDs from the provided candidate list.\n\n"
                f"{history_context}"
                f"Text:\n{text}\n\n"
                f"Candidates:\n{candidate_lines}\n"
            )

        return (
            "당신은 epistemic-debt 감지를 검토하는 심사자입니다.\n"
            "텍스트 안에서 실제로 근거가 부족한 주장이나 불확실한 단정에 해당하는 rule ID만 남기세요.\n"
            "에이전트의 이전 실행 맥락을 고려하여, 실제로 행한 적 없는 작업의 결과를 추측하고 있는지 확인하세요.\n"
            "예시 문장, 도구 설명, 패턴 인용, 메타 안내문은 제외하세요.\n"
            "채택한 각 rule ID마다 왜 문제가 되는지 짧게 설명하세요.\n"
            "설명은 반드시 한국어로 작성하세요.\n"
            "결과에는 제공된 후보 목록의 rule ID만 사용하세요.\n\n"
            f"{history_context}"
            f"Text:\n{text}\n\n"
            f"Candidates:\n{candidate_lines}\n"
        )


def gemini_api_key_from_env() -> Optional[str]:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
