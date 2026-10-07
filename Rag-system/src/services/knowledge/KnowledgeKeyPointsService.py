class KnowledgeKeyPointsService:

    TASK = "key points extraction"

    def __init__(
        self,
        retrieval_service,
        generation_client,
        template_parser,
    ):
        self.retrieval_service = retrieval_service
        self.generation_client = generation_client
        self.template_parser = template_parser

    async def extract(
        self,
        project,
        query: str = "",
        limit: int = 10,
        top_k: int = 5,
        max_output_tokens: int = None,
        temperature: float = None,
    ):

        documents = await self.retrieval_service.retrieve(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
        )

        if not documents:
            return {
                "key_points": [],
                "documents": [],
            }

        system_prompt = self.template_parser.get(
            group="knowledge",
            key="system_prompt",
            vars={"task": self.TASK},
        )

        footer_prompt = self.template_parser.get(
            group="knowledge",
            key="footer_prompt",
            vars={
                "task": self.TASK,
                "query": query,
            },
        )

        document_prompts = []

        for index, document in enumerate(documents, start=1):

            chunk_text = getattr(
                document,
                "page_content",
                getattr(document, "text", ""),
            )

            document_prompt = self.template_parser.get(
                group="knowledge",
                key="document_prompt",
                vars={
                    "doc_num": index,
                    "chunk_text": chunk_text,
                },
            )

            if document_prompt:
                document_prompts.append(document_prompt)

        prompt = "\n\n".join(
            [system_prompt]
            + document_prompts
            + [footer_prompt]
        )

        response = self.generation_client.generate_text(
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return {
            "key_points": response,
            "documents": documents,
            "query": query,
        }