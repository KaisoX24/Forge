from langchain.tools import tool
from retrieval.retriever import Retriever
def make_retrieval_tool(retriever: Retriever):
    @tool(
    description=(
        "Retrieve relevant documentation from the knowledge base. "
        "Provide a specific query describing the concept, API, behavior, "
        "or implementation detail for which documentation is needed."
        )
    )
    def retrieve_documentation(query: str)->str:
        docs=retriever.retrieve(query)
        if not docs:
            return "No relevant documentation found for this query."
        return "\n\n---\n\n".join(
                f"Source: {d.metadata.get('url', d.metadata.get('source_file'))}"
                f"{d.metadata.get('anchor') or ''}\n{d.content}"
                for d in docs
            )
    return retrieve_documentation

    
