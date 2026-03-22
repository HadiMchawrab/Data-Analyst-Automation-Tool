import json
import logging


def extract_json(content: str) -> str:
    """Extract JSON from LLM response, handling ```json fenced code blocks."""
    content = content.strip()
    if "```json" in content:
        start = content.find("```json") + len("```json")
        end = content.find("```", start)
        if end == -1:
            return content[start:].strip()
        return content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        if end == -1:
            return content[start:].strip()
        return content[start:end].strip()
    return content


def parse_llm_json(content: str, context: str = "LLM response") -> dict:
    """Extract and parse JSON from an LLM response string."""
    extracted = extract_json(content)
    try:
        return json.loads(extracted)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON from {context}:\n{extracted}")
        raise ValueError(f"Invalid JSON in {context}") from e
