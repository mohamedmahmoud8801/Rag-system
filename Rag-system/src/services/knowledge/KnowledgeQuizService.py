class KnowledgeQuizService:
    TASK = "quiz generation"
    def __init__(self, retrieval_service, generation_client, template_parser):
        self.retrieval_service = retrieval_service
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def generate(self, db_client, project, query="", file_id=None, **kwargs):
        documents = await self.retrieval_service.retrieve(project=project, query=query, file_id=file_id, db_client=db_client)
        if not documents: return {"quiz": [], "documents": [], "query": query}

        lang_instruction = query if query else ""
        batch_size = 30
        all_questions = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            doc_prompts = [getattr(doc, "page_content", getattr(doc, "text", "")) for doc in batch]
            
            # 👇 بنمرر تعليمات اللغة هنا
            prompt = f"""
            {lang_instruction}
            
            بناءً على النص التالي، قم بإنشاء أسئلة اختيار من متعدد (حد أقصى 5 أسئلة).
            يجب أن يكون الرد **بصيغة JSON فقط**.
            الصيغة: [{{"question": "السؤال", "options": ["أ", "ب", "ج", "د"], "answer": "الإجابة الصحيحة"}}]
            النص:
            {' '.join(doc_prompts)}
            """
            
            response = self.generation_client.generate_text(prompt=prompt)
            if response:
                import json
                try:
                    cleaned = response.replace("```json", "").replace("```", "").strip()
                    questions = json.loads(cleaned)
                    all_questions.extend(questions)
                except:
                    pass

        return {"quiz": all_questions, "documents": documents, "query": query}