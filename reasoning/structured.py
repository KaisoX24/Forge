from __future__ import annotations
import logging
from typing import Callable,TypeVar,Any,overload
from langchain.messages import AIMessage,HumanMessage
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

logger=logging.getLogger(__name__)
T=TypeVar("T",bound=BaseModel)
R=TypeVar("R")

def _describe_error(err: BaseException) -> str:
    "Short, model-readable description of why parsing failed."
    cause = err.__cause__
    errors = getattr(cause, "errors", None)
    if callable(errors):
        lines = []
        for e in errors():
            where = ".".join(str(p) for p in e["loc"]) or "output"
            lines.append(f"- {where}: {e['msg']}")
        return "The JSON did not match the required format:\n" + "\n".join(lines)
    text = str(err)
    if "Invalid json" in text:
        return "The reply was not valid JSON."
    return text[:400]

class StructuredResult:
    "Calls a model for structured output, retrying with feedback. Knows nothing about retrieval."
    def __init__(
        self,
        llm,
        *,
        max_attempts:int=3,
        error_cls:type[Exception]
    ):
        self.ERROR=error_cls
        self.llm=llm
        self.max_attempts=max_attempts

    @overload
    def call(self, schema: type[T], messages: list[BaseMessage], *, label: str,
             validate: Callable[[T], None] | None = None) -> T: ...
    
    @overload
    def call(self, schema: type[T], messages: list[BaseMessage], *, label: str,
             validate: Callable[[T], R]) -> T | R: ...
    
    def call(
        self,
        schema: type[T],
        messages: list[BaseMessage],
        *,
        label: str,
        validate: Callable[[T], Any] | None = None,
    ) -> Any:
            
        structured = self.llm.with_structured_output(schema, include_raw=True)
        feedback:list[BaseMessage]=[]
        last_problem = "no attempt was made"
        for attempt in range(1, self.max_attempts + 1):
            try:
            # Runs for max 3 iterations if any error occurs store the detail and pass it to llm for retry
                result = structured.invoke(list(messages)+feedback)
            except Exception as exc:
                last_problem = f"model call failed: {type(exc).__name__}: {exc}"
                logger.warning("%s attempt %d failed: %s", label, attempt, last_problem)
                continue
            raw, parsed, error = result.get("raw"), result.get("parsed"), result.get("parsing_error")
            self._log_attempt(label, attempt, raw)

            problem = None
            replacement=None
            if parsed is None:
                problem = _describe_error(error) if error else "The reply was empty."
            elif validate is not None:
                try:
                    replacement=validate(parsed)
                except ValueError as exc:
                    problem = str(exc)

            if problem is None:
                return parsed if replacement is None else replacement
            
            logger.warning("%s attempt %d rejected: %s", label, attempt, problem.replace("\n", " | "))
            logger.error(
                "\n========== FAILED GENERATION ATTEMPT ==========\n"
                "LABEL: %s\n"
                "ATTEMPT: %d\n"
                "VALIDATION ERROR:\n%s\n"
                "RAW MODEL RESPONSE:\n%s\n"
                "================================================",
                label,
                attempt,
                problem,
                self._text(raw),
            )

            if parsed is not None:
                logger.error(
                    "PARSED OUTPUT:\n%s",
                    parsed.model_dump_json(indent=2),
                )
            last_problem=problem
            previous = self._text(raw)
            if parsed is None and previous.strip():
                feedback = [
                    AIMessage(content=previous),
                    HumanMessage(content=f"Your previous reply was rejected:\n{problem}\n\n"
                                        "Reply again with corrected JSON only."),
                ]

            else:
                feedback = [
                    HumanMessage(content=f"A previous attempt was rejected for this reason:\n{problem}\n\n"
                                        "Avoid it. Reply with the JSON only.")
                ]

        raise self.ERROR(f"{label}: gave up after {self.max_attempts} attempts. Last problem: {last_problem}")

    @staticmethod
    def _text(raw) -> str:
        # Handles Extraction of messages from the llms response
        content = getattr(raw, "content", "")
        return content if isinstance(content, str) else str(content)
    
    def _log_attempt(self, label: str, attempt: int, raw) -> None:
        # Basic Diagonostic for evaluation
        meta = getattr(raw, "response_metadata", None) or {}
        prompt_tokens = meta.get("prompt_eval_count")
        output_tokens = meta.get("eval_count")
        done_reason = meta.get("done_reason")
        logger.info(
            "%s attempt %d: done_reason=%s prompt_tokens=%s output_tokens=%s empty=%s",
            label, attempt, done_reason, prompt_tokens, output_tokens, not self._text(raw).strip(),
        )
        num_ctx = getattr(self.llm, "num_ctx", None)
        if prompt_tokens and num_ctx and prompt_tokens >= 0.9 * num_ctx:
            logger.warning("%s: prompt used %s of %s context tokens; truncation is likely", label, prompt_tokens, num_ctx)
        if done_reason == "length":
            logger.warning("%s: generation stopped at the token limit before finishing", label)