from langgraph.prebuilt import create_react_agent


def _filter_new_messages(input_messages: list, result_messages: list) -> list:
    """从 graph.invoke 结果中提取本轮新生成的消息。"""
    return result_messages[len(input_messages):]


def make_graph(llm, tools):
    return create_react_agent(model=llm, tools=tools)
