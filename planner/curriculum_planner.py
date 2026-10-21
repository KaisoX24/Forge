from models.data_models import Curriculum, RetrievedDocument
from langchain.messages import HumanMessage, SystemMessage
from retrieval.retrieval_tool import RetrievalTool
from reasoning.model import get_llm,get_online_llm
from pathlib import Path


class CurriculumPlanner:
    def __init__(
        self,
        model_name: str,
        retrieval: RetrievalTool,
    ):
        self.retrieval = retrieval
        self.retrieval_tool = retrieval.as_tool()

        self.llm = get_llm(model_name)
        self.llm_with_tools = self.llm.bind_tools(
            [self.retrieval_tool]
        )

        self.system_message = Path(
            Path(__file__).parent.parent
            / "reasoning"
            / "system_messages"
            / "curriculum_planner.txt"
        ).read_text(encoding="utf-8")

    def _run_research(
        self,
        messages: list,
        max_itr: int = 5,
    ) -> list[RetrievedDocument]:

        research_documents = []

        for _ in range(max_itr):
            response = self.llm_with_tools.invoke(messages)

            if not response.tool_calls:
                return research_documents

            messages.append(response)

            for tool_call in response.tool_calls:
                query = tool_call["args"]["query"]

                documents = self.retrieval.retrieve(query)

                tool_result = self.retrieval_tool.invoke(tool_call)

                messages.append(tool_result)

                research_documents.extend(documents)

        raise RuntimeError(
            "Curriculum planner exceeded maximum research iterations."
        )

    def _generate_curriculum(
        self,
        technology: str,
        research_documents: list[RetrievedDocument],
    ) -> Curriculum:

        research_context = "\n\n---\n\n".join(
            f"Source: {doc.metadata.get('url', doc.metadata.get('source_file'))}"
            f"{doc.metadata.get('anchor') or ''}\n"
            f"{doc.content}"
            for doc in research_documents
        )

        messages = [
            SystemMessage(content=self.system_message),
            HumanMessage(
                content=(
                    f"Create a learning curriculum for {technology}.\n\n"
                    "Use the following retrieved documentation as the "
                    "primary factual source for the curriculum.\n\n"
                    f"{research_context}"
                )
            ),
        ]

        structured_llm = self.llm.with_structured_output(Curriculum)

        return structured_llm.invoke(messages)

    def create_curriculum(self, technology: str) -> Curriculum:

        messages = [
            SystemMessage(content=self.system_message),
            HumanMessage(
                content=f"Create a learning curriculum for {technology}."
            ),
        ]

        research_documents = self._run_research(messages)

        return self._generate_curriculum(
            technology,
            research_documents,
        )