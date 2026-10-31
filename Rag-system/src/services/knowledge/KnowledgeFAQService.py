class KnowledgeFAQService:
    TASK = "faq"
    def __init__(self, retrieval_service, generation_client, template_parser):
        self.retrieval_service = retrieval_service
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def generate(self, db_client, project, query="", file_id=None, **kwargs):
        documents = await self.retrieval_service.retrieve(project=project, query=query, file_id=file_id, db_client=db_client)
        if not documents: return {"faq": None, "documents": [], "query": query}

        lang_instruction = query if query else ""
        full_text = "\n\n".join([getattr(d, "page_content", getattr(d, "text", "")) for d in documents])
        if len(full_text) > 15000:
            full_text = full_text[:15000]

        # 👇 شيلنا "باللغة العربية" ومررنا تعليمات اللغة
        prompt = f"{lang_instruction}\n\nاستخرج أهم 5 أسئلة شائعة وإجاباتها من النص التالي:\n\n{full_text}"
        response = self.generation_client.generate_text(prompt=prompt)
        return {"faq": response, "documents": documents, "query": query}