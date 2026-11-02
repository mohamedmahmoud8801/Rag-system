class KnowledgeSummaryService:
    TASK = "summarization"
    def __init__(self, retrieval_service, generation_client, template_parser):
        self.retrieval_service = retrieval_service
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def summarize(self, db_client, project, query="", file_id=None, **kwargs):
        documents = await self.retrieval_service.retrieve(project=project, query=query, file_id=file_id, db_client=db_client)
        if not documents: return {"summary": None, "documents": [], "query": query}

        lang_instruction = query if query else ""
        batch_size = 30
        partial_summaries = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            doc_prompts = [getattr(doc, "page_content", getattr(doc, "text", "")) for doc in batch]
            
            # 👇 لاحظ هنا بنستخدم partial_prompt (مش final_prompt)
            partial_prompt = f"{lang_instruction}\n\nلخص الجزء التالي من النص:\n\n" + "\n\n".join(doc_prompts)
            
            partial_res = self.generation_client.generate_text(prompt=partial_prompt)
            if partial_res: partial_summaries.append(partial_res)

        if not partial_summaries: return {"summary": "لم يتمكن النظام من التلخيص.", "documents": documents, "query": query}

        # 2. المرحلة الثانية (Reduce): بنجمع الملخصات ونعمل تقرير نهائي مفصل
        # 👇 هنا بنستخدم الـ final_prompt الجديد اللي بيطلب تفاصيل وعناوين
        final_prompt = f"""
{lang_instruction}

أنت خبير تلخيص.
لقد قمت بتلخيص أجزاء من فيديو طويل. إليك الملخصات الجزئية:
{' '.join(partial_summaries)}

المطلوب:
دمج هذه الملخصات في تقرير نهائي شامل ومفصل جداً.
- قسّم التقرير إلى عناوين رئيسية وعناوين فرعية.
- اذكر كل التفاصيل والأرقام والأسماء المهمة.
- لا تختصر، اجعل التقرير طويلاً ومفيداً للمذاكرة.

التقرير النهائي:
"""
        response = self.generation_client.generate_text(prompt=final_prompt)
        
        return {"summary": response, "documents": documents, "query": query}