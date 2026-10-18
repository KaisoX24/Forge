from langchain.tools import tool
from retrieval.retriever import Retriever
from models.data_models import RetrievedDocument

class RetrievalTool:
    def __init__(self,retriever:Retriever):
        self.retriver=retriever

    @tool(
    description=(
        "Retrieve relevant documentation from the knowledge base. "
        "Provide a specific query describing the concept, API, behavior, "
        "or implementation detail for which documentation is needed."
        )
    )
    def retrieve_documentation(self,query: str)->list[RetrievedDocument]:
        return self.retriver.retrieve(query)
