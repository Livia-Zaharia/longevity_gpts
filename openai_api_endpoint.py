import time
from pathlib import Path
from fastapi import FastAPI, Request
from just_agents.llm_session import LLMSession
from literature.routes import _hybrid_search
from genetics.main import rsid_lookup, gene_lookup, pathway_lookup, disease_lookup, sequencing_info
from clinical_trials.clinical_trails_router import _process_sql, clinical_trails_full_trial
from precious3GPT.p3gpt_tool import get_omics_data, get_enrichment
from precious3GPT.routes import omics_router
from starlette.responses import StreamingResponse
from dotenv import load_dotenv
from just_agents.utils import RotateKeys
from fastapi.middleware.cors import CORSMiddleware
from open_genes.tools import db_query
import loguru
import yaml

log_path = Path(__file__)
log_path = Path(log_path.parent, "logs", "openai_api_endpoint.log")
loguru.logger.add(log_path.absolute(), rotation="10 MB")


load_dotenv(override=True)
# What is the influence of different alleles in rs10937739 and what is MTOR gene?
app = FastAPI(title="Genetics Genie API endpoint.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(omics_router)

TOOLS = [_hybrid_search, rsid_lookup, gene_lookup, pathway_lookup, disease_lookup, sequencing_info,
             _process_sql, clinical_trails_full_trial, db_query, get_omics_data, get_enrichment, _hybrid_search]

@app.get("/", description="Defalt message", response_model=str)
def default():
    return "This is default page for Genetics Genie API endpoint."

def get_options(request: dict):
    with open("endpoint_options.yaml") as f:
        options_llm = yaml.full_load(f).get(request["model"])
    key_getter = options_llm.pop("key_getter", None)
    if key_getter:
        options_llm["key_getter"] = RotateKeys(key_getter)
    prompt_path = options_llm.pop("system_prompt", None)
    if prompt_path:
        prompt_path = Path("prompts", prompt_path)
        with open(prompt_path) as f:
            if (len(request["messages"]) > 0) and (request["messages"][0]["role"] == "system"):
                request["messages"][0]["content"] = f.read()
            else:
                request["messages"].insert(0, {"role": "system", "content": f.read()})
    return options_llm


def get_session(options_llm: dict) -> LLMSession:
    tools_dict = {func.__name__: func for func in TOOLS}
    tool_names = options_llm.pop("tools", None)
    model_tools = None
    if tool_names:
        model_tools = [tools_dict[tool] for tool in tool_names]
    session: LLMSession = LLMSession(
        llm_options=options_llm,
        tools=model_tools
    )
    return session

def message_cleaner(request: dict):
    for message in request["messages"]:
        if message["role"] == "user":
            content = message["content"]
            if type(content) is list:
                if len(content) > 0:
                    if type(content[0]) is dict:
                        if content[0].get("type", "") == "text":
                            if type(content[0].get("text", None)) is str:
                                message["content"] = content[0]["text"]

@app.post("/v1/chat/completions")
def chat_completions(request: dict):
    try:
        loguru.logger.debug(request)
        options = get_options(request)
        session = get_session(options)
        message_cleaner(request)
        if request["messages"]:
            if request.get("stream") and str(request.get("stream")).lower() != "false":
                return StreamingResponse(
                    session.stream_all(request["messages"], run_callbacks=False), media_type="application/x-ndjson"
                )
            resp_content = session.query_add_all(request["messages"], run_callbacks=False)
        else:
            resp_content = "Something goes wrong, request did not contain messages!!!"
    except Exception as e:
        loguru.logger.error(str(e))
        resp_content = str(e)
    return {
        "id": "1",
        "object": "chat.completion",
        "created": time.time(),
        "model": options["model"],
        "choices": [{"message": {"role": "assistant", "content": resp_content}}],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("openai_api_endpoint:app", host="0.0.0.0", port=8088, workers=10)

