class KnowledgeMindMapService:
    TASK = "mindmap"
    def __init__(self, retrieval_service, generation_client, template_parser):
        self.retrieval_service = retrieval_service
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def generate(self, db_client, project, query="", file_id=None, **kwargs):
        documents = await self.retrieval_service.retrieve(project=project, query=query, file_id=file_id, db_client=db_client)
        if not documents: return {"mindmap": None, "documents": [], "query": query}

        lang_instruction = query if query else ""
        full_text = "\n\n".join([getattr(d, "page_content", getattr(d, "text", "")) for d in documents])
        if len(full_text) > 15000:
            full_text = full_text[:15000]

        # 👇 شيلنا "باللغة العربية" ومررنا تعليمات اللغة
        prompt = f"""
        {lang_instruction}
        
        أنت خبير في تنظيم المعرفة. قم بإنشاء "خريطة ذهنية" للمحتوى التالي.
        استخدم تنسيق Markdown (عناوين #، ونقاط -) لتمثيل الهيكل الشجري والعلاقات.
        
        المحتوى:
        {full_text}
        """
        response = self.generation_client.generate_text(prompt=prompt)
        return {"mindmap": response, "documents": documents, "query": query}