class KnowledgeFlashcardsService:
    TASK = "flashcard generation"
    def __init__(self, retrieval_service, generation_client, template_parser):
        self.retrieval_service = retrieval_service
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def generate(self, db_client, project, query="", file_id=None, **kwargs):
        documents = await self.retrieval_service.retrieve(project=project, query=query, file_id=file_id, db_client=db_client)
        if not documents: return {"flashcards": [], "documents": [], "query": query}

        lang_instruction = query if query else ""
        batch_size = 30
        all_cards = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            doc_prompts = [getattr(doc, "page_content", getattr(doc, "text", "")) for doc in batch]
            
            # 👇 بنمرر تعليمات اللغة هنا
            prompt = f"""
            {lang_instruction}
            
            بناءً على النص التالي، قم باستخراج بطاقات تعليمية (Flashcards).
            يجب أن يكون الرد **بصيغة JSON فقط**.
            الصيغة: [{{"front": "السؤال", "back": "الإجابة"}}]
            النص:
            {' '.join(doc_prompts)}
            """
            
            response = self.generation_client.generate_text(prompt=prompt)
            if response:
                import json
                try:
                    cleaned = response.replace("```json", "").replace("```", "").strip()
                    cards = json.loads(cleaned)
                    all_cards.extend(cards)
                except:
                    pass

        return {"flashcards": all_cards, "documents": documents, "query": query}