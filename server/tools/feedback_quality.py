"""
Feedback quality analysis and improvement - LLM-powered content enhancement.

GENERIC MODULE: Copy to any MCP for quality checking.
Works with any issue type (bug/feature/improvement).
"""

import re
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FeedbackQualityAnalyzer:
    """
    Analyzes feedback quality and generates improvement suggestions.
    Uses heuristic analysis + LLM-powered rewriting for unclear content.
    """

    def __init__(self):
        # Quality scoring weights
        self.weights = {
            "vague_language": -2,
            "missing_details": -3,
            "grammar_issues": -1,
            "good_structure": +2,
            "specific_examples": +2,
            "clear_steps": +2,
        }

        # Vague words that reduce quality score
        self.vague_words = [
            "something", "somehow", "maybe", "sometimes", "stuff",
            "things", "whatever", "kind of", "sort of", "etc",
            "and so on", "or something", "i think", "probably"
        ]

        # Required elements by issue type
        self.required_elements = {
            "bug": ["what happened", "expected behavior", "actual behavior"],
            "feature": ["what feature", "why needed", "expected behavior"],
            "improvement": ["what to improve", "why", "expected outcome"]
        }

    def analyze_feedback_quality(
        self,
        issue_type: str,
        title: str,
        description: str
    ) -> Dict:
        """
        Analyze feedback quality and return score + suggestions.

        Args:
            issue_type: "bug", "feature", or "improvement"
            title: Issue title
            description: Issue description

        Returns:
            {
                "quality_score": 0-10,
                "issues_found": [list of problems],
                "suggestions": [list of improvements],
                "needs_improvement": bool,
                "severity": "low" | "medium" | "high"
            }
        """
        combined = f"{title} {description}".lower()
        issues_found = []
        suggestions = []
        score = 7  # Start with decent score

        # Check 1: Vague language
        vague_count = sum(1 for word in self.vague_words if word in combined)
        if vague_count > 3:
            issues_found.append(f"Contains {vague_count} vague words (something, maybe, etc.)")
            suggestions.append("Be more specific - avoid words like 'something', 'somehow', 'maybe'")
            score += self.weights["vague_language"] * min(vague_count, 3)

        # Check 2: Length and detail
        if len(description) < 50:
            issues_found.append("Description is very short (less than 50 characters)")
            suggestions.append("Add more details to help us understand the issue")
            score += self.weights["missing_details"]

        # Check 3: Missing required elements
        required = self.required_elements.get(issue_type, [])
        missing = []
        for element in required:
            # Simple keyword check
            keywords = element.split()
            if not any(kw in combined for kw in keywords):
                missing.append(element)

        if missing:
            issues_found.append(f"Missing key information: {', '.join(missing)}")
            suggestions.append(f"Please describe: {', '.join(missing)}")
            score += self.weights["missing_details"]

        # Check 4: Grammar and structure
        # Simple checks for common issues
        if re.search(r'\b[a-z][a-z\s]{30,}[.!?]', description):  # Long sentence without caps
            issues_found.append("May have grammar issues (missing capitalization)")
            suggestions.append("Check capitalization and punctuation")
            score += self.weights["grammar_issues"]

        if description.count('.') == 0 and len(description) > 50:
            issues_found.append("No sentence breaks in description")
            suggestions.append("Break text into clear sentences")
            score += self.weights["grammar_issues"]

        # Check 5: Positive signals
        if any(word in combined for word in ["steps to reproduce", "expected", "actual", "should be", "currently"]):
            score += self.weights["good_structure"]

        if re.search(r'1\.|2\.|step 1|step 2|\n-|\n\*', description):
            score += self.weights["clear_steps"]

        if any(word in combined for word in ["example", "for instance", "specifically", "when i"]):
            score += self.weights["specific_examples"]

        # Clamp score to 0-10
        score = max(0, min(10, score))

        # Determine severity
        if score >= 7:
            severity = "low"
            needs_improvement = False
        elif score >= 4:
            severity = "medium"
            needs_improvement = True
        else:
            severity = "high"
            needs_improvement = True

        return {
            "quality_score": round(score, 1),
            "issues_found": issues_found,
            "suggestions": suggestions,
            "needs_improvement": needs_improvement,
            "severity": severity,
            "vague_word_count": vague_count if vague_count > 3 else 0
        }

    def generate_improvement_prompt(
        self,
        issue_type: str,
        title: str,
        description: str,
        quality_analysis: Dict
    ) -> str:
        """
        Generate prompt for LLM to improve unclear feedback.

        This prompt guides Claude on how to rewrite user feedback
        to be clearer and more actionable.
        """

        issues_section = ""
        if quality_analysis["issues_found"]:
            issues_list = "\n".join(f"- {issue}" for issue in quality_analysis["issues_found"])
            issues_section = f"\n**Issues detected:**\n{issues_list}\n"

        prompt = f"""You are helping a user improve their feedback for a software project.

**Issue Type:** {issue_type}
**Current Title:** {title}
**Current Description:** {description}

**Quality Score:** {quality_analysis['quality_score']}/10
{issues_section}

**Your task:**
Rewrite this feedback to be clearer, more specific, and more actionable. Follow these guidelines:

1. **For Bug Reports:**
   - What happened? (actual behavior)
   - What should happen? (expected behavior)
   - Steps to reproduce (if applicable)
   - Any error messages or relevant details

2. **For Feature Requests:**
   - What feature do you want?
   - Why is it needed? (use case)
   - How should it work?

3. **For Improvements:**
   - What should be improved?
   - Why is the current state problematic?
   - What would be better?

**Important:**
- Keep the user's original meaning and intent
- Remove vague words (something, somehow, maybe, etc.)
- Add structure with clear sections or bullet points
- Be specific and concrete
- Keep it concise but complete
- Maintain the user's tone (don't make it overly formal if they wrote casually)

**Output Format:**
Return ONLY a JSON object with this exact structure:
{{
  "improved_title": "Clear, specific title (max 100 chars)",
  "improved_description": "Well-structured description with all key details",
  "changes_made": ["List of improvements made"]
}}

Do not include any text outside the JSON object."""

        return prompt

    def parse_improved_feedback(self, llm_response: str) -> Dict:
        """
        Parse LLM response to extract improved feedback.

        Args:
            llm_response: Raw response from LLM

        Returns:
            {
                "improved_title": str,
                "improved_description": str,
                "changes_made": [list],
                "error": str (if parsing failed)
            }
        """
        import json

        try:
            # Try to extract JSON from response
            # Handle cases where LLM adds markdown code blocks
            content = llm_response.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*\n', '', content)
                content = re.sub(r'\n```\s*$', '', content)

            # Parse JSON
            result = json.loads(content)

            # Validate required fields
            if "improved_title" not in result or "improved_description" not in result:
                return {
                    "error": "LLM response missing required fields",
                    "raw_response": llm_response
                }

            return {
                "improved_title": result["improved_title"],
                "improved_description": result["improved_description"],
                "changes_made": result.get("changes_made", []),
                "error": None
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "error": f"Could not parse LLM response as JSON: {str(e)}",
                "raw_response": llm_response
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing feedback: {e}")
            return {
                "error": f"Unexpected error: {str(e)}",
                "raw_response": llm_response
            }


# Global instance
_quality_analyzer = FeedbackQualityAnalyzer()


def get_quality_analyzer() -> FeedbackQualityAnalyzer:
    """Get the global quality analyzer instance."""
    return _quality_analyzer


def quick_quality_check(issue_type: str, title: str, description: str) -> Tuple[bool, str, Dict]:
    """
    Quick quality check with user-friendly message.

    Returns:
        (is_good_quality, message, analysis_dict)
    """
    analyzer = get_quality_analyzer()
    analysis = analyzer.analyze_feedback_quality(issue_type, title, description)

    if not analysis["needs_improvement"]:
        return True, "✅ Feedback looks good!", analysis

    # Build friendly message
    score = analysis["quality_score"]
    issues = analysis["issues_found"]

    message = f"📊 **Quality Check:** {score}/10\n\n"

    if analysis["severity"] == "high":
        message += "⚠️ **Your feedback needs improvement:**\n"
    else:
        message += "💡 **Suggestions to improve your feedback:**\n"

    for issue in issues[:3]:  # Show max 3 issues
        message += f"• {issue}\n"

    if analysis["suggestions"]:
        message += f"\n**How to improve:**\n"
        for suggestion in analysis["suggestions"][:3]:
            message += f"• {suggestion}\n"

    message += f"\n💬 Would you like me to help rewrite this to be clearer?"

    return False, message, analysis
