from langchain.tools import tool
from retrieval.retriever import Retriever
from models.data_models import RetrievedDocument


class RetrievalTool:
    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def retrieve(self, query: str) -> list[RetrievedDocument]:
        return self.retriever.retrieve(query)

    def format_documents(
        self,
        documents: list[RetrievedDocument],
    ) -> str:

        if not documents:
            return "No relevant documentation found for this query."

        return "\n\n---\n\n".join(
            f"Source: {d.metadata.get('url', d.metadata.get('source_file'))}"
            f"{d.metadata.get('anchor') or ''}\n"
            f"{d.content}"
            for d in documents
        )

    def as_tool(self):

        @tool(
            description=(
                "Retrieve relevant documentation from the knowledge base. "
                "Provide a specific query describing the concept, API, "
                "behavior, or implementation detail for which documentation "
                "is needed."
            )
        )
        def retrieve_documentation(query: str) -> str:
            documents = self.retrieve(query)
            return self.format_documents(documents)

        return retrieve_documentation