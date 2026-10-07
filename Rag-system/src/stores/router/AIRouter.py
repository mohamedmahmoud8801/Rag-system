import json

from stores.router.RouterEnums import RouterIntentEnum


class AIRouter:

    def __init__(self, generation_client):
        self.generation_client = generation_client

    async def classify(
        self,
        query: str,
        max_output_tokens: int = 100,
        temperature: float = 0.0,
    ):

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        prompt = f"""
You are an AI query router.

Your job is to classify the user's request into exactly ONE intent.

Available intents:

1. rag
   Use for normal question answering based on retrieved documents.

2. sql
   Use when the user asks about structured database data,
   records, counts, filtering, aggregation, comparisons, or database values.

3. knowledge_qa
   Use when the user explicitly wants an answer/explanation from
   the available knowledge documents.

4. knowledge_summary
   Use when the user asks to summarize, condense, or give a summary
   of provided knowledge.

5. knowledge_key_points
   Use when the user asks for key points, main points, or important points.

6. knowledge_notes
   Use when the user asks to create study notes or organized notes.

7. knowledge_flashcards
   Use when the user asks for flashcards.

8. knowledge_quiz
   Use when the user asks for a quiz, test, or questions with answers.

Important rules:

- Return exactly ONE intent.
- Do not answer the user's question.
- Do not generate SQL.
- Do not explain your decision.
- Return ONLY valid JSON.

Expected format:

{{
    "intent": "rag"
}}

User query:

{query}
"""

        response = self.generation_client.generate_text(
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        if not response:
            raise ValueError("Router returned an empty response.")

        parsed = self._parse_response(response)

        intent = parsed.get("intent")

        valid_intents = {
            item.value
            for item in RouterIntentEnum
        }

        if intent not in valid_intents:
            raise ValueError(
                f"Invalid router intent: {intent}"
            )

        return intent

    @staticmethod
    def _parse_response(response):

        if isinstance(response, dict):
            return response

        response = response.strip()

        if response.startswith("```"):
            response = response.replace("```json", "")
            response = response.replace("```", "")
            response = response.strip()

        try:
            return json.loads(response)

        except json.JSONDecodeError as e:

            raise ValueError(
                f"Invalid router JSON response: {response}"
            ) from e
